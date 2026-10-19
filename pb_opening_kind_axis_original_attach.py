"""Attach filling-kind and axis-ownership shadows to original opening rows.

Uses only producer-owned kind tokens and figured-label evidence. Never invents
a second axis or grants measurement.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pb_opening_axis_ownership_shadow import assess_opening_axis_ownership_shadow
from pb_opening_filling_kind_shadow import assess_opening_filling_kind_shadow


def _label_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    label = row.get("original_label_dimension_result") or {}
    evidence = label.get("evidence") or {}
    values = evidence.get("dimension_values_mm")
    return {
        "dimension_values_mm": tuple(values) if values else (),
        "axis_order_resolved": bool(evidence.get("axis_order_resolved")),
        "area_m2": evidence.get("area_m2"),
        "label_evidence_id": evidence.get("evidence_id"),
    }


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
    for decision in opening_decisions:
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
        kind_receipts = tuple(
            sorted(set(eid for eid in (
                canonical.get("opening_kind_evidence_id"),
                canonical.get("type_mark_evidence_id"),
            ) if type(eid) is str and eid
            and eid == eid.strip() and eid in evidence_ids))
        )
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
