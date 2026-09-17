"""Executable authority-selection attacks for future Net-wall Boolean Union.

TEST ONLY. Geometry is supplied by test fixtures; these tests do not mint physical
void or net-wall authority.
"""
from __future__ import annotations

from dataclasses import replace

import pytest
from shapely.geometry import box

from tests.net_wall_boolean_reference_v1 import (
    normalized_wkb_hex,
    reference_net_wall_polygon,
    reference_void_union,
)
from tests.net_wall_boolean_selection_reference_v1 import (
    ReferenceApplicableVoid,
    select_target_wall_voids_or_none,
)


def _void(opening_id: str, geometry, *, wall_id: str = "wall-a") -> ReferenceApplicableVoid:
    return ReferenceApplicableVoid(
        opening_identity_id=opening_id,
        host_wall_id=wall_id,
        geometry=geometry,
    )


def test_wrong_wall_void_is_never_subtracted_from_target_wall() -> None:
    gross = box(0.0, 0.0, 10.0, 3.0)
    target = _void("opening-1", box(1.0, 0.0, 2.0, 2.0))
    wrong_wall = _void("opening-2", box(4.0, 0.0, 6.0, 2.0), wall_id="wall-b")
    selected = select_target_wall_voids_or_none(
        (target, wrong_wall),
        target_wall_id="wall-a",
        opening_universe_complete=True,
    )
    assert selected is not None
    assert reference_net_wall_polygon(gross, selected).area == pytest.approx(28.0)


def test_incomplete_opening_universe_blocks_net_wall_but_not_gross_wall() -> None:
    gross = box(0.0, 0.0, 10.0, 3.0)
    selected = select_target_wall_voids_or_none(
        (_void("opening-1", box(1.0, 0.0, 2.0, 2.0)),),
        target_wall_id="wall-a",
        opening_universe_complete=False,
    )
    assert selected is None
    assert gross.area == pytest.approx(30.0)


def test_one_unresolved_relevant_void_blocks_net_wall() -> None:
    resolved = _void("opening-1", box(1.0, 0.0, 2.0, 2.0))
    unresolved = replace(_void("opening-2", box(3.0, 0.0, 4.0, 2.0)), resolved=False)
    assert select_target_wall_voids_or_none(
        (resolved, unresolved),
        target_wall_id="wall-a",
        opening_universe_complete=True,
    ) is None


def test_ambiguous_physical_wall_equivalence_blocks_net_wall() -> None:
    ambiguous = replace(
        _void("opening-1", box(1.0, 0.0, 2.0, 2.0)),
        physical_equivalence_unambiguous=False,
    )
    assert select_target_wall_voids_or_none(
        (ambiguous,),
        target_wall_id="wall-a",
        opening_universe_complete=True,
    ) is None


def test_exact_duplicate_void_does_not_double_deduct() -> None:
    geometry = box(1.0, 0.0, 3.0, 2.0)
    duplicate = _void("opening-1", geometry)
    selected = select_target_wall_voids_or_none(
        (duplicate, duplicate),
        target_wall_id="wall-a",
        opening_universe_complete=True,
    )
    assert selected is not None
    assert reference_void_union(selected).area == pytest.approx(4.0)


def test_conflicting_geometry_for_same_physical_opening_blocks_not_first_wins() -> None:
    first = _void("opening-1", box(1.0, 0.0, 3.0, 2.0))
    conflict = _void("opening-1", box(1.5, 0.0, 3.5, 2.0))
    assert select_target_wall_voids_or_none(
        (first, conflict),
        target_wall_id="wall-a",
        opening_universe_complete=True,
    ) is None


def test_partial_overlap_and_contained_voids_use_union_not_scalar_sum() -> None:
    outer = box(1.0, 0.0, 5.0, 2.0)
    partial = box(4.0, 0.0, 7.0, 2.0)
    contained = box(2.0, 0.5, 3.0, 1.5)
    union = reference_void_union((outer, partial, contained))
    assert union.area == pytest.approx(12.0)
    assert union.area != pytest.approx(outer.area + partial.area + contained.area)


def test_disjoint_same_size_distinct_openings_remain_two_geometric_voids() -> None:
    first = box(1.0, 0.0, 2.0, 2.0)
    second = box(4.0, 0.0, 5.0, 2.0)
    selected = select_target_wall_voids_or_none(
        (_void("opening-1", first), _void("opening-2", second)),
        target_wall_id="wall-a",
        opening_universe_complete=True,
    )
    assert selected is not None
    assert len(selected) == 2
    assert reference_void_union(selected).area == pytest.approx(4.0)


def test_union_serialization_is_deterministic_under_input_order() -> None:
    first = box(1.0, 0.0, 3.0, 2.0)
    second = box(2.0, 1.0, 4.0, 3.0)
    forward = reference_void_union((first, second))
    reverse = reference_void_union((second, first))
    assert normalized_wkb_hex(forward) == normalized_wkb_hex(reverse)