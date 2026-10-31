"""Review of b76f92325: a layer dropped for a wall-face stub stays visible as a rival, and naming cannot grant an ink role.

Written failing first (the proof dropped such a layer silently and a caller's naming granted glazing its role)."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    SEEDED_COMPETING_LAYER_UNRESOLVED,
    SEEDED_INK_ROLE_ASSERTED_ONLY_BY_CALLER,
    SEEDED_OPENING_INK_UNACCOUNTED,
    SEEDED_WALL_FACE_CONTINUES_INSIDE_GAP,
    VISIBLE_WALL_CONTINUATION_REQUIRED,
)
from test_physical_opening_seeded_existence_review_v1 import POSES
from test_physical_opening_seeded_existence_v1 import (
    GLAZING,
    LAYERED,
    PLAIN,
    SHARED_STUB,
    SILL_STUB,
    _fixture,
    _ids,
    _selector,
)

CORR = EvidenceResolutionStatus.CORROBORATED
CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
UNRESOLVED_ROLE = "unresolved_no_producer_authenticated_role"
OUTSIDE_THE_GAP = (((222.0, 100.0), (260.0, 100.0)),)         # collinear with a face but beyond the gap


@pytest.mark.parametrize("kw", POSES)
def test_a_layer_dropped_for_a_stub_stays_visible_and_blocks_a_unique_opening(kw):
    physical, published, ids, kw = _fixture(LAYERED + SILL_STUB, **kw)
    members = _ids(ids, LAYERED, kw)
    stub = _ids(ids, SILL_STUB, kw)
    kept = physical.prove_seeded_existence(_selector(published, members[8]), members)       # a jamb of the clean layer
    assert kept.status is ABST and kept.existence_record is None
    assert kept.reason_codes == (SEEDED_COMPETING_LAYER_UNRESOLVED,)
    assert kept.candidate is not None and set(kept.candidate.source_observation_ids).isdisjoint({members[6], members[7]})
    (atom,) = kept.opposing_evidence_atoms
    assert atom.status is CAND and atom.metadata["polarity"] == "opposing"
    assert set(atom.metadata["opposing_observation_ids"]) == set(stub)
    assert {members[6], members[7]} <= set(atom.metadata["source_observation_ids"])
    assert atom.metadata["role_status"] == UNRESOLVED_ROLE
    dropped = physical.prove_seeded_existence(_selector(published, members[6]), members)    # a jamb of the stubbed layer
    assert dropped.status is ABST and dropped.existence_record is None
    assert dropped.reason_codes == (VISIBLE_WALL_CONTINUATION_REQUIRED, SEEDED_COMPETING_LAYER_UNRESOLVED)
    assert dropped.opposing_evidence_atoms == kept.opposing_evidence_atoms


def test_the_rival_inventory_does_not_depend_on_the_order_or_repetition_of_the_named_members():
    physical, published, ids, kw = _fixture(LAYERED + SILL_STUB)
    members = _ids(ids, LAYERED, kw)
    selector = _selector(published, members[8])
    first = physical.prove_seeded_existence(selector, members)
    assert physical.prove_seeded_existence(selector, list(reversed(members))) == first
    assert physical.prove_seeded_existence(selector, tuple(members) + tuple(members)) == first
    assert physical.prove_seeded_existence(selector, members) == first          # replay


@pytest.mark.parametrize("accounted", [False, True])
def test_when_every_layer_is_stubbed_each_one_is_inventoried(accounted):
    physical, published, ids, kw = _fixture(LAYERED + SHARED_STUB)
    members = _ids(ids, LAYERED, kw)
    stub = _ids(ids, SHARED_STUB, kw)
    proof = physical.prove_seeded_existence(_selector(published, members[6]), members, stub if accounted else ())
    assert proof.status is ABST and proof.reason_codes == (SEEDED_WALL_FACE_CONTINUES_INSIDE_GAP,)
    assert len(proof.opposing_evidence_atoms) == 2
    assert all(set(a.metadata["opposing_observation_ids"]) == set(stub) for a in proof.opposing_evidence_atoms)
    assert len({a.evidence_id for a in proof.opposing_evidence_atoms}) == 2


def test_without_a_stub_there_is_no_rival_and_the_opening_stands():
    physical, published, ids, kw = _fixture(LAYERED)
    members = _ids(ids, LAYERED, kw)
    proof = physical.prove_seeded_existence(_selector(published, members[8]), members)
    assert proof.status is CORR and proof.opposing_evidence_atoms == ()


def test_a_face_line_beyond_the_gap_is_not_a_rival_layer():
    physical, published, ids, kw = _fixture(LAYERED + OUTSIDE_THE_GAP)
    members = _ids(ids, LAYERED, kw)
    proof = physical.prove_seeded_existence(_selector(published, members[8]), members)
    assert proof.status is CORR and proof.opposing_evidence_atoms == ()


def test_members_from_another_snapshot_cannot_stand_in_for_a_rival_inventory():
    physical, published, ids, kw = _fixture(LAYERED + SILL_STUB)
    _other_physical, _other_published, other_ids, other_kw = _fixture(LAYERED + SILL_STUB)
    members = _ids(ids, LAYERED, kw)
    foreign = _ids(other_ids, LAYERED, other_kw)
    proof = physical.prove_seeded_existence(_selector(published, members[8]), members[:5] + foreign[5:])
    assert proof.status is ABST and proof.existence_record is None and proof.opposing_evidence_atoms == ()


@pytest.mark.parametrize("kw", POSES)
def test_naming_ink_between_the_faces_cannot_grant_its_role(kw):
    physical, published, ids, kw = _fixture(LAYERED + GLAZING, **kw)
    members = _ids(ids, LAYERED, kw)
    glass = _ids(ids, GLAZING, kw)
    selector = _selector(published, members[6])
    none = physical.prove_seeded_existence(selector, members)
    partly = physical.prove_seeded_existence(selector, members, glass[:1])
    named = physical.prove_seeded_existence(selector, members, glass)
    assert none.reason_codes == partly.reason_codes == (SEEDED_OPENING_INK_UNACCOUNTED,)
    assert named.status is ABST and named.reason_codes == (SEEDED_INK_ROLE_ASSERTED_ONLY_BY_CALLER,)
    assert named.existence_record is None and named.candidate is not None


def test_a_plain_opening_with_glazing_is_not_granted_by_naming_either():
    physical, published, ids, kw = _fixture(PLAIN + GLAZING)
    members = _ids(ids, PLAIN, kw)
    glass = _ids(ids, GLAZING, kw)
    named = physical.prove_seeded_existence(_selector(published, members[4]), members, glass)
    assert named.status is ABST and named.reason_codes == (SEEDED_INK_ROLE_ASSERTED_ONLY_BY_CALLER,)
    clean = physical.prove_seeded_existence(_selector(published, members[4]), members)
    assert clean.status is ABST and clean.reason_codes == (SEEDED_OPENING_INK_UNACCOUNTED,)
