"""TEST-ONLY Lamu roof evidence audit on current main. DO NOT MERGE."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
import urllib.request

import fitz
import pytest

from pb_benchmark_accuracy_engine import BenchmarkAccuracyEngine
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_viewport_segmentation import (
    calibrate_viewport_layout,
    extract_vector_frames,
    extract_view_title_anchors,
    segment_page_viewports,
)


URL = "https://lamu.go.ke/wp-content/uploads/2018/11/Bill-of-Quantities-ECD-2No-Classrooms-and-Twin-Toilets-Ishakani.pdf"
SHA256 = "fa53c9b72fd35189f11848f9a26ccc3512c8c03b5316e78cad6a4d55c09330f2"
BENCHMARK_ID = "tenders_ke_lamu_ishakani_ecd_classrooms"


def _segments(page: fitz.Page) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for drawing in page.get_drawings() or ():
        for item in drawing.get("items", ()) or ():
            if not item or item[0] != "l" or len(item) < 3:
                continue
            p0, p1 = item[1], item[2]
            x0, y0, x1, y1 = map(float, (p0.x, p0.y, p1.x, p1.y))
            dx, dy = x1 - x0, y1 - y0
            length = math.hypot(dx, dy)
            if length < 6.0:
                continue
            angle = math.degrees(math.atan2(dy, dx))
            while angle <= -90.0:
                angle += 180.0
            while angle > 90.0:
                angle -= 180.0
            out.append({
                "p0": [round(x0, 3), round(y0, 3)],
                "p1": [round(x1, 3), round(y1, 3)],
                "length": round(length, 3),
                "angle_deg": round(angle, 3),
            })
    return out


@pytest.mark.skipif(
    sys.version_info[:2] != (3, 13),
    reason="diagnostic executes once on Python 3.13 only",
)
def test_lamu_roof_evidence_current_main(tmp_path: Path) -> None:
    source = tmp_path / "lamu.pdf"
    request = urllib.request.Request(
        URL,
        headers={"User-Agent": "PlanReader-lamu-roof-diagnostic/1.0"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        source.write_bytes(response.read())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SHA256

    extractor = GenericPlanReaderExtractor()
    predictions = extractor.extract_from_pdf(
        source,
        pages=[40, 41, 42, 43, 44],
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
            if item.item_id == "LMU-E4-A"
        ),
        None,
    )

    pages = []
    doc = fitz.open(str(source))
    try:
        for page_index in range(40, 45):
            page = doc[page_index]
            text = page.get_text("text") or ""
            relevant = [
                line.strip()
                for line in text.splitlines()
                if line.strip()
                and any(
                    token in line.upper()
                    for token in (
                        "ROOF", "EAVE", "OVERHANG", "PITCH", "RIDGE",
                        "LEVEL", "ELEVATION", "FLOOR PLAN", "SECTION",
                        "SCALE", "VERANDA", "VERANDAH",
                    )
                )
            ]
            calibration = calibrate_viewport_layout(page)
            anchors = extract_view_title_anchors(page)
            frames = extract_vector_frames(page, calibration)
            viewports = segment_page_viewports(page, page_number=page_index + 1)
            segs = _segments(page)
            diagonal = [
                row for row in segs
                if 8.0 <= abs(float(row["angle_deg"])) <= 70.0
                and float(row["length"]) >= 20.0
            ]
            pages.append({
                "page": page_index + 1,
                "size": [float(page.rect.width), float(page.rect.height)],
                "relevant_text": relevant,
                "title_anchors": [
                    {
                        "text": anchor.text,
                        "view_type": anchor.view_type,
                        "bbox": list(anchor.bbox),
                    }
                    for anchor in anchors
                ],
                "vector_frames": [list(frame) for frame in frames],
                "viewports": [
                    {
                        "view_id": v.view_id,
                        "view_type": v.view_type,
                        "label": v.label,
                        "status": v.status,
                        "boundary_source": v.boundary_source,
                        "bbox": list(v.bounding_box) if v.bounding_box else None,
                        "scale_raw": v.scale_raw,
                        "scale_denominator": v.scale_denominator,
                        "scale_conflict": v.scale_conflict,
                    }
                    for v in viewports
                ],
                "segment_count_ge6pt": len(segs),
                "roof_like_diagonals": diagonal[:80],
            })
    finally:
        doc.close()

    payload = {
        "production_sha": "2a679a43b81625859d6dd6e888824a06094563ad",
        "project": {
            "accepted": int(report.exact_matches + report.within_5_percent),
            "denominator": int(report.total_items_compared),
            "accuracy_percentage": report.overall_accuracy_percentage,
            "exact": int(report.exact_matches),
            "within_5": int(report.within_5_percent),
            "gross": int(report.gross_mismatches),
            "missed": int(report.missed_items),
            "hallucinated": int(report.hallucinated_items),
        },
        "target_LMU_E4_A": target,
        "roof_predictions": [
            row for row in pred_rows
            if "roof" in str(row.get("tag") or "").lower()
            or "roof" in str(row.get("description") or "").lower()
        ],
        "related_predictions": [
            row for row in pred_rows
            if str(row.get("tag") or "") in {
                "perimeter_walling", "gable_walling", "floor_screed",
                "damp_proof_course",
            }
        ],
        "pages": pages,
    }
    pytest.fail("LAMU_ROOF_RESULT=" + json.dumps(payload, sort_keys=True))
