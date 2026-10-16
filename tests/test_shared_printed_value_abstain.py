"""Shared printed-value readers abstain when the text has two answers."""
from pb_planreader_shared import (
    detect_drawing_number,
    detect_scale_from_text,
    extract_scale_ratio,
)


def test_one_scale_is_kept_and_two_scales_abstain():
    assert extract_scale_ratio("Scale: 1:100") == 100
    assert extract_scale_ratio("1:100 and 1:100") == 100
    assert extract_scale_ratio("1:100 and 1:50") is None
    assert extract_scale_ratio("1 : 100") == 100


def test_scale_detail_abstains_on_two_denominators():
    single = detect_scale_from_text("Scale 1:75")
    assert single is not None
    assert single["ratio"] == 75
    assert single["confidence"] == "medium"
    repeated = detect_scale_from_text("1:100\n1:100")
    assert repeated is not None
    assert repeated["confidence"] == "high"
    assert detect_scale_from_text("1:100 and 1:20") is None


def test_one_drawing_number_is_kept_and_two_numbers_abstain():
    assert detect_drawing_number("Drawing A01") == "A01"
    assert detect_drawing_number("See DWG-A02-01") == "A02-01"
    assert detect_drawing_number("A01 and A01") == "A01"
    assert detect_drawing_number("A01 and A02") is None
    assert detect_drawing_number("No drawing number here") is None
