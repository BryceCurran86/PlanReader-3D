"""Anonymous painted wall and doorway evidence: no layer-name dependence."""
from __future__ import annotations
import copy

import pytest

from pb_layered_wall_doorway_room_ring_shadow import build_layered_wall_doorway_room_rings as build
from pb_migration_contracts import EvidenceResolutionStatus as S
from tests.test_original_live_dark_filled_wall_rooms_20261112 import _dark_rect_room, _rect
from tests.test_layered_wall_doorway_room_ring_shadow_v1 import swing, WALL, SHA


def report(rows, enabled=True):
    return build(rows, source_sha256=SHA, page_index=0, dark_painted_wall_source=enabled)


def door_room(*, color=(0., 0., 0.), with_leaf=True, circular=True, layer="", opacity=1.0):
    gray=(.195,.195,.195)
    rows=[
        _rect(-2,-2,102,0,gray,layer=layer),
        _rect(-2,100,102,102,gray,layer=layer),
        _rect(-2,0,0,100,gray,layer=layer),
        _rect(100,0,102,35,gray,layer=layer),
        _rect(100,59,102,100,gray,layer=layer),
    ]
    rows += [dict(row,color=color,stroke_opacity=opacity) for row in
             swing((100,35),(76,35),(100,59),layer=layer,with_leaf=with_leaf,circular=circular)]
    return rows


def candidates(result):
    return [r for r in result.rings if r.status is S.CANDIDATE]


def test_black_is_not_discarded_when_the_same_unnamed_gray_room_is_traceable():
    gray=list(_dark_rect_room())
    black=[dict(row,fill=(0.,0.,0.)) for row in gray]
    a,b=report(gray),report(black)
    assert (a.wall_strip_count,len(candidates(a))) == (4,1)
    assert (b.wall_strip_count,len(candidates(b))) == (4,1)
    assert candidates(a)[0].polygon_pdf_pts == candidates(b)[0].polygon_pdf_pts
    assert all(not r.metric_area_issued and not r.commercial_projection_allowed for r in b.rings)


def test_named_black_strips_are_not_counted_again_by_the_anonymous_fill_adapter():
    named=[dict(row,fill=(0.,0.,0.),layer=WALL) for row in _dark_rect_room()]
    a,b=report(named,False),report(named)
    assert a.wall_strip_count == b.wall_strip_count == 4
    assert candidates(a)[0].polygon_pdf_pts == candidates(b)[0].polygon_pdf_pts


def test_black_swing_and_leaf_close_the_actual_wall_gap_without_a_wall_layer():
    rows=door_room()
    result=report(rows)
    assert result.wall_gap_count == 1 and len(result.closures) == 1
    assert len(candidates(result)) == 1
    assert not candidates(result)[0].metric_area_issued
    assert not candidates(result)[0].commercial_projection_allowed
    named=report([dict(row,layer=WALL) for row in rows])
    assert candidates(result)[0].polygon_pdf_pts == candidates(named)[0].polygon_pdf_pts


@pytest.mark.parametrize("kw", [
    dict(with_leaf=False),dict(circular=False),dict(color=(0.,.5,0.)),
    dict(color=(.5,.5,.5)),dict(color=None),dict(opacity=.5),
    dict(opacity=float("nan")),dict(opacity=True),
])
def test_absent_unpainted_colored_transparent_or_malformed_door_evidence_leaves_gap_open(kw):
    result=report(door_room(**kw))
    assert not result.closures and not candidates(result)


def test_competing_black_source_swings_remain_unresolved():
    rows=door_room()
    rows += [dict(row,color=(0.,0.,0.),stroke_opacity=1.) for row in
             swing((100,59),(76,59),(100,35),layer="")]
    assert not report(rows).closures


def test_anonymous_mode_is_default_off_deterministic_and_does_not_mutate_source():
    rows=door_room()
    before=copy.deepcopy(rows)
    assert not report(rows,False).closures
    a,b=report(rows),report(rows)
    assert a == b and rows == before
    assert all(0 <= i < len(rows) for r in a.rings for i in r.bounding_wall_path_indices)
