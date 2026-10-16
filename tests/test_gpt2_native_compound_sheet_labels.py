"""Native CAD compound title-field tests. No free-text sheet election."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz

from pb_page_title_authority import (
    analyse_page, page_cells, parse_label, resolve_document,
)

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SOURCE_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def test_native_multi_label_span_retains_separate_strict_fields():
    doc = fitz.open()
    try:
        page = doc.new_page(width=1300, height=900)
        page.insert_text((730, 800), "Job Number - Drawing Number", fontsize=10)
        page.insert_text((730, 780), "Drawing Title", fontsize=10)
        before = page.get_text("text")
        cells = page_cells(page)
        after = page.get_text("text")
        assert before == after
        keys = [parse_label(cell) for cell in cells]
        keys = [p.field for p in keys if p is not None]
        assert "other_number" in keys
        assert "sheet_number" in keys
        assert "title" in keys
    finally:
        doc.close()


def test_unsplit_native_number_code_never_mints_label():
    doc = fitz.open()
    try:
        page = doc.new_page(width=1300, height=900)
        page.insert_text((730, 800), "A502", fontsize=10)
        assert not any(
            x.field == "sheet_number" for cell in page_cells(page)
            if (x := parse_label(cell)) is not None
        )
    finally:
        doc.close()


def test_native_production_source_p24_to_p27_all_own_sheet_numbers():
    source = ORIGINAL.read_bytes()
    assert hashlib.sha256(source).hexdigest() == SOURCE_SHA
    with fitz.open(stream=source, filetype="pdf") as doc:
        assert doc.page_count == 31
        analyses = [
            analyse_page(doc[i], i + 1, allow_ocr=False)
            for i in range(doc.page_count)
        ]
        resolved = resolve_document(analyses)
        # The original CAD composite "Job Number - Drawing Number" must
        # be parsed before sheet identity can distinguish A501 from the
        # A502 callout on the same source page.
        expected = {24: "A500", 25: "A501", 26: "A502", 27: "A503"}
        for page_num, sheet_number in expected.items():
            assert resolved[page_num - 1].sheet_number == sheet_number, (
                page_num, analyses[page_num - 1].sheet_numbers,
                resolved[page_num - 1]
            )
        # Conflict: two printed code-like words on page 25 must NOT
        # cause a nearest or first-word guessed sheet identity.
        assert resolved[24].sheet_number == "A501"


def test_source_page_bytes_are_not_rewritten_by_title_reader():
    source = ORIGINAL.read_bytes()
    before = hashlib.sha256(source).digest()
    with fitz.open(stream=source, filetype="pdf") as doc:
        page = doc[25]
        _ = analyse_page(page, 26, allow_ocr=False)
        _ = page_cells(page)
    assert hashlib.sha256(ORIGINAL.read_bytes()).digest() == before
