"""Verify original client source FILE BYTES against the exact signed V1 SHA set.

Byte verification alone does not prove a wall, source viewport, producer
decision scope, completeness or frozen Full Plan V2 source authority.
This verifier never uploads original PDFs, changes signed outputs, publishes
a score or exposes original drawing content in its diagnostic.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_source_closed_run_export import (
    SealedSourceClosedRun, sealed_source_closed_run_from_dict,
)
from tools.gpt3_safe_original_report_output import (
    preflight_new_diagnostic, write_new_diagnostic,
)
from tools.report_gpt3_four_project_evidence import FROZEN_ROOT, _json_object


def _file_sha256(path: Path) -> str:
    """Bound memory to a 1-MiB chunk for arbitrarily large original drawings."""
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_original_source_sha_envelope(
    sealed: SealedSourceClosedRun, source_files: list[Path],
) -> dict:
    sealed = sealed_source_closed_run_from_dict(sealed.to_dict())
    expected = set(sealed.source_sha256s)
    if not expected or not sealed.quantities:
        raise ValueError("original file verification requires nonempty sealed sources")
    if not source_files or len(source_files) != len(expected):
        raise ValueError("one original source file per unique signed SHA required")
    found = {}
    for path in source_files:
        if path.is_symlink() or not path.is_file():
            raise ValueError("source original must be a regular non-symlink file")
        # Do not trust filenames or caller-provided hashes. Digest real bytes
        # from the original file on this run.
        source_sha = _file_sha256(path)
        if source_sha not in expected:
            raise ValueError("original source file bytes do not match signed V1 envelope")
        if source_sha in found:
            raise ValueError("duplicate original source SHA cannot satisfy two documents")
        found[source_sha] = path
    if set(found) != expected:
        raise ValueError("original source SHA envelope is incomplete")
    return {
        "schema_version": "gpt3_original_source_sha_envelope.v1",
        "publication_status": "UNPUBLISHED",
        "original_source_bytes_sha_verified": True,
        "source_record_issuer_authenticated": False,
        "physical_geometry_source_authenticated": False,
        "source_authenticated": False,
        "official_v2_accuracy": None,
        "project_id": sealed.project_id,
        "sealed_run_fingerprint": sealed.fingerprint,
        "sealed_quantity_count": len(sealed.quantities),
        "original_source_sha256s": sorted(found),
        "file_contents_exported": False,
    }


def build_original_source_sha_report(
    *, sealed_path: Path, original_paths: list[Path],
) -> dict:
    sources = [sealed_path, *original_paths]
    originals = [_file_sha256(path) for path in sources]
    sealed = sealed_source_closed_run_from_dict(_json_object(sealed_path))
    report = verify_original_source_sha_envelope(sealed, original_paths)
    if originals != [_file_sha256(path) for path in sources]:
        raise ValueError("original source bytes changed during audit")
    report["sealed_v1_file_sha256"] = originals[0]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sealed-run", type=Path, required=True)
    parser.add_argument("--original-source", type=Path, required=True, action="append")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    protected = (FROZEN_ROOT, args.sealed_run, *args.original_source)
    preflight_new_diagnostic(args.output, protected_roots=protected)
    report = build_original_source_sha_report(
        sealed_path=args.sealed_run, original_paths=args.original_source,
    )
    write_new_diagnostic(
        args.output,
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
        protected_roots=protected,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
