"""The internal door inventory uses ONE internal-wall layer predicate and no privileged width value.

Synthetic geometry only (the swing fixture of the existing inventory tests). Before this change the inventory kept
its own three-name layer regex and accepted only the printed tokens 720 and 870 for a hinge.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import pb_source_internal_door_completeness_shadow as completeness
from pb_source_internal_door_completeness_shadow import (
    inspect_source_internal_door_completeness,
)
from pb_source_internal_swing_room_barrier import _INTERNAL_WALL_LAYER
from tests.test_source_internal_door_completeness_shadow import _source_native_door


def _door(layer):
    rows = _source_native_door()
    for row in rows:
        row["layer"] = layer
    return rows


def _word(text, x=108.0, y=28.0):
    return (x, y, x + 10.0, y + 8.0, text, 0, 0, 0)


def _swing(words, rows=None):
    review = inspect_source_internal_door_completeness(rows or _source_native_door(), words, page_index=2)
    swings = [m for m in review.marks if m.kind == "native_swing_arc_leaf"]
    assert len(swings) == 1
    return swings[0]


CONVENTIONS = ["Enclosure_WallInternal", "Wall_Internal", "Internal Wall", "A-WALL-INTR", "building.wall.internal"]


@pytest.mark.parametrize("layer", CONVENTIONS)
def test_every_internal_wall_convention_the_hosting_detector_accepts_is_hosted_in_the_inventory(layer):
    review = inspect_source_internal_door_completeness(_door(layer), (), page_index=2)
    assert [m.status for m in review.marks] == ["HOSTED_TOPOLOGY_ONLY"]
    assert review.hosted_swing_count == 1 and review.unhosted_swing_symbol_count == 0


@pytest.mark.parametrize("layer", CONVENTIONS)
def test_an_unhosted_swing_on_any_accepted_convention_is_listed_not_silently_missed(layer):
    rows = _door(layer)
    rows.pop(0)  # one black wall end gone: no host, but the arc and leaf are still a source swing symbol
    review = inspect_source_internal_door_completeness(rows, (), page_index=2)
    assert [m.status for m in review.marks] == ["NEEDS_HOST"]
    assert review.unhosted_swing_symbol_count == 1


@pytest.mark.parametrize("layer", ["Wall_External", "Furniture", "A-WALL", "Annotation", "", "Enclosure_WallInternalNote"])
def test_other_layers_are_not_internal_walls(layer):
    rows = _door(layer)
    rows.pop(0)
    assert inspect_source_internal_door_completeness(rows, (), page_index=2).marks == ()


def test_the_inventory_and_the_hosting_detector_share_one_predicate():
    assert completeness._INTERNAL_WALL_LAYER is _INTERNAL_WALL_LAYER


# ---------------------------------------------------------------- hinge width ownership

@pytest.mark.parametrize("token,expected", [("720", 720), ("870", 870), ("900", 900), ("1000", 1000), ("1,000", 1000),
                                            ("1200", 1200), ("600", 600), ("1400", 1400)])
def test_one_plausible_token_near_the_swing_is_its_width_whatever_the_value(token, expected):
    mark = _swing([_word(token)])
    assert mark.label_width_mm == expected and mark.label_width_word_index == 0


@pytest.mark.parametrize("token", ["599", "1401", "2100", "450", "3,000", "CS", "D01", "7200", "72", "abc"])
def test_a_token_that_is_not_a_plausible_door_width_is_never_a_width(token):
    mark = _swing([_word(token)])
    assert mark.label_width_mm is None and mark.label_width_word_index is None


def test_two_plausible_tokens_near_the_swing_are_ambiguous_and_none_is_chosen():
    mark = _swing([_word("900", 104.0, 28.0), _word("1000", 112.0, 28.0)])
    assert mark.label_width_mm is None and mark.label_width_word_index is None
    # the same token printed twice is still two candidates, not one
    mark = _swing([_word("900", 104.0, 28.0), _word("900", 112.0, 28.0)])
    assert mark.label_width_mm is None


def test_a_plausible_token_outside_the_radius_is_not_owned():
    far = _word("900", 300.0, 300.0)
    assert _swing([far]).label_width_mm is None
    # and an ambiguous neighbour does not poison a clean owner elsewhere in the page
    assert _swing([far, _word("870")]).label_width_mm == 870


def test_the_width_is_a_witness_not_a_measurement():
    mark = _swing([_word("900")])
    assert mark.physical_opening_authenticated is False and mark.measurement_authorized is False
    assert mark.to_dict()["measurement_authorized"] is False


def test_no_privileged_width_literal_is_left_in_the_inventory():
    text = Path(completeness.__file__).read_text(encoding="utf-8")
    code = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    assert not re.search(r"\b(?:720|870)\b", code)
    assert "_nearest_native_hinge_width" not in text


# ---------------------------------------------------------------- the ownership radius is pinned, not implied

@pytest.mark.parametrize("distance,owned", [(0.0, True), (14.0, True), (14.9, True), (15.0, False), (15.1, False), (30.0, False)])
def test_a_width_token_is_owned_only_inside_the_fifteen_point_radius(distance, owned):
    # the swing fixture's arc box is (100, 20, 125, 45): its centre is (112.5, 32.5)
    word = (112.5 + distance - 5.0, 32.5 - 4.0, 112.5 + distance + 5.0, 32.5 + 4.0, "900", 0, 0, 0)
    assert (_swing([word]).label_width_mm == 900) is owned


def test_a_cavity_slider_width_above_the_door_range_is_still_ignored():
    # 1401-1499 pass the digit pattern; the shared upper bound must still exclude them for hinges and sliders alike
    assert _swing([_word("1400")]).label_width_mm == 1400
    assert _swing([_word("1401")]).label_width_mm is None
    assert _swing([_word("1499")]).label_width_mm is None


@pytest.mark.parametrize("token,expected", [("1400", 1400), ("1401", None), ("600", 600), ("1,200", 1200)])
def test_a_cavity_slider_callout_width_uses_the_same_plausible_range(token, expected):
    words = [(36, 105, 46, 113, token, 0, 0, 0), (50, 105, 60, 113, "CS", 0, 0, 1)]
    review = inspect_source_internal_door_completeness((), words, page_index=2)
    sliders = [m for m in review.marks if m.kind == "native_cavity_slider_callout"]
    assert len(sliders) == 1 and sliders[0].label_width_mm == expected
