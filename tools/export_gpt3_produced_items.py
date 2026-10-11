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
from collections.abc import Mapping

from pb_combine_source_closed_runs import load_verified_sealed_run
from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_closed_run_export import SourceClosedRunConflictError


def _unique_customer_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    received: dict[str, Any] = {}
    for key,value in pairs:
        if key in received:
            raise ValueError(f"duplicate customer provenance JSON key: {key}")
        received[key] = value
    return received


def _reject_customer_json_constant(token: str) -> None:
    raise ValueError(f"non-finite customer JSON value: {token}")


def _finite_customer_json_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("out-of-range customer JSON number")
    return value


def _finite_customer_json_int(token: str) -> int:
    value = int(token)
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError("out-of-range customer JSON integer")
    return value


def _strict_customer_json(text: str) -> Any:
    # Mirror the source-run importer complexity bound. Serialized notes may
    # contain many quoted brackets; only genuine JSON structure counts.
    depth=0
    in_string=False
    escaped=False
    for character in text:
        if in_string:
            if escaped:
                escaped=False
            elif ord(character)==92:
                escaped=True
            elif character=='"':
                in_string=False
        elif character=='"':
            in_string=True
        elif character in "[{":
            depth+=1
            if depth>512:
                raise ValueError("customer JSON nesting exceeds safe parser depth")
        elif character in "]}":
            depth-=1
    try:
        return json.loads(
            text,
            object_pairs_hook=_unique_customer_json_keys,
            parse_constant=_reject_customer_json_constant,
            parse_float=_finite_customer_json_float,
            parse_int=_finite_customer_json_int,
        )
    except RecursionError as exc:
        raise ValueError("customer JSON nesting exceeds safe parser depth") from exc


def _verify_embedded_customer_notes(rows: Sequence[Mapping[str, Any]]) -> None:
    # Commercial adapter provenance can be embedded as JSON text in notes.
    # Outer strict parsing alone does not stop last-write-wins inside it.
    for row in rows:
        if not isinstance(row,Mapping):
            raise TypeError("customer rows must contain mappings")
        notes = row.get("notes")
        if isinstance(notes,str) and notes.lstrip().startswith("{"):
            _strict_customer_json(notes)


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
    customer_rows: Sequence[Mapping[str, Any]] | None = None,
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

    # Source-closed quantity proof is not proof the customer ever saw the
    # row. Only the existing exact source→customer bijection can assert that.
    customer_verified = customer_rows is not None
    if customer_rows is not None:
        _verify_embedded_customer_notes(customer_rows)
        verify_sealed_customer_output(sealed,customer_rows)

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    # Old V1 seals may predate the partial-physical-overlap fix. Do not
    # publish A+B and B+C as two quantities of the same physical claim.
    physical_claims: dict[tuple[str,str], set[str]] = {}
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
            or row.value < 0
        ):
            raise SourceClosedRunConflictError("nonfinite or negative sealed quantity cannot be exported")
        if row.abstained and row.value is not None:
            raise SourceClosedRunConflictError("ABSTAIN source quantity has a fabricated numeric value")
        if not row.abstained and (row.value is None or not row.object_identity_refs):
            raise SourceClosedRunConflictError("firm source quantity has no valid value or object")
        if row.source_sha256 not in actual_hashes:
            raise SourceClosedRunConflictError("signed quantity has no verified original source SHA")
        if not row.abstained:
            identity_key = (row.family.strip().lower(),row.semantic_key)
            claimed_ids = physical_claims.setdefault(identity_key,set())
            refs = set(row.object_identity_refs)
            if len(refs) != len(row.object_identity_refs) or claimed_ids.intersection(refs):
                raise SourceClosedRunConflictError(
                    "overlapping or duplicate signed physical source claims cannot be exported"
                )
            claimed_ids.update(refs)
        items.append({
            "quantity_id": row.quantity_id,
            "trade_category": None,
            "trade_authority_status": "UNAVAILABLE_NOT_INFERRED",
            "customer_output_parity_verified": customer_verified,
            "customer_output_parity_status": (
                "SIGNED_CUSTOMER_BIJECTION_VERIFIED" if customer_verified
                else "NOT_CHECKED_SOURCE_SEAL_ONLY"
            ),
            "project_id": sealed.project_id,
            "family": row.family,
            "semantic_key": row.semantic_key,
            "status": row.status,
            "authority": row.authority,
            "confidence": row.confidence,
            "value": row.value,
            "unit": row.unit,
            "object_refs": list(row.object_identity_refs),
            "lineage_ok": row.lineage_ok,
            "abstained": row.abstained,
            "source_document_id": row.document_id,
            "source_page": row.source_page,
            "viewport_id": row.viewport_id,
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
    parser.add_argument("--customer-rows", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    input_paths = [args.sealed_run, *args.source]
    if args.customer_rows is not None:
        input_paths.append(args.customer_rows)
    destination = args.output.resolve()
    if destination in {source.resolve() for source in input_paths}:
        raise ValueError("produced-items output must not overwrite original source inputs")
    # A misconfigured output path must never mutate the frozen reference
    # universe, manifests, expected quantities or official evaluator. They
    # are not necessarily listed among --source input PDFs for this run.
    frozen_benchmark_root = (
        Path(__file__).resolve().parent.parent
        / "benchmarks" / "frozen_holdout" / "full_plan_v2"
    ).resolve()
    if destination == frozen_benchmark_root or destination.is_relative_to(frozen_benchmark_root):
        raise ValueError("produced-items output must not overwrite frozen V2 benchmark inputs")
    # A concurrent source producer can rotate PDFs or the sealed run after
    # the initial verification. Recheck both immediately before publication.
    customer_rows = None
    original_customer_sha = None
    if args.customer_rows is not None:
        original_customer_sha = _sha256(args.customer_rows)
        customer_rows = _strict_customer_json(
            args.customer_rows.read_text(encoding="utf-8")
        )
        if not isinstance(customer_rows,list):
            raise TypeError("customer rows must be a JSON array")
    original_seal = load_verified_sealed_run(args.sealed_run)
    produced = export_verified_produced_items(
        args.sealed_run, args.source, expected_project_id=args.project_id,
        customer_rows=customer_rows,
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
    if args.customer_rows is not None and (
        _sha256(args.customer_rows) != original_customer_sha
    ):
        raise SourceClosedRunConflictError("customer rows changed during produced-items export")
    _atomic_write(args.output, produced)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
