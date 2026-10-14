"""Replay the exact original Maryborough FT3 source-authority first gate.

Diagnostic only. This does not publish a floor finish, customer quantity,
benchmark identity, or score. It asks current production source-material
authority for the earliest real gate: authenticated FT3 definition, then
page-7 floor-plan FT3 occurrence scope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import fitz

from pb_drawing_evidence_binding import DrawingViewType
from pb_source_material_semantic_authority import (
    _bbox_fully_inside,
    _recover_admissible_viewport_lines,
    _recover_admissible_viewport_words,
    _trusted_lines_for_viewport,
    _trusted_words_by_page,
    SourceMaterialDefinitionSelector,
    SourceMaterialOccurrenceSelector,
    SourceMaterialSemanticProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gpt2_ft3_native_text_integrity_firstgate import (
    native_finish_schedule_text_first_gates,
)
from pb_viewport_segmentation import (
    segment_page_viewports,
    validate_non_overlapping_viewports,
)

PROJECT = "au_qld_maryborough_service_station"
EXPECTED_SHA256 = (
    "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
)
SOURCE_PAGES = ("7", "9", "11")
FLOOR_PAGE_NUMBER = 7


def _status(value: Any) -> str:
    owned = getattr(value, "value", value)
    return str(owned)


def _local_ft3_line_gates(
    *,
    producer: SourceMaterialSemanticProducer,
    source: SourceVisibilityProducer,
    published: object,
    viewport: object,
    words: tuple[object, ...],
) -> dict[str, Any]:
    """Inspect exact FT3 source lines inside the authenticated floor viewport."""

    recovered = _recover_admissible_viewport_words(
        source=source,
        published=published,
        raster=producer._raster,
        words=words,
        viewport=viewport,
    )
    recovered = _recover_admissible_viewport_lines(
        source=source,
        published=published,
        raster=producer._raster,
        words=recovered,
        viewport=viewport,
    )

    grouped: dict[tuple[int, int], list[object]] = {}
    for word in recovered:
        if not _bbox_fully_inside(word.bbox, viewport.bounding_box):
            continue
        grouped.setdefault((word.block_no, word.line_no), []).append(word)

    candidates = []
    for (block_no, line_no), line_words in sorted(grouped.items()):
        ordered = sorted(
            line_words,
            key=lambda row: (row.word_no, row.bbox[0], row.observation_id),
        )
        if not any(str(row.text).strip().upper() == "FT3" for row in ordered):
            continue
        candidates.append(
            {
                "block_no": int(block_no),
                "line_no": int(line_no),
                "text": " ".join(
                    str(row.text).strip()
                    for row in ordered
                    if str(row.text).strip()
                ),
                "all_words_trusted": all(bool(row.trusted) for row in ordered),
                "words": [
                    {
                        "observation_id": str(row.observation_id),
                        "word_no": int(row.word_no),
                        "text": str(row.text),
                        "trusted": bool(row.trusted),
                        "reason_codes": list(row.reason_codes),
                        "bbox_pdf_pts": list(row.bbox),
                    }
                    for row in ordered
                ],
            }
        )

    trusted_lines, viewport_complete, viewport_reasons = _trusted_lines_for_viewport(
        recovered,
        viewport,
    )
    exact_trusted_ft3_lines = [
        {
            "text": text,
            "bbox_pdf_pts": list(bbox),
            "observation_ids": list(observation_ids),
        }
        for text, bbox, observation_ids in trusted_lines
        if any(token.upper() == "FT3" for token in text.split())
    ]
    return {
        "diagnostic_only": True,
        "viewport_text_scope_complete": bool(viewport_complete),
        "viewport_text_scope_reason_codes": list(viewport_reasons),
        "candidate_lines": candidates,
        "trusted_exact_ft3_lines": exact_trusted_ft3_lines,
        "new_material_occurrence_published": False,
        "new_floor_finish_quantity_published": False,
    }


def _verify_source(pdf: Path) -> tuple[bytes, str]:
    payload = pdf.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError("wrong Maryborough original source SHA")
    return payload, digest


def inspect_ft3_firstgate(pdf: Path) -> dict[str, Any]:
    payload, digest = _verify_source(pdf)

    doc = fitz.open(stream=payload, filetype="pdf")
    if doc.page_count != 31:
        raise ValueError("unexpected Maryborough original page count")
    floor_viewports = tuple(
        segment_page_viewports(
            doc.load_page(FLOOR_PAGE_NUMBER - 1),
            page_number=FLOOR_PAGE_NUMBER,
        )
    )
    if not validate_non_overlapping_viewports(floor_viewports):
        raise ValueError("page-7 viewport segmentation overlaps")
    floor_candidates = tuple(
        viewport
        for viewport in floor_viewports
        if viewport.view_type == DrawingViewType.FLOOR_PLAN.value
    )
    doc.close()
    if len(floor_candidates) != 1:
        raise ValueError("Maryborough page 7 must have one floor-plan viewport")
    floor_view = floor_candidates[0]
    if not floor_view.view_id or not floor_view.bounding_box:
        raise ValueError("Maryborough page-7 floor viewport is unowned")

    source = SourceVisibilityProducer(
        producer_method="gpt3-maryborough-ft3-source-firstgate",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="gpt3-maryborough-ft3-source-firstgate",
        source_bytes=payload,
        source_locator="memory://maryborough-ft3-firstgate.pdf",
        page_ids=SOURCE_PAGES,
    )
    if published.revision.source_sha256 != digest:
        raise ValueError("source visibility revision SHA drifted")

    producer = SourceMaterialSemanticProducer.from_source_visibility_producer(source)
    authority = producer.publish(published.revision.revision_id)
    # The material producer has already performed its own trusted-text check.
    # Inspect those same original receipts independently as a diagnostic:
    # raw FT3 schedule text is NOT a semantic definition or material occurrence.
    words_by_page = _trusted_words_by_page(source, published)
    page7_words = words_by_page.get("7", ())
    try:
        native_schedule = native_finish_schedule_text_first_gates(
            words_by_page.get("11", ())
        )
    except RuntimeError as exc:
        native_schedule = {
            "original_source_text_integrity_error_diagnostic_only": str(exc),
            "native_schedule_definition_authenticated_by_this_report": False,
            "new_material_occurrences_published": False,
            "diagnostic_only": True,
        }
    lineage = dict(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=digest,
        snapshot_id=published.snapshot.snapshot_id,
    )

    definitions: dict[str, dict[str, Any]] = {}
    for code in ("FT2", "FT3"):
        result = authority.resolve_definition(
            SourceMaterialDefinitionSelector(**lineage, code=code)
        )
        record = result.record
        definitions[code] = {
            "status": _status(result.status),
            "reason_codes": list(result.reason_codes),
            "record_id": getattr(record, "record_id", None),
            "description": getattr(record, "description", None),
            "semantic_finish": getattr(record, "semantic_finish", None),
            "source_definition_ids": list(
                getattr(record, "source_definition_ids", ()) or ()
            ),
            "source_page_ids": list(
                getattr(record, "source_page_ids", ()) or ()
            ),
            "source_viewport_ids": list(
                getattr(record, "source_viewport_ids", ()) or ()
            ),
        }

    scope = authority.resolve_occurrences(
        SourceMaterialOccurrenceSelector(
            **lineage,
            page_id=str(FLOOR_PAGE_NUMBER),
            viewport_id=floor_view.view_id,
        )
    )
    occurrences = [
        {
            "record_id": record.record_id,
            "code": record.code,
            "semantic_finish": record.semantic_finish,
            "definition_record_id": record.definition_record_id,
            "bbox_pdf_pts": list(record.bbox_pdf_pts),
            "raw_text": record.raw_text,
            "source_evidence_id": record.source_evidence_id,
            "source_text_observation_ids": list(
                record.source_text_observation_ids
            ),
        }
        for record in scope.records
        if record.code in {"FT2", "FT3"}
    ]

    ft3 = definitions["FT3"]
    ft3_occurrences = [
        row for row in occurrences if row["code"] == "FT3"
    ]
    first_unclosed_gate = (
        "FT3_DEFINITION_UNAVAILABLE"
        if ft3["record_id"] is None
        else "FLOOR_MATERIAL_OCCURRENCE_SCOPE_UNRESOLVED"
        if not bool(scope.scope_complete)
        else "FT3_FLOOR_OCCURRENCE_UNAVAILABLE"
        if not ft3_occurrences
        else "PHYSICAL_ROOM_FT3_OWNER_UNRESOLVED"
    )

    return {
        "project_id": PROJECT,
        "source_sha256": digest,
        "source_page_count": 31,
        "decoded_source_pages": list(SOURCE_PAGES),
        "floor_page_id": str(FLOOR_PAGE_NUMBER),
        "floor_viewport_id": floor_view.view_id,
        "floor_viewport_bbox": list(floor_view.bounding_box),
        "definitions": definitions,
        "original_page11_native_schedule_word_first_gates_diagnostic_only": native_schedule,
        "original_page7_local_ft3_line_first_gates_diagnostic_only": _local_ft3_line_gates(
            producer=producer,
            source=source,
            published=published,
            viewport=floor_view,
            words=page7_words,
        ),
        "floor_occurrence_scope": {
            "status": _status(scope.status),
            "reason_codes": list(scope.reason_codes),
            "scope_complete": bool(scope.scope_complete),
            "material_occurrence_count": len(scope.records),
            "ft2_ft3_occurrences": occurrences,
        },
        "first_unclosed_gate": first_unclosed_gate,
        "floor_finish_quantity_published": False,
        "customer_quantity_published": False,
        "benchmark_identity_assigned": False,
        "benchmark_accuracy": None,
        "diagnostic_only": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = inspect_ft3_firstgate(args.pdf)
    payload = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
