"""A crossed original RCP ink loop cannot seal a physical ceiling m²."""
import pytest
from pb_live_ceiling_lining_source_closed_export import _original_ceiling_simple_bbox
from pb_source_closed_run_export import SourceClosedRunConflictError


def _bbox(points):
    return _original_ceiling_simple_bbox(points,quantity_id="synthetic-ceiling-area")


def test_original_simple_ceiling_zone_valid_and_closure_is_idempotent():
    rect=((0,0),(10,0),(10,8),(0,8))
    assert _bbox(rect) == (0,0,10,8)
    assert _bbox(rect+(rect[0],)) == (0,0,10,8)


def test_concave_source_ceiling_zones_can_still_seal():
    assert _bbox(((0,0),(8,0),(8,3),(3,3),(3,7),(0,7))) == (0,0,8,7)


@pytest.mark.parametrize("source_ring",[
    ((0,0),(10,0),(0,10),(10,10),(0,15)),
    ((0,0),(10,10),(0,10),(10,0)),
    ((0,0),(10,0),(10,5),(4,3),(10,5),(0,5)),
    ((0,0),(10,0),(10,10),(0,10),(10,0)),
])
def test_crossed_or_repeated_source_ceiling_ink_cannot_seal(source_ring):
    with pytest.raises(SourceClosedRunConflictError,match="ceiling polygon"):
        _bbox(source_ring)


def test_untypeable_or_nonfinite_source_rings_cannot_seal():
    for points in (
        ((0,0),(3,float("nan")),(3,3),(0,3)),
        ((0,0),(True,0),(3,3),(0,3)),
        ((0,0),(3,0)),
    ):
        with pytest.raises(SourceClosedRunConflictError,match="ceiling polygon"):
            _bbox(points)


def test_unrepresentably_large_original_ceiling_geometry_never_crashes_customer_seal():
    huge=1e308
    ring=((0.,0.),(huge,huge),(huge,0.),(0.,huge))
    with pytest.raises(SourceClosedRunConflictError,match="ceiling polygon"):
        _bbox(ring)


@pytest.mark.parametrize("source_ring", [None, True, 5, "not-a-ring", {"x": 1}])
def test_untyped_original_ceiling_polygon_abstains_without_raw_exception(source_ring):
    with pytest.raises(SourceClosedRunConflictError, match="ceiling polygon"):
        _bbox(source_ring)

