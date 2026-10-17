"""Original FREEZER display-cabinet source is not a structural room wall."""
import hashlib
from pathlib import Path
import fitz
import pytest
from tools.diag_original_freezer_manufactured_frontage_owner_shadow import (
    audit_original_manufactured_frontage_competitors as audit,
)
SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
BASE={
    "expected_sha256":SHA,"floor_page":7,"finish_page":11,"schedule_page":28,
    "original_floor_bbox":(350.,1150.,620.,1310.),
    "original_finish_bbox":(425.,1150.,710.,1310.),
    "inner_front_source_ids":("d62621i0","d62620i0"),
    "outer_case_source_ids":("d62512i0","d62523i0"),
    "access_door_code":"D17",
    "manufacturer_door_codes":("D18","D19"),
    "expected_translation_pdf_pts":(78.,0.),
}


@pytest.mark.skipif(not SOURCE.is_file(), reason="private original PDF unavailable in merge CI; separate SHA-pinned source acceptance required")
def test_original_manufactured_frontage_and_outer_case_are_distinct_native_ink():
    raw=SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    r=audit(raw,**BASE)
    assert r["inner_original_x_pdf_pts"]==588.24
    assert r["outer_case_original_x_pdf_pts"]==596.88
    assert r["original_ink_column_separation_pdf_pts"]==8.64
    assert r["original_double_cabinet_ink_not_structural_wall_proof"]
    assert not r["physical_source_room_enclosed"]
    assert not r["source_metric_wall_or_opening_width_proven"]
    assert r["new_firm_quantities"]==0
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SHA


@pytest.mark.skipif(not SOURCE.is_file(), reason="private original PDF unavailable in merge CI; separate SHA-pinned source acceptance required")
def test_original_d17_access_door_is_not_manufacturer_display_shelving_door():
    r=audit(SOURCE.read_bytes(),**BASE)
    rows=r["original_access_and_manufactured_door_rows"]
    assert "SLIDING" in rows["D17"]["untrusted_original_literals"]
    for c in ("D18","D19"):
        words=rows[c]["untrusted_original_literals"]
        assert {"AS","PER","MANUFACTURER","DISPLAY","SHELVING"}<=set(words)
        assert not rows[c]["source_row_text_integrity_granted"]
        assert not rows[c]["physical_plan_opening_owner_granted"]
    assert r["display_door_count_default_one_forbidden"]


@pytest.mark.skipif(not SOURCE.is_file(), reason="private original PDF unavailable in merge CI; separate SHA-pinned source acceptance required")
def test_outside_case_substitution_does_not_authenticate_room_face():
    raw=SOURCE.read_bytes()
    with pytest.raises(ValueError,match="inside_manufactured_frontage_and_outer_case_conflict"):
        audit(raw,**{**BASE,
           "inner_front_source_ids":BASE["outer_case_source_ids"],
           "outer_case_source_ids":BASE["inner_front_source_ids"]})
    with pytest.raises(ValueError,match="separate_manufactured_frontage"):
        audit(raw,**{**BASE,"outer_case_source_ids":BASE["inner_front_source_ids"]})


@pytest.mark.skipif(not SOURCE.is_file(), reason="private original PDF unavailable in merge CI; separate SHA-pinned source acceptance required")
def test_original_schedule_label_swaps_fail_not_default_a_shelving_count():
    raw=SOURCE.read_bytes()
    with pytest.raises(ValueError,match="access_door_source_type_unresolved"):
        audit(raw,**{**BASE,"access_door_code":"D18",
                     "manufacturer_door_codes":("D17","D19")})
    with pytest.raises(ValueError,match="display_cabinet_source_type_unresolved"):
        audit(raw,**{**BASE,"manufacturer_door_codes":("D18","D28")})


@pytest.mark.skipif(not SOURCE.is_file(), reason="private original PDF unavailable in merge CI; separate SHA-pinned source acceptance required")
def test_missing_actual_source_path_sha_and_bounded_universe_abstain():
    raw=SOURCE.read_bytes()
    with pytest.raises(ValueError,match="immutable_source_sha_required"):
        audit(raw+b"altered",**BASE)
    with pytest.raises(ValueError,match="missing_original_frontage_source_pair"):
        audit(raw,**{**BASE,"inner_front_source_ids":("d999999i0","d62620i0")})
