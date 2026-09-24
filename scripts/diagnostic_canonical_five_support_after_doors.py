from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

from pb_public_tender_benchmark import PublicTenderBenchmark

BENCHMARK_IDS = (
    "tenders_ke_kstvet_cbc_classroom",
    "tenders_ke_murera_science_lab",
    "tenders_ke_ghazi_science_lab",
    "tenders_ke_lamu_ishakani_ecd_classrooms",
    "tenders_ke_umma_hostels",
)
PROJECT_TIMEOUT_SECONDS = 420


def _download(url: str, target: Path) -> None:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "PlanReader-canonical-Tesseract-production/1.0"},
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
    if drawing is None:
        raise RuntimeError(f"drawing_manifest_missing:{bench.benchmark_id}")
    url = str(bench.download_manifest.get("source_url") or "")
    filename = str(drawing.get("filename") or "")
    expected_sha = str(drawing.get("sha256") or "").lower()
    if not url or not filename or len(expected_sha) != 64:
        raise RuntimeError(f"invalid_source_manifest:{bench.benchmark_id}")
    return url, filename, expected_sha


def _run_one(benchmark_id: str, source_path: Path) -> dict[str, object]:
    code = r"""
import json
import sys
from pathlib import Path
from pb_benchmark_accuracy_engine import BenchmarkAccuracyEngine

benchmark_id = sys.argv[1]
source_path = Path(sys.argv[2])
engine = BenchmarkAccuracyEngine(
    benchmarks_dir="benchmarks/public_tenders",
    output_dir=Path("/tmp/results") / benchmark_id,
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
    "hallucinated_results": [
        item.to_dict()
        for item in report.item_results
        if item.status.value == "hallucinated_item"
    ],
}
print("PROJECT_RESULT=" + json.dumps(payload, sort_keys=True), flush=True)
"""
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code, benchmark_id, str(source_path)],
            cwd="/app",
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
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
        }
    payload = json.loads(payload_line[len(marker):])
    payload["elapsed_seconds"] = round(time.monotonic() - started, 2)
    payload["returncode"] = proc.returncode
    return payload


sources: dict[str, Path] = {}
for benchmark_id in BENCHMARK_IDS:
    bench = PublicTenderBenchmark.load(
        benchmark_id,
        base_dir="benchmarks/public_tenders",
    )
    url, filename, expected_sha = _source_spec(bench)
    source_path = Path("/tmp") / f"{benchmark_id}-{filename}"
    _download(url, source_path)
    actual_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if actual_sha != expected_sha:
        raise SystemExit(
            f"source_hash_mismatch:{benchmark_id}:"
            f"expected={expected_sha}:actual={actual_sha}"
        )
    sources[benchmark_id] = source_path

rows = [_run_one(benchmark_id, sources[benchmark_id]) for benchmark_id in BENCHMARK_IDS]
scored = [
    row
    for row in rows
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
    round(100.0 * totals["accepted"] / denominator, 2) if denominator else None
)
totals["strict_exact_percentage"] = (
    round(100.0 * totals["exact"] / denominator, 2) if denominator else None
)
result = {
    "diagnostic": "canonical_five_support_after_doors",
    "projects": rows,
    "scored_project_count": len(scored),
    "totals": totals,
}
print("CANONICAL_FIVE_SUPPORT_RESULT=" + json.dumps(result, sort_keys=True), flush=True)
