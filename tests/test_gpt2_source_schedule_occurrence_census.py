"""Native source-role positives, conflict negatives and SHA-pinned drawing replay."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from random import Random

import fitz
import pytest

from tools import diag_gpt2_source_schedule_occurrence_census as diag


ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SOURCE_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"

HEADING = ("INTERNAL", "FINISHES", "SCHEDULE")
COLUMNS = ("MARK", "MANUFACTURER", "DESCRIPTION", "COMMENTS")
CODES = ("FT2", "FT3")


def _word(text, block, line, number, x, y):
    return {
        "text": text, "address": [block, line, number],
        "native_bbox": [x, y, x + 10, y + 10],
        "rendered_bbox": [x, y, x + 10, y + 10],
        "xc": x + 5, "yc": y + 5,
    }


def _fixture():
    words = []

    def put(block, y, cells):
        for col, (x, parts) in enumerate(cells):
            for num, item in enumerate(parts):
                words.append(_word(item, block, col, num, x + num * 13, y))

    put(100, 10, [(100, ["INTERNAL", "FINISHES", "SCHEDULE"])])
    put(101, 40, [
        (100, ["MARK"]), (200, ["MANUFACTURER"]),
        (300, ["DESCRIPTION"]), (600, ["COMMENTS"]),
    ])
    put(102, 60, [
        (100, ["FT2"]), (200, ["MAKER"]),
        (300, ["800x400", "STOCKTON"]), (600, ["R10"]),
    ])
    put(103, 80, [
        (100, ["FT3"]), (200, ["MAKER"]),
        (300, ["600x600", "DURA"]), (600, ["R12"]),
    ])
    put(104, 0, [(850, ["FT2"]), (920, ["FT3"])])
    return words


@pytest.mark.parametrize("seed", range(10))
def test_native_schedule_plan_separation_stable_under_word_order(monkeypatch, seed):
    words = _fixture()
    Random(seed).shuffle(words)
    monkeypatch.setattr(diag, "_words", lambda page: words)
    with fitz.open() as doc:
        result = diag.audit_page_schedule(
            doc.new_page(), heading=HEADING, columns=COLUMNS, marks=CODES
        )
    rows, marks = result["source_table_rows"], result["unbound_non_schedule_marks"]
    assert rows["FT2"]["source_address"] == [102, 0, 0]
    assert rows["FT3"]["source_address"] == [103, 0, 0]
    assert "STOCKTON" in rows["FT2"]["cells"]["description"]
    assert "DURA" in rows["FT3"]["cells"]["description"]
    assert len(marks["FT2"]) == len(marks["FT3"]) == 1
    assert result["schedule_rows_are_not_physical_occurrences"]
    assert result["floor_and_ceiling_quantity_publication_granted"] is False
    assert result["cross_sheet_correspondence_granted"] is False


@pytest.mark.parametrize("edit", [
    lambda w: w.extend([
        dict(x, address=[300, x["address"][1], x["address"][2]], yc=x["yc"]+120)
        for x in w if x["address"][0] == 100
    ]),
    lambda w: w.__setitem__(slice(None), [
        x for x in w if x["text"] != "COMMENTS"
    ]),
    lambda w: w.extend([
        dict(x, address=[105, x["address"][1], x["address"][2]], yc=x["yc"]+120)
        for x in w if x["address"][0] == 103
    ]),
    lambda w: w.__setitem__(slice(None), [
        x for x in w if x["address"][0] != 102
    ]),
    lambda w: w.extend([
        dict(x, address=[106, x["address"][1], x["address"][2]], yc=x["yc"]+80)
        for x in w if x["address"][0] == 102
    ]),
])
def test_missing_or_duplicate_source_row_remains_blocked(monkeypatch, edit):
    words = _fixture()
    edit(words)
    monkeypatch.setattr(diag, "_words", lambda page: words)
    with fitz.open() as doc:
        with pytest.raises(diag.ScheduleSourceConflict):
            diag.audit_page_schedule(
                doc.new_page(), heading=HEADING, columns=COLUMNS, marks=CODES
            )


def test_source_sha_mismatch_blocks_before_parsing():
    with fitz.open() as doc:
        doc.new_page().insert_text((60, 90), "TEST PDF")
        data = doc.tobytes()
    with pytest.raises(diag.ScheduleSourceConflict, match="SHA-256 mismatch"):
        diag.audit_pdf_bytes(
            data, expected_sha256="0" * 64,
            page_specs=((1, HEADING, COLUMNS, CODES),)
        )
    with pytest.raises(diag.ScheduleSourceConflict, match="invalid or repeated"):
        diag.audit_pdf_bytes(
            data, expected_sha256=sha256(data).hexdigest(),
            page_specs=((1, HEADING, COLUMNS, CODES),
                        (1, HEADING, COLUMNS, CODES))
        )


def test_native_bbox_unrotated_rendered_bbox_rotated():
    with fitz.open() as doc:
        page = doc.new_page(width=120, height=220)
        page.insert_text((30, 75), "FT2")
        native = page.get_text("words")[0]
        first = diag._words(page)[0]
        assert first["rendered_bbox"] == first["native_bbox"]
        page.set_rotation(90)
        second = diag._words(page)[0]
        assert second["native_bbox"] == first["native_bbox"]
        assert second["rendered_bbox"] != first["native_bbox"]
        expected = fitz.Rect(native[:4]) * page.rotation_matrix
        assert all(abs(a - b) < 1e-5 for a, b in zip(
            second["rendered_bbox"], expected
        ))
        assert second["address"] == first["address"]


def test_sha_pinned_original_floor_and_ceiling_evidence():
    if not ORIGINAL.is_file():
        pytest.skip("PRIVATE ORIGINAL ABSENT: original source NOT verified in public CI")
    source = ORIGINAL.read_bytes()
    assert sha256(source).hexdigest() == SOURCE_SHA
    result = diag.audit_pdf_bytes(
        source, expected_sha256=SOURCE_SHA,
        page_specs=diag.MARY_SCHEDULE_SPECS
    )
    floor, ceiling = result["source_pages"][11], result["source_pages"][9]
    assert result["page_count"] == 31
    assert floor["page_rotation"] == ceiling["page_rotation"] == 90
    ft2 = floor["source_table_rows"]["FT2"]["cells"]
    ft3 = floor["source_table_rows"]["FT3"]["cells"]
    assert "800x400" in ft2["description"]
    assert "600x600" in ft3["description"]
    assert "R10" in ft2["comments"] and "R12" in ft3["comments"]
    assert len(floor["unbound_non_schedule_marks"]["FT2"]) == 8
    assert len(floor["unbound_non_schedule_marks"]["FT3"]) == 5
    assert len(ceiling["unbound_non_schedule_marks"]["IPF1"]) == 11
    assert len(ceiling["unbound_non_schedule_marks"]["CLD3"]) == 3
    assert not result["geometry_or_quantity_promoted"]
    assert not result["source_private_bytes_exported"]
