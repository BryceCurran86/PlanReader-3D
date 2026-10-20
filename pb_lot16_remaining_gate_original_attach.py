"""Lot16 original attach for remaining Cursor quantity-recovery shadow gates."""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from pb_authorised_quantity_export_shadow import filter_authorised_quantity_rows_for_export
from pb_frame_unproven_pair_shadow import build_frame_unproven_pair_ledger
from pb_hosted_opening_deduction_shadow import assess_hosted_opening_deduction_shadow
from pb_lot16_inventory_dedupe_fragment_label_attach import (
    attach_inventory_dedupe_fragment_label_shadows,
)
from pb_lot16_opening_receipt_refresh_shadow import refresh_opening_first_gate_receipt
from pb_opening_universe_completeness_shadow import (
    assess_opening_universe_completeness_shadow,
)
from pb_signed_eight_id_retention import assert_signed_quantity_ids_retained
from pb_w4_candidate_id_collision_shadow import build_w4_candidate_id_collision_shadow
from pb_wall_length_height_quantity_shadow import assess_wall_length_height_face_shadow


def attach_lot16_remaining_gate_shadows(
    *,
    opening_decisions: Sequence[Mapping[str, Any]],
    canonical_by_id: Mapping[str, Mapping[str, Any]],
    observe_rows_by_id: Mapping[str, Mapping[str, Any]],
    existing_observe_rows: Sequence[Mapping[str, Any]],
    existing_canonical: Sequence[Mapping[str, Any]],
    f07_view: Mapping[str, Any],
    source_root: Mapping[str, str],
    customer_quantity_ids: Sequence[str],
    wall_candidate_records: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    inventory = attach_inventory_dedupe_fragment_label_shadows(
        opening_decisions=opening_decisions,
        observe_rows_by_id=observe_rows_by_id,
        expected_source_root=source_root,
    )
    universe = assess_opening_universe_completeness_shadow(
        instance_ids=[str(d["physical_opening_id"]) for d in opening_decisions],
        universe_complete=False,
    )
    signed_ids = [
        str(d["prior_signed_quantity_id"])
        for d in opening_decisions
        if d.get("prior_signed_quantity_id")
    ]
    retention = assert_signed_quantity_ids_retained(
        required_quantity_ids=customer_quantity_ids or signed_ids,
        observed_quantity_ids=signed_ids,
    )
    receipt = refresh_opening_first_gate_receipt(
        list(existing_observe_rows),
        list(existing_canonical),
        dict(f07_view),
        source_root=dict(source_root),
    )

    wall_gates: Counter[str] = Counter()
    deduction_gates: Counter[str] = Counter()
    frame_ledgers = []
    for decision in opening_decisions:
        oid = str(decision["physical_opening_id"])
        members = tuple(decision.get("source_host_member_wall_ids") or ())
        wall_id = members[0] if members else f"unhosted:{oid}"
        wall = assess_wall_length_height_face_shadow(
            wall_id=wall_id,
            length_m=None,
            length_authority=None,
            height_m=None,
            height_authority=None,
        )
        deduction = assess_hosted_opening_deduction_shadow(
            wall_id=wall_id,
            opening_id=oid,
            host_binding_record_id=decision.get("authenticated_host_record_id"),
            void_record_id=None,
            opening_area_m2=None,
            opening_area_authority=None,
        )
        wall_gates[wall["first_remaining_gate"]] += 1
        deduction_gates[deduction["first_remaining_gate"]] += 1
        reasons = tuple(decision.get("frame_reason_codes") or ())
        if any(str(r).startswith("opening_host_frame_unproven_wall_pair:") for r in reasons):
            frame_ledgers.append(build_frame_unproven_pair_ledger(
                reasons, (),
                component_member_ids=members,
            ))

    export_rows = [
        {
            "quantity_id": d.get("prior_signed_quantity_id") or f"unsigned:{d['physical_opening_id']}",
            "authority_status": "firm" if d.get("prior_signed_quantity_id") else "abstained",
        }
        for d in opening_decisions
    ]
    authorised = filter_authorised_quantity_rows_for_export(export_rows)
    w4 = build_w4_candidate_id_collision_shadow(wall_candidate_records)

    unrecorded_count = 0
    for ledger in frame_ledgers:
        for pair in ledger.get("unproven_pairs") or ():
            if pair.get("producer_relation") == "UNRECORDED":
                unrecorded_count += 1

    return {
        "status": "UNPUBLISHED_LOT16_REMAINING_GATE_ORIGINAL_ATTACH",
        "inventory": {
            "inventory_status": inventory["inventory_status"],
            "fragment_status": inventory["fragment_status"],
            "fragment_shared_wall_count": inventory["fragment_shared_wall_count"],
            "opening_count": inventory["opening_count"],
        },
        "universe_gate": universe["first_remaining_gate"],
        "signed_id_retention": retention["status"],
        "receipt_refresh_status": receipt.get("status"),
        "wall_length_height_gate_counts": dict(sorted(wall_gates.items())),
        "hosted_deduction_gate_counts": dict(sorted(deduction_gates.items())),
        "frame_unproven_pair_ledger_count": len(frame_ledgers),
        "frame_unrecorded_competitor_count": unrecorded_count,
        "authorised_export": {
            "exportable_count": authorised["exportable_count"],
            "withheld_count": authorised["withheld_count"],
            "jobhub_export_activated": False,
        },
        "w4_collision_status": w4.get("status"),
        "w4_collision_count": len(w4.get("collisions") or ()),
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
