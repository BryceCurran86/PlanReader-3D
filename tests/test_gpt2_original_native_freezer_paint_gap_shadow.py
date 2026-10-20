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


def _pdf(*, displaced=False, thick_bridge=False, same_width=False):
    p=fitz.open()
    for index,dx in enumerate((0.,77.76)):
        if displaced and index:dx+=10
        page=p.new_page(width=650,height=500)
        def line(a,b,width):
            d=page.new_shape()
            d.draw_line(fitz.Point(*a),fitz.Point(*b))
            d.finish(color=(0,0,0),width=width);d.commit()
        for y in (100.,104.):
            line((50+dx,y),(100+dx,y),.96)
            line((160+dx,y),(240+dx,y),.96)
            line((100+dx,y),(160+dx,y),.96 if same_width else .48)
        if thick_bridge and index:
            line((100+dx,100),(160+dx,100),.96)
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
