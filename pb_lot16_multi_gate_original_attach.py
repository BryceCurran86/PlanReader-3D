"""Attach many Cursor shadow gates to Lot16 handoff/canonical/observe rows.

Default-off diagnostic enrichment. Never invents axes, grants host, or seals.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from pb_bifold_filling_kind_shadow import assess_bifold_filling_kind_shadow
from pb_canonical_quantity_attach_shadow import attach_quantity_to_canonical_entity_shadow
from pb_door_height_owner_gate_shadow import assess_door_height_owner_gate_shadow
from pb_frozen_v2_eval_readiness_shadow import assess_frozen_v2_eval_readiness_shadow
from pb_glazed_opening_frame_area_readiness_shadow import (
    assess_glazed_opening_frame_area_readiness_shadow,
)
from pb_opening_kind_axis_original_attach import attach_kind_and_axis_shadows
from pb_source_closed_seal_readiness_shadow import (
    assess_source_closed_seal_readiness_shadow,
)
from pb_source_lineage_required_fields_shadow import (
    enforce_source_lineage_required_fields_shadow,
)
from pb_stacker_host_frame_readiness_shadow import (
    assess_stacker_host_frame_readiness_shadow,
)
from pb_trade_quantity_evidence_readiness_shadow import (
    assess_trade_quantity_evidence_readiness_shadow,
)
from pb_whole_wall_frame_readiness_shadow import (
    assess_whole_wall_frame_readiness_shadow,
)


def _label_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    label = row.get("original_label_dimension_result") or {}
    evidence = label.get("evidence") or {}
    values = evidence.get("dimension_values_mm")
    return {
        "dimension_values_mm": tuple(values) if values else (),
        "axis_order_resolved": bool(evidence.get("axis_order_resolved")),
        "area_m2": evidence.get("area_m2"),
    }


def attach_lot16_multi_gate_shadows(
    *,
    opening_decisions: Sequence[Mapping[str, Any]],
    canonical_by_id: Mapping[str, Mapping[str, Any]],
    observe_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    kind_axis = attach_kind_and_axis_shadows(
        opening_decisions=opening_decisions,
        canonical_by_id=canonical_by_id,
        observe_rows_by_id=observe_rows_by_id,
    )
    by_kind_axis = {r["physical_opening_id"]: r for r in kind_axis["openings"]}

    lineage_rows = []
    for decision in opening_decisions:
        oid = str(decision["physical_opening_id"])
        c = canonical_by_id[oid]
        lineage_rows.append({
            "quantity_id": decision.get("prior_signed_quantity_id") or f"unsigned:{oid}",
            "physical_object_id": oid,
            "document_id": c.get("document_id"),
            "revision_id": c.get("revision_id"),
            "source_sha256": c.get("source_sha256"),
            "snapshot_id": c.get("snapshot_id"),
            "decision_scope_id": decision.get("source_decision_scope_id"),
        })
    lineage = enforce_source_lineage_required_fields_shadow(lineage_rows)

    attached: list[dict[str, Any]] = []
    gate_bags: dict[str, Counter] = {
        "door_height": Counter(),
        "whole_wall_frame": Counter(),
        "stacker_host": Counter(),
        "bifold_kind": Counter(),
        "glazed_frame": Counter(),
        "seal": Counter(),
        "trade": Counter(),
        "canonical_attach": Counter(),
    }

    for decision in opening_decisions:
        oid = str(decision["physical_opening_id"])
        canonical = canonical_by_id[oid]
        observed = observe_rows_by_id[oid]
        label = _label_fields(observed)
        values = label["dimension_values_mm"]
        width_only = float(values[0]) if len(values) == 1 else None
        members = tuple(decision.get("source_host_member_wall_ids") or ())

        door_h = assess_door_height_owner_gate_shadow(
            physical_opening_id=oid,
            owned_height_evidence_ids=(),
            owned_height_mm=None,
            user_approved_height=False,
            label_width_only_mm=width_only,
        )
        frame = assess_whole_wall_frame_readiness_shadow(
            physical_opening_id=oid,
            host_record_id=decision.get("authenticated_host_record_id"),
            frame_record_id=decision.get("authenticated_frame_record_id"),
            frame_reason_codes=tuple(decision.get("frame_reason_codes") or ()),
        )
        stacker = assess_stacker_host_frame_readiness_shadow(
            physical_opening_id=oid,
            unique_image_frame_present=False,
            structural_host_wall_id=members[0] if members else None,
            host_binding_evidence_ids=(
                (str(decision["authenticated_host_record_id"]),)
                if decision.get("authenticated_host_record_id") else ()
            ),
            host_frame_evidence_ids=(
                (str(decision["authenticated_frame_record_id"]),)
                if decision.get("authenticated_frame_record_id") else ()
            ),
        )
        bifold = assess_bifold_filling_kind_shadow(
            physical_opening_id=oid,
            plan_filling_role_evidence_ids=(),
            manufacturer_or_elevation_evidence_ids=(),
            gap_geometry_present=True,
        )
        figured_pair = values if len(values) == 2 else None
        glazed = assess_glazed_opening_frame_area_readiness_shadow(
            physical_opening_id=oid,
            host_record_id=decision.get("authenticated_host_record_id"),
            frame_record_id=decision.get("authenticated_frame_record_id"),
            opening_kind=canonical.get("opening_kind"),
            figured_pair_mm=figured_pair,
            axis_order_resolved=bool(decision.get("axis_order_authenticated")),
        )
        qid = str(decision.get("prior_signed_quantity_id") or f"unsigned:{oid}")
        seal = assess_source_closed_seal_readiness_shadow(
            quantity_id=qid,
            authority_status="firm" if decision.get("prior_signed_quantity_id") else None,
            source_lineage_complete=lineage["status"]
            == "SOURCE_LINEAGE_FIELDS_PRESENT_REVIEW_ONLY",
            dedupe_clear=True,
            prior_signed_ids_retained=True,
            owner_promotion_approved=False,
        )
        trade = assess_trade_quantity_evidence_readiness_shadow(
            trade="carpentry",
            evidence_ids=(qid,) if decision.get("prior_signed_quantity_id") else (),
            quantity_authority_status=(
                "firm" if decision.get("prior_signed_quantity_id") else None
            ),
        )
        root = {
            "document_id": str(canonical.get("document_id") or ""),
            "revision_id": str(canonical.get("revision_id") or ""),
            "source_sha256": str(canonical.get("source_sha256") or ""),
            "snapshot_id": str(canonical.get("snapshot_id") or ""),
        }
        canonical_attach = attach_quantity_to_canonical_entity_shadow(
            quantity_id=qid,
            canonical_entity_id=oid,
            quantity_source_root=root,
            entity_source_root=root,
            quantity_authority_status=(
                "firm" if decision.get("prior_signed_quantity_id") else None
            ),
        )

        for key, assessment in (
            ("door_height", door_h),
            ("whole_wall_frame", frame),
            ("stacker_host", stacker),
            ("bifold_kind", bifold),
            ("glazed_frame", glazed),
            ("seal", seal),
            ("trade", trade),
            ("canonical_attach", canonical_attach),
        ):
            gate_bags[key][assessment["first_remaining_gate"]] += 1

        attached.append({
            "physical_opening_id": oid,
            "handoff_first_remaining_gate": decision.get("first_remaining_gate"),
            "prior_signed_quantity_id": decision.get("prior_signed_quantity_id"),
            "kind_axis": {
                "kind_gate": by_kind_axis[oid]["kind_shadow"]["first_remaining_gate"],
                "axis_gate": by_kind_axis[oid]["axis_shadow"]["first_remaining_gate"],
                "figured_value_count": by_kind_axis[oid]["axis_shadow"]["figured_value_count"],
            },
            "door_height_gate": door_h["first_remaining_gate"],
            "whole_wall_frame_gate": frame["first_remaining_gate"],
            "stacker_host_gate": stacker["first_remaining_gate"],
            "bifold_kind_gate": bifold["first_remaining_gate"],
            "glazed_frame_gate": glazed["first_remaining_gate"],
            "seal_gate": seal["first_remaining_gate"],
            "trade_gate": trade["first_remaining_gate"],
            "canonical_attach_gate": canonical_attach["first_remaining_gate"],
            "invented_second_axis": False,
            "measurement_published": False,
        })

    frozen = assess_frozen_v2_eval_readiness_shadow(
        sealed_source_output_present=True,
        prior_signed_identities_retained=True,
        owner_authorised_new_rows=False,
        evaluator_truth_unchanged=True,
    )

    return {
        "status": "UNPUBLISHED_LOT16_MULTI_GATE_ORIGINAL_ATTACH",
        "opening_count": len(attached),
        "kind_axis_gate_counts": {
            "kind": kind_axis["kind_gate_counts"],
            "axis": kind_axis["axis_gate_counts"],
        },
        "gate_counts": {k: dict(sorted(v.items())) for k, v in gate_bags.items()},
        "source_lineage_status": lineage["status"],
        "source_lineage_blocker_count": len(lineage["blockers"]),
        "frozen_v2_eval_gate": frozen["first_remaining_gate"],
        "openings": attached,
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
