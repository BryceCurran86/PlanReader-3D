"""TEST-ONLY Ghazi ceiling diagnostic on current main. DO NOT MERGE."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import urllib.request

import pytest

from pb_benchmark_accuracy_engine import BenchmarkAccuracyEngine
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_hosted_opening_instance_adapter import authoritative_floor_plan_viewports
from pb_migration_contracts import ViewportEvidence, ViewportResolutionStatus
from pb_migration_provider_envelope import ProviderContext
from pb_source_owned_ceiling_lining_pipeline import run_source_owned_ceiling_lining_shadow
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    calibrate_viewport_layout,
    extract_vector_frames,
    extract_view_title_anchors,
    segment_page_viewports,
)
import fitz


URL = "https://tenders.go.ke/storage/Documents/1739211305954-tender-document-for-construction-of-science-laboratory-at-ghazi-primary-school.pdf"
SHA256 = "c8c001c9dadb791e7cb18b7bea19ce795eebba2f9b9eb7dec4844212da4d8f4f"
BENCHMARK_ID = "tenders_ke_ghazi_science_lab"


@pytest.mark.skipif(
    sys.version_info[:2] != (3, 13),
    reason="diagnostic executes once on Python 3.13 only",
)
def test_ghazi_ceiling_current_main_diagnostic(tmp_path: Path) -> None:
    source = tmp_path / "ghazi.pdf"
    request = urllib.request.Request(
        URL,
        headers={"User-Agent": "PlanReader-ghazi-ceiling-diagnostic/1.0"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        source.write_bytes(response.read())
    actual_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    assert actual_sha == SHA256

    extractor = GenericPlanReaderExtractor()
    predictions = extractor.extract_from_pdf(
        source,
        pages=[166],
        collect_item35_shadow=False,
    )
    pred_rows = [p.to_dict() for p in predictions]

    engine = BenchmarkAccuracyEngine(
        benchmarks_dir="benchmarks/public_tenders",
        output_dir=tmp_path / "results",
    )
    report = engine.evaluate_benchmark(
        benchmark_id=BENCHMARK_ID,
        pdf_path=source,
        predictions=pred_rows,
        auto_extract=False,
    )
    target = next(
        (
            item.to_dict()
            for item in report.item_results
            if item.item_id == "GZ-E8-H"
        ),
        None,
    )

    raw = source.read_bytes()
    visibility = SourceVisibilityProducer(
        producer_method="ghazi-ceiling-diagnostic",
        producer_version="1.0",
    )
    published = visibility.ingest_native_pdf_bytes(
        document_id="ghazi-ceiling-diagnostic",
        source_bytes=raw,
        source_locator="memory://ghazi.pdf",
        page_ids=("167",),
    )
    stages = []
    pdf = fitz.open(stream=raw, filetype="pdf")
    try:
        page = pdf[166]
        page_text = page.get_text("text") or ""
        relevant_text_lines = [
            line.strip()
            for line in page_text.splitlines()
            if line.strip()
            and any(
                token in line.upper()
                for token in (
                    "PLAN",
                    "LAYOUT",
                    "DESIGN",
                    "SCHEME",
                    "SCALE",
                    "CEILING",
                    "CHIP",
                    "BOARD",
                )
            )
        ]
        calibration = calibrate_viewport_layout(page)
        title_anchors = extract_view_title_anchors(page)
        vector_frames = extract_vector_frames(page, calibration)
        all_segmented = segment_page_viewports(page, page_number=167)
        segmented_viewports = tuple(
            authoritative_floor_plan_viewports(page, page_number=167)
        )
        for segmented in segmented_viewports:
            bbox = (
                tuple(float(value) for value in segmented.bounding_box)
                if segmented.bounding_box is not None
                else None
            )
            stage = {
                "view_id": str(getattr(segmented, "view_id", "")),
                "bbox": bbox,
                "confidence": float(getattr(segmented, "confidence", 0.0)),
            }
            if bbox is None or not stage["view_id"]:
                stage["pipeline_error"] = "viewport_missing_bbox_or_id"
                stages.append(stage)
                continue

            current = visibility.published_snapshot_for_revision(
                published.revision.revision_id
            )
            assert current is not None
            viewport = ViewportEvidence(
                viewport_id=stage["view_id"],
                document_id=current.revision.document_id,
                page_id="167",
                bbox=bbox,
                view_type="floor_plan",
                status=ViewportResolutionStatus.RESOLVED,
                evidence_ids=(),
                confidence=stage["confidence"],
            )
            context = ProviderContext(
                run_id=f"diag:{current.snapshot.snapshot_id}:{stage['view_id']}",
                workspace_id="diagnostic",
                project_id="diagnostic",
                document_id=current.revision.document_id,
                source_sha256=current.revision.source_sha256,
                revision_id=current.revision.revision_id,
                current_revision_id=current.revision.revision_id,
                selected_pages=(166,),
                owned_viewport_ids=(stage["view_id"],),
                evidence_snapshot_id=current.snapshot.snapshot_id,
                owned_page_numbers=(167,),
                viewport_page_ownership=((stage["view_id"], 167),),
            )
            try:
                result = run_source_owned_ceiling_lining_shadow(
                    source_visibility_producer=visibility,
                    context=context,
                    viewport=viewport,
                    page_no=167,
                )
                stage["pipeline"] = {
                    "status": result.status.value,
                    "reason_codes": list(result.reason_codes),
                    "finish_candidates": [
                        {
                            "evidence_id": item.evidence_id,
                            "raw_text": str(getattr(item, "raw_text", "")),
                            "bbox": list(getattr(item, "bbox", ()) or ()),
                            "method": str(getattr(item, "method", "")),
                        }
                        for item in result.finish_candidates
                    ],
                    "physical_scale": {
                        "status": result.physical_scale_result.status.value,
                        "reason_codes": list(result.physical_scale_result.reason_codes),
                    },
                    "scale_bridge": {
                        "status": result.scale_bridge.status.value,
                        "reason_codes": list(result.scale_bridge.reason_codes),
                        "has_calibration": result.scale_bridge.calibration is not None,
                        "has_physical_scale_evidence": (
                            result.scale_bridge.physical_scale_evidence is not None
                        ),
                    },
                    "room_areas": [
                        {
                            "quantity_id": q.quantity_id,
                            "value": q.value,
                            "unit": q.unit,
                            "status": q.status,
                            "authority": q.authority,
                            "abstained": q.abstained,
                            "blocking_reasons": list(q.blocking_reasons),
                            "reason_codes": list(q.reason_codes),
                        }
                        for q in result.room_area_quantities
                    ],
                    "ceilings": [
                        {
                            "quantity_id": q.quantity_id,
                            "value": q.value,
                            "unit": q.unit,
                            "status": q.status,
                            "authority": q.authority,
                            "abstained": q.abstained,
                            "blocking_reasons": list(q.blocking_reasons),
                            "reason_codes": list(q.reason_codes),
                            "finish_descriptor": (
                                q.metadata.get("finish_descriptor")
                                if isinstance(q.metadata, dict)
                                else None
                            ),
                        }
                        for q in result.ceiling_quantities
                    ],
                }
            except Exception as exc:
                stage["pipeline_error"] = f"{type(exc).__name__}:{exc}"
            stages.append(stage)
    finally:
        pdf.close()

    payload = {
        "production_sha": "2a679a43b81625859d6dd6e888824a06094563ad",
        "source_visibility": {
            "decoded_pages": list(published.coverage.decoded_pages),
            "coverage_state": published.coverage.state,
            "visible_observation_count": len(published.visible_observation_ids),
            "text_observation_count": len(published.text_observation_ids),
        },
        "viewport_diagnostic": {
            "page_size": [
                float(page.rect.width) if 'page' in locals() else None,
                float(page.rect.height) if 'page' in locals() else None,
            ],
            "relevant_text_lines": relevant_text_lines,
            "title_anchors": [
                {
                    "text": anchor.text,
                    "bbox": list(anchor.bbox),
                    "view_type": anchor.view_type,
                }
                for anchor in title_anchors
            ],
            "vector_frames": [list(frame) for frame in vector_frames],
            "segmented": [
                {
                    "view_id": vp.view_id,
                    "view_type": vp.view_type,
                    "label": vp.label,
                    "title_bbox": list(vp.title_bbox),
                    "bounding_box": (
                        list(vp.bounding_box)
                        if vp.bounding_box is not None
                        else None
                    ),
                    "status": vp.status,
                    "boundary_source": vp.boundary_source,
                    "confidence": vp.confidence,
                    "notes": list(vp.notes),
                    "provenance": vp.provenance,
                }
                for vp in all_segmented
            ],
        },
        "stages": stages,
        "ceiling_lining_live": extractor.ceiling_lining_live,
        "ceiling_predictions": [
            row
            for row in pred_rows
            if "ceiling" in str(row.get("tag") or "").lower()
            or "ceiling" in str(row.get("description") or "").lower()
        ],
        "target_GZ_E8_H": target,
        "project": {
            "accepted": int(report.exact_matches + report.within_5_percent),
            "denominator": int(report.total_items_compared),
            "exact": int(report.exact_matches),
            "within_5": int(report.within_5_percent),
            "gross": int(report.gross_mismatches),
            "missed": int(report.missed_items),
            "hallucinated": int(report.hallucinated_items),
            "accuracy_percentage": report.overall_accuracy_percentage,
        },
        "extraction_status": extractor.extraction_status,
    }
    pytest.fail("GHAZI_CEILING_RESULT=" + json.dumps(payload, sort_keys=True))
