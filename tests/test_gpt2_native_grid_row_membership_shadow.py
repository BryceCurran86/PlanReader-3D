"""Source-only native grid row membership; no door quantity, metric, or benchmark."""
from dataclasses import replace
from hashlib import sha256

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_door_schedule_authority import SourceDoorScheduleWord
from pb_gpt2_native_grid_row_membership_shadow import (
    NativeGridRowScope, inspect_original_native_grid_row_shadow,
)


def _case(*, duplicate_code=False, untrusted=False, shifted=0.0):
    pdf = fitz.open()
    page = pdf.new_page(width=420, height=340)
    for x in (100+shifted, 142+shifted):
        for a,b in ((30,100),(100,170),(170,260)):
            page.draw_line(fitz.Point(x,a),fitz.Point(x,b),
                           color=(0,0,0),width=.48)
    content = pdf.tobytes()
    pdf.close()
    words = [
        SourceDoorScheduleWord(
            observation_id=f"native:{i}",page_id="1",partition_id="page:1",
            block_no=i,line_no=0,word_no=0,literal=literal,
            trusted=(not untrusted or i != 2),
            bbox_pdf_pts=(x+shifted,y,x+shifted+width,y+10.0),
        ) for i,(literal,x,y,width) in enumerate((
            ("D13",106,217,20), ("TRUCK",106,196,30),
            ("SWING",107,142,29), ("920",106,75,18),
            ("D14",162,214,21),
            *((("D13",107,184,20),) if duplicate_code else ()),
        ))
    ]
    return content,tuple(words),NativeGridRowScope(
        page_number=1,left_boundary_paths=(0,1,2),
        right_boundary_paths=(3,4,5),code_address=(0,0,0))


def _audit(b=None, words=None, scope=None, **kwargs):
    if b is None:
        b, words, scope = _case()
    return inspect_original_native_grid_row_shadow(
        b,source_sha256=sha256(b).hexdigest(),
        words=words,scope=scope,**kwargs)


def test_original_ruled_row_connects_multiple_native_blocks_without_grants():
    b,w,s=_case()
    result=_audit(b,w,s)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.native_blocks==(0,1,2,3)
    assert result.code_observation_id=="native:0"
    assert result.competing_same_code_observation_ids==()
    assert result.first_unclosed_gate.endswith("no_kind_host_count_or_dimensions")
    assert result.shadow_only
    assert not any((result.source_dimension_authorized,
                    result.physical_door_identity_proven,
                    result.opening_count_granted,
                    result.firm_quantity_issued,
                    result.commercial_projection_allowed))
    assert b==b[:]


def test_source_grid_metamorphic_translation_preserves_membership():
    first,w,s=_case()
    moved,wm,sm=_case(shifted=33.0)
    assert _audit(first,w,s).native_blocks==_audit(moved,wm,sm).native_blocks


def test_competing_printed_code_stays_abstained():
    b,w,s=_case(duplicate_code=True)
    result=_audit(b,w,s)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "competing_or_untrusted" in result.first_unclosed_gate


def test_untrusted_original_word_blocks_source_membership():
    b,w,s=_case(untrusted=True)
    assert _audit(b,w,s).status is EvidenceResolutionStatus.ABSTAINED


def test_unrelated_outside_row_code_does_not_grant_extra_door():
    b,w,s=_case()
    duplicate=replace(w[-1],observation_id="native:outside",literal="D13")
    result=_audit(b,w[:-1]+(duplicate,),s)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.competing_same_code_observation_ids==("native:outside",)
    assert not result.opening_count_granted


def test_wrong_original_hash_cannot_use_source_ink():
    b,w,s=_case()
    with pytest.raises(ValueError,match="SHA"):
        inspect_original_native_grid_row_shadow(
            b,source_sha256="0"*64,words=w,scope=s)


@pytest.mark.parametrize("paths", [(0,1), (1,2), (0,0,2), (0,1,2,3)])
def test_partial_duplicate_or_foreign_boundary_sources_fail(paths):
    b,w,s=_case()
    with pytest.raises(ValueError):
        _audit(b,w,replace(s,left_boundary_paths=paths))


def test_wrong_page_and_code_address_fail_closed():
    b,w,s=_case()
    with pytest.raises(ValueError,match="page"):
        _audit(b,w,replace(s,page_number=2))
    with pytest.raises(ValueError,match="canonical"):
        _audit(b,w,replace(s,code_address=(1,0,0)))


def test_global_two_point_five_snap_is_not_grid_source_tolerance():
    with pytest.raises(ValueError,match="scope"):
        _audit(tolerance_pdf_pt=2.5)


def test_duplicate_native_word_addresses_are_rejected():
    b,w,s=_case()
    with pytest.raises(ValueError,match="duplicated"):
        _audit(b,w+(replace(w[2],observation_id="other"),),s)


def test_source_ink_and_word_universe_not_modified_by_shadow():
    b,w,s=_case()
    before=(b,w,s)
    first=_audit(b,w,s)
    second=_audit(b,w,s)
    assert first==second
    assert (b,w,s)==before
