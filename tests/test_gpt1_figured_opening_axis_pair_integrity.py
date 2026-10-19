"""Shadow-only regression: figured opening axes must match the actual pair."""
import math

import pytest

from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import (
    _axis_values_match_figured_pair,
)


@pytest.mark.parametrize("width_m,height_m,pair,expected", [
    (0.9, 2.1, (900.0, 2100.0), True),
    (2.1, 0.9, (900.0, 2100.0), True),
    (0.9, 2.1, [2100.0, 900.0], True),
    # These have the same area as the authentic pair but different axes.
    (0.7, 2.7, (900.0, 2100.0), False),
    (1.05, 1.8, (900.0, 2100.0), False),
    (0.9, 2.1, (900.0,), False),
    (0.9, 2.1, (900.0, 0.0), False),
    (0.9, 2.1, (900.0, float("nan")), False),
    (True, 2.1, (900.0, 2100.0), False),
    (0.9, 2.1, (True, 2100.0), False),
    (0.9, 2.1, "900x2100", False),
    (0.9, 2.1, None, False),
])
def test_axis_pair_identity_does_not_accept_area_equivalence(
    width_m, height_m, pair, expected,
):
    assert _axis_values_match_figured_pair(width_m, height_m, pair) is expected


def test_axis_pair_never_mutates_source_dimension_list():
    pair = [2100.0, 900.0]
    assert _axis_values_match_figured_pair(0.9, 2.1, pair)
    assert pair == [2100.0, 900.0]


def test_near_finite_rounding_is_accepted_but_bad_measurement_is_not():
    assert _axis_values_match_figured_pair(0.9, 2.1, (900.0000001, 2100.0))
    assert not _axis_values_match_figured_pair(float("inf"), 2.1, (900., 2100.))
