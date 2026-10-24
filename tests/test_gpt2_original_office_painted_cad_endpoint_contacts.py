"""Source-original OFFICE painted CAD joins are not W2 endpoint snaps."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_original_room_four_edge_source_ink_shadow import (
    audit_source_painted_enclosure_correspondence_shadow as paint_audit,
    audit_source_enclosure_correspondence as strict_audit,
)

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"

ORIGINAL_SIDES = {
    "left": ("d52239i0", "d2657i0"),
    "right": ("d66220i0", "d3062i0"),
    "bottom": ("d53725i0", "d2931i0"),
    "top_partial": ("d52625i0", "d2845i0"),
}
SYNTHETIC_SIDES = {
    "left": ("d0i0", "d0i0"),
    "right": ("d1i0", "d1i0"),
    "bottom": ("d2i0", "d2i0"),
    "top_partial": ("d3i0", "d3i0"),
}


def _source(*, right_deficit=.48, top_starts_at_left=False,
            bottom_white=False, shift=60.):
    original=fitz.open()
    for dx in (0., shift):
        page=original.new_page(width=350,height=220)
        x0,x1=20.+dx,120.+dx
        wall_color=(0,0,0)
        page.draw_line((x0,20.),(x0,100.),color=wall_color,width=.48)
        page.draw_line((x1,20.),(x1,100.),color=wall_color,width=.48)
        page.draw_line((x0,100.),(x1-right_deficit,100.),
                       color=(1,1,1) if bottom_white else wall_color,
                       width=.48)
        page.draw_line((x0 if top_starts_at_left else x0+30.,20.),
                       (x1-right_deficit,20.),color=wall_color,width=.48)
    raw=original.tobytes()
    original.close()
    return raw


def _audit(raw, **kwargs):
    payload={
        "expected_sha256":hashlib.sha256(raw).hexdigest(),
        "floor_page_1_based":1,
        "finish_page_1_based":2,
        "original_side_pairs":SYNTHETIC_SIDES,
        "expected_translation_pdf_pts":(60.,0.),
    }
    payload.update(kwargs)
    return paint_audit(raw,**payload)


def test_native_black_strokes_touch_with_real_paint_not_synthetic_room_wall():
    row=_audit(_source())
    assert row["status"]=="original_painted_wall_ink_correspondence_candidate_only"
    assert row["source_floor_painted_corner_evidence"][
        "original_source_raw_endpoint_deficits_pdf_pts"]=={
            "bottom_right":.48,"top_right":.48}
    assert row["source_original_paint_contact_not_W2_endpoint_snap"] is True
    assert row["source_authenticated_structural_room_or_wall"] is False
    assert row["source_finished_face_or_finish_threshold_authenticated"] is False
    assert row["new_firm_quantities"]==0


def test_exact_path_names_repeated_on_different_original_pages_are_not_aliases():
    result=_audit(_source(),original_side_pairs=SYNTHETIC_SIDES)
    assert len(result["original_four_side_ink_witnesses"])==4
    assert result["source_cross_page_physical_room_equality_authenticated"] is False


@pytest.mark.parametrize("kwargs",[
    {"expected_sha256":"0"*64},
    {"expected_translation_pdf_pts":(61.,0.)},
    {"expected_translation_pdf_pts":(float("nan"),0.)},
    {"original_side_pairs":{
        "left":("d0i0","d0i0"),
        "right":("d0i0","d1i0"),
        "bottom":("d2i0","d2i0"),
        "top_partial":("d3i0","d3i0"),
    }},
    {"max_native_paths":1},
])
def test_original_source_sha_transform_alias_and_cap_fail_closed(kwargs):
    with pytest.raises(ValueError):
        _audit(_source(),**kwargs)


def test_paint_width_cannot_bridge_real_missing_source_wall_gap():
    with pytest.raises(ValueError,match="original_painted_corner_contact_unproven"):
        _audit(_source(right_deficit=.7))


def test_closed_top_ink_is_not_a_missing_doorway():
    with pytest.raises(ValueError,match="native_original_room_wall_side_or_gap_conflict"):
        _audit(_source(top_starts_at_left=True))


def test_white_ink_cannot_impersonate_physical_black_wall_source():
    with pytest.raises(ValueError,match="original_source_black_structural_ink_required"):
        _audit(_source(bottom_white=True))


@pytest.mark.skipif(not ORIGINAL.exists(),reason="private original not provisioned")
def test_original_office_p7_and_p11_exact_painted_corner_source_evidence():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    row=paint_audit(
        raw,expected_sha256=SHA,
        floor_page_1_based=7,finish_page_1_based=11,
        original_side_pairs=ORIGINAL_SIDES,
        expected_translation_pdf_pts=(78.,0.),
    )
    assert row["status"]=="original_painted_wall_ink_correspondence_candidate_only"
    floor=row["source_floor_painted_corner_evidence"]
    finish=row["source_finish_painted_corner_evidence"]
    assert floor["original_source_ink_bbox_pdf_pts"]==(
        173.52,1383.2,316.8,1584.56)
    assert finish["original_source_ink_bbox_pdf_pts"]==(
        251.52,1383.2,394.8,1584.56)
    assert floor["original_source_top_virtual_door_gap_pdf_pts"]==(
        (173.52,1383.2),(233.76,1383.2))
    assert finish["original_source_top_virtual_door_gap_pdf_pts"]==(
        (251.52,1383.2),(311.76,1383.2))
    assert floor["original_source_raw_endpoint_deficits_pdf_pts"]=={
        "bottom_right":.48,"top_right":.48}
    assert finish["original_source_raw_endpoint_deficits_pdf_pts"]=={
        "bottom_right":.48,"top_right":.48}
    assert row["new_firm_quantities"]==0
    # Existing exact centreline hook must remain conservative; this new
    # shadow is explicitly OPT-IN and never changes its strict behaviour.
    with pytest.raises(ValueError):
        strict_audit(
            raw,expected_sha256=SHA,
            floor_page_1_based=7,finish_page_1_based=11,
            original_side_pairs=ORIGINAL_SIDES,
            expected_translation_pdf_pts=(78.,0.),
        )
