"""Verify original client source FILE BYTES against the exact signed V1 SHA set.

Byte verification alone does not prove a wall, source viewport, producer
decision scope, completeness or frozen Full Plan V2 source authority.
This verifier never uploads original PDFs, changes signed outputs, publishes
a score or exposes original drawing content in its diagnostic.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pb_source_closed_run_export import (
    SealedSourceClosedRun, sealed_source_closed_run_from_dict,
)
from tools.gpt3_safe_original_report_output import (
    preflight_new_diagnostic, write_new_diagnostic,
)
from tools.gpt3_original_source_preflight import (
    _original_source_path_kind, _stable_original_digest,
)
from tools.report_gpt3_four_project_evidence import FROZEN_ROOT, _json_object


def _source_witness(path: Path) -> tuple[str, tuple[int, ...]]:
    """Bind one original/seal digest to its regular no-follow source inode."""
    try:
        kind = _original_source_path_kind(path)
    except ValueError as exc:
        raise ValueError("source original must be a regular non-symlink file") from exc
    if kind != "regular":
        raise ValueError("source original must be a regular non-symlink file")
    return _stable_original_digest(path)


def _assert_source_witnesses(
    paths: list[Path], expected: tuple[tuple[str, tuple[int, ...]], ...],
) -> None:
    """A same-byte source replacement is still a different audit input."""
    if len(paths) != len(expected):
        raise ValueError("original source inventory changed during audit")
    for path, witness in zip(paths, expected):
        if _source_witness(path) != witness:
            raise ValueError("original source changed during audit")


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
        # No-follow descriptor SHA+inode proof; a raced symlink or same-byte
        # replacement cannot stand in for the authenticated original.
        source_sha, _identity = _source_witness(path)
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


def _build_original_source_sha_report_with_witnesses(
    *, sealed_path: Path, original_paths: list[Path],
) -> tuple[dict, tuple[tuple[str, tuple[int, ...]], ...]]:
    sources = [sealed_path, *original_paths]
    witnesses = tuple(_source_witness(path) for path in sources)
    sealed = sealed_source_closed_run_from_dict(_json_object(sealed_path))
    report = verify_original_source_sha_envelope(sealed, original_paths)
    _assert_source_witnesses(sources, witnesses)
    report["sealed_v1_file_sha256"] = witnesses[0][0]
    return report, witnesses


def build_original_source_sha_report(
    *, sealed_path: Path, original_paths: list[Path],
) -> dict:
    report, _witnesses = _build_original_source_sha_report_with_witnesses(
        sealed_path=sealed_path, original_paths=original_paths,
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sealed-run", type=Path, required=True)
    parser.add_argument("--original-source", type=Path, required=True, action="append")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    protected = (FROZEN_ROOT, args.sealed_run, *args.original_source)
    preflight_new_diagnostic(args.output, protected_roots=protected)
    report, witnesses = _build_original_source_sha_report_with_witnesses(
        sealed_path=args.sealed_run, original_paths=args.original_source,
    )
    sources = [args.sealed_run, *args.original_source]
    write_new_diagnostic(
        args.output,
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
        protected_roots=protected,
        verify_inputs=lambda: _assert_source_witnesses(sources, witnesses),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
