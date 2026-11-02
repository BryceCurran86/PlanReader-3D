"""S2a (owner directive 2026-11-02): source-owned classification of the ink on and across a wall face.

For every structure the six-line rule finds among the named members, survivors AND set-aside ones, the authority lists
each non-member visible line that is collinear with one of that structure's faces and overlaps its gap, and classifies
it by where it starts and ends relative to the two jamb stations: opening-local, or running on as shared wall face.
Nothing is dropped, nothing is decided, no role is asserted."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import SeededFaceInkInventory, _seeded_ink_checks, _structure_frame
from test_physical_opening_seeded_existence_review_v1 import FLUSH_OUTER_ONE, HALF_MIDDLE, POSES, SPLIT_MIDDLE  # noqa: F401
from test_physical_opening_seeded_existence_v1 import (
    FLUSH_MIDDLE, FLUSH_OUTER, GLAZING, LAYERED, PLAIN, SILL_STUB, _fixture, _ids, _selector)

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED

# a face line that runs on past both jambs of a gap (a shared wall face), and one that runs past a single jamb
THROUGH = (((60.0, 100.0), (180.0, 100.0)),)
HALF_FACE = (((100.0, 100.0), (122.0, 100.0)),)
PAST_ONE_JAMB = (((60.0, 100.0), (120.0, 100.0)),)
INSIDE = (((110.0, 100.0), (130.0, 100.0)),)
OUTSIDE_THE_GAP = (((222.0, 100.0), (260.0, 100.0)),)


def _inventory(segments, member_segments, selector_index, **kw):
    physical, published, ids, kw = _fixture(segments, **kw)
    members = _ids(ids, member_segments, kw)
    inventory = physical.seeded_face_ink_inventory(_selector(published, members[selector_index]), members)
    return physical, published, ids, kw, members, inventory


def _ink(inventory, ids_for):
    """{observation id: (extent class, locality)} over every structure (ids are unique per structure here)."""
    out = {}
    for structure in inventory.structures:
        for ink in structure.face_ink:
            if ink.observation_id in ids_for:
                out[ink.observation_id] = (ink.extent_class, ink.locality)
    return out


@pytest.mark.parametrize("kw", POSES)
@pytest.mark.parametrize("name,extra,expected", [
    ("spans_the_gap", FLUSH_OUTER_ONE, ("at_at", "opening_local")),
    ("half_the_gap", HALF_FACE, ("at_within", "opening_local")),
    ("inside_the_gap", INSIDE, ("within_within", "opening_local")),
    ("past_one_jamb", PAST_ONE_JAMB, ("beyond_within", "extends_past_one_jamb")),
    ("through_both", THROUGH, ("beyond_beyond", "extends_past_both_jambs")),
])
def test_face_ink_is_classified_by_where_it_starts_and_ends_relative_to_the_gap_in_every_pose(kw, name, extra, expected):
    physical, published, ids, kw, members, inventory = _inventory(PLAIN + extra, PLAIN, 4, **kw)
    ink = _ids(ids, extra, kw)
    assert inventory.status is CAND and not inventory.asserts_role
    found = _ink(inventory, set(ink))
    assert found == {ink[0]: expected}, name


def test_split_segments_are_listed_separately_so_a_consumer_can_see_what_covers_the_gap():
    physical, published, ids, kw, members, inventory = _inventory(LAYERED + SPLIT_MIDDLE, LAYERED, 6)
    ink = _ids(ids, SPLIT_MIDDLE, kw)
    classes = {}
    for structure in inventory.structures:
        for item in structure.face_ink:
            if item.observation_id in ink:
                classes.setdefault(item.observation_id, set()).add(item.extent_class)
    assert classes == {ink[0]: {"at_within"}, ink[1]: {"at_within"}}      # one anchored at each jamb, neither spanning


def test_every_competing_structure_is_retained_with_its_own_stubs_and_the_shared_support_is_named():
    physical, published, ids, kw, members, inventory = _inventory(LAYERED + SILL_STUB, LAYERED, 8)
    stub = _ids(ids, SILL_STUB, kw)[0]
    assert len(inventory.structures) == 2
    by_status = {s.status: s for s in inventory.structures}
    assert set(by_status) == {"set_aside", "survivor"}
    assert [i.observation_id for i in by_status["set_aside"].face_ink] == [stub]
    assert by_status["set_aside"].face_ink[0].extent_class == "within_within"
    assert by_status["survivor"].face_ink == ()
    shared = set(by_status["set_aside"].shared_member_ids)
    assert shared == set(by_status["survivor"].shared_member_ids) and len(shared) == 2        # the two pieces of the shared face
    assert {members[6], members[7]} <= set(by_status["set_aside"].member_ids)


def test_interior_ink_that_is_not_on_a_face_is_listed_apart_from_face_ink():
    physical, published, ids, kw, members, inventory = _inventory(PLAIN + GLAZING + FLUSH_OUTER_ONE, PLAIN, 4)
    glass = set(_ids(ids, GLAZING, kw))
    (structure,) = inventory.structures
    assert set(structure.interior_ink_ids) == glass
    assert {i.observation_id for i in structure.face_ink}.isdisjoint(glass) and len(structure.face_ink) == 1


def test_ink_beyond_the_gap_or_off_the_faces_is_not_inventoried_and_the_answer_ignores_unrelated_content():
    far = (((300.0, 150.0), (360.0, 150.0)),)
    _p, _pub, _ids_, _kw, _m, plain = _inventory(PLAIN, PLAIN, 4)
    physical, published, ids, kw, members, inventory = _inventory(PLAIN + OUTSIDE_THE_GAP + far, PLAIN, 4)
    (structure,) = inventory.structures
    assert structure.face_ink == () and structure.interior_ink_ids == ()
    assert (structure.gap_start, structure.gap_end, structure.face_offsets) == (
        plain.structures[0].gap_start, plain.structures[0].gap_end, plain.structures[0].face_offsets)


@pytest.mark.parametrize("extra", [FLUSH_OUTER, FLUSH_MIDDLE, SPLIT_MIDDLE, SILL_STUB, THROUGH, GLAZING])
def test_the_inventory_agrees_with_the_veto_inputs_it_refines(extra):
    physical, published, ids, kw, members, inventory = _inventory(LAYERED + extra, LAYERED, 6)
    failure, _source, records, by_id, _restricted = physical._seeded_universe(_selector(published, members[6]), members)
    assert failure is None
    for structure in inventory.structures:
        frame = _structure_frame(structure.member_ids, by_id)
        stubs, interior, continuing = _seeded_ink_checks(frame, frozenset(structure.member_ids), frozenset(), records)
        listed = {i.observation_id: i.extent_class for i in structure.face_ink}
        assert {k for k, v in listed.items() if v == "within_within"} == set(stubs)
        assert {k for k, v in listed.items() if v != "within_within"} == set(continuing)
        assert set(structure.interior_ink_ids) == set(interior)


def test_order_repetition_replay_and_no_mutation():
    physical, published, ids, kw = _fixture(LAYERED + SILL_STUB + THROUGH + GLAZING)
    members = _ids(ids, LAYERED, kw)
    selector = _selector(published, members[8])
    names = [n for n in ("_visible_candidate_cache", "_visible_candidate_membership_cache", "_visible_existence_cache",
                         "_visible_viewport_scope_cache", "_visible_viewport_candidate_membership_cache")
             if hasattr(physical, n)]
    before = {n: dict(getattr(physical, n)) for n in names}
    first = physical.seeded_face_ink_inventory(selector, members)
    assert physical.seeded_face_ink_inventory(selector, list(reversed(members))) == first
    assert physical.seeded_face_ink_inventory(selector, tuple(members) + tuple(members)) == first
    assert physical.seeded_face_ink_inventory(selector, members) == first
    assert {n: dict(getattr(physical, n)) for n in names} == before
    assert [s.candidate_id for s in first.structures] == sorted(s.candidate_id for s in first.structures)


def test_foreign_unknown_or_selector_less_members_abstain_and_nothing_grants_authority():
    physical, published, ids, kw = _fixture(PLAIN)
    _o, other_published, other_ids, other_kw = _fixture(PLAIN)
    members, foreign = _ids(ids, PLAIN, kw), _ids(other_ids, PLAIN, other_kw)
    selector = _selector(published, members[4])
    for bad in ([], ["no-such-observation"], members[:3] + foreign[3:], [m for m in members if m != members[4]]):
        inventory = physical.seeded_face_ink_inventory(selector, bad)
        assert inventory.status is ABST and inventory.structures == ()
    good = physical.seeded_face_ink_inventory(selector, members)
    assert not (good.asserts_role or good.grants_quantity or good.grants_firm_authority)
    with pytest.raises(TypeError):
        physical.seeded_face_ink_inventory("not-a-selector", members)
    with pytest.raises(TypeError):
        physical.seeded_face_ink_inventory(selector, members[0])
