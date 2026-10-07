"""Fail-closed audit for sealed QuantityEvidence -> customer takeoff rows.

This module does not create, transform, approve, or score quantities. It proves
that the non-abstained rows in a sealed source-closed run are represented
exactly once in the commercial customer projection with the same source,
revision, canonical-entity, and evidence lineage.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import re
from typing import Any

from pb_source_closed_run_export import SealedSourceClosedRun, SealedSourceClosedQuantity


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class CustomerOutputVerificationError(RuntimeError):
    """The sealed run and customer projection are not a one-to-one lineage match."""


def _clean(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _norm_unit(value: Any) -> str:
    return _clean(value).lower().replace(" ", "")


def _string_tuple(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (_clean(values),) if _clean(values) else ()
    try:
        return tuple(sorted(_clean(value) for value in values if _clean(value)))
    except TypeError as exc:
        raise CustomerOutputVerificationError(
            "customer lineage field must be a sequence"
        ) from exc


def _projection_provenance(row: Mapping[str, Any]) -> Mapping[str, Any]:
    direct = row.get("commercial_projection_provenance")
    if isinstance(direct, Mapping):
        return direct

    notes = row.get("notes")
    if isinstance(notes, str) and notes.strip():
        try:
            parsed = json.loads(notes)
        except json.JSONDecodeError as exc:
            raise CustomerOutputVerificationError(
                "customer row notes contain invalid projection provenance JSON"
            ) from exc
        if isinstance(parsed, Mapping):
            return parsed

    raise CustomerOutputVerificationError(
        "customer row is missing commercial projection provenance"
    )


def _require_equal(name: str, actual: Any, expected: Any, quantity_id: str) -> None:
    if actual != expected:
        raise CustomerOutputVerificationError(
            f"customer row {quantity_id!r} {name} mismatch: "
            f"{actual!r} != {expected!r}"
        )


def _verify_row_lineage(
    sealed: SealedSourceClosedQuantity,
    row: Mapping[str, Any],
) -> None:
    quantity_id = sealed.quantity_id
    if not sealed.lineage_ok:
        raise CustomerOutputVerificationError(
            f"sealed quantity {quantity_id!r} has incomplete lineage: "
            + ", ".join(sealed.lineage_reason_codes)
        )

    _require_equal("project_id", _clean(row.get("project_id")), sealed.project_id, quantity_id)
    _require_equal("quantity_family", _clean(row.get("quantity_family")), sealed.family, quantity_id)
    _require_equal("semantic_key", _clean(row.get("semantic_key")), sealed.semantic_key, quantity_id)
    _require_equal("unit", _norm_unit(row.get("unit")), _norm_unit(sealed.unit), quantity_id)
    _require_equal("document_id", _clean(row.get("document_id")), sealed.document_id, quantity_id)
    _require_equal(
        "source_sha256",
        _clean(row.get("source_sha256")).lower(),
        sealed.source_sha256.lower(),
        quantity_id,
    )
    _require_equal("source_page", _clean(row.get("source_page")), sealed.source_page, quantity_id)
    _require_equal("viewport_id", _clean(row.get("viewport_id")), sealed.viewport_id, quantity_id)
    _require_equal("revision_id", _clean(row.get("revision_id")), sealed.revision_id, quantity_id)

    if sealed.value is None:
        raise CustomerOutputVerificationError(
            f"non-abstained sealed quantity {quantity_id!r} has no value"
        )
    try:
        row_value = float(row.get("quantity"))
    except (TypeError, ValueError, OverflowError) as exc:
        raise CustomerOutputVerificationError(
            f"customer row {quantity_id!r} has invalid quantity"
        ) from exc
    _require_equal("quantity", row_value, float(sealed.value), quantity_id)

    _require_equal(
        "canonical_entity_ids",
        _string_tuple(row.get("canonical_entity_ids")),
        tuple(sorted(sealed.trace_canonical_entity_ids)),
        quantity_id,
    )
    _require_equal(
        "evidence_ids",
        _string_tuple(row.get("evidence_ids")),
        tuple(sorted(sealed.trace_evidence_ids)),
        quantity_id,
    )

    fingerprint = _clean(row.get("commercial_projection_fingerprint")).lower()
    if not _SHA256_RE.fullmatch(fingerprint):
        raise CustomerOutputVerificationError(
            f"customer row {quantity_id!r} is missing a valid projection fingerprint"
        )

    provenance = _projection_provenance(row)
    qprov = provenance.get("quantity")
    tprov = provenance.get("source_trace")
    if not isinstance(qprov, Mapping) or not isinstance(tprov, Mapping):
        raise CustomerOutputVerificationError(
            f"customer row {quantity_id!r} has incomplete projection provenance"
        )

    _require_equal(
        "provenance.quantity_id",
        _clean(qprov.get("quantity_id")),
        sealed.quantity_id,
        quantity_id,
    )
    _require_equal(
        "provenance.input_entity_ids",
        _string_tuple(qprov.get("input_entity_ids")),
        tuple(sorted(sealed.object_identity_refs)),
        quantity_id,
    )
    _require_equal(
        "provenance.quantity_evidence_ids",
        _string_tuple(qprov.get("evidence_ids")),
        tuple(sorted(sealed.evidence_ids)),
        quantity_id,
    )
    _require_equal(
        "provenance.source_project_id",
        _clean(tprov.get("project_id")),
        sealed.project_id,
        quantity_id,
    )
    _require_equal(
        "provenance.source_document_id",
        _clean(tprov.get("document_id")),
        sealed.document_id,
        quantity_id,
    )
    _require_equal(
        "provenance.source_sha256",
        _clean(tprov.get("source_sha256")).lower(),
        sealed.source_sha256.lower(),
        quantity_id,
    )
    _require_equal(
        "provenance.source_page",
        _clean(tprov.get("source_page")),
        sealed.source_page,
        quantity_id,
    )
    _require_equal(
        "provenance.viewport_id",
        _clean(tprov.get("viewport_id")),
        sealed.viewport_id,
        quantity_id,
    )
    _require_equal(
        "provenance.revision_id",
        _clean(tprov.get("revision_id")),
        sealed.revision_id,
        quantity_id,
    )
    _require_equal(
        "provenance.canonical_entity_ids",
        _string_tuple(tprov.get("canonical_entity_ids")),
        tuple(sorted(sealed.trace_canonical_entity_ids)),
        quantity_id,
    )
    _require_equal(
        "provenance.trace_evidence_ids",
        _string_tuple(tprov.get("evidence_ids")),
        tuple(sorted(sealed.trace_evidence_ids)),
        quantity_id,
    )


@dataclass(frozen=True)
class SealedCustomerOutputVerification:
    project_id: str
    sealed_quantity_count: int
    valid_quantity_count: int
    abstained_quantity_count: int
    customer_row_count: int
    verified_quantity_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "sealed_quantity_count": self.sealed_quantity_count,
            "valid_quantity_count": self.valid_quantity_count,
            "abstained_quantity_count": self.abstained_quantity_count,
            "customer_row_count": self.customer_row_count,
            "verified_quantity_ids": list(self.verified_quantity_ids),
            "complete": True,
        }


def verify_sealed_customer_output(
    sealed_run: SealedSourceClosedRun,
    customer_rows: Sequence[Mapping[str, Any]],
) -> SealedCustomerOutputVerification:
    """Prove a bijection between valid sealed quantities and customer rows.

    Rows without quantity_id are outside this automated projection and are
    ignored (for example manual estimator rows). Every row with a quantity_id is
    treated as an automated customer projection and must correspond to exactly
    one non-abstained sealed quantity.
    """
    if not isinstance(sealed_run, SealedSourceClosedRun):
        raise TypeError("sealed_run must be a SealedSourceClosedRun")

    sealed_by_id = {row.quantity_id: row for row in sealed_run.quantities}
    if len(sealed_by_id) != len(sealed_run.quantities):
        raise CustomerOutputVerificationError("sealed run contains duplicate quantity ids")

    valid = {
        row.quantity_id: row
        for row in sealed_run.quantities
        if not row.abstained
    }
    abstained_ids = {
        row.quantity_id for row in sealed_run.quantities if row.abstained
    }

    customer_by_id: dict[str, Mapping[str, Any]] = {}
    for row in customer_rows:
        if not isinstance(row, Mapping):
            raise TypeError("customer_rows must contain mappings")
        quantity_id = _clean(row.get("quantity_id"))
        if not quantity_id:
            continue
        if quantity_id in customer_by_id:
            raise CustomerOutputVerificationError(
                f"duplicate customer row for quantity {quantity_id!r}"
            )
        customer_by_id[quantity_id] = row

    expected_ids = set(valid)
    actual_ids = set(customer_by_id)
    missing = sorted(expected_ids - actual_ids)
    leaked_abstentions = sorted(abstained_ids & actual_ids)
    extra = sorted(actual_ids - expected_ids - abstained_ids)
    if missing:
        raise CustomerOutputVerificationError(
            "valid sealed quantities missing customer rows: " + ", ".join(missing)
        )
    if leaked_abstentions:
        raise CustomerOutputVerificationError(
            "abstained quantities leaked into customer output: "
            + ", ".join(leaked_abstentions)
        )
    if extra:
        raise CustomerOutputVerificationError(
            "customer rows have no valid sealed quantity: " + ", ".join(extra)
        )

    for quantity_id in sorted(expected_ids):
        _verify_row_lineage(valid[quantity_id], customer_by_id[quantity_id])

    return SealedCustomerOutputVerification(
        project_id=sealed_run.project_id,
        sealed_quantity_count=len(sealed_run.quantities),
        valid_quantity_count=len(valid),
        abstained_quantity_count=len(abstained_ids),
        customer_row_count=len(customer_by_id),
        verified_quantity_ids=tuple(sorted(expected_ids)),
    )
