"""B02 diagnostic regression: native source lines must stay separate."""
from pb_material_schedule_v1222 import parse_schedule_text


def test_split_native_material_row_keeps_code_and_description_lines():
    records = parse_schedule_text("FPB\nFLUSHSET PLASTERBOARD", page_id=9)
    assert len(records) == 1
    assert records[0]["code"] == "FPB"
    assert "FLUSHSET PLASTERBOARD" in records[0]["description"]
    assert records[0]["source_lines"] == ("FPB", "FLUSHSET PLASTERBOARD")


def test_missing_description_must_not_publish_definition():
    assert parse_schedule_text("FPB", page_id=9) == []
