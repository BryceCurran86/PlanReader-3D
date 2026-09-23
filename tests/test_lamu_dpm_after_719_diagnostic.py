"""TEST-ONLY Lamu DPM outcome after structural drawing pre-scan fix.

Never merge. Downloads the manifest-pinned Lamu source, verifies SHA-256,
runs the unchanged extractor/scorer on the registered drawing pages, then
intentionally fails on Python 3.13 with a machine-readable result.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import urllib.request

import pytest

from pb_benchmark_accuracy_engine import BenchmarkAccuracyEngine
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


URL = "https://lamu.go.ke/wp-content/uploads/2018/11/Bill-of-Quantities-ECD-2No-Classrooms-and-Twin-Toilets-Ishakani.pdf"
SHA256 = "fa53c9b72fd35189f11848f9a26ccc3512c8c03b5316e78cad6a4d55c09330f2"
BENCHMARK_ID = "tenders_ke_lamu_ishakani_ecd_classrooms"


@pytest.mark.skipif(
    sys.version_info[:2] != (3, 13),
    reason="diagnostic executes once on Python 3.13 only",
)
def test_lamu_dpm_after_structural_sheet_scan(tmp_path: Path) -> None:
    source = tmp_path / "lamu.pdf"
    req = urllib.request.Request(
        URL,
        headers={"User-Agent": "PlanReader-Lamu-DPM-diagnostic/1.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        source.write_bytes(response.read())
    actual = hashlib.sha256(source.read_bytes()).hexdigest()
    assert actual == SHA256

    extractor = GenericPlanReaderExtractor()
    predictions = extractor.extract_from_pdf(
        source,
        pages=list(range(40, 45)),
        collect_item35_shadow=False,
    )
    rows = [item.to_dict() for item in predictions]
    dpm = next(
        (row for row in rows if row.get("tag") == "substructure_bed_dpm"),
        None,
    )

    engine = BenchmarkAccuracyEngine(
        benchmarks_dir="benchmarks/public_tenders",
        output_dir=tmp_path / "results",
    )
    report = engine.evaluate_benchmark(
        benchmark_id=BENCHMARK_ID,
        pdf_path=source,
        auto_extract=True,
    )
    target = next(
        item.to_dict()
        for item in report.item_results
        if item.item_id == "LMU-E3-C"
    )

    import fitz
    page_audit = []
    doc = fitz.open(str(source))
    try:
        for page_index in range(40, 45):
            page = doc[page_index]
            text_value = page.get_text("text") or ""
            lines = [
                line.strip()
                for line in text_value.splitlines()
                if any(
                    token in line.lower()
                    for token in (
                        "poly", "dpm", "d.p.m", "membrane", "a142", "mesh",
                        "foundation", "slab", "blinding", "hardcore",
                    )
                )
            ]
            page_audit.append(
                {
                    "page": page_index + 1,
                    "is_drawing_page": extractor.is_drawing_page(text_value, page),
                    "has_dpm": extractor._has_dpm_specification(text_value),
                    "has_large_raster": extractor._page_has_large_raster(page),
                    "text_length": len(text_value.strip()),
                    "matching_lines": lines[:80],
                    "drawing_count": len(page.get_drawings() or []),
                    "image_count": len(page.get_images() or []),
                }
            )
    finally:
        doc.close()

    payload = {
        "production_sha": "095353d2a39e8b09c1e321f03d98abdaa8cb8f6d",
        "page_audit": page_audit,
        "dpm_prediction": dpm,
        "target_LMU_E3_C": target,
        "project": {
            "accepted": int(report.exact_matches + report.within_5_percent),
            "denominator": int(report.total_items_compared),
            "accuracy_percentage": report.overall_accuracy_percentage,
            "strict_exact_percentage": report.strict_exact_accuracy_percentage,
            "exact": int(report.exact_matches),
            "within_5": int(report.within_5_percent),
            "gross": int(report.gross_mismatches),
            "missed": int(report.missed_items),
            "hallucinated": int(report.hallucinated_items),
        },
    }
    pytest.fail("LAMU_DPM_RESULT=" + json.dumps(payload, sort_keys=True))
