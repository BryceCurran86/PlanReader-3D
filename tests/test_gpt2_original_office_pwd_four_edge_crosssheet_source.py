"""Original OFFICE/PWD wall sides and gaps are source ink, not finished areas."""
import hashlib
from pathlib import Path
import fitz
import pytest
from tools.diag_original_room_four_edge_source_ink_shadow import (
    audit_source_enclosure_correspondence as audit,
)

SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
OFFICE={
    "left":("d52239i0","d2657i0"),
    "right":("d66216i0","d3058i0"),
    "bottom":("d53725i0","d2931i0"),
    "top_partial":("d52625i0","d2845i0"),
}
PWD={
    "left":("d66215i0","d3057i0"),
    "right":("d53702i0","d2908i0"),
    "bottom":("d53724i0","d2930i0"),
    "top_partial":("d52626i0","d2846i0"),
}


@pytest.mark.parametrize("pair,expected_gap",[(OFFICE,60.24),(PWD,64.08)])
def test_exact_original_crosssheet_room_ink_positive_door_gaps_unclosed(pair,expected_gap):
    source=SOURCE.read_bytes()
    assert hashlib.sha256(source).hexdigest()==SHA
    receipt=audit(source,expected_sha256=SHA,floor_page_1_based=7,
            finish_page_1_based=11,original_side_pairs=pair,
            expected_translation_pdf_pts=(78.,0.))
    assert len(receipt["original_witnesses"])==4
    opening=receipt["original_top_gap_pdf_pts"]
    assert round(opening[1][0]-opening[0][0],2)==expected_gap
    assert receipt["original_top_gap_is_a_door_without_jamb_proof"] is False
    assert receipt["canonical_cross_sheet_physical_room_equality_granted"] is False
    assert receipt["source_finished_face_and_area_verified"] is False
    assert receipt["new_firm_quantities"]==0
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SHA


def test_original_source_face_rivals_and_unverified_door_gap_do_not_convert_to_firm():
    b=SOURCE.read_bytes()
    near={**OFFICE,"left":("d66216i0","d3058i0")}
    with pytest.raises(ValueError,match="distinct_source_path_item"):
        audit(b,expected_sha256=SHA,floor_page_1_based=7,
            finish_page_1_based=11,original_side_pairs=near,
            expected_translation_pdf_pts=(78.,0.))
    with pytest.raises(ValueError,match="source_side_ink_or_translation_conflict"):
        audit(b,expected_sha256=SHA,floor_page_1_based=7,
            finish_page_1_based=11,original_side_pairs=OFFICE,
            expected_translation_pdf_pts=(77.76,0.))


def test_swapping_a_face_from_pwd_to_office_abstains_instead_of_splicing_room():
    b=SOURCE.read_bytes()
    spliced={**OFFICE,"right":PWD["right"]}
    with pytest.raises(ValueError,match="native_original_wall_side_or_doorway_gap_conflict"):
        audit(b,expected_sha256=SHA,floor_page_1_based=7,
            finish_page_1_based=11,original_side_pairs=spliced,
            expected_translation_pdf_pts=(78.,0.))


def test_source_page_or_sha_mutation_abstains_without_partial_receipt():
    original=SOURCE.read_bytes()
    kwargs={"expected_sha256":SHA,"floor_page_1_based":7,
            "finish_page_1_based":11,"original_side_pairs":OFFICE,
            "expected_translation_pdf_pts":(78.,0.)}
    with pytest.raises(ValueError,match="original_source_sha_mismatch"):
        audit(original+b"tampered",**kwargs)
    with pytest.raises(ValueError,match="distinct_original_source_pages_required"):
        audit(original,**{**kwargs,"finish_page_1_based":7})
    with pytest.raises(ValueError,match="four_explicit_original_edge_pair_candidates"):
        audit(original,**{**kwargs,"original_side_pairs":{"left":OFFICE["left"]}})


def test_unavailable_source_path_and_safety_cap_fail_closed():
    source=SOURCE.read_bytes()
    with pytest.raises(ValueError,match="original_native_path_item_missing"):
        audit(source,expected_sha256=SHA,floor_page_1_based=7,
            finish_page_1_based=11,original_side_pairs={**OFFICE,"left":("d999999i0","d2657i0")},
            expected_translation_pdf_pts=(78.,0.))
    result=audit(source,expected_sha256=SHA,floor_page_1_based=7,
            finish_page_1_based=11,original_side_pairs=OFFICE,
            expected_translation_pdf_pts=(78.,0.),max_native_paths=100)
    assert result["status"]=="source_path_cap_exceeded"
    assert not result["room_authority_granted"]
