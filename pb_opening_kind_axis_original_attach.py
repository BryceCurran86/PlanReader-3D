"""Attach filling-kind and axis-ownership shadows to original opening rows.

Uses only producer-owned kind tokens and figured-label evidence. Never invents
a second axis or grants measurement.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_axis_ownership_shadow import assess_opening_axis_ownership_shadow
from pb_opening_filling_kind_shadow import assess_opening_filling_kind_shadow
from pb_opening_kind_authority import resolve_opening_kind
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS


def _label_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    label = row.get("original_label_dimension_result") or {}
    evidence = label.get("evidence") or {}
    values = evidence.get("dimension_values_mm")
    return {
        "dimension_values_mm": tuple(values) if values else (),
        "axis_order_resolved": evidence.get("axis_order_resolved") is True,
        "area_m2": evidence.get("area_m2"),
        "label_evidence_id": evidence.get("evidence_id"),
    }


def _original_structural_kind_receipt(
    *, physical_opening_id: str, canonical: Mapping[str, Any],
    observed: Mapping[str, Any], canonical_receipts: frozenset[str],
) -> str | None:
    """Re-prove source OWNED structural kind, not a figured label or host gap.

    Original G17 PhysicalOpeningAuthority must have issued an existence
    record with the same source root, page and structural class as canonical.
    This is review-only: neither this helper nor a label grants FIRM.
    """
    rec = observed.get("physical_existence_record")
    if (not isinstance(rec, Mapping)
            or rec.get("record_id") != physical_opening_id
            or rec.get("proposition") != PHYSICAL_OPENING_EXISTS
            or rec.get("status") is not EvidenceResolutionStatus.CORROBORATED
            or canonical.get("physical_opening_id") != physical_opening_id
            or physical_opening_id not in canonical_receipts
            or type(rec.get("structural_pattern")) is not str
            or not rec["structural_pattern"]
            or rec["structural_pattern"] != canonical.get("structural_pattern")
            or any(not canonical.get(k) or canonical.get(k) != rec.get(k)
                   for k in ("document_id", "revision_id",
                             "source_sha256", "snapshot_id", "page_id"))):
        return None
    observed_ids = rec.get("source_observation_ids")
    if (type(observed_ids) not in (tuple, list)
            or not observed_ids
            or any(type(x) is not str or x not in canonical_receipts
                   for x in observed_ids)):
        return None
    proof = resolve_opening_kind(structural_pattern=rec["structural_pattern"])
    if (proof.status is not EvidenceResolutionStatus.CORROBORATED
            or proof.opening_kind != canonical.get("opening_kind")):
        return None
    return physical_opening_id


def attach_kind_and_axis_shadows(
    *,
    opening_decisions: Sequence[Mapping[str, Any]],
    canonical_by_id: Mapping[str, Mapping[str, Any]],
    observe_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    # Exactly one source-owned decision per physical opening, across all
    # three producer snapshots. Missing/extra/rekeyed members cannot be
    # concealed by the pretty-printed shadow ledger.
    ids = [str(d.get("physical_opening_id") or "").strip()
           for d in opening_decisions]
    if (
        len(set(ids)) != len(ids)
        or any(not identity for identity in ids)
        or set(ids) != set(canonical_by_id)
        or set(ids) != set(observe_rows_by_id)
    ):
        raise ValueError("source-owned kind/axis physical opening inventory mismatch")
    attached: list[dict[str, Any]] = []
    kind_gates: dict[str, int] = {}
    axis_gates: dict[str, int] = {}
    for decision in sorted(
        opening_decisions,
        key=lambda item: str(item.get("physical_opening_id") or ""),
    ):
        oid = str(decision.get("physical_opening_id") or "").strip()
        if not oid:
            raise ValueError("physical opening identity required")
        canonical = canonical_by_id[oid]
        observed = observe_rows_by_id[oid]
        label = _label_fields(observed)
        # A figured AREA-label receipt is a measurement source, not proof
        # that an object is a door rather than a window. Pass only separate,
        # producer-issued semantic-kind or opening-mark receipt IDs that are
        # still owned by the exact canonical opening evidence set.
        original_receipts = canonical.get("evidence_ids")
        evidence_ids = (
            frozenset(original_receipts)
            if type(original_receipts) in (tuple, list)
            and all(type(item) is str for item in original_receipts)
            else frozenset()
        )
        typed_kind_receipts = tuple(
            sorted(set(eid for eid in (
                canonical.get("opening_kind_evidence_id"),
                canonical.get("type_mark_evidence_id"),
            ) if type(eid) is str and eid
            and eid == eid.strip() and eid in evidence_ids))
        )
        physical_kind_receipt = _original_structural_kind_receipt(
            physical_opening_id=oid, canonical=canonical, observed=observed,
            canonical_receipts=evidence_ids,
        )
        kind_receipts = tuple(sorted(set(
            (*typed_kind_receipts, *((physical_kind_receipt,)
              if physical_kind_receipt else ()))
        )))
        kind = assess_opening_filling_kind_shadow(
            physical_opening_id=oid,
            opening_kind=canonical.get("opening_kind"),
            source_kind_evidence_ids=kind_receipts,
        )
        axis = assess_opening_axis_ownership_shadow(
            physical_opening_id=oid,
            dimension_values_mm=label["dimension_values_mm"],
            axis_order_resolved=label["axis_order_resolved"],
            width_record_id=canonical.get("width_record_id"),
            height_record_id=canonical.get("height_record_id"),
            width_m=canonical.get("width_m"),
            height_m=canonical.get("height_m"),
            area_m2=label["area_m2"],
            canonical_evidence_ids=canonical.get("evidence_ids"),
            geometry_complete=canonical.get("geometry_complete"),
        )
        kind_gates[kind["first_remaining_gate"]] = (
            kind_gates.get(kind["first_remaining_gate"], 0) + 1
        )
        axis_gates[axis["first_remaining_gate"]] = (
            axis_gates.get(axis["first_remaining_gate"], 0) + 1
        )
        attached.append({
            "physical_opening_id": oid,
            "handoff_first_remaining_gate": decision.get("first_remaining_gate"),
            "prior_signed_quantity_id": decision.get("prior_signed_quantity_id"),
            "kind_shadow": kind,
            "original_structural_kind_source_reproved": bool(physical_kind_receipt),
            "axis_shadow": axis,
            "invented_second_axis": False,
            "measurement_published": False,
        })
    return {
        "status": "UNPUBLISHED_KIND_AXIS_ORIGINAL_ATTACH",
        "opening_count": len(attached),
        "kind_gate_counts": dict(sorted(kind_gates.items())),
        "axis_gate_counts": dict(sorted(axis_gates.items())),
        "openings": attached,
        "measurement_published": False,
        "customer_seal_granted": False,
        "opening_count_granted": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
