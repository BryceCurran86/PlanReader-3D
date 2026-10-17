"""Original FT2 PWD and FT3 OFFICE marks inside candidates, never floor area."""
import hashlib
from pathlib import Path
import pytest
from tools.diag_original_finish_mark_in_room_ink_shadow import (
    audit_original_floor_finish_mark_enclosure_candidate as audit,
    _native_mark_containment_census as census,
)
PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
OFFICE={"left":("d52239i0","d2657i0"),
        "right":("d66216i0","d3058i0"),
        "bottom":("d53725i0","d2931i0"),
        "top_partial":("d52625i0","d2845i0")}
PWD={"left":("d66215i0","d3057i0"),
     "right":("d53702i0","d2908i0"),
     "bottom":("d53724i0","d2930i0"),
     "top_partial":("d52626i0","d2846i0")}


@pytest.mark.parametrize("edges,code,address",[
    (OFFICE,"FT3",[113,0,0]),
    (PWD,"FT2",[56,0,0]),
])
def test_original_mark_inside_strict_matched_source_ink_box_not_authenticated(edges,code,address):
    raw=PDF.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    out=audit(raw,expected_sha256=SHA,
              floor_page=7,finish_page=11,source_side_pairs=edges,
              translation_pdf_pts=(78.,0.),finish_code_literal=code)
    marks=out["source_mark_word_evidence"]
    assert marks["unique_native_code_word_in_enclosure"]
    assert len(marks["in_enclosure_candidates"])==1
    assert marks["in_enclosure_candidates"][0]["original_source_word_address"]==address
    assert not marks["physical_source_floor_owner_authenticated"]
    assert out["original_top_door_gap_remains_open"]
    assert not out["unique_original_w4_finished_face_owner_proven"]
    assert not out["source_mark_material_definition_issued"]
    assert not out["original_cross_sheet_floor_identity_issued"]
    assert out["new_firm_quantities"]==0


def test_source_name_alone_or_wrong_finish_mark_never_mints_room_finish():
    raw=PDF.read_bytes()
    out=audit(raw,expected_sha256=SHA,
              floor_page=7,finish_page=11,source_side_pairs=OFFICE,
              translation_pdf_pts=(78.,0.),finish_code_literal="FT2")
    assert not out["source_mark_word_evidence"]["unique_native_code_word_in_enclosure"]
    assert not out["source_mark_word_evidence"]["in_enclosure_candidates"]
    assert not out["original_cross_sheet_floor_identity_issued"]


def test_duplicate_same_literal_and_boundary_touching_original_bbox_abstain():
    words=[
        (20,20,30,30,"FT3",3,0,0),
        (22,23,32,33,"FT3",4,0,0),
        (0,20,10,30,"FT3",5,0,0),
        (44,20,50,28,"FT3",6,0,0),
    ]
    r=census(words,code="FT3",bbox=(10,10,45,45))
    assert len(r["in_enclosure_candidates"])==2
    assert not r["unique_native_code_word_in_enclosure"]
    assert all(not m["producer_issued_material_occurrence"] for m in r["in_enclosure_candidates"])
    assert not r["physical_source_floor_owner_authenticated"]


def test_source_sha_and_competing_doorway_wall_abort_containment():
    raw=PDF.read_bytes()
    with pytest.raises(ValueError,match="original_source_sha_mismatch"):
        audit(raw+b"tampered",expected_sha256=SHA,
              floor_page=7,finish_page=11,source_side_pairs=PWD,
              translation_pdf_pts=(78.,0.),finish_code_literal="FT2")
    with pytest.raises(ValueError,match="source_side_ink_or_translation_conflict"):
        audit(raw,expected_sha256=SHA,
              floor_page=7,finish_page=11,source_side_pairs=PWD,
              translation_pdf_pts=(77.76,0.),finish_code_literal="FT2")
