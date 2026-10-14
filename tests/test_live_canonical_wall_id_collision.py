"""Colliding *candidate* canonical wall ids are retained locally, not page-fatal.

Observed on an original plan set: two boundary-clean wall candidates built from the
same source primitives (and classified as one physical wall) share a
``candidate_identity_id``. The boundary-clean branch keys candidates by that id, so the
old global collision guard returned CONFLICT with no walls at all, discarding every
unrelated wall on the page.  These tests pin the shadow-mode fix: only groups made
exclusively of unresolved candidates are localized, nothing is merged, dropped or
promoted, and any collision involving a physically resolved wall still fails closed.
"""
from __future__ import annotations

import copy
from dataclasses import replace

import pytest

import pb_live_canonical_wall_composition as composition
from pb_live_canonical_wall_composition import (
    LIVE_CANONICAL_WALL_BOUNDARY_CLEAN_PARTIAL,
    LIVE_CANONICAL_WALL_FRAME_CONFLICT,
    LIVE_CANONICAL_WALL_ID_COLLISION_CANDIDATE,
    LIVE_CANONICAL_WALL_PARTIAL,
    _localize_candidate_id_collisions,
    compose_live_canonical_walls,
)
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_live_canonical_wall_composition import _boundary_incomplete_source

COLLISION_STATUS = "candidate_canonical_id_collision_unresolved"


@pytest.fixture(scope="module")
def clean_walls():
    source, wall_opening, _scope = _boundary_incomplete_source()
    result = compose_live_canonical_walls(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert len(result.walls) >= 4
    return result.walls, dict(result.candidate_to_canonical_wall_id)


def _collide(walls, indexes, shared="wall2_shared_duplicate_id"):
    out = list(walls)
    for index in indexes:
        out[index] = replace(out[index], canonical_wall_id=shared)
    return out


def _mapping_for(walls):
    return {
        member: wall.canonical_wall_id
        for wall in walls
        for member in wall.member_wall_candidate_ids
    }


def test_colliding_candidates_are_rekeyed_not_dropped(clean_walls) -> None:
    walls, _ = clean_walls
    forged = _collide(walls, (0, 1))
    rekeyed, remap, localized = _localize_candidate_id_collisions(
        forged, _mapping_for(forged)
    )

    assert localized is True
    assert len(rekeyed) == len(walls)
    ids = [wall.canonical_wall_id for wall in rekeyed]
    assert len(set(ids)) == len(ids)
    assert "wall2_shared_duplicate_id" not in ids
    for index in (0, 1):
        wall = rekeyed[index]
        assert wall.identity_status == COLLISION_STATUS
        assert wall.physical_identity_resolved is False
        assert wall.physical_wall_id is None
        assert wall.member_wall_candidate_ids == walls[index].member_wall_candidate_ids
        assert wall.plan_members == walls[index].plan_members
        for member in wall.member_wall_candidate_ids:
            assert remap[member] == wall.canonical_wall_id
    # Unrelated walls are untouched, object for object.
    for index in range(2, len(walls)):
        assert rekeyed[index] is forged[index]


def test_no_member_keeps_the_shared_id_and_ties_are_not_broken(clean_walls) -> None:
    walls, _ = clean_walls
    forged = _collide(walls, (0, 1, 2))
    rekeyed, _, localized = _localize_candidate_id_collisions(
        forged, _mapping_for(forged)
    )
    assert localized is True
    new_ids = {rekeyed[i].canonical_wall_id for i in (0, 1, 2)}
    assert len(new_ids) == 3
    assert "wall2_shared_duplicate_id" not in new_ids


def test_rekey_is_input_order_invariant_and_deterministic(clean_walls) -> None:
    walls, _ = clean_walls
    forged = _collide(walls, (0, 1))
    forward, forward_map, _ = _localize_candidate_id_collisions(
        forged, _mapping_for(forged)
    )
    reordered = list(reversed(forged))
    backward, backward_map, _ = _localize_candidate_id_collisions(
        reordered, _mapping_for(reordered)
    )
    assert forward_map == backward_map
    assert {w.canonical_wall_id for w in forward} == {
        w.canonical_wall_id for w in backward
    }
    again, again_map, _ = _localize_candidate_id_collisions(
        forged, _mapping_for(forged)
    )
    assert again_map == forward_map
    assert [w.canonical_wall_id for w in again] == [
        w.canonical_wall_id for w in forward
    ]


def test_rekey_ignores_unrelated_content(clean_walls) -> None:
    walls, _ = clean_walls
    forged = _collide(walls, (0, 1))
    _, base_map, _ = _localize_candidate_id_collisions(
        forged, _mapping_for(forged)
    )
    # Dropping an unrelated wall must not move the colliding group's new ids.
    smaller = [forged[0], forged[1], *forged[3:]]
    _, other_map, _ = _localize_candidate_id_collisions(
        smaller, _mapping_for(smaller)
    )
    for member in forged[0].member_wall_candidate_ids + forged[1].member_wall_candidate_ids:
        assert base_map[member] == other_map[member]


def test_inputs_are_not_mutated(clean_walls) -> None:
    walls, _ = clean_walls
    forged = _collide(walls, (0, 1))
    mapping = _mapping_for(forged)
    forged_before = list(forged)
    mapping_before = copy.deepcopy(mapping)
    _localize_candidate_id_collisions(forged, mapping)
    assert forged == forged_before
    assert mapping == mapping_before


def test_distinct_ids_are_a_no_op(clean_walls) -> None:
    walls, _ = clean_walls
    plain = list(walls)
    out, remap, localized = _localize_candidate_id_collisions(
        plain, _mapping_for(plain)
    )
    assert localized is False
    assert out is plain or out == plain
    assert remap == _mapping_for(plain)


def test_collision_with_a_physically_resolved_wall_is_not_localized(clean_walls) -> None:
    walls, _ = clean_walls
    forged = _collide(walls, (0, 1))
    forged[0] = replace(
        forged[0],
        physical_identity_resolved=True,
        physical_wall_id=forged[0].canonical_wall_id,
        identity_status="physical_resolved_by_equivalence",
    )
    out, remap, localized = _localize_candidate_id_collisions(
        forged, _mapping_for(forged)
    )
    assert localized is False
    assert [w.canonical_wall_id for w in out] == [w.canonical_wall_id for w in forged]
    assert remap == _mapping_for(forged)


def test_resolved_collision_still_fails_the_whole_composition(monkeypatch) -> None:
    """The global fail-closed guard is unchanged for resolved-wall collisions."""
    source, wall_opening, _scope = _boundary_incomplete_source()
    original = composition._make_wall
    calls = {"n": 0}

    def forcing(**kwargs):
        wall = original(**kwargs)
        calls["n"] += 1
        if calls["n"] <= 2:
            wall = replace(
                wall,
                canonical_wall_id="wall2_forced_resolved_collision",
                physical_identity_resolved=True,
                physical_wall_id="wall2_forced_resolved_collision",
            )
        return wall

    monkeypatch.setattr(composition, "_make_wall", forcing)
    result = compose_live_canonical_walls(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.walls == ()
    assert LIVE_CANONICAL_WALL_FRAME_CONFLICT in result.reason_codes


def _forced_candidate_collision(monkeypatch):
    source, wall_opening, scope = _boundary_incomplete_source()
    original = composition._make_wall
    calls = {"n": 0}

    def forcing(**kwargs):
        wall = original(**kwargs)
        calls["n"] += 1
        if calls["n"] <= 2:
            wall = replace(wall, canonical_wall_id="wall2_forced_candidate_collision")
        return wall

    monkeypatch.setattr(composition, "_make_wall", forcing)
    return source, wall_opening, scope


def test_end_to_end_duplicate_pair_no_longer_discards_the_page(monkeypatch) -> None:
    source, wall_opening, scope = _forced_candidate_collision(monkeypatch)
    evaluation = scope.boundary_evaluation
    clean = set(evaluation.evaluated_wall_candidate_ids) - set(
        evaluation.boundary_tainted_wall_candidate_ids
    )

    result = compose_live_canonical_walls(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.reason_codes[0] == LIVE_CANONICAL_WALL_PARTIAL
    assert LIVE_CANONICAL_WALL_ID_COLLISION_CANDIDATE in result.reason_codes
    assert LIVE_CANONICAL_WALL_BOUNDARY_CLEAN_PARTIAL in result.reason_codes
    assert LIVE_CANONICAL_WALL_FRAME_CONFLICT not in result.reason_codes
    ids = [wall.canonical_wall_id for wall in result.walls]
    assert len(ids) == len(set(ids)) == len(clean)
    emitted = {m for w in result.walls for m in w.member_wall_candidate_ids}
    assert emitted == clean
    assert set(result.candidate_to_canonical_wall_id) == clean
    collided = [w for w in result.walls if w.identity_status == COLLISION_STATUS]
    assert len(collided) == 2
    # Shadow guarantee: nothing is promoted and no quantity-bearing field is set.
    for wall in result.walls:
        assert wall.physical_identity_resolved is False
        assert wall.physical_wall_id is None
        assert wall.length_m is None and wall.height_m is None
        assert wall.gross_area_m2 is None and wall.net_area_m2 is None
        assert wall.quantity_complete is False
    assert set(result.unresolved_wall_candidate_ids) == {
        record.wall_candidate_id for record in scope.records
    }
    for wall in collided:
        for member in wall.member_wall_candidate_ids:
            assert result.candidate_to_canonical_wall_id[member] == wall.canonical_wall_id


def test_end_to_end_replay_is_deterministic(monkeypatch) -> None:
    source, wall_opening, _scope = _forced_candidate_collision(monkeypatch)
    first = compose_live_canonical_walls(
        source_visibility_producer=source, wall_opening_composition=wall_opening
    )
    # Reset the call counter by re-forcing for the second replay.
    source2, wall_opening2, _ = _forced_candidate_collision(monkeypatch)
    second = compose_live_canonical_walls(
        source_visibility_producer=source2, wall_opening_composition=wall_opening2
    )
    assert [w.canonical_wall_id for w in first.walls] == [
        w.canonical_wall_id for w in second.walls
    ]
    assert dict(first.candidate_to_canonical_wall_id) == dict(
        second.candidate_to_canonical_wall_id
    )


def test_without_localization_the_same_input_reproduces_the_old_defect(monkeypatch) -> None:
    """Control: disabling the new step restores the page-fatal CONFLICT."""
    source, wall_opening, _scope = _forced_candidate_collision(monkeypatch)
    monkeypatch.setattr(
        composition,
        "_localize_candidate_id_collisions",
        lambda walls, mapping: (walls, dict(mapping), False),
    )
    result = compose_live_canonical_walls(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.walls == ()
    assert LIVE_CANONICAL_WALL_FRAME_CONFLICT in result.reason_codes
