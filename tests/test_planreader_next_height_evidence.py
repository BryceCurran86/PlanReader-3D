"""Shadow source-height identification; never assume 2740 TP or joinery 2100."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from planreader_next.engine import NativePage, NativeWord, NativeSegment, SourceConflict, load_native_page
from planreader_next.height_evidence import (
    SECTION_FFL_FCL, RCP_MATERIAL_HEIGHT, section_ffl_fcl_heights,
    rcp_material_height_callouts, height_evidence_inventory,
    validate_height_receipt,
)


def _word(ref, text, x, y, dx=11, dy=10):
    return NativeWord(ref, text, (x, y, x+dx, y+dy))


def _section():
    return NativePage(
        "a"*64, 6,
        (
            _word("w2700","2700",204,454,7,18),
            _word("w2740","2740",178,454,7,18),
            _word("w2100","2100",226,475,7,18),
            _word("wffl","FFL",186,533,11,8),
            _word("wfcl","FCL",209,392,12,10),
            _word("wtp","TP",186,390,9,10),
        ), (),
        (
            NativeSegment("dim_2700","line",207,392,207,544),
            NativeSegment("dim_2740","line",184.5,389,184.5,545),
        ),
    )


def _rcp():
    return NativePage(
        "b"*64, 8, (
            _word("word:b0:l0:w0:i0","2400",400,1500,12,20),
            _word("word:b0:l1:w0:i1","GRID",386.5,1500.3,12,20),
            _word("word:b1:l0:w0:i2","2500",400,1600,12,20),
            _word("word:b1:l1:w0:i3","IPF1",386.5,1600.3,12,20),
            _word("word:b2:l0:w0:i4","3000",400,1700,12,20),
            _word("word:b2:l1:w0:i5","FPB",386.5,1700.3,12,20),
            _word("word:b3:l0:w0:i6","1980",400,1800,12,20),
            _word("word:b3:l2:w0:i7","IPF1",386.5,1800.3,12,20),
            _word("word:b4:l0:w0:i8","2700",400,1900,12,20),
            _word("word:b5:l0:w0:i9","WPB",386.5,1900.3,12,20),
            _word("word:b6:l0:w0:i10","1100",400,2000,12,20),
            _word("word:b6:l1:w0:i11","GRID",386.5,2000.3,12,20),
        ), (), (),
    )


def test_ffl_to_fcl_owned_section_height_not_top_plate_or_joinery():
    found=section_ffl_fcl_heights(_section())
    assert len(found)==1
    receipt=found[0]
    assert receipt["height_mm"]=="2700"
    assert receipt["height_word_ref"]=="w2700"
    assert receipt["dimension_segment_refs"]==["dim_2700"]
    assert receipt["witness_word_refs"]==["wffl","wfcl"]
    assert not receipt["commercial_publishable"]
    assert not receipt["wall_or_room_scope_authenticated"]
    assert validate_height_receipt(_section(), receipt)==receipt


def test_rcp_material_height_bubble_pairs_and_nearby_numbers_abstain():
    found=rcp_material_height_callouts(_rcp())
    assert {(x["height_mm"],x["material_code_candidate"]) for x in found} == {
        ("2400","GRID"),("2500","IPF1"),("3000","FPB")
    }
    assert not any(x["height_mm"] in ("1980","2700","1100") for x in found)
    assert all(x["ceiling_zone_authenticated"] is False for x in found)
    first=found[0]
    assert validate_height_receipt(_rcp(),first)==first


def test_untrusted_height_value_and_wrong_source_receipts_rejected():
    page=_section()
    receipt=section_ffl_fcl_heights(page)[0]
    bad=deepcopy(receipt)
    bad["height_mm"]="2740"
    with pytest.raises(SourceConflict,match="height_receipt_value_mismatch"):
        validate_height_receipt(page,bad)
    bad=deepcopy(receipt);bad["source_sha256"]="0"*64
    with pytest.raises(SourceConflict,match="height_receipt_source_mismatch"):
        validate_height_receipt(page,bad)
    bad=deepcopy(receipt);bad["dimension_segment_refs"]=["not-this-line"]
    with pytest.raises(SourceConflict,match="height_receipt_not_uniquely_source_owned"):
        validate_height_receipt(page,bad)


def test_source_viewport_excludes_legend_sample_without_fabricated_zone():
    page=_rcp()
    found=rcp_material_height_callouts(page,viewport_pdf_pts=[370,1490,430,1650])
    assert [(r["height_mm"],r["material_code_candidate"]) for r in found] == [
        ("2400","GRID"),("2500","IPF1")
    ]
    assert not any(r["ceiling_zone_authenticated"] for r in found)
    with pytest.raises(SourceConflict,match="height_viewport_invalid"):
        rcp_material_height_callouts(page,viewport_pdf_pts=[10,10,9,30])


def test_inventory_does_not_make_a_ceiling_area_or_building_quantity():
    inventory=height_evidence_inventory(_section())
    assert len(inventory["section_ffl_fcl"])==1
    assert not inventory["rcp_material_callouts"]
    assert inventory["official_score"] is None
    assert not inventory["commercial_publishable"]
    assert not any("quantity_m2" in row for row in inventory["section_ffl_fcl"])


def test_real_3laurel_section_height_if_authenticated_original_is_provisioned():
    import os
    source=os.environ.get("PLANREADER_3LAUREL_ORIGINAL_PDF")
    if not source or not Path(source).is_file():
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN")
    page=load_native_page(Path(source),6)
    if page.source_sha256 != "014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e":
        raise AssertionError("original SHA mismatch")
    found=section_ffl_fcl_heights(page)
    assert len(found)==1
    assert found[0]["height_word_ref"]=="word:b30:l0:w0:i230"
    assert found[0]["height_mm"]=="2700"
    assert found[0]["dimension_segment_refs"]==["d5955i0"]


def test_real_maryborough_rcp_pairs_if_provisioned():
    import os
    source=os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not source or not Path(source).is_file():
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN")
    page=load_native_page(Path(source),8)
    if page.source_sha256 != "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007":
        raise AssertionError("original SHA mismatch")
    found=rcp_material_height_callouts(page)
    assert len(found)==18
    assert any(x["height_mm"]=="2400" and x["material_code_candidate"]=="GRID" for x in found)
    assert any(x["height_mm"]=="3000" and x["material_code_candidate"]=="FPB" for x in found)
    assert not any(x["height_mm"]=="1980" for x in found)
