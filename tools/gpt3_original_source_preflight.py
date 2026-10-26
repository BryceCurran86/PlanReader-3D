"""Classify original PDF presence before a GPT3 original-source replay.

A missing private original is SOURCE_BLOCKED: not a passing score and not a
silent production success. A present file whose digest disagrees is fail-closed.
This tool never copies, uploads, or invents PDF bytes.
"""
from __future__ import annotations

import argparse
import os
from hashlib import sha256
import json
from pathlib import Path
from stat import S_ISREG
from tools.gpt3_safe_original_report_output import (
    preflight_new_diagnostic,
    write_new_diagnostic,
)
import sys
from typing import Any

SOURCE_PRESENT = "SOURCE_PRESENT"
SOURCE_BLOCKED = "SOURCE_BLOCKED"
SOURCE_MISMATCH = "SOURCE_MISMATCH"
ORIGINAL_PDF_ABSENT = "original_pdf_absent"
ORIGINAL_PDF_DIGEST_MISMATCH = "original_pdf_digest_mismatch"



def _original_source_path_kind(pdf_path: Path) -> str:
    """Only a genuinely absent regular-file path is SOURCE_BLOCKED.

    Python 3.14 pathlib is_file() can suppress filesystem errors and treat
    inaccessible inputs as absent. lstat preserves those errors and refuses
    symlink/nonregular namespace substitutions, including dangling links.
    """
    try:
        mode = pdf_path.lstat().st_mode
    except FileNotFoundError:
        return "missing"
    except OSError as exc:
        raise ValueError("original source path cannot be inspected") from exc
    if not S_ISREG(mode):
        raise ValueError("original source path is not a regular file")
    return "regular"


def _stable_original_digest(pdf_path: Path) -> str:
    """Hash only the same regular source inode that was inspected.

    A second Path.read_bytes() after lstat can follow a replaced symlink or
    hash an unrelated same-byte file. Open a descriptor without following the
    final symlink, compare file identity before/during/after the read, and
    reject even same-digest namespace swaps. O_NONBLOCK prevents a raced FIFO
    from blocking before fstat can reject it.
    """
    try:
        before = pdf_path.lstat()
        if not S_ISREG(before.st_mode):
            raise ValueError("original source path is not a regular file")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(pdf_path, flags), "rb") as source:
            opened = os.fstat(source.fileno())
            if not S_ISREG(opened.st_mode):
                raise ValueError("original source changed during preflight")
            digest = sha256()
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
            completed = os.fstat(source.fileno())
        after = pdf_path.lstat()
    except OSError as exc:
        raise ValueError("original source changed or inaccessible during preflight") from exc
    identity_and_content = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if (
        not S_ISREG(after.st_mode)
        or any(
            getattr(snapshot, field) != getattr(before, field)
            for snapshot in (opened, completed, after)
            for field in identity_and_content
        )
    ):
        raise ValueError("original source changed during preflight")
    return digest.hexdigest()


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
    if _original_source_path_kind(pdf_path) == "missing":
        receipt.update(
            status=SOURCE_BLOCKED,
            reason=ORIGINAL_PDF_ABSENT,
        )
        return receipt
    actual = _stable_original_digest(pdf_path)
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


def _protected_report_roots(pdf: Path) -> tuple[Path, ...]:
    """Source originals, historical signed/customer and frozen evaluator are not outputs."""
    repo = Path(__file__).resolve().parents[1]
    return (
        pdf,
        repo / "documents/sources",
        repo / "benchmarks/frozen_holdout/full_plan_v2",
        repo / "docs/engineering",
    )


def _assert_receipt_source_unchanged(pdf: Path, receipt: dict[str, Any]) -> None:
    """A stale source status must never survive exclusive diagnostic publication."""
    kind = _original_source_path_kind(pdf)
    if receipt["status"] == SOURCE_BLOCKED:
        if kind != "missing":
            raise ValueError("original source appeared during preflight")
        return
    if kind != "regular":
        raise ValueError("original source disappeared during preflight")
    if _stable_original_digest(pdf) != receipt["actual_sha256"]:
        raise ValueError("original source changed during preflight")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    protected = _protected_report_roots(args.pdf)
    # Refuse an occupied/aliased destination before reading private PDF bytes.
    if args.output is not None:
        preflight_new_diagnostic(args.output, protected_roots=protected)
    receipt = classify_original_source_preflight(args.pdf, args.expected_sha256)
    text = json.dumps(receipt, sort_keys=True) + "\n"
    if args.output is not None:
        write_new_diagnostic(
            args.output, text, protected_roots=protected,
            verify_inputs=lambda: _assert_receipt_source_unchanged(args.pdf, receipt),
        )
    sys.stdout.write(text)
    status = receipt["status"]
    if status == SOURCE_PRESENT:
        return 0
    if status == SOURCE_BLOCKED:
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
