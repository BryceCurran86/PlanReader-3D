"""Source-candidate membership only: no snapshot rekey masquerading as geometry."""
from dataclasses import asdict, replace

import pytest

from pb_opening_host_binding_authority import OpeningHostBindingRecord
from pb_opening_host_source_candidate_witness import (
    source_candidate_membership_witness_id as witness,
)


def host_record():
    return OpeningHostBindingRecord(
        record_id="opening_host_binding_v3_a",
        document_id="same-document",
        revision_id="source-revision-a",
        source_sha256="a"*64,
        snapshot_id="source-snapshot-a",
        page_id="3",
        decision_scope_id="wall-source:page-3",
        opening_identity_id="physical_opening_existence_38c03575",
        host_wall_id="opening_host_binding_group_old",
        member_wall_candidate_ids=("wall_old",),
        member_candidate_identity_ids=("wall2_same_source_path",),
        member_equivalence_groups=(("wall_old",),),
        source_observation_ids=("source_obs_old",),
    )


def test_snapshot_churn_retains_only_candidate_membership_witness():
    old=host_record()
    new=replace(
        old,
        snapshot_id="source-snapshot-with-new-visible-raster-source",
        record_id="opening_host_binding_v3_new",
        host_wall_id="opening_host_binding_group_new",
        source_observation_ids=("source_obs_same", "source_obs_new"),
    )
    assert old != new
    assert old.record_id != new.record_id
    assert old.host_wall_id != new.host_wall_id
    assert old.source_candidate_membership_witness_id
    assert old.source_candidate_membership_witness_id == new.source_candidate_membership_witness_id
    assert "source_candidate_membership_witness_id" not in asdict(old)


@pytest.mark.parametrize("change", [
    {"source_sha256": "b"*64},
    {"document_id": "different-owner"},
    {"page_id": "4"},
    {"opening_identity_id": "physical_opening_existence_other"},
    {"member_candidate_identity_ids": ("wall2_other_credible_source",)},
    {"member_candidate_identity_ids": ("wall2_same_source_path", "wall2_another_wall")},
])
def test_distinct_source_or_candidate_membership_cannot_reuse_witness(change):
    original=host_record()
    changed=replace(original, **change)
    assert changed.source_candidate_membership_witness_id
    assert changed.source_candidate_membership_witness_id != original.source_candidate_membership_witness_id


def test_member_order_does_not_affect_same_source_witness():
    original=replace(host_record(),member_candidate_identity_ids=("wall2_a","wall2_b"))
    swapped=replace(original,member_candidate_identity_ids=("wall2_b","wall2_a"))
    assert original.source_candidate_membership_witness_id == swapped.source_candidate_membership_witness_id


@pytest.mark.parametrize("damage", [
    {"source_sha256": "truncated"},
    {"source_sha256": "F"*64},
    {"opening_identity_id": "label_DOOR_1"},
    {"page_id": ""},
    {"page_id": "page_three"},
    {"member_candidate_identity_ids": ()},
    {"member_candidate_identity_ids": ("wall2_same_source_path","wall2_same_source_path")},
    {"member_candidate_identity_ids": ("wall_old_assembly_only",)},
    {"member_candidate_identity_ids": (None,)},
])
def test_unverifiable_or_duplicate_candidate_identity_produces_no_witness(damage):
    r=replace(host_record(),**damage)
    assert r.source_candidate_membership_witness_id is None


def test_properties_do_not_mutate_or_certify_snapshot_scoped_host_evidence():
    record=host_record()
    source=asdict(record)
    key=record.source_candidate_membership_witness_id
    assert key.startswith("opening_source_candidate_membership_witness_v1_")
    assert asdict(record)==source
    assert record.record_id=="opening_host_binding_v3_a"
    assert record.host_wall_id=="opening_host_binding_group_old"
    assert record.member_equivalence_groups==(("wall_old",),)


def test_raw_helper_never_uses_snapshot_ids_or_host_wall_addresses():
    v=witness(
        document_id="same-document",
        source_sha256="a"*64,
        page_id="3",
        opening_identity_id="physical_opening_existence_38c03575",
        member_candidate_identity_ids=("wall2_same_source_path",),
    )
    assert v==host_record().source_candidate_membership_witness_id
    assert witness(
        document_id="same-document",
        source_sha256="a"*64,
        page_id="3",
        opening_identity_id="physical_opening_existence_38c03575",
        member_candidate_identity_ids=(),
    ) is None
