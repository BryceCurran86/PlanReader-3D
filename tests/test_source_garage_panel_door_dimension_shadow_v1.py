"""Unit tests for Item 20: garage/panel door host & dimension shadow."""

from __future__ import annotations

from pathlib import Path

from pb_source_garage_panel_door_dimension_shadow import (
    GarageDoorDimensionWitness,
    GarageDoorHostWitness,
    SourceLineageRef,
    classify_garage_door_kind,
    evaluate_garage_panel_door_dimension_shadow,
    parse_garage_door_callout_dimensions,
)
from tools.audit_no_job_specific_shared_rules import audit_shared_source


def _lineage(page: str = "page_01", vp: str = "vp_plan", rev: str = "rev_a") -> SourceLineageRef:
    return SourceLineageRef(
        document_id="doc_arch_01",
        revision_id=rev,
        source_sha256="a" * 64,
        page_id=page,
        viewport_id=vp,
    )


def _host(
    *,
    opening_id: str = "open_garage_01",
    label: str = "AUTO PANEL LIFT GARAGE DOOR",
    span_pts: float = 136.06,  # ~4800 mm at 1:100 (35.2778 mm/pt)
    mm_per_pt: float | None = 35.2778,
    start_wall: str = "wall_ext_north_a",
    end_wall: str = "wall_ext_north_b",
    jambs: tuple[str, ...] = ("cap_left", "cap_right"),
    coplanar: bool = True,
) -> GarageDoorHostWitness:
    return GarageDoorHostWitness(
        opening_id=opening_id,
        lineage=_lineage(),
        start_host_wall_id=start_wall,
        end_host_wall_id=end_wall,
        jamb_cap_ids=jambs,
        aperture_span_pts=span_pts,
        native_label_text=label,
        calibrated_mm_per_pt=mm_per_pt,
        coplanar_host_walls_verified=coplanar,
    )


def test_authenticated_panel_lift_door_with_plan_callout_and_elevation_corroboration() -> None:
    host = _host()
    w_plan = GarageDoorDimensionWitness(
        witness_id="w_callout_01",
        source_kind="plan_callout",
        lineage=_lineage(),
        linked_opening_id="open_garage_01",
        raw_callout_text="PANEL LIFT DOOR 4800W x 2100H",
        dimension_basis="clear_opening",
    )
    w_elev = GarageDoorDimensionWitness(
        witness_id="w_elev_01",
        source_kind="elevation_dimension",
        lineage=_lineage(page="page_05", vp="vp_elev_north"),
        linked_opening_id="open_garage_01",
        width_mm=4800.0,
        height_mm=2100.0,
        dimension_basis="clear_opening",
        allows_cross_page_same_revision=True,
    )
    res = evaluate_garage_panel_door_dimension_shadow(host, (w_plan, w_elev))
    assert res.abstained is False
    assert res.host_authenticated is True
    assert res.dimension_authenticated is True
    assert res.garage_door_kind == "panel_lift_door"
    assert res.width_mm == 4800.0
    assert res.height_mm == 2100.0
    assert res.dimension_basis == "clear_opening"
    assert res.standard_door_2040_fallback_blocked is True
    assert res.commercial_authority_granted is False
    assert res.measurement_authorized is False
    assert res.shadow_only is True
    assert res.blocking_reasons == ()
    assert res.supporting_witness_ids == ("w_callout_01", "w_elev_01")


def test_missing_height_strictly_forbids_2040_mm_pedestrian_door_fallback() -> None:
    host = _host(label="SECTIONAL OVERHEAD DOOR")
    w_width_only = GarageDoorDimensionWitness(
        witness_id="w_width_only",
        source_kind="plan_callout",
        lineage=_lineage(),
        linked_opening_id="open_garage_01",
        raw_callout_text="4800W SECTIONAL DOOR",
        dimension_basis="structural_opening",
    )
    res = evaluate_garage_panel_door_dimension_shadow(host, (w_width_only,))
    assert res.abstained is True
    assert res.dimension_authenticated is False
    assert res.height_mm is None
    assert res.standard_door_2040_fallback_blocked is True
    assert "garage_door_height_missing_2040_fallback_forbidden" in res.blocking_reasons


def test_assumed_2040_default_height_witness_is_explicitly_rejected() -> None:
    host = _host(label="ROLLER DOOR")
    w_width = GarageDoorDimensionWitness(
        witness_id="w_width_01",
        source_kind="plan_callout",
        lineage=_lineage(),
        linked_opening_id="open_garage_01",
        width_mm=4800.0,
        dimension_basis="clear_opening",
    )
    w_assumed_2040 = GarageDoorDimensionWitness(
        witness_id="w_default_2040",
        source_kind="assumed_standard_external_door_height",
        lineage=_lineage(),
        linked_opening_id="open_garage_01",
        height_mm=2040.0,
        is_default_assumption=True,
    )
    res = evaluate_garage_panel_door_dimension_shadow(host, (w_width, w_assumed_2040))
    assert res.abstained is True
    assert res.height_mm is None
    assert "w_default_2040" in res.rejected_witness_ids
    assert "assumed_2040_door_height_rejected_for_garage_door" in res.blocking_reasons
    assert "garage_door_height_missing_2040_fallback_forbidden" in res.blocking_reasons


def test_unhosted_roller_shutter_and_geometry_mismatch_fail_closed() -> None:
    unhosted = _host(label="ROLLER SHUTTER", start_wall="", jambs=("cap_only_one",))
    w_sched = GarageDoorDimensionWitness(
        witness_id="w_sched_01",
        source_kind="schedule_row",
        lineage=_lineage(),
        linked_opening_id="open_garage_01",
        width_mm=4800.0,
        height_mm=2400.0,
        dimension_basis="clear_opening",
    )
    res_unhosted = evaluate_garage_panel_door_dimension_shadow(unhosted, (w_sched,))
    assert res_unhosted.abstained is True
    assert res_unhosted.host_authenticated is False
    assert "unhosted_garage_opening_rejected" in res_unhosted.blocking_reasons
    assert "missing_dual_jamb_cap_witness" in res_unhosted.blocking_reasons

    # Calibrated span is ~4800 mm, but schedule says 2400 mm wide -> reject mismatch
    w_wrong_width = GarageDoorDimensionWitness(
        witness_id="w_sched_wrong_w",
        source_kind="schedule_row",
        lineage=_lineage(),
        linked_opening_id="open_garage_01",
        width_mm=2400.0,
        height_mm=2400.0,
        dimension_basis="clear_opening",
    )
    res_mismatch = evaluate_garage_panel_door_dimension_shadow(_host(), (w_wrong_width,))
    assert res_mismatch.abstained is True
    assert "garage_aperture_width_geometry_mismatch" in res_mismatch.blocking_reasons


def test_cross_viewport_cross_revision_conflicts_and_bare_pair_ambiguity() -> None:
    host = _host()
    w_cross_vp = GarageDoorDimensionWitness(
        witness_id="w_other_vp",
        source_kind="plan_callout",
        lineage=_lineage(vp="vp_detail_inset"),
        linked_opening_id="open_garage_01",
        width_mm=4800.0,
        height_mm=2100.0,
        dimension_basis="clear_opening",
    )
    w_cross_rev = GarageDoorDimensionWitness(
        witness_id="w_other_rev",
        source_kind="schedule_row",
        lineage=_lineage(rev="rev_b"),
        linked_opening_id="open_garage_01",
        width_mm=4800.0,
        height_mm=2100.0,
        dimension_basis="clear_opening",
    )
    res_transfer = evaluate_garage_panel_door_dimension_shadow(host, (w_cross_vp, w_cross_rev))
    assert res_transfer.abstained is True
    assert "cross_viewport_transfer_rejected" in res_transfer.blocking_reasons
    assert "cross_revision_or_document_transfer_rejected" in res_transfer.blocking_reasons

    # Conflicting heights (2100 vs 2400) must fail closed
    w1 = GarageDoorDimensionWitness(
        witness_id="w1",
        source_kind="plan_callout",
        lineage=_lineage(),
        linked_opening_id="open_garage_01",
        width_mm=4800.0,
        height_mm=2100.0,
        dimension_basis="clear_opening",
    )
    w2 = GarageDoorDimensionWitness(
        witness_id="w2",
        source_kind="elevation_dimension",
        lineage=_lineage(page="page_05", vp="vp_elev"),
        linked_opening_id="open_garage_01",
        width_mm=4800.0,
        height_mm=2400.0,
        dimension_basis="clear_opening",
        allows_cross_page_same_revision=True,
    )
    res_conflict = evaluate_garage_panel_door_dimension_shadow(host, (w1, w2))
    assert res_conflict.abstained is True
    assert "conflicting_garage_door_height_witnesses" in res_conflict.blocking_reasons

    # Bare unlabeled pair without explicit header order fails closed
    assert parse_garage_door_callout_dimensions("4800 x 2100") == (
        None,
        None,
        "ambiguous_unlabeled_dimension_pair",
    )
    assert parse_garage_door_callout_dimensions("2100H x 4800W") == (4800.0, 2100.0, None)
    assert parse_garage_door_callout_dimensions("4800 x 2100", bare_pair_order="w_x_h") == (
        4800.0,
        2100.0,
        None,
    )

    # Pedestrian door must never be classified as garage door
    assert classify_garage_door_kind("EXTERNAL ENTRY HINGED DOOR") is None
    res_ped = evaluate_garage_panel_door_dimension_shadow(
        _host(label="EXTERNAL ENTRY HINGED DOOR"), (w1,)
    )
    assert res_ped.abstained is True
    assert "not_a_garage_or_panel_door" in res_ped.blocking_reasons


def test_shared_source_audit_is_clean() -> None:
    module_path = Path(__file__).resolve().parent.parent / "pb_source_garage_panel_door_dimension_shadow.py"
    assert audit_shared_source(module_path.read_text(encoding="utf-8"), filename=module_path.name) == ()
