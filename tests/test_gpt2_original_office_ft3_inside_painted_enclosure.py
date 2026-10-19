"""An original p11 FT3 mark may belong to OFFICE ink, not yet its floor."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_original_painted_enclosure_finish_mark_shadow import (
    audit_original_painted_enclosure_finish_word_candidates as audit,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
ORIGINAL_SIDES={
    "left":("d52239i0","d2657i0"),
    "right":("d66220i0","d3062i0"),
    "bottom":("d53725i0","d2931i0"),
    "top_partial":("d52625i0","d2845i0"),
}
SYNTHETIC_SIDES={
    role:(f"d{i}i0",f"d{i}i0")
    for i,role in enumerate(("left","right","bottom","top_partial"))
}


def _synthetic(*,duplicate_inside=False,crossing=False):
    doc=fitz.open()
    for offset in (0,78):
        p=doc.new_page(width=340,height=220)
        for a,b in (
            ((20,30),(20,150)),
            ((130,30),(130,150)),
            ((20,150),(129.52,150)),
            ((65,30),(129.52,30)),
        ):
            p.draw_line((a[0]+offset,a[1]),
                        (b[0]+offset,b[1]),
                        color=(0,0,0),width=.48)
        if offset:
            p.insert_text((118,90),"FT3")
            p.insert_text((260,90),"FT3")
            if duplicate_inside:
                p.insert_text((140,110),"FT3")
            if crossing:
                p.insert_text((205,135),"FT3")
    source=doc.tobytes()
    doc.close()
    return source


def _run(raw,**options):
    params={
        "expected_sha256":hashlib.sha256(raw).hexdigest(),
        "floor_page_1_based":1,
        "finish_page_1_based":2,
        "original_side_pairs":SYNTHETIC_SIDES,
        "expected_translation_pdf_pts":(78.,0.),
        "original_finish_code":"FT3",
    }
    params.update(options)
    return audit(raw,**params)


def test_one_native_ft3_word_inside_four_painted_sides_does_not_mint_area():
    row=_run(_synthetic())
    assert row["status"]=="one_original_finish_word_inside_painted_enclosure_candidate"
    assert len(row["source_original_finish_code_words_inside_painted_enclosure"])==1
    assert len(row["source_other_same_code_original_word_competitors"])==1
    assert row["source_original_finish_code_words_crossing_painted_boundary"]==()
    assert row["source_original_ink_floor_finish_correspondence"][
        "source_original_paint_contact_not_W2_endpoint_snap"] is True
    assert row["source_quantity_sealing_authority_granted"] is False
    assert row["source_finished_wall_face_authenticated"] is False
    assert row["new_firm_quantities"]==0


@pytest.mark.parametrize("extra",[
    {"duplicate_inside":True},
    {"crossing":True},
])
def test_extra_or_boundary_straddling_finish_mark_cannot_elect_a_single_owner(extra):
    result=_run(_synthetic(**extra))
    assert result["status"]=="original_finish_word_inside_painted_enclosure_abstained"
    assert result["first_remaining_authority_gate"]==(
        "original_printed_finish_code_room_ownership_not_unique"
    )
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("changes",[
    {"expected_sha256":"0"*64},
    {"expected_translation_pdf_pts":(77.,0.)},
    {"original_finish_code":"FT3 "},
    {"original_finish_code":None},
    {"max_native_words":1},
    {"original_side_pairs":{
        "left":("d0i0","d0i0"),
        "right":("d0i0","d1i0"),
        "bottom":("d2i0","d2i0"),
        "top_partial":("d3i0","d3i0"),
    }},
])
def test_missing_or_foreign_original_source_does_not_mint_finish_claim(changes):
    with pytest.raises(ValueError):
        _run(_synthetic(),**changes)


@pytest.mark.skipif(not ORIGINAL.is_file(),reason="private original PDF not provisioned")
def test_original_office_ft3_occurrence_owns_one_printed_ink_candidate_only():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    result=audit(
        raw,expected_sha256=SHA,
        floor_page_1_based=7,finish_page_1_based=11,
        original_side_pairs=ORIGINAL_SIDES,
        expected_translation_pdf_pts=(78.,0.),
        original_finish_code="FT3",
    )
    assert result["status"]=="one_original_finish_word_inside_painted_enclosure_candidate"
    mark=result["source_original_finish_code_words_inside_painted_enclosure"]
    assert len(mark)==1
    assert mark[0]["source_original_finish_word_address"]==(11,113,0,0)
    assert len(result["source_other_same_code_original_word_competitors"])==5
    assert result["source_original_finish_code_words_crossing_painted_boundary"]==()
    assert result["source_finished_wall_face_authenticated"] is False
    assert result["source_cross_page_physical_room_equivalence_authenticated"] is False
    assert result["new_firm_quantities"]==0
