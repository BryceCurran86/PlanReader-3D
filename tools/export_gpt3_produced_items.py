"""Export real source-closed quantities to frozen-V2-compatible produced items.

This is an evidence exporter, not the frozen evaluator and not a trade
classifier. It cannot assign an unknown trade from room names, takeoff gold,
semantic keys or aliases. Full benchmark readiness remains UNPUBLISHED until
source coverage and independent commercial trade authority are proven.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Sequence

from pb_combine_source_closed_runs import load_verified_sealed_run
from pb_source_closed_run_export import SourceClosedRunConflictError


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_verified_produced_items(
    sealed_path: Path | str,
    original_sources: Sequence[Path | str],
    *,
    expected_project_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return only exact source-verified signed quantities, without inferred trades.

    All original PDFs must be supplied as bytes: a claimed or frozen
    manifest SHA alone is not proof the producer used these original files.
    V1 sealed envelopes do not sign independent trade categorisation.
    """
    sealed = load_verified_sealed_run(sealed_path)
    if expected_project_id is not None and sealed.project_id != expected_project_id:
        raise SourceClosedRunConflictError("produced-items project identity mismatch")
    if not original_sources:
        raise SourceClosedRunConflictError("original source files must be supplied for SHA verification")
    actual_hashes: list[str] = []
    resolved_paths: set[Path] = set()
    for source in original_sources:
        path = Path(source).resolve(strict=True)
        if path in resolved_paths:
            raise SourceClosedRunConflictError("duplicate original source input path")
        resolved_paths.add(path)
        if not path.is_file():
            raise SourceClosedRunConflictError("original source must be a regular file")
        actual_hashes.append(_sha256(path))
    if len(actual_hashes) != len(set(actual_hashes)):
        raise SourceClosedRunConflictError("duplicate original source SHA receipts")
    if set(actual_hashes) != set(sealed.source_sha256s):
        raise SourceClosedRunConflictError("original source SHA does not match sealed envelope")

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in sealed.quantities:
        if row.quantity_id in seen:
            raise SourceClosedRunConflictError("duplicate signed quantity ID")
        seen.add(row.quantity_id)
        if not row.lineage_ok:
            raise SourceClosedRunConflictError(
                f"cannot export quantity with unverified lineage: {row.quantity_id}"
            )
        # Historical V1 seals may have been created before final-vs-review
        # status gates existed. A valid fingerprint never authorizes a
        # provisional numeric quantity as production takeoff.
        status = str(getattr(row.status, "value", row.status)).strip().lower()
        if not row.abstained and status not in {"firm", "corroborated"}:
            raise SourceClosedRunConflictError("nonfirm sealed quantity cannot be exported")
        if not row.abstained and (
            row.blocking_reasons
            or any("conflict" in str(reason).lower() for reason in row.reason_codes)
        ):
            raise SourceClosedRunConflictError("blocked sealed quantity cannot be exported")
        if not row.abstained and (
            type(row.value) not in (int,float)
            or not math.isfinite(row.value)
        ):
            raise SourceClosedRunConflictError("nonfinite sealed quantity cannot be exported")
        if row.abstained and row.value is not None:
            raise SourceClosedRunConflictError("ABSTAIN source quantity has a fabricated numeric value")
        if not row.abstained and (row.value is None or not row.object_identity_refs):
            raise SourceClosedRunConflictError("firm source quantity has no valid value or object")
        if row.source_sha256 not in actual_hashes:
            raise SourceClosedRunConflictError("signed quantity has no verified original source SHA")
        items.append({
            "quantity_id": row.quantity_id,
            "trade_category": None,
            "trade_authority_status": "UNAVAILABLE_NOT_INFERRED",
            "family": row.family,
            "semantic_key": row.semantic_key,
            "value": row.value,
            "unit": row.unit,
            "object_refs": list(row.object_identity_refs),
            "lineage_ok": row.lineage_ok,
            "abstained": row.abstained,
            "source_document_id": row.document_id,
            "source_sha256": row.source_sha256,
            "revision_id": row.revision_id,
            "sealed_quantity_fingerprint": row.fingerprint,
        })
    return sorted(items, key=lambda item: item["quantity_id"])


def _atomic_write(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(items, sort_keys=True, indent=2, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sealed-run", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True, action="append")
    parser.add_argument("--project-id", type=str, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    input_paths = [args.sealed_run, *args.source]
    if args.output.resolve() in {source.resolve() for source in input_paths}:
        raise ValueError("produced-items output must not overwrite original source inputs")
    # A concurrent source producer can rotate PDFs or the sealed run after
    # the initial verification. Recheck both immediately before publication.
    original_seal = load_verified_sealed_run(args.sealed_run)
    produced = export_verified_produced_items(
        args.sealed_run, args.source, expected_project_id=args.project_id
    )
    current_seal = load_verified_sealed_run(args.sealed_run)
    if current_seal.fingerprint != original_seal.fingerprint:
        raise SourceClosedRunConflictError("sealed run changed during produced-items export")
    current_source_shas = [_sha256(Path(path)) for path in args.source]
    if (
        len(set(current_source_shas)) != len(current_source_shas)
        or set(current_source_shas) != set(original_seal.source_sha256s)
    ):
        raise SourceClosedRunConflictError("original source changed during produced-items export")
    _atomic_write(args.output, produced)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
