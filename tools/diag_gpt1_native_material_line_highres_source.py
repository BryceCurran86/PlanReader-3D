"""Exact source-native material row text corroboration audit (never publication).

No hardcoded benchmark gold, material text, source SHA, native block index,
or expected area is read by this tool. All arguments identify original source
bytes; material candidates and trusted native OCR receipts are producer-owned.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz
import pb_source_material_semantic_authority as material_module

from pb_source_material_semantic_authority import (
    SourceMaterialSemanticProducer,
    _raw_material_definition_candidates,
    _trusted_words_by_page,
    _recover_native_material_block,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def inspect_native_material_row(
    pdf_path: Path, *,
    expected_source_sha256: str, page_id: str, material_code: str,
) -> dict:
    source_bytes = pdf_path.read_bytes()
    original_sha = hashlib.sha256(source_bytes).hexdigest()
    if original_sha != expected_source_sha256:
        raise ValueError("original source PDF SHA mismatch")
    with fitz.open(stream=source_bytes, filetype="pdf") as doc:
        if not 1 <= int(page_id) <= doc.page_count:
            raise ValueError("source page out of bounds")
    source = SourceVisibilityProducer(
        producer_method="gpt1-native-material-fixed-dpi-source-audit",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="gpt1-native-material-fixed-dpi-source-audit",
        source_bytes=source_bytes,
        source_locator="memory://verified-original-source.pdf",
        page_ids=(str(page_id),),
    )
    producer = SourceMaterialSemanticProducer.from_source_visibility_producer(source)
    source_words = _trusted_words_by_page(source, published)[str(page_id)]
    # Source-native code/description parser creates candidate identities.
    # The expected code only narrows the already-discovered candidate universe.
    candidates = [
        row for row in _raw_material_definition_candidates(source_words)
        if row[3] == material_code
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            f"source-owned {material_code} candidate ambiguity: {len(candidates)}"
        )
    partition_id, block_no, words, code, _candidate = candidates[0]
    # Diagnostic read-only observer of the exact production OCR routine, to
    # distinguish a failed source crop, image orientation, missing reading,
    # disagreement or native punctuation mismatch. Never override a result.
    views = []
    original_reader = material_module._single_isolated_material_line_reading
    def observed_reader(backend, image, *, dpi):
        reading = original_reader(backend, image, dpi=dpi)
        views.append({
            "dpi": dpi,
            "backend_name": backend.name,
            "image_size_px": list(image.size),
            "ocr_reading": reading,
            "rendered_image_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        })
        return reading
    material_module._single_isolated_material_line_reading = observed_reader
    try:
        recovered = _recover_native_material_block(
            source=source,
            published=published,
            raster=producer._raster,
            block_words=words,
        )
    finally:
        material_module._single_isolated_material_line_reading = original_reader
    if len(recovered) != len(words):
        raise RuntimeError("source material word cardinality changed")
    before = {word.observation_id: word for word in words}
    details = []
    for word in recovered:
        native = before[word.observation_id]
        if (
            word.text != native.text
            or word.page_id != native.page_id
            or word.source_partition_id != native.source_partition_id
            or word.bbox != native.bbox
            or (word.block_no, word.line_no, word.word_no)
            != (native.block_no, native.line_no, native.word_no)
        ):
            raise RuntimeError("source text/geometry identity changed")
        details.append({
            "observation_id": word.observation_id,
            "block_no": word.block_no,
            "line_no": word.line_no,
            "word_no": word.word_no,
            "native_text": word.text,
            "trusted": word.trusted,
            "reason_codes": list(word.reason_codes),
        })
    return {
        "source_sha256_verified": True,
        "source_sha256": original_sha,
        "source_page_id": str(page_id),
        "material_code": code,
        "source_partition_id": partition_id,
        "source_block_no": block_no,
        "native_word_count": len(words),
        "original_native_untrusted_count": sum(not w.trusted for w in words),
        "post_raster_trusted_count": sum(w.trusted for w in recovered),
        "post_raster_untrusted_count": sum(not w.trusted for w in recovered),
        "word_receipts": details,
        "original_source_material_line_ocr_views_diagnostic_only": views,
        "material_definition_published": False,
        "material_occurrence_published": False,
        "signed_construction_quantity_published": False,
        "frozen_benchmark_accuracy": None,
        "diagnostic_only": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--material-code", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = inspect_native_material_row(
        args.pdf, expected_source_sha256=args.source_sha256,
        page_id=args.page_id, material_code=args.material_code,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        key: value for key, value in report.items() if key != "word_receipts"
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
