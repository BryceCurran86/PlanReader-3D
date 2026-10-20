"""Exact W4 wall-pair equivalence is not last-write-wins.

Source-neutral original-record-shaped tuples only. A repeated wall pair that
contradicts an earlier authenticated physical classification stays AMBIGUOUS
for every ordering and can never unblock a physical opening host frame.
"""
from dataclasses import replace
from itertools import permutations
from types import SimpleNamespace

import pytest

from pb_opening_host_frame_authority import _pair_lookup
from pb_physical_wall_identity import PhysicalEquivalenceClass as Class


SAME = Class.SAME_PHYSICAL_WALLS if hasattr(Class, "SAME_PHYSICAL_WALLS") else Class.SAME_PHYSICAL_WALL
DISTINCT = Class.DISTINCT_PHYSICAL_WALLS
AMBIGUOUS = Class.AMBIGUOUS_PHYSICAL_EQUIVALENCE


def _lookup(rows):
    return _pair_lookup(SimpleNamespace(pair_classifications=rows))


@pytest.mark.parametrize("classes", [
    (SAME.value, DISTINCT.value, SAME.value),
    (DISTINCT.value, SAME.value, DISTINCT.value),
    (AMBIGUOUS.value, SAME.value, SAME.value),
    (AMBIGUOUS.value, DISTINCT.value, DISTINCT.value),
    (SAME.value, "unknown_source_role", SAME.value),
])
def test_wall_pair_conflicts_stay_ambiguous_across_all_input_orders(classes):
    for order in set(permutations(classes)):
        rows = [("wall_a", "wall_b", label) for label in order]
        result = _lookup(rows)
        assert result == {("wall_a", "wall_b"): AMBIGUOUS}


@pytest.mark.parametrize("classification", [SAME, DISTINCT, AMBIGUOUS])
def test_repeated_identical_wall_pair_does_not_invent_an_opposite_class(classification):
    rows = [
        ("wall_b", "wall_a", classification.value),
        ("wall_a", "wall_b", classification.value),
        ("wall_b", "wall_a", classification.value),
    ]
    assert _lookup(rows) == {("wall_a", "wall_b"): classification}


def test_unrelated_wall_pair_never_changes_when_first_pair_conflicts():
    rows = [
        ("wall_a", "wall_b", SAME.value),
        ("wall_c", "wall_d", DISTINCT.value),
        ("wall_b", "wall_a", DISTINCT.value),
        ("wall_a", "wall_b", SAME.value),
    ]
    assert _lookup(rows) == {
        ("wall_a", "wall_b"): AMBIGUOUS,
        ("wall_c", "wall_d"): DISTINCT,
    }


def test_ambiguous_relation_is_retained_not_treated_as_positive_distinct():
    contradiction = [
        ("aligned_competitor", "host_component", DISTINCT.value),
        ("host_component", "aligned_competitor", SAME.value),
        ("aligned_competitor", "host_component", DISTINCT.value),
    ]
    classification = _lookup(contradiction)[
        ("aligned_competitor", "host_component")
    ]
    assert classification is AMBIGUOUS
    assert classification is not Class.DISTINCT_PHYSICAL_WALLS


def test_pair_lookup_never_mutates_original_issuer_rows():
    rows = [
        ("left", "right", SAME.value),
        ("right", "left", DISTINCT.value),
        ("right", "left", SAME.value),
    ]
    original = list(rows)
    assert _lookup(rows) == {("left", "right"): AMBIGUOUS}
    assert rows == original


def test_frame_cannot_recover_distinctness_after_four_source_receipts():
    """A final apparently valid DISTINCT must not wash out earlier SAME."""
    original = (
        ("frame_left", "frame_right", DISTINCT.value),
        ("frame_right", "frame_left", SAME.value),
        ("frame_left", "frame_right", AMBIGUOUS.value),
        ("frame_left", "frame_right", DISTINCT.value),
    )
    for permutation in set(permutations(original)):
        observed = _lookup(permutation)
        assert observed[("frame_left", "frame_right")] is AMBIGUOUS
        assert observed[("frame_left", "frame_right")] is not DISTINCT
    assert len(original) == 4



def test_original_shaped_conflict_blocks_actual_whole_wall_frame(monkeypatch):
    """A conflicting DISTINCT cannot exclude a real aligned competing wall.

    Use the repository's producer-built two-opening sealed PDF fixture and add
    one synthetic rival W4 wall. This controls only a source-neutral wall-pair
    classification seam; it is not a new source authority or production grant.
    """
    from pb_migration_contracts import EvidenceResolutionStatus as Status
    from test_raster_connected_host_frame import _fixture, _publish, _scope
    from test_gptmax_raster_split_frame_shadow import _aligned_wall_piece_records

    _source, _composition, producer, bound = _fixture()
    baseline = _publish(producer, bound)
    assert all(row.status is Status.CORROBORATED for row in baseline)
    scope = _scope(producer, bound)

    # Independent aligned W4 support outside the actual connected host chain.
    centerline = baseline[0].evidence.origin_pt[1]
    rival_record = _aligned_wall_piece_records(
        scope.records[0], centerline, count=1, pitch=80.0,
    )[0]
    rival_id = rival_record.wall_candidate_id
    members = sorted({wall_id for row in bound
                      for wall_id in row[3].member_wall_candidate_ids})
    assert rival_id not in members
    assert set(members) == set(baseline[0].evidence.whole_wall_candidate_ids)

    original_pairs = tuple(scope.equivalence.pair_classifications)
    positive_pairs = tuple((rival_id, member, DISTINCT.value) for member in members)
    active = {"scope": scope}
    monkeypatch.setattr(producer._walls, "resolve_scope",
                        lambda _selector: active["scope"])

    def issued(rows):
        active["scope"] = replace(
            scope,
            records=(*scope.records, rival_record),
            equivalence=replace(
                scope.equivalence,
                pair_classifications=(*original_pairs, *rows),
            ),
        )
        return _publish(producer, bound)

    # Control: an independent positive DISTINCT relation for every member
    # may exclude this separately authenticated W4 rival.
    distinct = issued(positive_pairs)
    assert distinct == baseline

    # An explicit contradictory original relation with ANY component member
    # must keep the whole-wall publisher in ABSTAIN, in every issuer order.
    target = members[0]
    other_positive = tuple(p for p in positive_pairs if p[1] != target)
    for classes in set(permutations((
        DISTINCT.value, SAME.value, DISTINCT.value,
    ))):
        rows = (*other_positive, *((rival_id, target, label)
                                   for label in classes))
        withheld = issued(rows)
        assert all(row.status is Status.ABSTAINED and row.evidence is None
                   for row in withheld)
        assert all(
            "opening_host_frame_aligned_fragment_distinctness_unproven"
            in row.reason_codes for row in withheld
        )
        # Conflict cannot amend source-bounded commercial opening areas.
        assert _publish(producer, tuple(reversed(bound))) == tuple(reversed(withheld))

    assert tuple(scope.equivalence.pair_classifications) == original_pairs
