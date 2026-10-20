"""Original PDF-only, commercial-inert GPT2 cross-view cap witness tests."""
from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path
import fitz
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_gpt2_original_native_crossview_wall_caps_shadow import (
    NativeWallCapScope, audit_original_native_wall_cap_translation_shadow,
)


def _original_like_source(*, shifted_right=False, red_face=False):
    pdf=fitz.open()
    for page_index,shift in enumerate((0.,78.)):
        page=pdf.new_page(width=550,height=500)
        if shifted_right and page_index==1:
            shift+=10.
        def ink(a,b,color=(0,0,0)):
            p=page.new_shape()
            p.draw_line(fitz.Point(*a),fitz.Point(*b))
            p.finish(color=color,width=0.48)
            p.commit()
        ink((100+shift,100),(100+shift,110))
        ink((160+shift,110),(160+shift,100))
        ink((90+shift,100),(100+shift,100))
        ink((160+shift,100),(200+shift,100),
            color=(1,0,0) if red_face and page_index==1 else (0,0,0))
        ink((90+shift,110),(100+shift,110))
        ink((160+shift,110),(200+shift,110))
        page.insert_text((360,180),"UNRELATED PLAN NOTE")
    data=pdf.tobytes()
    pdf.close()
    return data


def _run(pdf=None,*,shifts=((43.92,0),(78.,0)),left=None,right=None,
         source_sha=None,**kwargs):
    if pdf is None: pdf=_original_like_source()
    return audit_original_native_wall_cap_translation_shadow(
        pdf,source_sha256=source_sha or sha256(pdf).hexdigest(),
        first=left or NativeWallCapScope(1,(0,1),(2,3,4,5)),
        second=right or NativeWallCapScope(2,(0,1),(2,3,4,5)),
        translations_pdf_pt=shifts,**kwargs)


def test_exact_original_two_cap_ink_selects_one_candidate_not_physical_wall():
    r=_run()
    assert r.status is EvidenceResolutionStatus.CANDIDATE
    assert r.compatible_translations_pdf_pt == ((78.,0.),)
    assert [x["source_ink_compatible"] for x in r.original_translation_receipts] == [False,True]
    assert r.first.cap_x_pdf_pt == (100.,160.)
    assert r.second.cap_x_pdf_pt == (178.,238.)
    assert r.shadow_only
    assert not any((r.original_w4_wall_issued,r.physical_jamb_issued,
                    r.doorway_threshold_issued,r.physical_floor_issued,
                    r.material_issued,r.firm_area_issued,
                    r.commercial_projection_allowed))


def test_displaced_original_wall_cap_abstains_even_with_nearby_mark():
    r=_run(_original_like_source(shifted_right=True))
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert r.compatible_translations_pdf_pt == ()
    assert all(not x["source_ink_compatible"] for x in r.original_translation_receipts)


def test_same_source_ink_two_matching_transforms_cannot_select_nearest():
    r=_run(shifts=((78.,0.),(78.1,0.)))
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert len(r.compatible_translations_pdf_pt)==2
    assert not r.physical_floor_issued


def test_foreign_colored_wall_face_never_becomes_source_wall():
    with pytest.raises(ValueError,match="black line"):
        _run(_original_like_source(red_face=True))


@pytest.mark.parametrize("caps,faces",[
    ((0,0),(2,3,4,5)),
    ((0,9999),(2,3,4,5)),
    ((0,1),(2,3,3,5)),
    ((0,1),(2,3,4,1)),
])
def test_missing_duplicate_or_spliced_original_path_fails_closed(caps,faces):
    with pytest.raises(ValueError):
        _run(left=NativeWallCapScope(1,caps,faces))


def test_original_wrong_source_sha_or_page_fails_before_any_grant():
    data=_original_like_source()
    with pytest.raises(ValueError,match="SHA"):
        _run(data,source_sha="0"*64)
    with pytest.raises(ValueError,match="pages"):
        _run(data,right=NativeWallCapScope(1,(0,1),(2,3,4,5)))


def test_excessive_source_tolerance_not_wall_snap_authority():
    with pytest.raises(ValueError,match="tolerance"):
        _run(native_witness_tolerance_pt=2.5)
    assert _run(shifts=((81.,0.),)).status is EvidenceResolutionStatus.ABSTAINED


def test_candidate_permutation_and_source_byte_invariance():
    data=_original_like_source()
    before=sha256(data).hexdigest()
    a=_run(data,shifts=((78.,0.),(43.92,0.)))
    b=_run(data,shifts=((43.92,0.),(78.,0.)))
    assert a==b
    assert sha256(data).hexdigest()==before


def test_duplicate_source_hypothesis_does_not_vote_twice():
    with pytest.raises(ValueError,match="repeated"):
        _run(shifts=((78.,0.),(78.,0.)))


def test_original_maryborough_p7_p11_when_owner_pdf_provisioned():
    private_path=os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not private_path:
        pytest.skip("owner-original PDF missing; source blocked rather than fixture")
    private_pdf=Path(private_path).read_bytes()
    digest=os.environ["PLANREADER_MARYBOROUGH_SOURCE_SHA256"]
    r=_run(
        private_pdf,source_sha=digest,
        left=NativeWallCapScope(7,(52623,52630),(52624,52629,52622,52625)),
        right=NativeWallCapScope(11,(2843,2850),(2844,2849,2842,2845)),
    )
    assert r.status is EvidenceResolutionStatus.CANDIDATE
    assert r.compatible_translations_pdf_pt == ((78.,0.),)
    assert r.first.cap_x_pdf_pt == (177.12,233.76)
    assert r.second.cap_x_pdf_pt == (254.88,311.76)
    assert not r.doorway_threshold_issued and not r.firm_area_issued
