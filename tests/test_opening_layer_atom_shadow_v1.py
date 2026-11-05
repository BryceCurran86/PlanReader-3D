"""Opening-level typed layer atom: SHADOW only. It reads the layer of an opening's OWN source primitives (already resolved by the caller) and
says whether the source attests that the opening sits in wall linework. It is a PRECISION signal (opposing a candidate that lies wholly in one
non-wall layer on a page that names wall layers), never a recall signal: it never creates or rescues an opening. Synthetic values only.
"""
from __future__ import annotations

from itertools import permutations

import pytest

from pb_wall_layer_evidence_shadow import (
    OPENING_MIXED_LAYERS,
    OPENING_NO_LAYER,
    OPENING_OTHER_SINGLE_LAYER,
    OPENING_WALL_LAYER,
    classify_opening_layers,
)

WALL = "Enclosure_WallExternal"
WALL2 = "Enclosure_WallInternal"
OTHER = "Interior_Joinery"


def _kind(values, uses=True):
    return classify_opening_layers(values, page_uses_explicit_wall_layers=uses)


def test_all_primitives_in_one_wall_named_layer_is_a_wall_layer_opening():
    atom = _kind([WALL, WALL, WALL])
    assert atom.kind == OPENING_WALL_LAYER and atom.layer_value == WALL and atom.opposing is False


def test_two_different_wall_layers_are_mixed_not_attested():
    assert _kind([WALL, WALL2]).kind == OPENING_MIXED_LAYERS


@pytest.mark.parametrize("layer", ["Finish_WallTile", "Wall_Lining", "A-WALL-CLADDING"])
def test_a_finish_or_lining_layer_is_not_a_wall_layer_opening(layer):
    assert _kind([layer, layer]).kind == OPENING_OTHER_SINGLE_LAYER


def test_a_single_non_wall_layer_opposes_only_on_a_page_that_names_a_wall_layer():
    on_wall_page = _kind([OTHER, OTHER])
    assert on_wall_page.kind == OPENING_OTHER_SINGLE_LAYER and on_wall_page.opposing is True
    on_plain_page = _kind([OTHER, OTHER], uses=False)
    assert on_plain_page.kind == OPENING_OTHER_SINGLE_LAYER and on_plain_page.opposing is False


def test_a_wall_layer_opening_is_never_opposing_whatever_the_page():
    assert _kind([WALL], uses=False).opposing is False and _kind([WALL], uses=True).opposing is False


def test_mixed_wall_and_other_layers_are_mixed_and_never_opposed():
    atom = _kind([WALL, OTHER, WALL])
    assert atom.kind == OPENING_MIXED_LAYERS and atom.opposing is False


@pytest.mark.parametrize("values", [[], [None], [WALL, None], ["", WALL], [WALL, ""], [None, None]])
def test_missing_unresolved_or_empty_layer_provenance_is_no_layer_never_a_guess(values):
    atom = _kind(values)
    assert atom.kind == OPENING_NO_LAYER and atom.opposing is False


def test_the_result_does_not_depend_on_order_or_repetition():
    reference = _kind([WALL, OTHER, WALL, OTHER])
    for order in permutations([WALL, OTHER, WALL, OTHER]):
        assert _kind(list(order)) == reference
    assert _kind([WALL] * 6) == _kind([WALL])


def test_inputs_are_not_mutated_and_a_tuple_works():
    values = [OTHER, OTHER]
    before = list(values)
    _kind(values)
    assert values == before
    assert _kind(tuple(values)) == _kind(values)


def test_every_result_is_shadow_only_and_grants_nothing():
    atom = _kind([WALL])
    assert atom.shadow_only is True and atom.live_effect is False and atom.grants_authority is False


@pytest.mark.parametrize("bad", ["Enclosure_WallExternal", 5, None, [WALL, 3], [3], [1.5], [True]])
def test_wrong_types_are_refused(bad):
    with pytest.raises(TypeError):
        classify_opening_layers(bad, page_uses_explicit_wall_layers=True)


@pytest.mark.parametrize("flag", [1, 0, "yes", None])
def test_the_page_flag_must_be_a_real_bool(flag):
    with pytest.raises(TypeError):
        classify_opening_layers([WALL], page_uses_explicit_wall_layers=flag)
