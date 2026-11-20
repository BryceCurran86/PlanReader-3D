"""Private original-PDF cold/warm native observation cache parity.

Checks source-observation identity only. Never authenticates walls, opening
areas, customer quantities, or frozen benchmark matches. Emits no source text
or individual source observation IDs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
import fitz
from pb_source_observation_authority import SourceObservationProducer

class NativeDecodeParityError(ValueError):
    """Source, scope, or cached observation identity cannot be authenticated."""

def check_original_native_decode_parity(
    source_bytes: bytes, *, expected_sha256: str, page_number: int,
) -> dict[str, object]:
    if not isinstance(source_bytes, bytes) or not source_bytes:
        raise NativeDecodeParityError("immutable_original_pdf_bytes_required")
    if type(expected_sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise NativeDecodeParityError("full_original_sha256_required")
    if hashlib.sha256(source_bytes).hexdigest() != expected_sha256:
        raise NativeDecodeParityError("original_source_digest_mismatch")
    if type(page_number) is not int or page_number < 1:
        raise NativeDecodeParityError("positive_integer_pdf_page_required")
    try:
        with fitz.open(stream=source_bytes, filetype="pdf") as pdf:
            if pdf.is_encrypted or not 1 <= page_number <= pdf.page_count:
                raise NativeDecodeParityError("original_source_page_unavailable")
    except (fitz.FileDataError, fitz.FileNotFoundError) as exc:
        raise NativeDecodeParityError("original_pdf_unreadable") from exc
    args = dict(
        document_id="live-source:" + expected_sha256[:32],
        source_bytes=source_bytes,
        source_locator="private://source-identity-parity",
        page_ids=(str(page_number),),
    )
    cold = SourceObservationProducer(producer_method="parity-check", producer_version="1")
    start = time.monotonic()
    first = cold.ingest_native_pdf_bytes(**args)
    cold_seconds = round(time.monotonic() - start, 3)
    cache_key = (expected_sha256, page_number)
    entry = cold._native_page_decode_cache.get(cache_key)
    if entry is None or entry.failed:
        raise NativeDecodeParityError("original_native_page_decode_unavailable")
    warm = SourceObservationProducer(producer_method="parity-check", producer_version="1")
    warm._native_page_decode_cache[cache_key] = entry
    start = time.monotonic()
    second = warm.ingest_native_pdf_bytes(**args)
    warm_seconds = round(time.monotonic() - start, 3)
    if not (
        first.revision.revision_id == second.revision.revision_id
        and first.revision.source_sha256 == second.revision.source_sha256
        and first.snapshot.snapshot_id == second.snapshot.snapshot_id
        and first.snapshot.observation_ids == second.snapshot.observation_ids
        and first.coverage == second.coverage
        and first.coverage.decoded_pages == (page_number,)
        and not first.coverage.failed_pages
    ):
        raise NativeDecodeParityError("cache_changed_original_source_observation_identity")
    return {
        "status": "SOURCE_NATIVE_DECODE_IDENTITY_PARITY_VERIFIED",
        "source_sha256": expected_sha256,
        "pdf_page": page_number,
        "observation_count": len(first.snapshot.observation_ids),
        "cold_seconds": cold_seconds,
        "warm_seconds": warm_seconds,
        "benchmark_scored": False,
        "physical_wall_authenticated": False,
        "commercial_quantity_authorized": False,
    }

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument("--sha256", required=True)
    ap.add_argument("--page", required=True, type=int, help="one-based PDF page")
    args = ap.parse_args(argv)
    try:
        if args.pdf.is_symlink() or not args.pdf.is_file():
            raise NativeDecodeParityError("original_private_pdf_required")
        report = check_original_native_decode_parity(
            args.pdf.read_bytes(), expected_sha256=args.sha256, page_number=args.page,
        )
    except (NativeDecodeParityError, ValueError, OSError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
