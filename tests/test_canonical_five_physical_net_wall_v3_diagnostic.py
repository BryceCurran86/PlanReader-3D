"""TEST-ONLY diagnostic: isolated canonical five-project post-ceiling benchmark.

Never merge. Executes only on Python 3.13. Each benchmark runs in a separate
subprocess with a hard timeout so one pathological source cannot stall the
entire canonical result. Source PDFs are downloaded from frozen manifest URLs
and SHA-256 verified before extraction.

No production code, benchmark gold, mappings, tolerances, scorer rules,
acceptance rules, or denominator definitions are changed.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

import pytest

from pb_public_tender_benchmark import PublicTenderBenchmark


BENCHMARK_IDS = (
    "tenders_ke_kstvet_cbc_classroom",
    "tenders_ke_murera_science_lab",
    "tenders_ke_ghazi_science_lab",
    "tenders_ke_lamu_ishakani_ecd_classrooms",
    "tenders_ke_umma_hostels",
)
PROJECT_TIMEOUT_SECONDS = 180


def _download(url: str, target: Path) -> None:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "PlanReader-canonical-diagnostic/1.1"},
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                target.write_bytes(response.read())
            return
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(
        f"download_failed:{url}:{type(last_error).__name__}:{last_error}"
    )


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


def _run_one(
    benchmark_id: str,
    source_path: Path,
    result_dir: Path,
) -> dict[str, object]:
    code = r'''
import json
import sys
from pathlib import Path
from pb_benchmark_accuracy_engine import BenchmarkAccuracyEngine

benchmark_id = sys.argv[1]
source_path = Path(sys.argv[2])
result_dir = Path(sys.argv[3])
engine = BenchmarkAccuracyEngine(
    benchmarks_dir="benchmarks/public_tenders",
    output_dir=result_dir,
)
report = engine.evaluate_benchmark(
    benchmark_id=benchmark_id,
    pdf_path=source_path,
    auto_extract=True,
)
payload = {
    "benchmark_id": benchmark_id,
    "is_scored": report.is_scored,
    "status": report.status,
    "errors": report.errors,
    "accepted": int(report.exact_matches + report.within_5_percent),
    "denominator": int(report.total_items_compared),
    "accuracy_percentage": report.overall_accuracy_percentage,
    "strict_exact_percentage": report.strict_exact_accuracy_percentage,
    "exact": int(report.exact_matches),
    "within_5": int(report.within_5_percent),
    "within_10": int(report.within_10_percent),
    "within_20": int(report.within_20_percent),
    "gross": int(report.gross_mismatches),
    "missed": int(report.missed_items),
    "hallucinated": int(report.hallucinated_items),
}
print("PROJECT_RESULT=" + json.dumps(payload, sort_keys=True), flush=True)
'''
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                code,
                benchmark_id,
                str(source_path),
                str(result_dir / benchmark_id),
            ],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            timeout=PROJECT_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "benchmark_id": benchmark_id,
            "status": "timeout",
            "timeout_seconds": PROJECT_TIMEOUT_SECONDS,
            "elapsed_seconds": round(time.monotonic() - started, 2),
        }

    elapsed = round(time.monotonic() - started, 2)
    marker = "PROJECT_RESULT="
    payload_line = next(
        (line for line in proc.stdout.splitlines() if line.startswith(marker)),
        None,
    )
    if payload_line is None:
        return {
            "benchmark_id": benchmark_id,
            "status": "subprocess_failed",
            "returncode": proc.returncode,
            "elapsed_seconds": elapsed,
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
        }
    payload = json.loads(payload_line[len(marker):])
    payload["elapsed_seconds"] = elapsed
    payload["returncode"] = proc.returncode
    return payload


@pytest.mark.skipif(
    sys.version_info[:2] != (3, 13),
    reason="canonical five-project diagnostic executes once on Python 3.13 only",
)
def test_canonical_five_post_ceiling_diagnostic(tmp_path: Path) -> None:
    sources: dict[str, Path] = {}
    for benchmark_id in BENCHMARK_IDS:
        bench = PublicTenderBenchmark.load(
            benchmark_id,
            base_dir="benchmarks/public_tenders",
        )
        url, filename, expected_sha = _source_spec(bench)
        source_path = tmp_path / filename
        if not source_path.exists():
            _download(url, source_path)

        actual_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
        assert actual_sha == expected_sha, (
            f"source_hash_mismatch:{benchmark_id}:"
            f"expected={expected_sha}:actual={actual_sha}"
        )
        sources[benchmark_id] = source_path

    result_dir = tmp_path / "results"
    project_rows: list[dict[str, object]] = []
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(BENCHMARK_IDS)
    ) as pool:
        future_by_id = {
            benchmark_id: pool.submit(
                _run_one,
                benchmark_id,
                sources[benchmark_id],
                result_dir,
            )
            for benchmark_id in BENCHMARK_IDS
        }
        for benchmark_id in BENCHMARK_IDS:
            row = future_by_id[benchmark_id].result()
            project_rows.append(row)

    scored = [
        row
        for row in project_rows
        if row.get("is_scored") is True and row.get("returncode") == 0
    ]
    totals = {
        "accepted": sum(int(row["accepted"]) for row in scored),
        "denominator": sum(int(row["denominator"]) for row in scored),
        "exact": sum(int(row["exact"]) for row in scored),
        "within_5": sum(int(row["within_5"]) for row in scored),
        "within_10": sum(int(row["within_10"]) for row in scored),
        "within_20": sum(int(row["within_20"]) for row in scored),
        "gross": sum(int(row["gross"]) for row in scored),
        "missed": sum(int(row["missed"]) for row in scored),
        "hallucinated": sum(int(row["hallucinated"]) for row in scored),
    }
    denominator = totals["denominator"]
    totals["accuracy_percentage"] = (
        round(100.0 * totals["accepted"] / denominator, 2)
        if denominator
        else None
    )
    totals["strict_exact_percentage"] = (
        round(100.0 * totals["exact"] / denominator, 2)
        if denominator
        else None
    )

    payload = {
        "diagnostic": "canonical_five_physical_net_wall_v3",
        "production_sha": "f6b9ff21bfc6a19b8e55255ee05ec405f6f86f53",
        "projects": project_rows,
        "scored_project_count": len(scored),
        "totals": totals,
    }

    pytest.fail("CANONICAL_FIVE_RESULT=" + json.dumps(payload, sort_keys=True))
