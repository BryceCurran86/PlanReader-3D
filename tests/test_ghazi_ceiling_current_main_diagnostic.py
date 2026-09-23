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

    payload = {
        "production_sha": "2a679a43b81625859d6dd6e888824a06094563ad",
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
