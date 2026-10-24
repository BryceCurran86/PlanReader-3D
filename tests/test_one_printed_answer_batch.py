"""One printed answer: a second different value clears the field."""
from __future__ import annotations

from pb_opening_schedule_v171 import detect_header, extract_mark
from pb_precision_3d_v132 import infer_level
from pb_revision_authority_v171 import extract_sheet_number, parse_revision_code
from pb_title_block_extractor_v173 import extract_title_block_from_text


def test_one_job_number_is_kept_and_two_job_numbers_abstain() -> None:
    one = extract_title_block_from_text(1, "JOB NO: PR-2026-99\nJOB NO: PR-2026-99")
    two = extract_title_block_from_text(1, "JOB NO: PR-2026-99\nPROJECT NO: AB-100")
    assert one.job_no == "PR-2026-99"
    assert two.job_no == ""
    assert two.confidence == 0.0


def test_one_sheet_number_is_kept_and_two_sheet_numbers_abstain() -> None:
    one = extract_title_block_from_text(1, "DWG NO: A-101")
    two = extract_title_block_from_text(1, "DWG NO: A-101\nSHEET NO: A-102")
    assert one.sheet_no == "A-101"
    assert two.sheet_no == ""


def test_one_revision_is_kept_and_two_revisions_abstain() -> None:
    one = extract_title_block_from_text(1, "REV: B\nREV: B")
    two = extract_title_block_from_text(1, "REV: A\nREV: B")
    assert one.revision == "B"
    assert two.revision == ""


def test_revisions_heading_is_not_revision_s() -> None:
    meta = extract_title_block_from_text(1, "REVISIONS\nREV: C")
    assert meta.revision == "C"
    assert parse_revision_code("REVISIONS.pdf") == ("0", 0)


def test_one_scale_is_kept_and_two_scales_abstain() -> None:
    one = extract_title_block_from_text(1, "SCALE: 1:100\nSCALE: 1:100")
    two = extract_title_block_from_text(1, "SCALE: 1:100\nSCALE: 1:50")
    assert one.scale_text == "1:100"
    assert two.scale_text == ""


def test_labelled_date_is_kept_and_an_unlabelled_ratio_is_not_a_date() -> None:
    labelled = extract_title_block_from_text(1, "DATE: 15/08/2026")
    ratio = extract_title_block_from_text(1, "1/100")
    two = extract_title_block_from_text(1, "DATE: 15/08/2026\nDATE: 01/01/2020")
    assert labelled.date_str == "15/08/2026"
    assert ratio.date_str == ""
    assert two.date_str == ""


def test_one_drawing_title_is_kept_and_two_titles_abstain() -> None:
    one = extract_title_block_from_text(1, "DRAWING TITLE: Ground Floor Plan")
    two = extract_title_block_from_text(
        1,
        "DRAWING TITLE: Ground Floor Plan\nDRAWING TITLE: Roof Plan",
    )
    assert one.drawing_title == "Ground Floor Plan"
    assert two.drawing_title == ""


def test_legend_key_with_two_descriptions_is_omitted() -> None:
    meta = extract_title_block_from_text(
        1,
        "P1 = Low Sheen Acrylic Wall System\nP1 = Gloss Enamel Door System\nFC01 = 9mm Fibre Cement Sheet",
    )
    assert "P1" not in meta.legend_keys
    assert meta.legend_keys["FC01"] == "9mm Fibre Cement Sheet"


def test_repeated_legend_description_is_kept() -> None:
    meta = extract_title_block_from_text(
        1,
        "P1 = Low Sheen Acrylic Wall System\nP1 = Low Sheen Acrylic Wall System",
    )
    assert meta.legend_keys["P1"] == "Low Sheen Acrylic Wall System"


def test_revision_code_abstains_on_two_tokens_and_keeps_one() -> None:
    assert parse_revision_code("A-101_Rev_A.pdf") == ("A", 1)
    assert parse_revision_code("Rev A Rev A") == ("A", 1)
    assert parse_revision_code("Rev A and Rev B") == ("0", 0)


def test_sheet_number_abstains_on_two_codes_and_on_a_bare_word() -> None:
    assert extract_sheet_number("A-101 Floor Plan") == "A-101"
    assert extract_sheet_number("A-101 and A-102") == "UNKNOWN"
    assert extract_sheet_number("Floor Plan") == "UNKNOWN"


def test_opening_mark_abstains_on_two_marks_and_keeps_one() -> None:
    assert extract_mark("Door D01 820x2040") == "D01"
    assert extract_mark("D01 D01") == "D01"
    assert extract_mark("D01 or W01") == ""


def test_header_abstains_when_two_width_columns_are_printed() -> None:
    one = detect_header(["Mark", "Width", "Height"])
    two = detect_header(["Mark", "Width", "Rough Opening Width", "Height"])
    assert one["width"] == 1
    assert "width" not in two
    assert two["mark"] == 0
    assert two["height"] == 3


def test_sill_height_is_not_a_second_opening_height() -> None:
    header = detect_header(["w#", "width", "height", "sill height"])
    assert header["height"] == 2
    doubled = detect_header(["Mark", "Height", "Opening Height"])
    assert "height" not in doubled


def test_two_printed_storeys_do_not_become_the_first_storey() -> None:
    assert infer_level("Level 7 Floor Plan")[:2] == ("Level 7", 7)
    assert infer_level("Ground Floor Plan")[:2] == ("Ground", 0)
    name, _index, reason = infer_level("Level 1 and Level 2")
    assert name == ""
    assert reason == "two printed storeys"
    unknown, unknown_index, unknown_reason = infer_level("Typical Floor Plan")
    assert unknown == "Ground / unregistered"
    assert unknown_index == 0
    assert "provisional" in unknown_reason.lower()
