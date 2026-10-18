"""One printed reading is kept. Two readings abstain."""

from pb_autopilot_v1223 import _printed_scale, _render_reference_page
from pb_elevation_registration_v135 import orientation_from_text
from pb_no_ai_takeoff_v1216 import classify_context
from pb_viewport_scale_binding import _parse_ratio_from_raw


def test_one_elevation_side_is_kept_and_two_abstain():
    assert orientation_from_text("A-301 NORTH ELEVATION") == "North"
    assert orientation_from_text("Elevation - East") == "East"
    assert orientation_from_text("SOUTH FACADE") == "South"
    assert orientation_from_text("West façade") == "West"
    assert orientation_from_text("NORTH ELEVATION AND SOUTH ELEVATION") == ""
    assert orientation_from_text("SOUTH ELEVATION AND NORTH ELEVATION") == ""
    assert orientation_from_text("SOUTH ELEVATION\nREFER NORTH ELEVATION") == "South"
    assert orientation_from_text("REFER NORTH ELEVATION") == ""


def test_one_viewport_ratio_is_kept_and_two_abstain():
    assert _parse_ratio_from_raw("SCALE 1:100") == 100.0
    assert _parse_ratio_from_raw("SCALE 1:100 AND SCALE 1:100") == 100.0
    assert _parse_ratio_from_raw("SCALE 1:100 AND SCALE 1:50") is None


def test_one_printed_page_scale_is_kept_and_two_abstain():
    assert _printed_scale({"scale_text": "1:100", "extracted_text": ""}) == "1:100"
    assert _printed_scale({"scale_text": "1:100", "extracted_text": "SCALE 1:100"}) == "1:100"
    assert _printed_scale({"scale_text": "1:100", "extracted_text": "DETAIL 1:20"}) == ""


def test_rendered_masonry_is_not_an_artist_page():
    assert _render_reference_page({"page_type": "Floor Plan", "page_label": "", "extracted_text": "RENDERED MASONRY"}) is False
    assert _render_reference_page({"page_type": "", "page_label": "Artist's impression", "extracted_text": ""}) is True


def test_painting_context_keeps_one_scope():
    assert classify_context(page_type="Floor Plan") == {
        "section": "Internal", "element": "Floor area", "row_role": "floor_area",
    }
    assert classify_context(page_type="North Elevation")["element"] == "External walls / cladding"
    assert classify_context(page_type="Reflected Ceiling Plan")["element"] == "Ceilings"
    assert classify_context(label="rendered masonry")["section"] == "General"
    assert classify_context(page_type="North Elevation", label="Floor Plan")["row_role"] == ""
    assert classify_context(page_type="Reflected Ceiling Plan\nREFER FLOOR PLAN")["element"] == "Ceilings"
