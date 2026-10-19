"""Batch-2 quantity recovery shadows (mission items 4,6,10,13,19–22)."""
import math

import pytest

from pb_canonical_quantity_attach_shadow import attach_quantity_to_canonical_entity_shadow
from pb_glazed_opening_frame_area_readiness_shadow import (
    assess_glazed_opening_frame_area_readiness_shadow,
)
from pb_opening_fragment_identity_shadow import assess_opening_fragment_identity_shadow
from pb_opening_label_leader_witness_shadow import bind_opening_label_leader_witness_shadow
from pb_pitched_ceiling_readiness_shadow import assess_pitched_ceiling_readiness_shadow
from pb_room_finish_quantity_readiness_shadow import assess_room_finish_quantity_readiness_shadow
from pb_signed_opening_dedupe_shadow import assess_signed_opening_dedupe_shadow
from pb_source_lineage_required_fields_shadow import enforce_source_lineage_required_fields_shadow

ROOT = {
    "document_id": "doc",
    "revision_id": "rev",
    "source_sha256": "a" * 64,
    "snapshot_id": "snap",
}


def test_proximity_only_label_binding_forbidden():
    r = bind_opening_label_leader_witness_shadow(
        physical_opening_id="o1",
        printed_mark="D01",
        schedule_row_id=None,
        leader_evidence_id=None,
        proximity_only=True,
    )
    assert r["first_remaining_gate"] == "proximity_only_label_binding_forbidden"


def test_mark_without_schedule_or_leader_abstains():
    r = bind_opening_label_leader_witness_shadow(
        physical_opening_id="o1",
        printed_mark="D01",
        schedule_row_id=None,
        leader_evidence_id=None,
    )
    assert r["first_remaining_gate"] == "printed_mark_without_owned_schedule_or_leader"


def test_owned_schedule_mark_is_review_only():
    r = bind_opening_label_leader_witness_shadow(
        physical_opening_id="o1",
        printed_mark="D01",
        schedule_row_id="sched-1",
        leader_evidence_id=None,
        dimension_witness_ids=("wit-1",),
    )
    assert r["first_remaining_gate"] == "opening_label_leader_witness_review_only"
    assert r["measurement_published"] is False


def test_signed_dedupe_blocks_quantity_id_reuse():
    r = assess_signed_opening_dedupe_shadow(
        candidate_physical_opening_id="new-opening",
        candidate_quantity_id="signed-eight-1",
        sealed_physical_opening_ids=("old-1",),
        sealed_quantity_ids=("signed-eight-1",),
    )
    assert "candidate_reuses_sealed_quantity_id" in r["blockers"]
    assert r["rekey_allowed"] is False


def test_signed_dedupe_blocks_alias_of_sealed_physical():
    r = assess_signed_opening_dedupe_shadow(
        candidate_physical_opening_id="new-opening",
        candidate_quantity_id=None,
        sealed_physical_opening_ids=("sealed-phys",),
        sealed_quantity_ids=(),
        alias_claims=(
            {"physical_opening_id": "new-opening", "alias_of_physical_opening_id": "sealed-phys"},
        ),
    )
    assert "candidate_aliases_sealed_physical_opening" in r["blockers"]


def test_fragment_identity_retains_shared_members_without_merge():
    r = assess_opening_fragment_identity_shadow(
        openings=(
            {"physical_opening_id": "o1", "host_member_wall_candidate_ids": ("w1", "w2")},
            {"physical_opening_id": "o2", "host_member_wall_candidate_ids": ("w2", "w3")},
        )
    )
    assert r["shared_fragment_owners"]["w2"] == ["o1", "o2"]
    assert r["merged_physical_opening_ids"] == []
    assert r["openings"][0]["identity_preserved"] is True


def test_glazed_area_requires_window_kind_and_axes():
    r = assess_glazed_opening_frame_area_readiness_shadow(
        physical_opening_id="o1",
        host_record_id="h",
        frame_record_id="f",
        opening_kind="door",
        figured_pair_mm=(1200.0, 1800.0),
        axis_order_resolved=True,
    )
    assert r["first_remaining_gate"] == "opening_filling_kind_unproven"
    assert r["aperture_geometry_used_as_area"] is False


def test_glazed_ready_still_unpublished():
    r = assess_glazed_opening_frame_area_readiness_shadow(
        physical_opening_id="o1",
        host_record_id="h",
        frame_record_id="f",
        opening_kind="window",
        figured_pair_mm=(1200.0, 1500.0),
        axis_order_resolved=True,
    )
    assert r["first_remaining_gate"] == "glazed_frame_area_review_only"
    assert r["measurement_published"] is False


def test_pitched_ceiling_without_pitch_abstains():
    r = assess_pitched_ceiling_readiness_shadow(
        room_or_plane_id="room-1",
        plan_area_m2=12.0,
        plan_area_authority="firm",
        pitch_ratio_or_degrees=None,
        pitch_authority=None,
    )
    assert r["first_remaining_gate"] == "ceiling_pitch_authority_unproven"
    assert r["plan_area_used_as_pitched_surface"] is False


def test_pitched_ceiling_review_only_factor():
    r = assess_pitched_ceiling_readiness_shadow(
        room_or_plane_id="room-1",
        plan_area_m2=10.0,
        plan_area_authority="firm",
        pitch_ratio_or_degrees=12.0,
        pitch_authority="corroborated",
    )
    assert r["first_remaining_gate"] == "pitched_ceiling_surface_review_only"
    assert r["surface_area_m2_review_only"] == pytest.approx(10.0 / math.cos(math.radians(12.0)))
    assert r["customer_seal_granted"] is False


def test_canonical_attach_requires_same_source_root_and_authority():
    bad = attach_quantity_to_canonical_entity_shadow(
        quantity_id="q1",
        canonical_entity_id="e1",
        quantity_source_root=ROOT,
        entity_source_root={**ROOT, "snapshot_id": "other"},
        quantity_authority_status="firm",
    )
    assert bad["first_remaining_gate"] == "canonical_attach_source_root_mismatch"
    good = attach_quantity_to_canonical_entity_shadow(
        quantity_id="q1",
        canonical_entity_id="e1",
        quantity_source_root=ROOT,
        entity_source_root=ROOT,
        quantity_authority_status="firm",
    )
    assert good["attach_review_only"] is True
    assert good["measurement_published"] is False


def test_source_lineage_missing_fields_block_publication():
    report = enforce_source_lineage_required_fields_shadow([
        {**ROOT, "decision_scope_id": "wall-source:page-3", "quantity_id": "q1"},
        {"document_id": "doc", "quantity_id": "q2"},
    ])
    assert report["status"] == "SOURCE_LINEAGE_INCOMPLETE"
    assert report["publication_allowed"] is False
    assert "source_sha256" in report["blockers"][0]["missing_fields"]


def test_room_finish_plain_floor_not_enough():
    r = assess_room_finish_quantity_readiness_shadow(
        room_id="room-1",
        room_face_record_id="face-1",
        finish_definition_id=None,
        finish_occurrence_id=None,
        area_m2=20.0,
        area_authority="firm",
    )
    assert r["first_remaining_gate"] == "finish_definition_unavailable"
    assert r["plain_floor_treated_as_finish"] is False
