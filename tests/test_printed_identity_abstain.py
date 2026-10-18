"""Printed identity keeps one answer. Two answers, and a filename, abstain."""

from __future__ import annotations

import sqlite3

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_planreader_shared import classify_page
from pb_revision_authority_v171 import (
    derive_revision_authority,
    extract_sheet_number,
    parse_revision_code,
)
from pb_title_block_extractor_v173 import (
    derive_title_block_metadata,
    extract_title_block_from_text,
)


def test_roof_plan_is_not_a_floor_plan():
    assert classify_page("ROOF PLAN") == "Roof Plan"
    assert classify_page("ROOF PLAN\nFLOOR PLAN") == "Other"
    assert classify_page("Site Plan and Landscape") == "Floor Plan"


def test_title_block_keeps_one_printed_value_and_drops_two():
    single = extract_title_block_from_text(
        1,
        "\n".join((
            "JOB NO: PR-2026-99",
            "DRAWING TITLE: Ground Floor Plan",
            "DWG NO: A-101",
            "REV: B",
            "SCALE: 1:100 @ A1",
            "DATE: 15/08/2026",
            "P1 = Low Sheen Acrylic Wall System",
        )),
    )
    assert single.job_no == "PR-2026-99"
    assert single.drawing_title == "Ground Floor Plan"
    assert single.sheet_no == "A-101"
    assert single.revision == "B"
    assert single.scale_text == "1:100 @ A1"
    assert single.date_str == "15/08/2026"
    assert single.legend_keys["P1"] == "Low Sheen Acrylic Wall System"

    competing = extract_title_block_from_text(
        2,
        "\n".join((
            "JOB NO: PR-2026-99",
            "JOB NO: PR-2026-10",
            "DRAWING TITLE: Ground Floor Plan",
            "DRAWING TITLE: Roof Plan",
            "DWG NO: A-101",
            "DWG NO: A-102",
            "REV: A",
            "REV: B",
            "SCALE: 1:100",
            "SCALE: 1:50",
            "DATE: 15/08/2026",
            "DATE: 16/08/2026",
            "P1 = Plaster",
            "P1 = Paint",
            "REVISIONS",
        )),
    )
    assert competing.job_no == ""
    assert competing.drawing_title == ""
    assert competing.sheet_no == ""
    assert competing.revision == ""
    assert competing.scale_text == ""
    assert competing.date_str == ""
    assert "P1" not in competing.legend_keys


def test_filename_revision_is_not_the_title_block_revision():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE pages (id INTEGER PRIMARY KEY, workspace_id INTEGER, "
        "page_label TEXT, scale_text TEXT, file_name TEXT)"
    )
    conn.execute(
        "INSERT INTO pages VALUES (1, 1, 'DWG NO: A-201 RCP', '1:50', 'A-201_Rev_C.pdf')"
    )
    meta = derive_title_block_metadata(conn, 1)._by_id[1]
    assert meta.sheet_no == "A-201"
    assert meta.revision == ""
    conn.close()


def test_revision_parser_keeps_one_code_and_rejects_ordinary_words():
    assert parse_revision_code("A-101_Rev_A.pdf") == ("A", 1)
    assert parse_revision_code("A-101_Rev_03.pdf") == ("03", 3)
    assert parse_revision_code("Rev A and Rev B") == ("0", 0)
    assert parse_revision_code("revisions") == ("0", 0)
    assert parse_revision_code("previous") == ("0", 0)
    assert extract_sheet_number("A-101 Floor Plan") == "A-101"
    assert extract_sheet_number("A-101 and A-102") == "UNKNOWN"
    assert extract_sheet_number("FLOOR PLAN") == "UNKNOWN"


def test_a_filename_revision_does_not_override_the_printed_revision():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE pages (
            id INTEGER PRIMARY KEY,
            workspace_id INTEGER,
            page_label TEXT,
            page_type TEXT,
            page_number INTEGER,
            file_name TEXT,
            selected INTEGER
        );
        """
    )
    conn.execute(
        "INSERT INTO pages VALUES (1, 1, 'A-101 Floor Plan Rev A', 'Plan', 1, 'A-101_Rev_C.pdf', 1)"
    )
    conn.execute(
        "INSERT INTO pages VALUES (2, 1, 'A-102 Floor Plan', 'Plan', 2, 'notes.pdf', 1)"
    )
    conn.execute(
        "INSERT INTO pages VALUES (3, 1, 'Notes', 'Plan', 3, 'other.pdf', 1)"
    )
    registry = derive_revision_authority(conn, 1)
    by_id = {record.page_id: record for record in registry.records}
    assert by_id[1].revision_code == "A"
    assert by_id[1].is_current is True
    assert by_id[2].is_superseded is False
    assert by_id[3].is_superseded is False
    assert by_id[2].sheet_number != by_id[3].sheet_number
    conn.close()


def test_extractor_sheet_number_requires_one_label():
    extractor = GenericPlanReaderExtractor()
    assert extractor.extract_sheet_number("DRAWING NO: A-101", 4) == "A-101"
    assert extractor.extract_sheet_number("DRAWING NO A-101\nSHEET NO A-102", 4) == "Page-4"
    assert extractor.extract_sheet_number("A101 SITE PLAN\nA102 FLOOR PLAN", 1) == "Page-1"
