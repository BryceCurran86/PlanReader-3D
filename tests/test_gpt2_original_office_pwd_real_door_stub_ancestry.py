"""Original Maryborough native room-doorway five-stroke source ancestry.

Actual original bytes are private and must not be uploaded to public GitHub.
SHA-positive original acceptance is owner-only; no manufactured W4 quantities.
"""
from pathlib import Path
import hashlib
import pytest

from tools.diag_gpt2_original_room_doorway_ancestry_shadow import (
    audit_gpt2_original_room_doorway_ancestry_pair as audit,
)

SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"

# Five printed wall strokes, including the previously omitted real short
# native top wall stub at the left/right of the actual door opening.
OFFICE={
  7:("d52239i0","d66216i0","d53725i0","d52622i0","d52625i0"),
  9:("d2532i0","d2534i0","d1954i0","d1864i0","d1859i0"),
  11:("d2657i0","d3058i0","d2931i0","d2842i0","d2845i0"),
}
PWD={
  7:("d66215i0","d53702i0","d53724i0","d52626i0","d52631i0"),
  9:("d2343i0","d1934i0","d1955i0","d1858i0","d1854i0"),
  11:("d3057i0","d2908i0","d2930i0","d2846i0","d2851i0"),
}

@pytest.mark.skipif(not SOURCE.exists(),reason="owner-private original PDF is not in GitHub checkout")
@pytest.mark.parametrize("room,second_page,translation,expected_status,expected_gap",[
    (OFFICE,9,106.32,"original_doorway_all_printed_wall_strokes_match_candidate",56.64),
    (PWD,9,106.32,"original_doorway_all_printed_wall_strokes_match_candidate",56.64),
    (PWD,11,78.,"original_doorway_all_printed_wall_strokes_match_candidate",56.64),
    (OFFICE,11,78.,"original_doorway_source_endpoint_rival_conflict",56.88),
])
def test_original_five_source_strokes_exactly_account_for_doorway_no_auto_snap(
    room,second_page,translation,expected_status,expected_gap
):
    source=SOURCE.read_bytes()
    assert hashlib.sha256(source).hexdigest()==SHA
    result=audit(
        source,expected_sha256=SHA,
        floor_page_1_based=7,second_page_1_based=second_page,
        original_floor_source_edge_ids=room[7],
        original_second_source_edge_ids=room[second_page],
        original_translation_pdf_pts=(translation,0.),
    )
    assert result["status"]==expected_status
    assert result["original_door_gap_length_floor_pdf_pts"]==56.64
    assert result["original_door_gap_length_second_pdf_pts"]==expected_gap
    assert not result["source_cross_sheet_physical_wall_issuer_granted"]
    assert not result["source_room_finished_face_binding_granted"]
    assert not result["source_virtual_closing_wall_painted"]
    assert result["new_firm_quantities"]==0
    if second_page==11 and room is OFFICE:
        assert result["first_unclosed_gate"]=="original_short_wall_stub_disagrees_across_sheets"
        assert result["original_unmatched_second_side_ink_pdf_pts"]
        assert result["original_unmatched_transferred_floor_ink_pdf_pts"]
        # 0.24 pt mismatch is real; 2.5pt snapping is FORBIDDEN here.
        assert [254.88,1383.2] in result["original_second_unclosed_gap_endpoints_pdf_pts"]


@pytest.mark.skipif(not SOURCE.exists(),reason="private original SHA acceptance required")
def test_sha_tampering_is_global_failure_not_silent_source_gap():
    raw=SOURCE.read_bytes()
    with pytest.raises(ValueError,match="original_source_sha_mismatch"):
        audit(
            raw+b"invalid",expected_sha256=SHA,
            floor_page_1_based=7,second_page_1_based=9,
            original_floor_source_edge_ids=PWD[7],
            original_second_source_edge_ids=PWD[9],
            original_translation_pdf_pts=(106.32,0.),
        )
