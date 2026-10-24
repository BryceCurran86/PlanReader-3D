from pb_door_height_owner_gate_shadow import assess_door_height_owner_gate_shadow
from pb_stacker_host_frame_readiness_shadow import assess_stacker_host_frame_readiness_shadow
from tools.diag_cursor_quantity_recovery_compose_shadow import (
    compose_quantity_recovery_shadow_row,
)


def test_image_frame_alone_never_grants_stacker_host():
    r = assess_stacker_host_frame_readiness_shadow(
        physical_opening_id="o-stacker",
        unique_image_frame_present=True,
    )
    assert r["first_remaining_gate"] == "stacker_structural_host_unproven"
    assert r["image_frame_used_as_structural_host"] is False
    assert r["host_granted"] is False


def test_competing_hosts_abstain():
    r = assess_stacker_host_frame_readiness_shadow(
        physical_opening_id="o-stacker",
        structural_host_wall_id="w-a",
        competing_host_wall_ids=("w-a", "w-b"),
        host_binding_evidence_ids=("b1",),
        host_frame_evidence_ids=("f1",),
    )
    assert r["first_remaining_gate"] == "stacker_host_ambiguous_competing_walls"


def test_full_stacker_evidence_still_review_only():
    r = assess_stacker_host_frame_readiness_shadow(
        physical_opening_id="o-stacker",
        unique_image_frame_present=True,
        structural_host_wall_id="w-a",
        host_binding_evidence_ids=("b1",),
        host_frame_evidence_ids=("f1",),
    )
    assert r["first_remaining_gate"] == "stacker_host_frame_review_only"
    assert r["measurement_published"] is False


def test_typical_2100_never_invented_as_door_height():
    r = assess_door_height_owner_gate_shadow(
        physical_opening_id="o-door",
        owned_height_mm=2100.0,
        label_width_only_mm=870.0,
    )
    assert r["first_remaining_gate"] == "door_height_unproven_no_owned_atom"
    assert r["invented_second_axis_mm"] is None
    assert r["owned_height_mm"] is None


def test_user_approved_height_stays_review_only():
    r = assess_door_height_owner_gate_shadow(
        physical_opening_id="o-door",
        owned_height_mm=2040.0,
        user_approved_height=True,
    )
    assert r["first_remaining_gate"] == "door_height_user_approved_review_only"
    assert r["measurement_published"] is False


def test_owned_figured_height_review_only():
    r = assess_door_height_owner_gate_shadow(
        physical_opening_id="o-door",
        owned_height_evidence_ids=("fig-h-1",),
        owned_height_mm=2110.0,
    )
    assert r["first_remaining_gate"] == "door_height_owned_figured_review_only"


def test_compose_diag_chains_gates_without_publishing():
    out = compose_quantity_recovery_shadow_row(
        {
            "physical_opening_id": "o-1",
            "unique_image_frame_present": True,
            "gap_geometry_present": True,
            "label_width_only_mm": 870.0,
        }
    )
    assert out["any_measurement_published"] is False
    assert out["benchmark_score_granted"] is False
    assert (
        out["first_remaining_gates"]["stacker_host_frame"]
        == "stacker_structural_host_unproven"
    )
    assert (
        out["first_remaining_gates"]["bifold_filling_kind"]
        == "bifold_plan_filling_role_unproven"
    )
    assert (
        out["first_remaining_gates"]["door_height_owner_gate"]
        == "door_height_second_axis_unavailable"
    )
