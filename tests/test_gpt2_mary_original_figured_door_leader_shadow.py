"""Original source figure/leader ink tests. Never accepts numeric dimension as FIRM."""
from hashlib import sha256
from pathlib import Path
import os
import fitz
import pytest
from pb_gpt2_mary_original_figured_door_leader_shadow import (
    OriginalDoorLeaderScope, inspect_original_door_figure_leader_shadow,
)


def _fixture(*,missing_tick=False, wrong_figure=False, shifted_cap=False,
             far_figure=False, invisible_baseline=False, dashed_tick=False,
             translucent_cap=False):
    pdf=fitz.open();page=pdf.new_page(width=700,height=700)
    def line(p,q,*,opacity=1.0,dashes=None):
        d=page.new_shape();d.draw_line(fitz.Point(*p),fitz.Point(*q))
        d.finish(color=(0,0,0),width=.48,stroke_opacity=opacity,dashes=dashes)
        d.commit()
    line((100,150),(230,150),opacity=0.0 if invisible_baseline else 1.0)
    line((100,170),(100,178),opacity=0.5 if translucent_cap else 1.0)
    line((200+(2 if shifted_cap else 0),170),(200+(2 if shifted_cap else 0),178))
    for x in (100,200):
        line((x,150),(x+3,147),
             dashes="[2 2] 0" if dashed_tick and x==100 else None)
        line((x,150),(x-3,153))
        line((x,150),(x,138))
        line((x,150),(x,160))
    page.insert_text((350,350) if far_figure else (145,160),
                     '70' if wrong_figure else '1000',fontsize=11)
    data=pdf.tobytes();pdf.close()
    return data,OriginalDoorLeaderScope(1,0,0,0,0,(1,2),(3,4,5,6),(7,8,9,10))


def _run(b=None,scope=None,**kwargs):
    if b is None:b,scope=_fixture()
    return inspect_original_door_figure_leader_shadow(
        b,source_sha256=sha256(b).hexdigest(),scope=scope,
        expected_cap_x_pdf_pt=(100.,200.),**kwargs)


def test_source_figure_leader_positive_does_not_grant_physical_door_or_width():
    r=_run()
    assert r.status=='SOURCE_FIGURE_LEADER_CANDIDATE'
    assert r.original_figured_text=='1000'
    assert r.original_gap_span_pdf_pt==100.
    assert r.shadow_only and not any((r.original_w4_wall_issued,
        r.actual_door_identity_proven,r.opening_jamb_identity_granted,
        r.physical_doorway_threshold_issued,r.figure_width_mm_authorized_for_physical_opening,
        r.floor_finish_area_issued,r.customer_projection_allowed))


def test_competing_short_70_word_never_becomes_1000_door_figure():
    b,scope=_fixture(wrong_figure=True)
    with pytest.raises(ValueError,match='figured dimension'):_run(b,scope)


def test_foreign_cap_does_not_match_figure_leader():
    b,scope=_fixture(shifted_cap=True)
    with pytest.raises(ValueError,match='cap'):_run(b,scope)


def test_spliced_tick_from_other_original_source_cannot_be_accepted():
    b,scope=_fixture()
    from dataclasses import replace
    with pytest.raises(ValueError,match='distinct'):
        _run(b,replace(scope,left_tick_paths=(3,4,5,7)))


def test_wrong_original_source_digest_rejected():
    b,scope=_fixture()
    with pytest.raises(ValueError,match='SHA'):
        inspect_original_door_figure_leader_shadow(b,source_sha256='0'*64,
            scope=scope,expected_cap_x_pdf_pt=(100.,200.))


def test_figure_cannot_use_global_wall_snap_tolerance():
    with pytest.raises(ValueError,match='tolerance'):
        _run(tolerance_pdf_pt=2.5)


def test_wrong_original_page_address_rejected():
    b,scope=_fixture()
    from dataclasses import replace
    with pytest.raises(ValueError,match='page'):
        _run(b,replace(scope,page_number=2))


def test_private_original_maryborough_native_leader_source_if_provisioned():
    loc=os.environ.get('PLANREADER_MARYBOROUGH_ORIGINAL_PDF')
    if not loc:pytest.skip('original private PDF not provided to test runner')
    b=Path(loc).read_bytes()
    r=inspect_original_door_figure_leader_shadow(
        b,source_sha256=os.environ['PLANREADER_MARYBOROUGH_SOURCE_SHA256'],
        scope=OriginalDoorLeaderScope(11,62,0,0,25698,(2843,2850),
            (25699,25700,25701,25702),(25703,25704,25705,25706)),
        expected_cap_x_pdf_pt=(254.87999,311.75998))
    assert r.status=='SOURCE_FIGURE_LEADER_CANDIDATE'
    assert r.original_gap_span_pdf_pt==pytest.approx(56.87999,abs=.001)
    assert r.original_figured_text=='1000' and r.rival_same_line_word_texts==('70',)
    assert not r.figure_width_mm_authorized_for_physical_opening


def test_same_printed_1000_elsewhere_on_original_page_cannot_own_leader():
    """Authentic text source address alone does not prove dimension ownership."""
    original, scope = _fixture(far_figure=True)
    with pytest.raises(ValueError, match="glyph does not belong"):
        _run(original, scope)


@pytest.mark.parametrize("source_style", [
    {"invisible_baseline": True},
    {"dashed_tick": True},
    {"translucent_cap": True},
])
def test_invisible_dashed_or_partial_original_dimension_ink_cannot_prove_leader(source_style):
    source,scope=_fixture(**source_style)
    with pytest.raises(ValueError, match="not visible solid ink"):
        _run(source,scope)


@pytest.mark.parametrize("foreign_rgb", (
    (-0.1,0.0,0.0),
    (float("nan"),0.0,0.0),
    (0.0,float("inf"),0.0),
    (0.0,0.0,float("-inf")),
    (0.0,0.0,0.25),
))
def test_original_native_dimension_paint_must_have_finite_black_channels(foreign_rgb):
    from pb_gpt2_mary_original_figured_door_leader_shadow import _native_line
    native={"items":[("l",fitz.Point(20,30),fitz.Point(40,30))],
            "color":foreign_rgb,"fill":None,"stroke_opacity":1.0,
            "dashes":"[] 0","width":0.48}
    with pytest.raises(ValueError, match="black source line"):
        _native_line(None,[native],0)
    actual=dict(native,color=(0.0,0.0,0.0))
    assert _native_line(None,[actual],0)==(20.0,30.0,40.0,30.0,0.48)
