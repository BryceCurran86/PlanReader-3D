"""Page index identity comes from this page's text and the title block.

A filename and the first sheet-like token in an index listing are not evidence.
"""
from pb_page_registration_v1225 import (
    _authoritative_page_label,
    classify_page as registration_classify_page,
    weighted_page_type,
)
from pb_planreader_3d_app import classify_page
from pb_registration_priority_guard_v1225 import classify_page as guarded_classify_page


def test_filename_cannot_override_the_page_text():
    page_type, label = classify_page(
        "NORTH ELEVATION\n1 : 100",
        "Lot16_Floor_Plan.pdf",
        4,
    )
    assert page_type == "Elevation"
    assert label == "Page 4"


def test_floor_plan_filename_with_no_page_text_stays_unclassified():
    page_type, label = classify_page("", "Q5446_Floor_Plan.pdf", 1)
    assert page_type == "Other"
    assert label == "Page 1"


def test_index_listing_does_not_become_this_page_sheet_number():
    listing = "\n".join([
        "DRAWING INDEX",
        "A101 SITE PLAN",
        "A102 FLOOR PLAN",
        "A201 ELEVATIONS",
    ])
    _page_type, label = classify_page(listing, "architecture.pdf", 1)
    assert label == "Page 1"


def test_page_text_floor_plan_is_still_recognised():
    page_type, label = classify_page(
        "PROP. FLOOR PLAN\nPWD\nLAUNDRY",
        "elevations.pdf",
        7,
    )
    assert page_type == "Floor Plan"
    assert label == "Page 7"


def test_reflected_ceiling_text_beats_a_floor_plan_filename():
    page_type, _label = classify_page(
        "PROP. REFLECTED CEILING PLAN",
        "floor-plan.pdf",
        9,
    )
    assert page_type == "Reflected Ceiling Plan"


def test_registration_ignores_the_filename_and_does_not_scrape_a_sheet_code():
    page_type, confidence, evidence = weighted_page_type(
        "NORTH ELEVATION",
        "Lot16_Floor_Plan.pdf",
        "",
    )
    assert page_type == "Elevation"
    assert "file name" not in evidence
    assert confidence > 0
    empty_type, empty_confidence, _evidence = weighted_page_type("", "floor-plan.pdf", "")
    assert empty_type == "Other" and empty_confidence == 0
    _typed, label = registration_classify_page(
        "DRAWING INDEX\nA101 SITE PLAN\nA102 FLOOR PLAN",
        "plans.pdf",
        2,
    )
    assert label == "Page 2"
    _guarded, guarded_label = guarded_classify_page(
        "DRAWING INDEX\nA101 SITE PLAN",
        "floor-plan.pdf",
        3,
    )
    assert guarded_label == "Page 3"


def test_a_neutral_label_can_adopt_one_title_block_sheet_number():
    assert _authoritative_page_label("Page 4", 4, "A-205") == "A-205"


def test_a_non_neutral_label_is_not_replaced_by_a_different_sheet_number():
    assert _authoritative_page_label("A101", 4, "A-205") == "A101"


def test_filename_order_does_not_change_the_page_text_result():
    first = classify_page("NORTH ELEVATION", "a.pdf", 4)
    second = classify_page("NORTH ELEVATION", "z-floor-plan.pdf", 4)
    assert first == second == ("Elevation", "Page 4")
