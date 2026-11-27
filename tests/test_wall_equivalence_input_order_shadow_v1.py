"""Order-independent wall-equivalence candidacy, default off (#4764 7211359981, geometry task C03). Synthetic only."""
from __future__ import annotations

import itertools
import math

import pytest

import pb_physical_wall_identity as identity
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_identity import PhysicalWallIdentity, resolve_physical_wall_equivalence

ANGLE = math.radians(0.8 * identity._EQUIVALENCE_ANGLE_TOL_DEG)
TOL = identity._EQUIVALENCE_LATERAL_TOL_PT


def _wall(wall_id, path, primitive):
    return PhysicalWallIdentity(
        wall_candidate_id=wall_id, viewport_id="vp", candidate_identity_id=f"cid::{wall_id}",
        path_fingerprint=tuple((float(x), float(y)) for x, y in path), source_primitive_ids=(primitive,),
        edge_ids=(f"e::{primitive}",), status=EvidenceResolutionStatus.CORROBORATED, level_id=None)


def _pair(*, dx=0.0, dy=0.0, scale=1.0, swap_ids=False):
    """A long wall and a short, very slightly angled wall just past its end and far to one side."""
    far = 4.0 * (TOL + 1.0) / math.sin(ANGLE)
    long_path = ((0.0, 0.0), (3000.0, 0.0))
    short_path = ((3001.0, -far), (3001.0 + 100.0 * math.cos(ANGLE), -far + 100.0 * math.sin(ANGLE)))
    move = lambda path: tuple((x * scale + dx, y * scale + dy) for x, y in path)
    first, second = ("w-b", "w-a") if swap_ids else ("w-a", "w-b")
    return _wall(first, move(long_path), "d1i0"), _wall(second, move(short_path), "d2i0")


def _verdict(resolution):
    return (resolution.representative_wall_ids, resolution.ambiguous_wall_ids, resolution.equivalence_groups)


def test_the_overlap_test_itself_depends_on_argument_order():
    long, short = _pair()
    features = identity._physical_wall_pair_features
    forward = identity._physical_wall_pair_identity_candidacy_with_features(long, short, features(long), features(short))
    backward = identity._physical_wall_pair_identity_candidacy_with_features(short, long, features(short), features(long))
    assert forward == (False, identity.PAIR_EXCLUDED_NO_LONGITUDINAL_OVERLAP) and backward == (True, None)


def test_default_behaviour_is_unchanged_and_order_dependent():
    long, short = _pair()
    assert resolve_physical_wall_equivalence([long, short]).representative_wall_ids == ("w-a", "w-b")
    assert resolve_physical_wall_equivalence([short, long]).representative_wall_ids == ()


@pytest.mark.parametrize("kwargs", [{}, {"swap_ids": True}, {"dx": 412.5, "dy": -77.25}, {"scale": 2.0}],
                         ids=["plain", "ids-swapped", "translated", "scaled"])
def test_the_option_gives_one_demotion_only_answer_in_either_order(kwargs):
    long, short = _pair(**kwargs)
    forward = resolve_physical_wall_equivalence([long, short], order_invariant_candidacy_shadow=True)
    backward = resolve_physical_wall_equivalence([short, long], order_invariant_candidacy_shadow=True)
    assert forward == backward
    assert forward.representative_wall_ids == () and set(forward.ambiguous_wall_ids) == {"w-a", "w-b"}
    for order in ([long, short], [short, long]):
        historical = resolve_physical_wall_equivalence(order).representative_wall_ids
        assert set(forward.representative_wall_ids) <= set(historical)


def _mixed():
    long, short = _pair()
    twin_a = _wall("w-c", ((6000.0, 500.0), (6900.0, 500.0)), "d3i0")  # past every other wall lengthwise
    twin_b = _wall("w-d", ((6000.0, 500.0), (6900.0, 500.0)), "d3i0")
    apart = _wall("w-e", ((8000.0, 900.0), (8400.0, 900.0)), "d4i0")  # never overlapping another wall lengthwise
    upright = _wall("w-f", ((-200.0, -200.0), (-200.0, 400.0)), "d5i0")
    return [long, short, twin_a, twin_b, apart, upright]


def test_every_input_order_gives_the_same_resolution_with_the_option():
    walls = _mixed()
    results = [resolve_physical_wall_equivalence(list(order), order_invariant_candidacy_shadow=True)
               for order in itertools.permutations(walls)]
    assert all(_verdict(result) == _verdict(results[0]) for result in results)
    assert all(result.candidate_pair_audit == results[0].candidate_pair_audit for result in results)
    verdict = results[0]
    assert ("w-c", "w-d") in verdict.equivalence_groups  # a true duplicate still merges
    assert {"w-e", "w-f"} <= set(verdict.representative_wall_ids)  # walls with no competitor still publish


def test_the_option_changes_nothing_when_no_pair_depends_on_order():
    walls = _mixed()[2:]
    for order in (walls, walls[::-1]):
        assert (resolve_physical_wall_equivalence(order)
                == resolve_physical_wall_equivalence(order, order_invariant_candidacy_shadow=True))


def test_inputs_are_not_mutated_and_the_option_must_be_a_boolean():
    walls = _mixed()
    before = list(walls)
    resolve_physical_wall_equivalence(walls, order_invariant_candidacy_shadow=True)
    assert walls == before
    with pytest.raises(TypeError):
        resolve_physical_wall_equivalence(walls, order_invariant_candidacy_shadow=1)


def test_exclusion_reasons_are_also_order_independent_with_a_physical_scale():
    long, short = _pair()  # one order excludes for no overlap, the other for separation beyond the wall band
    points_per_mm = 20.0 / identity.MAX_PLAUSIBLE_WALL_BODY_MM
    forward = resolve_physical_wall_equivalence([long, short], points_per_mm=points_per_mm,
                                                order_invariant_candidacy_shadow=True)
    backward = resolve_physical_wall_equivalence([short, long], points_per_mm=points_per_mm,
                                                 order_invariant_candidacy_shadow=True)
    assert forward == backward and forward.representative_wall_ids == ("w-a", "w-b")
    assert forward.candidate_pair_audit.excluded_pairs == 1
