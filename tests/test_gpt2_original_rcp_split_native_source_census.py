"""Native RCP ink crossing the derived viewport cut is a source blocker."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_original_rcp_native_partition_crossing_shadow import (
    audit_original_source_rcp_ink_partition_crossings as audit,
)

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
DIVIDER = 1379.6826171875


def _sample():
    doc=fitz.open()
    page=doc.new_page(width=200,height=200)
    page.draw_line((50,10),(50,120),color=(0,0,0),width=.48)
    page.insert_text((70,30),"GRID")
    page.insert_text((70,110),"IPF1")
    raw=doc.tobytes()
    doc.close()
    return raw


def _run(raw,**changes):
    fields={
        "expected_sha256":hashlib.sha256(raw).hexdigest(),
        "page_1_based":1,
        "proposed_partition_coordinate_pdf_pts":50.,
    }
    fields.update(changes)
    return audit(raw,**fields)


def test_painted_crossing_and_material_marks_on_both_sides_never_make_new_rcp_view():
    out=_run(_sample())
    assert len(out["original_native_black_vertical_line_crossings"])==1
    assert out["original_native_black_vertical_line_crossings"][0][
        "original_native_path_item_id"]=="d0i0"
    bands=out["original_material_code_words_by_proposed_coordinate_band"]
    assert len(bands["lower_pdf_coordinate_band"])==1
    assert len(bands["higher_pdf_coordinate_band"])==1
    assert out["proposed_partition_severs_original_ink"] is True
    assert out["source_partition_owner_authenticated"] is False
    assert out["new_firm_quantities"]==0


@pytest.mark.parametrize("kwargs", [
    {"expected_sha256":"0"*64},
    {"page_1_based":0},
    {"proposed_partition_coordinate_pdf_pts":float("nan")},
    {"minimum_original_black_stroke_width_pdf_pts":0},
    {"source_material_codes":("GRID","GRID")},
    {"maximum_native_paths":0},
    {"maximum_crossings":0},
])
def test_untrusted_rcp_source_or_partition_fails_closed(kwargs):
    with pytest.raises(ValueError):
        _run(_sample(),**kwargs)


def test_bounded_crossing_cap_does_not_report_truncated_source_universe():
    doc=fitz.open()
    page=doc.new_page(width=200,height=200)
    for x in (10,20,30):
        page.draw_line((x,10),(x,150),color=(0,0,0),width=.48)
    raw=doc.tobytes()
    doc.close()
    with pytest.raises(ValueError,match="original_native_partition_crossing_safety_cap"):
        _run(raw,maximum_crossings=2)


@pytest.mark.skipif(not ORIGINAL.is_file(),reason="private original PDF not provisioned")
def test_original_page9_a120_ink_and_codes_cross_the_proposed_rcp_split():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    out=audit(
        raw,expected_sha256=SHA,page_1_based=9,
        proposed_partition_coordinate_pdf_pts=DIVIDER,
    )
    crosses=out["original_native_black_vertical_line_crossings"]
    assert len(crosses)==70
    ids={row["original_native_path_item_id"] for row in crosses}
    assert {"d9755i0","d1118i0","d3900i0","d9747i0"} <= ids
    bands=out["original_material_code_words_by_proposed_coordinate_band"]
    codes=[r for group in bands.values() for r in group]
    assert len(codes)==15  # original 12 IPF1 + 3 GRID native words
    assert len(bands["lower_pdf_coordinate_band"])>0
    assert len(bands["higher_pdf_coordinate_band"])>0
    assert out["source_partition_owner_authenticated"] is False
    assert out["new_firm_quantities"]==0
