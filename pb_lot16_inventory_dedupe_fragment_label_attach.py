"""Lot16 original attach for inventory / dedupe / fragment / label shadows."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pb_opening_fragment_identity_shadow import assess_opening_fragment_identity_shadow
from pb_opening_label_leader_witness_shadow import bind_opening_label_leader_witness_shadow
from pb_opening_quantity_inventory_shadow import reject_duplicate_and_stale_quantity_rows
from pb_signed_opening_dedupe_shadow import assess_signed_opening_dedupe_shadow


def attach_inventory_dedupe_fragment_label_shadows(
    *,
    opening_decisions: Sequence[Mapping[str, Any]],
    observe_rows_by_id: Mapping[str, Mapping[str, Any]],
    expected_source_root: Mapping[str, str],
) -> dict[str, Any]:
    sealed_phys = [
        str(d["physical_opening_id"])
        for d in opening_decisions
        if d.get("prior_signed_quantity_id")
    ]
    sealed_qty = [
        str(d["prior_signed_quantity_id"])
        for d in opening_decisions
        if d.get("prior_signed_quantity_id")
    ]
    inventory_input = []
    for decision in opening_decisions:
        oid = str(decision["physical_opening_id"])
        inventory_input.append({
            "physical_opening_id": oid,
            "quantity_id": decision.get("prior_signed_quantity_id"),
            "document_id": expected_source_root.get("document_id"),
            "revision_id": expected_source_root.get("revision_id"),
            "source_sha256": expected_source_root.get("source_sha256"),
            "snapshot_id": expected_source_root.get("snapshot_id"),
        })
    inventory = reject_duplicate_and_stale_quantity_rows(
        inventory_input, expected_source_root=expected_source_root,
    )
    fragment = assess_opening_fragment_identity_shadow(
        openings=[
            {
                "physical_opening_id": d["physical_opening_id"],
                "host_member_wall_candidate_ids": d.get("source_host_member_wall_ids") or (),
            }
            for d in opening_decisions
        ],
    )

    attached = []
    for decision in opening_decisions:
        oid = str(decision["physical_opening_id"])
        observed = observe_rows_by_id[oid]
        label = observed.get("original_label_dimension_result") or {}
        evidence = label.get("evidence") or {}
        leader = bind_opening_label_leader_witness_shadow(
            physical_opening_id=oid,
            printed_mark=None,
            schedule_row_id=None,
            leader_evidence_id=None,
            dimension_witness_ids=(
                (str(evidence["evidence_id"]),) if evidence.get("evidence_id") else ()
            ),
            proximity_only=False,
        )
        # For signed rows, treat as already sealed members (self); for unsigned,
        # check against sealed sets without self-reuse blockers.
        sealed_phys_for = [x for x in sealed_phys if x != oid]
        sealed_qty_for = [
            x for x in sealed_qty if x != str(decision.get("prior_signed_quantity_id") or "")
        ]
        dedupe = assess_signed_opening_dedupe_shadow(
            candidate_physical_opening_id=oid,
            candidate_quantity_id=decision.get("prior_signed_quantity_id"),
            sealed_physical_opening_ids=sealed_phys_for,
            sealed_quantity_ids=sealed_qty_for,
        )
        attached.append({
            "physical_opening_id": oid,
            "label_leader_gate": leader["first_remaining_gate"],
            "signed_dedupe_gate": dedupe.get("first_remaining_gate") or dedupe.get("status"),
            "measurement_published": False,
        })
    return {
        "status": "UNPUBLISHED_LOT16_INVENTORY_DEDUPE_FRAGMENT_LABEL_ATTACH",
        "inventory_status": inventory.get("status") or inventory.get("first_remaining_gate"),
        "fragment_status": fragment.get("status") or fragment.get("first_remaining_gate"),
        "fragment_shared_wall_count": len(fragment.get("shared_fragment_owners") or {}),
        "opening_count": len(attached),
        "openings": attached,
        "measurement_published": False,
        "shadow_only": True,
    }
