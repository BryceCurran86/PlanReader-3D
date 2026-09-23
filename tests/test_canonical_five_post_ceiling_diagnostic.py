"""TEST-ONLY diagnostic: canonical five-project post-ceiling benchmark.

This file is intentionally never for merge.  It runs only on Python 3.13,
downloads the five registered development source PDFs from their frozen public
URLs, verifies every manifest SHA-256, runs BenchmarkAccuracyEngine against the
explicit source paths, and then raises with one machine-readable summary so the
GitHub Actions log captures the result.

It does not change production code, benchmark gold, mappings, tolerances,
acceptance rules, or denominator definitions.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request

import pytest

from pb_benchmark_accuracy_engine import BenchmarkAccuracyEngine
from pb_public_tender_benchmark import PublicTenderBenchmark


BENCHMARK_IDS = (
    "tenders_ke_kstvet_cbc_classroom",
    "tenders_ke_murera_science_lab",
    "tenders_ke_ghazi_science_lab",
    "tenders_ke_lamu_ishakani_ecd_classrooms",
    "tenders_ke_umma_hostels",
)


def _download(url: str, target: Path) -> None:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "PlanReader-canonical-diagnostic/1.0"},
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                target.write_bytes(response.read())
            return
        except Exception as exc:  # diagnostic retry only
            last_error = exc
            if attempt < 3:
                time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"download_failed:{url}:{type(last_error).__name__}:{last_error}")


def _source_spec(bench: PublicTenderBenchmark) -> tuple[str, str, str]:
    documents = bench.download_manifest.get("documents", [])
    drawing = next(
        (doc for doc in documents if doc.get("role") == "architectural_drawings"),
        None,
    )
    assert drawing is not None
    url = str(bench.download_manifest.get("source_url") or "")
    filename = str(drawing.get("filename") or "")
    expected_sha = str(drawing.get("sha256") or "").lower()
    assert url and filename and len(expected_sha) == 64
    return url, filename, expected_sha


@pytest.mark.skipif(
    sys.version_info[:2] != (3, 13),
    reason="canonical five-project diagnostic executes once on Python 3.13 only",
)
def test_canonical_five_post_ceiling_diagnostic(tmp_path: Path) -> None:
    engine = BenchmarkAccuracyEngine(
        benchmarks_dir="benchmarks/public_tenders",
        output_dir=tmp_path / "results",
    )

    project_rows: list[dict[str, object]] = []
    totals = {
        "accepted": 0,
        "denominator": 0,
        "exact": 0,
        "within_5": 0,
        "within_10": 0,
        "within_20": 0,
        "gross": 0,
        "missed": 0,
        "hallucinated": 0,
    }

    for benchmark_id in BENCHMARK_IDS:
        bench = PublicTenderBenchmark.load(
            benchmark_id,
            base_dir="benchmarks/public_tenders",
        )
        url, filename, expected_sha = _source_spec(bench)
        source_path = tmp_path / filename
        _download(url, source_path)

        actual_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
        assert actual_sha == expected_sha, (
            f"source_hash_mismatch:{benchmark_id}:"
            f"expected={expected_sha}:actual={actual_sha}"
        )

        report = engine.evaluate_benchmark(
            benchmark_id=benchmark_id,
            pdf_path=source_path,
            auto_extract=True,
        )
        assert report.is_scored, (
            f"benchmark_not_scored:{benchmark_id}:{report.status}:{report.errors}"
        )

        accepted = int(report.exact_matches + report.within_5_percent)
        denominator = int(report.total_items_compared)
        project_rows.append(
            {
                "benchmark_id": benchmark_id,
                "accepted": accepted,
                "denominator": denominator,
                "accuracy_percentage": report.overall_accuracy_percentage,
                "strict_exact_percentage": report.strict_exact_accuracy_percentage,
                "exact": report.exact_matches,
                "within_5": report.within_5_percent,
                "within_10": report.within_10_percent,
                "within_20": report.within_20_percent,
                "gross": report.gross_mismatches,
                "missed": report.missed_items,
                "hallucinated": report.hallucinated_items,
            }
        )

        totals["accepted"] += accepted
        totals["denominator"] += denominator
        totals["exact"] += int(report.exact_matches)
        totals["within_5"] += int(report.within_5_percent)
        totals["within_10"] += int(report.within_10_percent)
        totals["within_20"] += int(report.within_20_percent)
        totals["gross"] += int(report.gross_mismatches)
        totals["missed"] += int(report.missed_items)
        totals["hallucinated"] += int(report.hallucinated_items)

    denominator = totals["denominator"]
    totals["accuracy_percentage"] = round(
        100.0 * totals["accepted"] / denominator, 2
    )
    totals["strict_exact_percentage"] = round(
        100.0 * totals["exact"] / denominator, 2
    )

    payload = {
        "diagnostic": "canonical_five_post_ceiling",
        "production_sha": "2913ce43a395b2ce59d07ce4a67798d74e013d08",
        "projects": project_rows,
        "totals": totals,
    }

    # Intentional TEST-ONLY failure: expose the complete canonical result in
    # the Actions log without committing generated benchmark reports.
    pytest.fail("CANONICAL_FIVE_RESULT=" + json.dumps(payload, sort_keys=True))
