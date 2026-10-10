"""Source-proven repeated double borders are not a global viewport tolerance."""
from dataclasses import replace
from types import SimpleNamespace

from pb_viewport_segmentation import (
    ViewportLayoutCalibration,
    _collapse_source_repeated_plan_border_pair,
)


class Page:
    def __init__(self, paths):
        self.paths = paths

    def get_drawings(self):
        return self.paths


def pt(x,y):
    return SimpleNamespace(x=x,y=y)


def line(x0,y0,x1,y1):
    return ("l",pt(x0,y0),pt(x1,y1))


INNER=(49.68,424.64,1345.92,2316.56)
OUTER=(34.32,424.64,1345.92,2316.56)


def cal():
    return ViewportLayoutCalibration(
        median_word_height_pt=10.27,
        title_frame_gap_pt=20.,
        minimum_frame_span_pt=50.,
        title_separation_pt=10.,
        page_width_pt=1400.,
        page_height_pt=2400.,
    )


def paths():
    return [
        {"seqno":100+copy*10+offset,"type":"s",
         "width":.48,"color":(0.,0.,0.),"stroke_opacity":1.,
         "items":[shape]}
        for copy in range(2)
        for offset,shape in enumerate((
            line(41.0,500.0,41.0,900.0),
            line(41.0,900.0,45.0,930.0),
            line(45.0,930.0,49.9,970.0),
        ))
    ]


def test_source_drawn_duplicate_margin_can_choose_narrower_eligible_frame():
    # The outer source rectangle adds only a repeated border ornament
    # margin. The source owner is the narrower NATIVE frame, not an inferred
    # artificial crop rectangle or rescaled floor.
    result=_collapse_source_repeated_plan_border_pair(
        Page(paths()),(INNER,OUTER),cal(),()
    )
    assert result == [INNER]


def test_single_source_line_or_mismatched_stroke_cannot_resolve_competing_frames():
    assert _collapse_source_repeated_plan_border_pair(
        Page(paths()[:3]),(INNER,OUTER),cal(),()
    ) == [INNER,OUTER]
    changed=paths()
    changed[4]["color"]=(1.,0.,0.)
    assert _collapse_source_repeated_plan_border_pair(
        Page(changed),(INNER,OUTER),cal(),()
    ) == [INNER,OUTER]


def test_native_text_inside_differential_band_blocks_border_collapse():
    result=_collapse_source_repeated_plan_border_pair(
        Page(paths()),(INNER,OUTER),cal(),
        (((38.,600.,47.,620.),"ROOM TEXT"),)
    )
    assert result == [INNER,OUTER]


def test_source_stroke_materially_crossing_inner_plan_region_blocks():
    changed=paths()
    changed[2]["items"]=[line(45.,930.,55.,970.)]
    changed[5]["items"]=[line(45.,930.,55.,970.)]
    assert _collapse_source_repeated_plan_border_pair(
        Page(changed),(INNER,OUTER),cal(),()
    ) == [INNER,OUTER]


def test_non_matching_subregion_or_large_distinct_nested_frame_abstains():
    shifted=(OUTER[0],OUTER[1]-15.,OUTER[2],OUTER[3])
    assert _collapse_source_repeated_plan_border_pair(
        Page(paths()),(INNER,shifted),cal(),()
    ) == [INNER,shifted]
    wide_outer=(0.,OUTER[1],OUTER[2],OUTER[3])
    assert _collapse_source_repeated_plan_border_pair(
        Page(paths()),(INNER,wide_outer),cal(),()
    ) == [INNER,wide_outer]


def test_extra_source_rectangle_over_strip_blocks_duplicate_claim():
    changed=paths()
    changed.append({"seqno":401,"type":"s","items":[
        ("re",SimpleNamespace(x0=37.,y0=800.,x1=43.,y1=830.))
    ]})
    assert _collapse_source_repeated_plan_border_pair(
        Page(changed),(INNER,OUTER),cal(),()
    ) == [INNER,OUTER]


def test_not_exactly_two_competing_frames_never_selects_an_owner():
    third=(900.,2000.,1300.,2200.)
    assert _collapse_source_repeated_plan_border_pair(
        Page(paths()),(INNER,OUTER,third),cal(),()
    ) == [INNER,OUTER,third]


def test_unknown_native_quad_geometry_is_never_assumed_empty():
    changed=paths()
    changed.append({"seqno":441,"type":"s","items":[
        ("qu",object()),
    ]})
    assert _collapse_source_repeated_plan_border_pair(
        Page(changed),(INNER,OUTER),cal(),()
    ) == [INNER,OUTER]


def test_native_quad_over_border_strip_is_independent_graphic_content():
    changed=paths()
    quad=SimpleNamespace(
        ul=pt(38.,700.),ur=pt(45.,700.),
        ll=pt(38.,730.),lr=pt(45.,730.)
    )
    changed.append({"seqno":442,"type":"s","items":[
        ("qu",quad),
    ]})
    assert _collapse_source_repeated_plan_border_pair(
        Page(changed),(INNER,OUTER),cal(),()
    ) == [INNER,OUTER]


def _white_background_mask(*, seqno=3, fill=(1.,1.,1.), opacity=1.,
                           paint_type="f", stroke=None):
    return {
        "seqno": seqno,
        "type": paint_type,
        "fill": fill,
        "fill_opacity": opacity,
        "color": stroke,
        "items": [("re", SimpleNamespace(
            x0=40., y0=700., x1=75., y1=800.
        ))],
    }


def test_opaque_white_background_mask_before_source_double_strokes_is_nonowner():
    # A source paint background underneath the duplicated visible border
    # cannot compete with the producer-owned native line geometry.
    actual=[_white_background_mask()]+paths()
    assert _collapse_source_repeated_plan_border_pair(
        Page(actual), (INNER,OUTER), cal(), ()
    ) == [INNER]


def test_late_white_mask_still_blocks_source_border_recovery():
    actual=paths()+[_white_background_mask(seqno=9999)]
    assert _collapse_source_repeated_plan_border_pair(
        Page(actual), (INNER,OUTER), cal(), ()
    ) == [INNER,OUTER]


def test_colored_translucent_or_stroked_rectangle_never_grants_plan_boundary():
    for kwargs in (
        {"fill":(.9,.9,.9)},
        {"fill":(1.,0.,0.)},
        {"opacity":.5},
        {"stroke":(0.,0.,0.)},
        {"paint_type":"fs"},
    ):
        actual=[_white_background_mask(**kwargs)]+paths()
        assert _collapse_source_repeated_plan_border_pair(
            Page(actual),(INNER,OUTER),cal(),()
        ) == [INNER,OUTER],kwargs


def test_multiple_early_opaque_white_mask_rectangles_can_coexist():
    masks=[_white_background_mask(seqno=i) for i in (1,2,3)]
    assert _collapse_source_repeated_plan_border_pair(
        Page(masks+paths()),(INNER,OUTER),cal(),()
    ) == [INNER]
