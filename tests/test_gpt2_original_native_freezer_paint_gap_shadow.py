"""Original-painted D17 thick-gap vs thin-bridge source role proofs only."""
from hashlib import sha256
from pathlib import Path
import os
import fitz
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_gpt2_original_native_freezer_paint_gap_shadow import (
    NativePaintGapScope,audit_original_paint_gap_crossview_shadow,
)


def _pdf(*, displaced=False, thick_bridge=False, same_width=False,
         invisible_selected=False, dashed_selected=False,
         invisible_bridge=False, dashed_bridge=False,
         partial_bridge=False, endpoint_return=False,
         unrelated_thick_wall=False, thick_rect_bridge=False,
         unrelated_thick_rect=False, invisible_thick_rect=False,
         dashed_thick_rect=False, filled_black_rect=False,
         filled_rect_invisible=False, filled_rect_white=False,
         filled_rect_unrelated=False, filled_rect_partial=False,
         filled_polygon=False, polygon_partial=False,
         polygon_white=False, polygon_invisible=False,
         polygon_unrelated=False):
    p=fitz.open()
    for index,dx in enumerate((0.,77.76)):
        if displaced and index:dx+=10
        page=p.new_page(width=650,height=500)
        def line(a,b,width,*,opacity=1.0,dashes=None):
            d=page.new_shape()
            d.draw_line(fitz.Point(*a),fitz.Point(*b))
            d.finish(color=(0,0,0),width=width,
                     stroke_opacity=opacity,dashes=dashes)
            d.commit()
        for y in (100.,104.):
            line((50+dx,y),(100+dx,y),.96)
            line((160+dx,y),(240+dx,y),.96)
            line((100+dx,y),(160+dx,y),.96 if same_width else .48,
                 opacity=0.0 if invisible_selected and index else 1.0,
                 dashes="[2 2] 0" if dashed_selected and index else None)
        if thick_bridge and index:
            line((100+dx,100),(160+dx,100),.96,
                 opacity=0.0 if invisible_bridge else 1.0,
                 dashes="[2 2] 0" if dashed_bridge else None)
        if partial_bridge and index:
            line((100+dx,100),(112+dx,100),.96)
        if endpoint_return and index:
            line((159.8+dx,100),(164+dx,100),.96)
        if unrelated_thick_wall and index:
            line((260+dx,100),(300+dx,100),.96)

        # A solid BLACK native rectangle outline is one PyMuPDF "re" item,
        # even when its horizontal painted edge contradicts the thick gap.
        if (thick_rect_bridge or unrelated_thick_rect) and index:
            left = (100. if thick_rect_bridge else 260.) + dx
            right = (160. if thick_rect_bridge else 300.) + dx
            d = page.new_shape()
            d.draw_rect(fitz.Rect(left, 100., right, 104.))
            d.finish(
                color=(0, 0, 0), width=.96,
                stroke_opacity=0.0 if invisible_thick_rect else 1.0,
                dashes="[2 2] 0" if dashed_thick_rect else None,
            )
            d.commit()
        if (filled_black_rect or filled_rect_unrelated) and index:
            # An opaque fill-only `re` is visible PDF source paint despite
            # having NO stroked outline / linewidth / dash characteristics.
            left=(260. if filled_rect_unrelated else 100.)+dx
            right=(300. if filled_rect_unrelated else
                   112. if filled_rect_partial else 160.)+dx
            d=page.new_shape()
            d.draw_rect(fitz.Rect(left,99.,right,105.))
            d.finish(
                color=None,
                fill=(1,1,1) if filled_rect_white else (0,0,0),
                fill_opacity=0.0 if filled_rect_invisible else 1.0,
            )
            d.commit()
        if filled_polygon and index:
            # Native opaque fill-only closed polyline: PyMuPDF emits "l"
            # path items rather than "re" and no stroked outline.
            left=(260. if polygon_unrelated else 100.)+dx
            right=(300. if polygon_unrelated else
                   112. if polygon_partial else 160.)+dx
            d=page.new_shape()
            d.draw_polyline([
                fitz.Point(left,99.),fitz.Point(right,99.),
                fitz.Point(right,105.),fitz.Point(left,105.),
                fitz.Point(left,99.),
            ])
            d.finish(
                color=None,
                fill=(1,1,1) if polygon_white else (0,0,0),
                fill_opacity=0.0 if polygon_invisible else 1.0,
            )
            d.commit()
    b=p.tobytes();p.close();return b


def _scope(page):
    return NativePaintGapScope(page,(0,1,3,4),(2,5))


def _run(b=None,shifts=((77.76,0),(43.92,0))):
    b=b or _pdf()
    return audit_original_paint_gap_crossview_shadow(
        b,expected_sha256=sha256(b).hexdigest(),
        first=_scope(1),second=_scope(2),translations=shifts)


def test_thick_walls_broken_thin_filling_present_is_not_an_authorized_door():
    r=_run()
    assert r.status is EvidenceResolutionStatus.CANDIDATE
    assert r.matching_translation==(77.76,0.)
    assert [c[2] for c in r.candidate_translations]==[False,True]
    assert r.first.thick_width_pdf_pt==.96 and r.first.thin_width_pdf_pt==.48
    assert r.shadow_only
    assert not any((r.structural_wall_owned,r.physical_door_owned,
                    r.doorway_threshold_owned,r.material_floor_owned,
                    r.metric_area_owned,r.firm_quantity_issued,
                    r.commercial_projection_allowed))


def test_crossing_thick_original_wall_ink_cannot_be_inferred_as_thin_opening():
    with pytest.raises(ValueError,match="competing original thick"):
        _run(_pdf(thick_bridge=True))


def test_same_paint_width_cannot_assign_door_filling_role():
    with pytest.raises(ValueError,match="paint-width roles"):
        _run(_pdf(same_width=True))


def test_displaced_gap_retains_negative_cross_view_original():
    assert _run(_pdf(displaced=True)).status is EvidenceResolutionStatus.ABSTAINED


def test_multiple_supported_rivals_do_not_select_first():
    assert _run(shifts=((77.76,0),(77.86,0))).status is EvidenceResolutionStatus.ABSTAINED


def test_wrong_sha_and_duplicate_original_page_source_rejected():
    b=_pdf()
    with pytest.raises(ValueError,match="SHA"):
        audit_original_paint_gap_crossview_shadow(
            b,expected_sha256="0"*64,first=_scope(1),second=_scope(2),
            translations=((77.76,0),))
    with pytest.raises(ValueError,match="page"):
        audit_original_paint_gap_crossview_shadow(
            b,expected_sha256=sha256(b).hexdigest(),first=_scope(1),
            second=_scope(1),translations=((77.76,0),))


def test_source_transform_order_invariance_and_immutable_bytes():
    b=_pdf();before=sha256(b).hexdigest()
    a=_run(b,shifts=((77.76,0),(43.92,0)))
    z=_run(b,shifts=((43.92,0),(77.76,0)))
    assert a==z and sha256(b).hexdigest()==before


def test_original_freezer_d17_private_pdf_if_provisioned():
    loc=os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not loc:
        pytest.skip("private source missing: source blocked")
    b=Path(loc).read_bytes()
    r=audit_original_paint_gap_crossview_shadow(
        b,expected_sha256=os.environ["PLANREADER_MARYBOROUGH_SOURCE_SHA256"],
        first=NativePaintGapScope(7,(53737,53734,53738,53736),(53740,53741)),
        second=NativePaintGapScope(11,(2943,2940,2944,2942),(2946,2949)),
        translations=((77.76,0),(43.92,0)))
    assert r.matching_translation==(77.76,0.)
    assert not r.physical_door_owned and not r.firm_quantity_issued


@pytest.mark.parametrize("bad_source", [
    {"invisible_selected": True},
    {"dashed_selected": True},
])
def test_selected_thin_bridge_needs_visible_solid_original_paint(bad_source):
    with pytest.raises(ValueError, match="invisible or non-solid"):
        _run(_pdf(**bad_source))


@pytest.mark.parametrize("style", [
    {"invisible_bridge": True},
    {"dashed_bridge": True},
])
def test_nonvisible_or_drafting_thick_rival_does_not_counterfeit_a_real_wall(style):
    # A competing thick path must be visibly solid before it can veto
    # the selected gap. Its mere native drawing entry is not wall proof.
    r=_run(_pdf(thick_bridge=True, **style))
    assert r.status is EvidenceResolutionStatus.CANDIDATE
    assert r.matching_translation == (77.76, 0.)
    assert not r.structural_wall_owned
    assert not r.firm_quantity_issued


def test_original_thick_12pt_partial_source_bridge_blocks_painted_gap():
    # Previously an arbitrary >50% gap veto missed this real structural
    # contradiction; native diagnostic witness tolerance is only 0.25pt.
    with pytest.raises(ValueError,match="competing original thick"):
        _run(_pdf(partial_bridge=True))


def test_source_native_0p2pt_endpoint_return_is_not_a_real_partial_wall():
    # Owner-original Maryborough p7 has 0.24003pt genuine terminal return.
    # A negative-only source tolerance must preserve this exact figure.
    r=_run(_pdf(endpoint_return=True))
    assert r.status is EvidenceResolutionStatus.CANDIDATE
    assert not r.structural_wall_owned
    assert not r.firm_quantity_issued


def test_unrelated_original_solid_thick_stroke_preserves_valid_gap():
    """A separate source wall outside the selected gap is not a rival."""
    result = _run(_pdf(unrelated_thick_wall=True))
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.matching_translation == (77.76, 0.)
    assert not result.structural_wall_owned
    assert not result.firm_quantity_issued


def test_original_thick_rectangle_outline_edges_veto_contradictory_gap():
    # get_drawings returns ONE "re" primitive, not four "l" strokes.
    original = _pdf(thick_rect_bridge=True)
    with fitz.open(stream=original, filetype="pdf") as doc:
        rects = [
            item[0] for drawing in doc[1].get_drawings()
            for item in drawing["items"] if item[0] == "re"
        ]
    assert rects
    with pytest.raises(ValueError, match="competing original thick"):
        _run(original)


def test_unrelated_original_rectangle_outline_does_not_veto_gap():
    r = _run(_pdf(unrelated_thick_rect=True))
    assert r.status is EvidenceResolutionStatus.CANDIDATE
    assert r.matching_translation == (77.76, 0.)
    assert not r.structural_wall_owned and not r.firm_quantity_issued


@pytest.mark.parametrize("style", (
    {"invisible_thick_rect": True},
    {"dashed_thick_rect": True},
))
def test_nonvisible_rectangle_outline_cannot_fake_thick_wall_conflict(style):
    r = _run(_pdf(thick_rect_bridge=True, **style))
    assert r.status is EvidenceResolutionStatus.CANDIDATE
    assert not r.physical_door_owned and not r.commercial_projection_allowed


def test_rectangle_original_source_bytes_and_translation_order_preserved():
    raw = _pdf(unrelated_thick_rect=True)
    digest = sha256(raw).hexdigest()
    a = _run(raw, shifts=((77.76, 0), (43.92, 0)))
    b = _run(raw, shifts=((43.92, 0), (77.76, 0)))
    assert a == b
    assert sha256(raw).hexdigest() == digest


def test_opaque_black_filled_native_rectangle_without_stroke_blocks_gap():
    """Fill-only 're' must veto the gap, even without any black stroke."""
    raw=_pdf(filled_black_rect=True)
    with fitz.open(stream=raw,filetype="pdf") as doc:
        rival=doc[1].get_drawings()[-1]
        assert rival["fill"]==(0.0,0.0,0.0)
        assert rival["fill_opacity"]==1.0
        assert rival["color"] is None
        assert any(x[0]=="re" for x in rival["items"])
    with pytest.raises(ValueError,match="opaque black fill"):
        _run(raw)


def test_partially_overlapping_black_fill_still_blocks_original_wall_gap():
    with pytest.raises(ValueError,match="opaque black fill"):
        _run(_pdf(filled_black_rect=True,filled_rect_partial=True))


@pytest.mark.parametrize("control",(
    {"filled_black_rect":True,"filled_rect_invisible":True},
    {"filled_black_rect":True,"filled_rect_white":True},
    {"filled_rect_unrelated":True},
))
def test_nonblack_invisible_or_unrelated_native_rectangle_fill_is_not_wall_rival(control):
    source=_pdf(**control)
    result=_run(source)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.matching_translation==(77.76,0.)
    assert not result.structural_wall_owned
    assert not result.doorway_threshold_owned
    assert not result.firm_quantity_issued


def test_filled_native_rectangle_original_source_bytes_unchanged():
    source=_pdf(filled_black_rect=True,filled_rect_white=True)
    original=sha256(source).hexdigest()
    assert _run(source).status is EvidenceResolutionStatus.CANDIDATE
    assert sha256(source).hexdigest()==original



def test_source_visible_fill_only_closed_polygon_blocks_freezer_gap():
    raw=_pdf(filled_polygon=True)
    with fitz.open(stream=raw,filetype="pdf") as doc:
        rival=doc[1].get_drawings()[-1]
        assert rival["fill"]==(0.0,0.0,0.0)
        assert rival["fill_opacity"]==1.0
        assert rival["color"] is None
        assert any(item[0]=="l" for item in rival["items"])
        assert not any(item[0]=="re" for item in rival["items"])
    with pytest.raises(ValueError,match="opaque black fill"):
        _run(raw)


def test_source_visible_partial_polygon_fill_still_vetoes_gap():
    with pytest.raises(ValueError,match="opaque black fill"):
        _run(_pdf(filled_polygon=True,polygon_partial=True))


@pytest.mark.parametrize("control",(
    {"filled_polygon":True,"polygon_white":True},
    {"filled_polygon":True,"polygon_invisible":True},
    {"filled_polygon":True,"polygon_unrelated":True},
))
def test_nonblack_invisible_or_unrelated_polygon_fill_not_a_rival(control):
    source=_pdf(**control)
    result=_run(source)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.matching_translation==(77.76,0.)
    assert not result.structural_wall_owned
    assert not result.physical_door_owned
    assert not result.firm_quantity_issued


def test_polygon_source_bytes_immutable_even_when_negative():
    source=_pdf(filled_polygon=True)
    before=sha256(source).hexdigest()
    with pytest.raises(ValueError,match="opaque black fill"):
        _run(source)
    assert sha256(source).hexdigest()==before
