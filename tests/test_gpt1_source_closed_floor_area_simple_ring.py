"""Room-owned floor areas must retain a simple original source polygon."""
import pytest
from pb_live_floor_area_source_closed_export import _source_floor_area_simple_bbox
from pb_source_closed_run_export import SourceClosedRunConflictError


def _bbox(p): return _source_floor_area_simple_bbox(p,quantity_id="original-floor-qty")


def test_original_simple_rectangular_and_l_shaped_floors_remain_eligible():
    rectangle=((0.,0.),(10.,0.),(10.,7.),(0.,7.))
    assert _bbox(rectangle)==(0.,0.,10.,7.)
    assert _bbox(rectangle+(rectangle[0],))==(0.,0.,10.,7.)
    assert _bbox(((0,0),(9,0),(9,3),(3,3),(3,6),(0,6)))==(0,0,9,6)


@pytest.mark.parametrize("ring",[
    ((0,0),(10,0),(0,10),(10,10),(0,14)),
    ((0,0),(10,10),(0,10),(10,0)),
    ((0,0),(10,0),(10,10),(5,5),(10,10),(0,10)),
])
def test_positive_bbox_but_crossed_or_repeated_floor_source_cannot_seal(ring):
    with pytest.raises(SourceClosedRunConflictError,match="source ring"):
        _bbox(ring)
