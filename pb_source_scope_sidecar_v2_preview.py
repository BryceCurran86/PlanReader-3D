"""Versioned tamper-evident scope sidecar alongside unmodified V1 source seals.

This binds source-producer snapshot, decision-scope and record identifiers to
the existing exact signed V1 run/quantity fingerprints. It is *not* proof that
the producer metadata itself came from the original PDF: that authority must
be verified upstream, and is deliberately never asserted by this sidecar.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from pb_migration_contracts import QuantityEvidence
from pb_customer_output_verification import (
    _customer_quantity_id, _projection_provenance, verify_sealed_customer_output,
)
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import (
    SealedSourceClosedRun, SourceClosedRunConflictError,
    seal_source_closed_quantity, sealed_source_closed_run_from_dict,
)

SCOPE_SIDECAR_SCHEMA = "gpt3_source_scope_sidecar.v2-preview.1"
SCOPE_NOT_AUTHENTICATED = "SOURCE_PRODUCER_AUTHORITY_NOT_INDEPENDENTLY_VERIFIED"
SNAPSHOT_KEYS = ("source_snapshot_id", "evidence_snapshot_id", "snapshot_id")
SCOPE_KEYS = ("decision_scope_id",)
RECORD_KEYS = ("source_scope_record_id",)


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _producer_id(metadata: Mapping[str, Any], aliases: tuple[str, ...], field: str) -> str:
    values = [metadata[name] for name in aliases if name in metadata]
    if not values:
        raise SourceClosedRunConflictError(f"{field} producer receipt missing")
    if any(type(value) is not str or not value or value.strip() != value for value in values):
        raise SourceClosedRunConflictError(f"{field} producer receipt malformed")
    if len(set(values)) != 1:
        raise SourceClosedRunConflictError(f"{field} producer aliases conflict")
    return values[0]


def _source_scope_pair(
    quantity: QuantityEvidence, trace: CommercialTakeoffSourceTrace,
    names: tuple[str, ...], field: str,
) -> str:
    qmeta = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
    tmeta = trace.metadata if isinstance(trace.metadata, Mapping) else {}
    first = _producer_id(qmeta, names, field)
    second = _producer_id(tmeta, names, field)
    if first != second:
        raise SourceClosedRunConflictError(f"{field} quantity/trace producer receipts disagree")
    return first


def build_v2_preview_scope_sidecar(
    sealed: SealedSourceClosedRun,
    quantities: Sequence[QuantityEvidence],
    traces_by_quantity_id: Mapping[str, CommercialTakeoffSourceTrace],
) -> dict[str, Any]:
    """Build only when all provided scope IDs agree with source-owned receipts.

    Matching metadata is NOT independently source-authenticated. Never publish
    the sidecar as customer authority or substitute it for the V1 signed seal.
    """
    sealed = sealed_source_closed_run_from_dict(sealed.to_dict())
    originals: dict[str, QuantityEvidence] = {}
    for quantity in quantities:
        if not isinstance(quantity, QuantityEvidence):
            raise TypeError("scope sidecar quantities must be QuantityEvidence")
        if quantity.quantity_id in originals:
            raise SourceClosedRunConflictError("duplicate scope-sidecar quantity ID")
        originals[quantity.quantity_id] = quantity
    if set(originals) != {row.quantity_id for row in sealed.quantities}:
        raise SourceClosedRunConflictError("scope-sidecar quantities differ from sealed run")
    observed_record_ids: set[str] = set()
    records: list[dict[str, Any]] = []
    for row in sealed.quantities:
        quantity = originals[row.quantity_id]
        trace = traces_by_quantity_id.get(row.quantity_id)
        if not isinstance(trace, CommercialTakeoffSourceTrace):
            raise SourceClosedRunConflictError("scope sidecar source trace missing")
        authenticated_v1 = seal_source_closed_quantity(quantity, trace=trace)
        if authenticated_v1.fingerprint != row.fingerprint or not row.lineage_ok:
            raise SourceClosedRunConflictError("scope sidecar quantity differs from V1 sealed receipt")
        snapshot = _source_scope_pair(quantity,trace,SNAPSHOT_KEYS,"snapshot_id")
        scope = _source_scope_pair(quantity,trace,SCOPE_KEYS,"decision_scope_id")
        record_id = _source_scope_pair(quantity,trace,RECORD_KEYS,"source_scope_record_id")
        if record_id in observed_record_ids:
            raise SourceClosedRunConflictError("source scope record reused across quantity identities")
        observed_record_ids.add(record_id)
        records.append({
            "quantity_id": row.quantity_id,
            "sealed_quantity_fingerprint": row.fingerprint,
            "source_document_id": row.document_id,
            "source_sha256": row.source_sha256,
            "revision_id": row.revision_id,
            "source_page": row.source_page,
            "viewport_id": row.viewport_id,
            "physical_object_refs": list(row.object_identity_refs),
            "source_scope_record_id": record_id,
            "source_snapshot_id": snapshot,
            "decision_scope_id": scope,
            "source_record_authentication": SCOPE_NOT_AUTHENTICATED,
        })
    payload: dict[str, Any] = {
        "schema_version": SCOPE_SIDECAR_SCHEMA,
        "publication_status": "UNPUBLISHED",
        "source_authenticated": False,
        "project_id": sealed.project_id,
        "sealed_run_fingerprint": sealed.fingerprint,
        "scope_records": sorted(records,key=lambda r:r["quantity_id"]),
    }
    return {**payload,"integrity_fingerprint":_fingerprint(payload)}


def verify_v2_preview_scope_sidecar(
    payload: Mapping[str, Any],
    sealed: SealedSourceClosedRun,
) -> bool:
    """Check tamper-evident v2-preview linkage; NOT original-source authority."""
    sealed = sealed_source_closed_run_from_dict(sealed.to_dict())
    if not isinstance(payload, Mapping):
        raise TypeError("scope sidecar must be a mapping")
    expected_envelope_keys = {
        "schema_version", "publication_status", "source_authenticated",
        "project_id", "sealed_run_fingerprint", "scope_records",
        "integrity_fingerprint",
    }
    if set(payload) != expected_envelope_keys:
        raise SourceClosedRunConflictError("scope sidecar envelope contains unsupported fields")
    if (
        payload.get("schema_version") != SCOPE_SIDECAR_SCHEMA
        or payload.get("publication_status") != "UNPUBLISHED"
        or payload.get("source_authenticated") is not False
        or payload.get("project_id") != sealed.project_id
        or payload.get("sealed_run_fingerprint") != sealed.fingerprint
    ):
        raise SourceClosedRunConflictError("scope sidecar is not bound to exact V1 sealed run")
    if type(payload.get("integrity_fingerprint")) is not str:
        raise SourceClosedRunConflictError("scope sidecar fingerprint missing")
    base = {key: value for key,value in payload.items() if key!="integrity_fingerprint"}
    if payload["integrity_fingerprint"] != _fingerprint(base):
        raise SourceClosedRunConflictError("scope sidecar integrity fingerprint mismatch")
    records = payload.get("scope_records")
    if not isinstance(records,list) or len(records)!=len(sealed.quantities):
        raise SourceClosedRunConflictError("scope sidecar quantity universe incomplete")
    by_id = {row.quantity_id:row for row in sealed.quantities}
    seen: set[str] = set()
    source_ids: set[str] = set()
    for record in records:
        if not isinstance(record,dict):
            raise SourceClosedRunConflictError("scope sidecar row must be an object")
        expected_record_keys = {
            "quantity_id", "sealed_quantity_fingerprint",
            "source_document_id", "source_sha256", "revision_id",
            "source_page", "viewport_id", "physical_object_refs",
            "source_scope_record_id", "source_snapshot_id",
            "decision_scope_id", "source_record_authentication",
        }
        if set(record) != expected_record_keys:
            raise SourceClosedRunConflictError("scope sidecar contains unsupported source record fields")
        quantity_id = record.get("quantity_id")
        if quantity_id in seen or quantity_id not in by_id:
            raise SourceClosedRunConflictError("duplicate or unsealed scope quantity identity")
        seen.add(quantity_id)
        row = by_id[quantity_id]
        expected = {
            "sealed_quantity_fingerprint":row.fingerprint,
            "source_document_id":row.document_id,
            "source_sha256":row.source_sha256,
            "revision_id":row.revision_id,
            "source_page":row.source_page,
            "viewport_id":row.viewport_id,
            "physical_object_refs":list(row.object_identity_refs),
            "source_record_authentication":SCOPE_NOT_AUTHENTICATED,
        }
        if any(record.get(k) != v for k,v in expected.items()):
            raise SourceClosedRunConflictError("scope sidecar source/quantity lineage mismatch")
        for key in ("source_scope_record_id","source_snapshot_id","decision_scope_id"):
            value=record.get(key)
            if type(value) is not str or not value or value.strip()!=value:
                raise SourceClosedRunConflictError("scope sidecar source scope ID malformed")
        source_id=record["source_scope_record_id"]
        if source_id in source_ids:
            raise SourceClosedRunConflictError("scope sidecar source record reused")
        source_ids.add(source_id)
    return True


def verify_v2_preview_scope_customer_receipts(
    payload: Mapping[str, Any],
    sealed: SealedSourceClosedRun,
    customer_rows: Sequence[Mapping[str, Any]],
) -> bool:
    """Verify read-only customer metadata parity with a V1-bound preview sidecar.

    This requires both the established signed V1/customer bijection and the
    optional V2-preview source-scope receipts. It does NOT authenticate the
    original producer claims in customer metadata or scope sidecar, and it
    never changes an old signed V1 fingerprint or authorizes publication.
    Legacy V1-only customer runs remain valid through their existing verifier.
    """
    verify_v2_preview_scope_sidecar(payload, sealed)
    verified = verify_sealed_customer_output(sealed, customer_rows)
    expected_ids = set(verified.verified_quantity_ids)
    records = {
        record["quantity_id"]: record for record in payload["scope_records"]
    }
    if not expected_ids.issubset(records):
        raise SourceClosedRunConflictError(
            "customer scope sidecar is missing sealed commercial quantity IDs"
        )
    seen: set[str] = set()
    for row in customer_rows:
        quantity_id = _customer_quantity_id(row)
        if not quantity_id:
            # The original verifier already rejected a manual row attempting
            # to impersonate source-authenticated commercial output.
            continue
        if quantity_id not in expected_ids or quantity_id in seen:
            raise SourceClosedRunConflictError(
                "customer scope row is not a unique sealed commercial quantity"
            )
        seen.add(quantity_id)
        record = records[quantity_id]
        provenance = _projection_provenance(row)
        quantity = provenance.get("quantity")
        trace = provenance.get("source_trace")
        if not isinstance(quantity, Mapping) or not isinstance(trace, Mapping):
            raise SourceClosedRunConflictError(
                "customer scope provenance requires quantity and source trace"
            )
        qmeta = quantity.get("metadata")
        tmeta = trace.get("metadata")
        if not isinstance(qmeta, Mapping) or not isinstance(tmeta, Mapping):
            raise SourceClosedRunConflictError(
                "customer scope producer metadata missing"
            )
        for aliases, field, expected in (
            (SNAPSHOT_KEYS, "snapshot_id", record["source_snapshot_id"]),
            (SCOPE_KEYS, "decision_scope_id", record["decision_scope_id"]),
            (RECORD_KEYS, "source_scope_record_id", record["source_scope_record_id"]),
        ):
            received = _producer_id(qmeta, aliases, field)
            traced = _producer_id(tmeta, aliases, field)
            if received != expected or traced != expected:
                raise SourceClosedRunConflictError(
                    f"customer {field} receipt conflicts with sealed scope sidecar"
                )
    if seen != expected_ids:
        raise SourceClosedRunConflictError(
            "customer scope preview is missing commercial quantities"
        )
    return True


__all__ = [
    "SCOPE_SIDECAR_SCHEMA",
    "SCOPE_NOT_AUTHENTICATED",
    "build_v2_preview_scope_sidecar",
    "verify_v2_preview_scope_sidecar",
    "verify_v2_preview_scope_customer_receipts",
]
