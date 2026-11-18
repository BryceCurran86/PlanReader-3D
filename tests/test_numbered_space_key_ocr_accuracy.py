"""Source-neutral OCR key accuracy for original PlanReader trace preview.

These are candidate room names, never physical boundaries or customer areas.
"""
from math import nan

from pb_new_numbered_space_key import parse_numbered_key, _unpack_line
from pb_portable_raster_ocr_authority import OCRLine


def line(text, x, y, w=12, h=8, confidence=0.99):
    return OCRLine(
        text=text,
        confidence=confidence,
        bbox_px=(x, y, x+w, y+h),
        bbox_pt=(x, y, x+w, y+h),
    )


SCOPE = dict(
    anchor_bbox_pdf_pts=(0.0, 0.0, 20.0, 8.0),
    crop_origin_pdf_pts=(0.0, 0.0),
    source_sha256="a" * 64,
    page_index=0,
)


def test_adjacent_multibox_words_reconstruct_full_room_name():
    crop = [
        line("1", 3, 18, 5), line("TRUCK", 20, 18, 30),
        line("DRIVER", 53, 18, 37), line("LOUNGE", 93, 18, 42),
        line("2", 3, 33, 5), line("FOOD", 20, 33, 29),
        line("PREP", 52, 33, 28),
        line("3", 3, 48, 5), line("OFFICE", 20, 48, 40),
    ]
    result = parse_numbered_key(crop, (), **SCOPE)
    assert result.status == "CANDIDATE"
    assert [x.name for x in result.entries] == [
        "TRUCK DRIVER LOUNGE", "FOOD PREP", "OFFICE",
    ]
    assert result.entries[0].key_label_bbox_pdf_pts == (20, 18, 135, 26)
    assert result.commercial_publishable is False


def test_inline_numbered_ocr_rows_become_source_name_candidates():
    result = parse_numbered_key([
        line("1. OFFICE", 3, 18, 80),
        line("2) KITCHEN", 3, 33, 94),
        line("3 - DINING", 3, 48, 95),
    ], (), **SCOPE)
    assert result.status == "CANDIDATE"
    assert [(x.number, x.name) for x in result.entries] == [
        (1, "OFFICE"), (2, "KITCHEN"), (3, "DINING"),
    ]
    assert all(not x.area_authorized for x in result.entries)


def test_distant_other_columns_are_not_joined_as_room_name():
    result = parse_numbered_key([
        line("1", 3, 18, 5), line("LIVING", 20, 18, 38),
        line("SCHEDULE", 130, 18, 45),
        line("2", 3, 33, 5), line("BEDROOM", 20, 33, 50),
        line("3", 3, 48, 5), line("OFFICE", 20, 48, 45),
    ], (), **SCOPE)
    assert result.status == "CANDIDATE"
    assert result.entries[0].name == "LIVING"


def test_conflicting_duplicate_inline_number_abstains():
    result = parse_numbered_key([
        line("1. OFFICE", 3, 18, 70),
        line("1. GARAGE", 3, 33, 70),
        line("2. BATH", 3, 48, 70),
        line("3. ENTRY", 3, 63, 70),
    ], (), **SCOPE)
    assert result.status == "ABSTAINED"
    assert "conflict" in result.reason


def test_nonsequential_inline_numbers_do_not_become_key():
    result = parse_numbered_key([
        line("1. OFFICE", 3, 18, 70),
        line("5. GARAGE", 3, 33, 70),
        line("9. BATH", 3, 48, 70),
    ], (), **SCOPE)
    assert result.status == "ABSTAINED"
    assert result.reason == "numbered_key_sequence_not_authenticated"


def test_nan_confidence_ocr_line_rejected():
    assert _unpack_line(line("ROOM", 3, 18, confidence=nan)) is None


def test_out_of_bounds_confidence_rejected():
    assert _unpack_line(line("ROOM", 3, 18, confidence=2.0)) is None


def test_malformed_ocr_bbox_rejected_without_crash():
    class Malformed:
        text = "OFFICE"
        confidence = .9
        bbox_pt = ("bad", 0, 1, 1)
    assert _unpack_line(Malformed()) is None


def test_inline_false_date_or_dimension_not_a_room_key():
    result = parse_numbered_key([
        line("1. OFFICE", 3, 18, 70),
        line("2. BATH", 3, 33, 70),
        line("11/2026", 3, 48, 70),
    ], (), **SCOPE)
    assert result.status == "ABSTAINED"
