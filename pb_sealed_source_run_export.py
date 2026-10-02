"""Deterministic benchmark-neutral sealing of source-owned production quantities.

This module serializes existing QuantityEvidence plus its authoritative
CommercialTakeoffSourceTrace into a tamper-evident run artifact. It does
not import benchmark truth, expected values, scoring rules, room names, or
golden identities. Reconciliation to any benchmark happens only after this
production artifact has been sealed.
"""
from __future__ import annotations

import hashlib
from typing import Mapping, Sequence

from pb_migration_contracts import QuantityEvidence, canonical_contract_json
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace


SEALED_SOURCE_RUN_SCHEMA_VERSION = "1.0.0"


class SealedSourceRunError(ValueError):
    """Raised when a production quantity cannot be sealed deterministically."""


def _required(value: object, name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise SealedSourceRunError(f"{name} must be non-empty")
    return clean


def _unique(values: Sequence[object]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _fingerprinted(payload: Mapping[str, object]) -> dict[str, object]:
    clean = dict(payload)
    clean.pop("fingerprint", None)
    fingerprint = hashlib.sha256(
        canonical_contract_json(clean).encode("utf-8")
    ).hexdigest()
    return {**clean, "fingerprint": fingerprint}


def _metadata_lineage_reasons(
    quantity: QuantityEvidence,
    trace: CommercialTakeoffSourceTrace,
) -> list[str]:
    metadata = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
    expected = {
        "project_id": trace.project_id,
        "document_id": trace.document_id,
        "source_sha256": trace.source_sha256,
        "revision_id": trace.revision_id,
    }
    reasons: list[str] = []
    for key, authoritative in expected.items():
        if key not in metadata or metadata.get(key) is None:
            continue
        if str(metadata.get(key)).strip() != str(authoritative).strip():
            reasons.append(f"quantity_metadata_{key}_mismatch")
    return reasons


def seal_quantity_evidence(
    quantity: QuantityEvidence,
    *,
    trace: CommercialTakeoffSourceTrace,
    project_id: str,
) -> dict[str, object]:
    """Seal one production quantity without benchmark-aware identity mapping."""

    if not isinstance(quantity, QuantityEvidence):
        raise TypeError("quantity must be a QuantityEvidence record")
    if not isinstance(trace, CommercialTakeoffSourceTrace):
        raise TypeError("trace must be a CommercialTakeoffSourceTrace")

    project = _required(project_id, "project_id")
    if trace.project_id != project:
        raise SealedSourceRunError(
            "source trace project_id does not match sealed-run project_id"
        )

    reasons = _metadata_lineage_reasons(quantity, trace)

    missing_evidence = sorted(set(quantity.evidence_ids) - set(trace.evidence_ids))
    if missing_evidence:
        reasons.append(
            "trace_missing_quantity_evidence:" + ",".join(missing_evidence)
        )

    missing_entities = sorted(
        set(quantity.input_entity_ids) - set(trace.canonical_entity_ids)
    )
    if missing_entities:
        reasons.append(
            "trace_missing_quantity_entities:" + ",".join(missing_entities)
        )

    object_identity_refs = _unique(quantity.input_entity_ids)

    row = {
        "schema_version": SEALED_SOURCE_RUN_SCHEMA_VERSION,
        "project_id": project,
        "quantity_id": quantity.quantity_id,
        "family": quantity.family,
        "semantic_key": quantity.semantic_key,
        "value": quantity.value,
        "unit": quantity.unit,
        "status": quantity.status,
        "authority": quantity.authority,
        "confidence": float(quantity.confidence),
        "abstained": bool(quantity.abstained),
        "document_id": trace.document_id,
        "source_sha256": trace.source_sha256,
        "source_page": trace.source_page,
        "viewport_id": trace.viewport_id,
        "revision_id": trace.revision_id,
        "object_identity_refs": list(object_identity_refs),
        "trace_canonical_entity_ids": list(_unique(trace.canonical_entity_ids)),
        "evidence_ids": list(_unique(quantity.evidence_ids)),
        "trace_evidence_ids": list(_unique(trace.evidence_ids)),
        "blocking_reasons": list(_unique(quantity.blocking_reasons)),
        "reason_codes": list(_unique(quantity.reason_codes)),
        "lineage_ok": not reasons,
        "lineage_reason_codes": reasons,
    }
    return _fingerprinted(row)


def seal_source_run(
    *,
    run_id: str,
    project_id: str,
    quantities: Sequence[QuantityEvidence],
    traces_by_quantity_id: Mapping[str, CommercialTakeoffSourceTrace],
) -> dict[str, object]:
    """Seal a deterministic project run from already-produced quantities."""

    run = _required(run_id, "run_id")
    project = _required(project_id, "project_id")
    quantity_rows = tuple(quantities)

    quantity_ids = [quantity.quantity_id for quantity in quantity_rows]
    if len(quantity_ids) != len(set(quantity_ids)):
        raise SealedSourceRunError("quantity_id values must be unique")

    sealed_rows: list[dict[str, object]] = []
    source_hashes: set[str] = set()
    revision_ids: set[str] = set()

    for quantity in sorted(quantity_rows, key=lambda item: item.quantity_id):
        trace = traces_by_quantity_id.get(quantity.quantity_id)
        if trace is None:
            raise SealedSourceRunError(
                f"missing source trace for quantity_id {quantity.quantity_id}"
            )
        sealed = seal_quantity_evidence(
            quantity,
            trace=trace,
            project_id=project,
        )
        sealed_rows.append(sealed)
        source_hashes.add(trace.source_sha256)
        revision_ids.add(trace.revision_id)

    if not sealed_rows:
        raise SealedSourceRunError("sealed source run requires at least one quantity")

    payload = {
        "schema_version": SEALED_SOURCE_RUN_SCHEMA_VERSION,
        "run_id": run,
        "project_id": project,
        "source_sha256s": sorted(source_hashes),
        "revision_ids": sorted(revision_ids),
        "quantities": sealed_rows,
    }
    return _fingerprinted(payload)


__all__ = [
    "SEALED_SOURCE_RUN_SCHEMA_VERSION",
    "SealedSourceRunError",
    "seal_quantity_evidence",
    "seal_source_run",
]
