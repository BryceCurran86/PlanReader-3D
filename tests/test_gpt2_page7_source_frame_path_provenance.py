"""Native line provenance alone must not resolve competing floor-plan frames."""
from types import SimpleNamespace

from tools.diag_gpt2_page7_frame_border_strip import (
    _source_line_path_provenance,
)


class _Page:
    def __init__(self, paths):
        self.paths=paths

    def get_drawings(self):
        return self.paths


def _point(x,y):
    return SimpleNamespace(x=x,y=y)


def _line(x0,y0,x1,y1):
    return ("l",_point(x0,y0),_point(x1,y1))


def test_source_path_receipts_keep_duplicate_paths_and_inner_boundary_crossing():
    outer=(0.,0.,100.,100.)
    inner=(10.,0.,100.,100.)
    strip=(0.,0.,10.,100.)
    arc=_line(4.,25.,13.,29.)
    paths=[
        {"seqno":11,"type":"s","width":.2,"color":(0.,0.,0.),
         "items":[_line(0.,0.,0.,100.),arc]},
        {"seqno":12,"type":"s","width":.2,"color":(0.,0.,0.),
         "items":[arc]},
    ]
    result=_source_line_path_provenance(_Page(paths),strip,0,outer,inner)
    assert result["line_intersection_count"]==2
    assert result["unique_line_geometry_count"]==1
    assert result["native_source_path_count"]==2
    assert result["inner_frame_crossing_line_count"]==2
    assert {row["drawing_seqno"] for row in result["source_path_receipts"]}=={"11","12"}
    assert result["classification"]=="SOURCE_PATH_CANDIDATE_ONLY_NOT_BOUNDARY_PROOF"


def test_only_actual_outer_or_inner_source_frame_edge_is_ignored():
    outer=(0.,0.,100.,100.)
    inner=(10.,0.,100.,100.)
    strip=(0.,0.,10.,100.)
    page=_Page([{"seqno":1,"items":[
        _line(0.,0.,0.,100.),_line(10.,0.,10.,100.),
        _line(5.,10.,5.,20.),
    ]}])
    result=_source_line_path_provenance(page,strip,0,outer,inner)
    assert result["line_intersection_count"]==1
    assert result["unique_line_geometry_count"]==1
    assert result["inner_frame_crossing_line_count"]==0


def test_orthogonal_border_strip_classifies_intersecting_source_line():
    outer=(0.,0.,100.,100.)
    inner=(0.,10.,100.,100.)
    strip=(0.,0.,100.,10.)
    page=_Page([{"seqno":22,"items":[
        _line(10.,0.,90.,0.),
        _line(10.,10.,90.,10.),
        _line(40.,5.,50.,20.),
    ]}])
    result=_source_line_path_provenance(page,strip,1,outer,inner)
    assert result["line_intersection_count"]==1
    assert result["inner_frame_crossing_line_count"]==1
