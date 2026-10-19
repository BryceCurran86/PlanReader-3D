"""Single-wall raster frames may not bind to an overwritten W4 wall ID.

Source-neutral fixture exercises the actual opening-frame projection path.
The duplicated address has one legitimate centered wall and one unrelated
parallel physical record; input order must not choose which frame appears.
"""
import pytest

from test_raster_opening_whole_wall_frame import (
    GEOMETRY, _binding, _opening, _producer, _record, _scope,
)


@pytest.mark.parametrize("reverse", (False, True))
def test_one_owned_w4_id_with_two_different_centerlines_cannot_issue_frame(reverse):
    eligible = _record("wall:host")
    unrelated = _record("wall:host", offset=100.0)
    # This is an upstream-claimed complete physical scope whose identity
    # ledger describes one eligible wall, but its records also carry an
    # inconsistent duplicate address. The original lookup silently elected
    # whichever one happened to occur last.
    scope = _scope((eligible,))
    scope.records = (
        (unrelated, eligible) if reverse else (eligible, unrelated)
    )
    result = _producer(scope)._raster_whole_wall_frame(
        binding=_binding(), opening=_opening(), geometry=GEOMETRY,
    )
    assert result is None


def test_independent_unique_wall_source_still_yields_original_whole_frame():
    result = _producer(_scope((_record("wall:host"),)))._raster_whole_wall_frame(
        binding=_binding(), opening=_opening(), geometry=GEOMETRY,
    )
    assert result is not None
    assert result.whole_wall_length == 200.0
    assert result.u0 == 80.0
    assert result.u1 == 120.0
