"""B02: parser limitations are diagnostic facts, not fabricated definitions."""
from pb_material_schedule_v1222 import parse_schedule_text


def test_split_alphabetic_code_requires_explicit_source_row_binding():
    # The legacy parser does not recognise a bare alphabetic token as a
    # source-defined code. Native block presence alone must not publish it.
    assert parse_schedule_text("FPB\nFLUSHSET PLASTERBOARD", page_id=9) == []


def test_missing_description_must_not_publish_definition():
    assert parse_schedule_text("FPB", page_id=9) == []


def test_explicit_same_line_alpha_definition_is_parser_candidate_only():
    records = parse_schedule_text("FPB FLUSHSET PLASTERBOARD", page_id=9)
    assert len(records) == 1
    assert records[0]["code"] == "FPB"
    assert "FLUSHSET PLASTERBOARD" in records[0]["description"]
