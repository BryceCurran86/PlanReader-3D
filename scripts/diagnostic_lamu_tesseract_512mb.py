from __future__ import annotations

import hashlib
import json
from pathlib import Path
import urllib.request

from pb_benchmark_accuracy_engine import BenchmarkAccuracyEngine
from pb_drawing_ocr_evidence_layer import DrawingOCREngine
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_portable_raster_ocr_authority import detect_ocr_capabilities

BENCHMARK_ID = "tenders_ke_lamu_ishakani_ecd_classrooms"
URL = "https://lamu.go.ke/wp-content/uploads/2018/11/Bill-of-Quantities-ECD-2No-Classrooms-and-Twin-Toilets-Ishakani.pdf"
EXPECTED_SHA = "fa53c9b72fd35189f11848f9a26ccc3512c8c03b5316e78cad6a4d55c09330f2"


def _ocr_text_for_page_120dpi(self, page, page_index):
    cached = self._ocr_text_by_page.get(page_index)
    if cached is not None:
        return cached
    text = ""
    try:
        lines = DrawingOCREngine().recognize_page_rect(page, dpi=120)
        text = "\n".join(str(line.get("text") or "") for line in lines)
    except Exception:
        text = ""
    self._ocr_text_by_page[page_index] = text
    return text


GenericPlanReaderExtractor._ocr_text_for_page = _ocr_text_for_page_120dpi

source = Path("/tmp/lamu.pdf")
request = urllib.request.Request(
    URL,
    headers={"User-Agent": "PlanReader-Lamu-Tesseract-Docker-512MB/1.0"},
)
with urllib.request.urlopen(request, timeout=120) as response:
    payload = response.read()
actual_sha = hashlib.sha256(payload).hexdigest()
if actual_sha != EXPECTED_SHA:
    raise SystemExit(f"source_hash_mismatch:expected={EXPECTED_SHA}:actual={actual_sha}")
source.write_bytes(payload)

capabilities = detect_ocr_capabilities()
if not capabilities.tesseract_available or capabilities.default_backend != "tesseract":
    raise SystemExit(
        "tesseract_capability_failed:"
        + json.dumps(
            {
                "available_backends": list(capabilities.available_backends),
                "default_backend": capabilities.default_backend,
            },
            sort_keys=True,
        )
    )

engine = BenchmarkAccuracyEngine(
    benchmarks_dir="benchmarks/public_tenders",
    output_dir="/tmp/lamu-results",
)
report = engine.evaluate_benchmark(
    benchmark_id=BENCHMARK_ID,
    pdf_path=source,
    auto_extract=True,
)
target = next(
    (
        item.to_dict()
        for item in report.item_results
        if item.item_id == "LMU-E3-C"
    ),
    None,
)
hallucinated = [
    item.to_dict()
    for item in report.item_results
    if item.status.value == "hallucinated_item"
]
result = {
    "diagnostic": "lamu_tesseract_docker_512mb_120dpi",
    "source_sha256": actual_sha,
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
        "status": report.status,
        "errors": report.errors,
    },
    "target_LMU_E3_C": target,
    "hallucinated_results": hallucinated,
}
print("LAMU_TESSERACT_DOCKER_RESULT=" + json.dumps(result, sort_keys=True), flush=True)
