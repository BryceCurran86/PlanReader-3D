"""Source-closed customer traces require one real simple floor perimeter."""
from types import SimpleNamespace
import pytest
from pb_live_room_area_source_closed_export import _source_bbox
from pb_source_closed_run_export import SourceClosedRunConflictError


def _floor(points):
    return SimpleNamespace(canonical_floor_id="original-floor-id",polygon_pdf_pts=points)


def test_closed_rectangle_and_simple_concave_source_ring_keep_source_extent():
    rect=((0,0),(10,0),(10,5),(0,5))
    assert _source_bbox(_floor(rect)) == (0,0,10,5)
    assert _source_bbox(_floor(rect + (rect[0],))) == (0,0,10,5)
    concave=((0,0),(8,0),(8,3),(3,3),(3,7),(0,7))
    assert _source_bbox(_floor(concave)) == (0,0,8,7)


@pytest.mark.parametrize("ring",[
    ((0,0),(10,0),(0,10),(10,10),(0,15)),
    ((0,0),(10,10),(0,10),(10,0)),
    ((0,0),(10,0),(10,5),(5,3),(10,5),(0,5)),
    ((0,0),(10,0),(10,10),(0,10),(10,0)),
])
def test_crossed_or_repeated_source_wall_ring_cannot_be_customer_sealed(ring):
    with pytest.raises(SourceClosedRunConflictError,match="polygon"):
        _source_bbox(_floor(ring))


def test_polygon_invalid_numeric_source_does_not_become_customer_quantity():
    with pytest.raises(SourceClosedRunConflictError,match="polygon"):
        _source_bbox(_floor(((0,0),(float("nan"),2),(2,2),(0,2))))


def test_original_two_vertex_closed_wall_trace_abstains_without_geos_exception():
    # Three PDF points with only two distinct vertices are not a triangle.
    with pytest.raises(SourceClosedRunConflictError, match="polygon"):
        _source_bbox(_floor(((0,0),(12,0),(0,0))))


def test_extreme_source_coordinate_does_not_escape_as_raw_geos_error():
    giant=1e308
    with pytest.raises(SourceClosedRunConflictError, match="polygon"):
        _source_bbox(_floor(((0,0),(giant,giant),(giant,0),(0,giant))))


def test_unrepresentable_large_integer_original_floor_point_abstains():
    with pytest.raises(SourceClosedRunConflictError, match="polygon"):
        _source_bbox(_floor(((0,0),(10**1000,0),(1,1),(0,1))))
