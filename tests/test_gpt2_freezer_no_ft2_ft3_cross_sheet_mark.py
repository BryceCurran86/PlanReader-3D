"""Original FREEZER source-ring cannot borrow any of thirteen FT2/FT3 marks."""
from __future__ import annotations
import hashlib
from pathlib import Path
import fitz

import pytest
from tests.test_gpt2_native_ft2_ft3_original_mark_census import _synthetic
from tools.diag_gpt2_original_crosssheet_finish_mark_floor_candidate import (
    audit_original_crosssheet_candidate_floor_finish_words as audit,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _call(raw,**updates):
    kw={
        "expected_sha256":hashlib.sha256(raw).hexdigest(),
        "original_floor_page_1_based":2,
        "original_finish_page_1_based":1,
        "candidate_original_floor_bbox_pdf_pts":(10.,0.,50.,50.),
        "unproven_original_source_translation_pdf_pts":(20.,0.),
        "original_finish_viewport_id":"independently-authenticated-source-needed",
    }
    kw.update(updates)
    return audit(raw,**kw)


def test_positive_printed_source_word_never_grants_physical_floor():
    doc=fitz.open(stream=_synthetic(),filetype="pdf")
    doc.new_page()
    source=doc.tobytes()
    doc.close()
    row=_call(source)
    assert len(row["native_finish_words_inside_candidate"])==1
    assert row["cross_page_structural_room_equivalence_proven"] is False
    assert row["new_firm_quantities"]==0


@pytest.mark.parametrize("invalid",[
    {"expected_sha256":"0"*64},
    {"unproven_original_source_translation_pdf_pts":(float("nan"),0.)},
    {"candidate_original_floor_bbox_pdf_pts":(0,0,0,20)},
    {"original_floor_page_1_based":1},
])
def test_false_source_sha_geometry_or_page_identity_fail_closed(invalid):
    doc=fitz.open(stream=_synthetic(),filetype="pdf")
    doc.new_page()
    data=doc.tobytes()
    doc.close()
    with pytest.raises(ValueError):
        _call(data,**invalid)


@pytest.mark.skipif(not ORIGINAL.is_file(),reason="private original not provisioned")
def test_original_freezer_has_no_ft2_ft3_native_mark_under_registration_hypothesis():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    row=audit(
        raw,expected_sha256=SHA,
        original_floor_page_1_based=7,
        original_finish_page_1_based=11,
        candidate_original_floor_bbox_pdf_pts=(368.64,1179.44,588.24,1275.92),
        unproven_original_source_translation_pdf_pts=(78.,0.),
        original_finish_viewport_id="source_plan_view_c57aa3592e81d66ad2fa5a92",
    )
    assert row["status"]=="no_printed_finish_mark_inside_unproven_translated_floor_candidate"
    assert row["native_finish_words_inside_candidate"]==()
    assert len(row["all_native_finish_word_competitors_outside_candidate"])==15
    assert row["new_firm_quantities"]==0
