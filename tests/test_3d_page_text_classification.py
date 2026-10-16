"""Page index identity comes from this page's text and the title block.

A filename and the first sheet-like token in an index listing are not evidence.
"""
from pb_page_registration_v1225 import (
    _authoritative_page_label,
    classify_page as registration_classify_page,
    weighted_page_type,
)
from pb_planreader_3d_app import classify_page
from pb_planreader_offline import classify_page_offline
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
    page_type, label = classify_page(listing, "architecture.pdf", 1)
    assert page_type == "Title / Drawing Register"
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


def test_a_short_token_inside_another_word_is_not_a_sheet_type():
    assert classify_page("RENDERED MASONRY\nINTERSECTION DETAIL", "render.pdf", 2) == (
        "Other", "Page 2",
    )


def test_a_reference_to_the_drawing_index_does_not_retype_a_floor_plan():
    page_type, label = classify_page(
        "PROP. FLOOR PLAN\nREFER TO DRAWING INDEX",
        "index.pdf",
        3,
    )
    assert page_type == "Floor Plan"
    assert label == "Page 3"


def test_two_different_sheet_headings_abstain():
    page_type, _label = classify_page(
        "PROP. FLOOR PLAN\nREFLECTED CEILING PLAN",
        "mixed.pdf",
        5,
    )
    assert page_type == "Other"


def test_door_elevations_stay_a_schedule():
    page_type, _label = classify_page("DOOR ELEVATIONS", "elev.pdf", 6)
    assert page_type == "Door / Window Schedule"


def test_registration_sheet_index_heading_beats_listed_floor_plans():
    page_type, confidence, evidence = weighted_page_type(
        "A101 SITE PLAN\nA102 FLOOR PLAN\nA201 ELEVATIONS",
        "plans.pdf",
        "DRAWING INDEX",
    )
    assert page_type == "Title / Drawing Register"
    assert confidence == 90
    assert evidence == "sheet index heading"
    floor_type, _confidence, _evidence = weighted_page_type(
        "REFER DRAWING INDEX",
        "floor-plan.pdf",
        "LEVEL 1 FLOOR PLAN",
    )
    assert floor_type == "Floor Plan"


class _OfflinePage:
    class _Rect:
        width = 200
        height = 100

    rect = _Rect()

    def get_text(self, mode="text", **_kwargs):
        if mode == "dict":
            return {"blocks": []}
        if mode == "words":
            return []
        return ""

    def get_drawings(self):
        return []

    def get_images(self):
        return []


def test_offline_classifier_ignores_filename_and_index_codes():
    page_type, label, _meta = classify_page_offline(
        _OfflinePage(),
        "NORTH ELEVATION\nDRAWING NUMBER A-301",
        "Floor_Plan.pdf",
        8,
    )
    assert page_type == "Elevation"
    assert label == "Page 8"
    index_type, index_label, _meta = classify_page_offline(
        _OfflinePage(),
        "DRAWING INDEX\nA102 FLOOR PLAN",
        "plans.pdf",
        1,
    )
    assert index_type == "Title / Drawing Register"
    assert index_label == "Page 1"


def test_filename_order_does_not_change_the_page_text_result():
    first = classify_page("NORTH ELEVATION", "a.pdf", 4)
    second = classify_page("NORTH ELEVATION", "z-floor-plan.pdf", 4)
    assert first == second == ("Elevation", "Page 4")
