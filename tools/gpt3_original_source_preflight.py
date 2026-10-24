"""Classify original PDF presence before a GPT3 original-source replay.

A missing private original is SOURCE_BLOCKED: not a passing score and not a
silent production success. A present file whose digest disagrees is fail-closed.
This tool never copies, uploads, or invents PDF bytes.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

SOURCE_PRESENT = "SOURCE_PRESENT"
SOURCE_BLOCKED = "SOURCE_BLOCKED"
SOURCE_MISMATCH = "SOURCE_MISMATCH"
ORIGINAL_PDF_ABSENT = "original_pdf_absent"
ORIGINAL_PDF_DIGEST_MISMATCH = "original_pdf_digest_mismatch"


def classify_original_source_preflight(
    pdf_path: Path,
    expected_sha256: str,
) -> dict[str, Any]:
    if not isinstance(pdf_path, Path):
        raise TypeError("pdf_path must be a Path")
    expected = str(expected_sha256 or "").strip().lower()
    if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
        raise ValueError("expected_sha256 must be 64 lowercase hex characters")
    receipt: dict[str, Any] = {
        "pdf_path": str(pdf_path),
        "expected_sha256": expected,
        "benchmark_score_granted": False,
        "original_source_verified": False,
    }
    if not pdf_path.is_file():
        receipt.update(
            status=SOURCE_BLOCKED,
            reason=ORIGINAL_PDF_ABSENT,
        )
        return receipt
    actual = sha256(pdf_path.read_bytes()).hexdigest()
    receipt["actual_sha256"] = actual
    if actual != expected:
        receipt.update(
            status=SOURCE_MISMATCH,
            reason=ORIGINAL_PDF_DIGEST_MISMATCH,
        )
        return receipt
    receipt.update(
        status=SOURCE_PRESENT,
        reason="original_pdf_digest_matches",
        original_source_verified=True,
    )
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    receipt = classify_original_source_preflight(args.pdf, args.expected_sha256)
    text = json.dumps(receipt, sort_keys=True) + "\n"
    sys.stdout.write(text)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    status = receipt["status"]
    if status == SOURCE_PRESENT:
        return 0
    if status == SOURCE_BLOCKED:
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
