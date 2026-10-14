"""Read-only original-source census of native finish-code marks on a plan.

Do not resolve floor identity by room-name proximity, title-block scale, source
drawing filename, benchmark identity, or equal quantity. Only producer-owned
native PDF word observations and the existing raster/text/viewport authorities
are queried. Incomplete source coverage remains incomplete.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_raster_text_corroboration_authority import (
    RasterTextCorroborationProducer,
    RasterTextCorroborationSelector,
)
from pb_source_material_semantic_authority import _trusted_words_by_page
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    segment_page_viewports,
    validate_non_overlapping_viewports,
    is_authoritative_derived_viewport,
)
from pb_drawing_evidence_binding import DrawingViewType


def _inside(inner, outer) -> bool:
    return bool(
        outer is not None
        and inner[0] >= outer[0]
        and inner[1] >= outer[1]
        and inner[2] <= outer[2]
        and inner[3] <= outer[3]
    )


def source_plan_mark_census(
    pdf: Path, *, original_sha256: str, source_page: int, code: str
) -> dict:
    data = pdf.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if sha != original_sha256:
        raise ValueError("source SHA mismatch")
    if not code.isalnum() or not code.isupper():
        raise ValueError("material code must be a literal uppercase token")
    with fitz.open(stream=data, filetype="pdf") as document:
        if not 1 <= source_page <= document.page_count:
            raise ValueError("invalid source page")
        viewports = tuple(
            segment_page_viewports(
                document.load_page(source_page - 1), page_number=source_page
            )
        )
    nonoverlapping = validate_non_overlapping_viewports(viewports)
    source = SourceVisibilityProducer(
        producer_method="gpt1-readonly-native-finish-plan-code-census",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="gpt1-readonly-native-finish-plan-code-census",
        source_bytes=data,
        source_locator="memory://verified-original-plan.pdf",
        page_ids=(str(source_page),),
    )
    raster = RasterTextCorroborationProducer.from_source_visibility_producer(source)
    page_words = _trusted_words_by_page(source, published)[str(source_page)]
    marks = []
    for w in page_words:
        if w.text != code:
            continue
        selector = RasterTextCorroborationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=w.observation_id,
        )
        proof = raster.publish(selector) if not w.trusted else None
        source_verified = bool(
            w.trusted
            or (
                proof is not None
                and proof.status is EvidenceResolutionStatus.CORROBORATED
                and proof.corroborated_text == w.text
                and proof.record is not None
            )
        )
        owning_views = [
            {
                "view_id": v.view_id,
                "type": v.view_type,
                "status": v.status,
                "boundary_source": v.boundary_source,
                "floor_plan": v.view_type == DrawingViewType.FLOOR_PLAN.value,
                "floor_finish_plan": v.view_type == DrawingViewType.FLOOR_FINISH_PLAN.value,
                "authoritative": bool(
                    v.status == "resolved"
                    or (nonoverlapping and is_authoritative_derived_viewport(v))
                ),
            }
            for v in viewports
            if _inside(w.bbox, v.bounding_box)
        ]
        marks.append({
            "source_word_observation_id": w.observation_id,
            "text": w.text,
            "block_no": w.block_no,
            "line_no": w.line_no,
            "word_no": w.word_no,
            "native_bbox_pdf_points": list(w.bbox),
            "source_partition_id": w.source_partition_id,
            "native_text_trusted": w.trusted,
            "native_text_reasons": list(w.reason_codes),
            "raster_status": getattr(proof.status, "value", None) if proof else None,
            "raster_reasons": list(proof.reason_codes) if proof else [],
            "source_text_verified": source_verified,
            "enclosing_source_viewports": owning_views,
            "eligible_positive_source_mark_only": bool(
                source_verified
                and len(owning_views) == 1
                and owning_views[0]["floor_finish_plan"]
                and owning_views[0]["authoritative"]
            ),
            "floor_identity_owner": None,
            "floor_finish_quantity": None,
        })
    return {
        "original_source_sha256": sha,
        "page_id": str(source_page),
        "material_code": code,
        "source_native_page_decoded": True,
        "viewports_non_overlapping": nonoverlapping,
        "viewports": [
            {
                "view_id": v.view_id, "type": v.view_type,
                "status": v.status, "boundary_source": v.boundary_source,
                "bbox": list(v.bounding_box) if v.bounding_box else None,
            } for v in viewports
        ],
        "native_code_word_count": len(marks),
        "marks": marks,
        "all_marks_source_text_verified": bool(marks and all(m["source_text_verified"] for m in marks)),
        "all_marks_source_plan_owned": bool(marks and all(m["eligible_positive_source_mark_only"] for m in marks)),
        "complete_material_occurrence_universe": False,
        "physical_floor_owned": False,
        "area_measured_m2": None,
        "signed_customer_quantity": None,
        "benchmark_accuracy": None,
        "diagnostic_only": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--page-id", type=int, required=True)
    parser.add_argument("--code", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arg = parser.parse_args(argv)
    result = source_plan_mark_census(
        arg.pdf, original_sha256=arg.source_sha256, source_page=arg.page_id,
        code=arg.code,
    )
    arg.output.parent.mkdir(parents=True, exist_ok=True)
    arg.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        k: v for k, v in result.items() if k != "marks"
    }, sort_keys=True))
    print("PER_MARK_EVIDENCE", json.dumps(result["marks"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
