"""The page-title authority reads drawing titles from structural evidence and fails closed.

Every sheet here is synthetic vector PDF text in generic layouts; no real
project, benchmark or expected title is used.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence, Tuple

import fitz
import pytest

import pb_page_title_authority as authority

A3 = (1191.0, 842.0)
A4 = (595.0, 842.0)

Text = Tuple  # (x, baseline_y, text, size[, bold])


def _sheet(texts: Iterable[Text] = (), size=A3, boxes: Sequence[Tuple[float, float, float, float]] = ()):
    doc = fitz.open()
    page = doc.new_page(width=size[0], height=size[1])
    for box in boxes:
        page.draw_rect(fitz.Rect(*box), color=(0, 0, 0), width=0.6)
    for x, y, text, font_size, *bold in texts:
        page.insert_text((x, y), text, fontsize=font_size, fontname="hebo" if bold and bold[0] else "helv")
    return doc, page


def _right_block(title_label="DRAWING TITLE", title_value="GROUND FLOOR PLAN", number="A-201", x=1000.0,
                 extra: Sequence[Text] = ()):
    """A right-edge title block: project and client above, fields below the title."""
    items = [
        (x, 520, "PROJECT TITLE", 6), (x, 532, "PROPOSED OFFICE BLOCK", 9),
        (x, 556, "CLIENT", 6), (x, 568, "ACME HOLDINGS", 9),
        (x, 650, "DRAWN", 6), (x + 60, 650, "CHECKED", 6), (x + 120, 650, "SCALE", 6),
        (x, 662, "AB", 8), (x + 60, 662, "CD", 8), (x + 120, 662, "1:100", 8),
        (x, 690, "DRAWING NO", 6), (x + 120, 690, "REVISION", 6),
        (x, 704, number, 10), (x + 120, 704, "C", 10),
    ]
    if title_label:
        items.append((x, 596, title_label, 6))
    if title_value:
        items.append((x, 612, title_value, 11))
    return items + list(extra)


def _resolve(page, **kwargs):
    return authority.resolve_page(page, 1, **kwargs)


# 1. explicit "DRAWING TITLE:" field

def test_explicit_drawing_title_field_in_the_same_cell():
    doc, page = _sheet(_right_block(title_label="DRAWING TITLE: SITE PLAN", title_value=""))
    result = _resolve(page)
    assert result.title == "SITE PLAN"
    assert result.source == "label" and "same cell" in result.reason
    assert result.confidence >= 90


# 2. title value on the next line

def test_title_value_on_the_line_below_its_label():
    doc, page = _sheet(_right_block(title_value="FIRST FLOOR PLAN"))
    result = _resolve(page)
    assert result.title == "FIRST FLOOR PLAN"
    assert "below label" in result.reason
    assert result.region == "title block"


def test_multi_line_title_value_is_joined():
    doc, page = _sheet(_right_block(title_value="FOUNDATION LAYOUT AND", extra=[(1000, 625, "RC COLUMN DETAILS", 11)]))
    assert _resolve(page).title == "FOUNDATION LAYOUT AND RC COLUMN DETAILS"


# 3. title block near the bottom / right

def test_bottom_strip_title_block_with_value_right_of_its_label():
    texts = [
        (40, 790, "PROJECT", 6), (90, 790, "PROPOSED TWO CLASSROOMS", 7),
        (40, 810, "DRG. TITLE", 6), (110, 810, "PLANS AND SECTIONS", 7),
        (400, 790, "DRAWN", 6), (440, 790, "M.S.A", 6), (400, 800, "CHECKED", 6), (440, 800, "M.S.A", 6),
        (400, 810, "SCALE", 6), (440, 810, "1:100", 6),
        (520, 790, "DRAWING NO", 6), (530, 805, "C.G.L 01", 8),
        (620, 500, "GROUND FLOOR PLAN", 12, True), (620, 300, "ELEVATION 01", 12, True),
    ]
    result = _resolve(_sheet(texts)[1])
    assert result.title == "PLANS AND SECTIONS"
    assert result.sheet_number == "C.G.L 01"


def test_right_edge_title_block_with_notes_above_it():
    notes = [(1000, 60 + 14 * i, f"{i}. All works to be carried out in accordance with the specification.", 6) for i in range(1, 12)]
    doc, page = _sheet(_right_block(extra=[(1000, 45, "NOTES", 8, True), *notes]))
    result = _resolve(page)
    assert result.title == "GROUND FLOOR PLAN"
    assert result.sheet_number == "A-201"


# 4. title located elsewhere / a different title-block layout

def test_title_block_in_the_top_left_corner():
    texts = [
        (40, 40, "TITLE", 6), (40, 54, "ROOF PLAN", 12),
        (40, 80, "SHEET NO", 6), (40, 92, "R-01", 9),
        (140, 40, "DRAWN", 6), (140, 52, "JK", 8), (200, 40, "SCALE", 6), (200, 52, "1:200", 8),
        (260, 40, "DATE", 6), (260, 52, "JAN 2025", 8),
    ]
    result = _resolve(_sheet(texts)[1])
    assert result.title == "ROOF PLAN"
    assert result.sheet_number == "R-01"


def test_empty_title_field_leaves_the_dominant_sheet_heading():
    # The title block's DRAWING TITLE cell is blank; REF (next field) must not be taken as its value.
    block = [
        (1000, 596, "DRAWING TITLE", 6), (1060, 596, "REF", 6), (1070, 610, "APPROVAL DRAWINGS", 7),
        (1000, 650, "DRAWN", 6), (1060, 650, "CHECKED", 6), (1120, 650, "SCALE", 6),
        (1000, 662, "AB", 8), (1060, 662, "CD", 8), (1120, 662, "N.T.S", 8),
        (1000, 690, "DRAWING NUMBER", 6), (1070, 690, "REVISION", 6), (1075, 704, "02", 8),
    ]
    heading = [(300, 60, "WINDOW AND DOOR SCHEDULE", 30, True)]
    result = _resolve(_sheet(block + heading)[1])
    assert result.title == "WINDOW AND DOOR SCHEDULE"
    assert result.source == "sheet_heading"
    assert result.sheet_number == "", "02 belongs to REVISION, the drawing-number cell is empty"
    assert not any(c["text"] in ("REF", "APPROVAL DRAWINGS") and c["score"] > 0 for c in result.candidates)


# 5. schedule page

def test_schedule_page_title_is_not_confused_by_table_headers():
    table = []
    for row, y in enumerate((150, 170, 190, 210)):
        table += [(80, y, f"D-0{row + 1}" if row else "MARK", 7), (160, y, "DESCRIPTION" if not row else "Single leaf flush door", 7),
                  (400, y, "SIZE" if not row else "900 x 2100", 7), (520, y, "FINISH" if not row else "Painted", 7)]
    result = _resolve(_sheet(_right_block(title_value="DOOR SCHEDULE") + table)[1])
    assert result.title == "DOOR SCHEDULE"


# 6. plan page / 7. elevation page / 8. section page

@pytest.mark.parametrize("title", ["GROUND FLOOR PLAN", "NORTH & SOUTH ELEVATIONS", "SECTIONS A-A AND B-B",
                                   "REFLECTED CEILING PLAN", "SITE PLAN"])
def test_plan_elevation_and_section_sheets(title):
    captions = [(100, 300, "NORTH ELEVATION", 12, True), (500, 300, "SOUTH ELEVATION", 12, True),
                (100, 600, "SECTION A-A", 12, True), (500, 600, "LOUNGE", 7), (600, 620, "BEDROOM 1", 7)]
    assert _resolve(_sheet(_right_block(title_value=title) + captions)[1]).title == title


def test_several_view_captions_without_a_title_block_title_fail_closed():
    captions = [(100, 300, "NORTH ELEVATION", 14, True), (500, 300, "SOUTH ELEVATION", 14, True),
                (100, 600, "EAST ELEVATION", 14, True), (500, 600, "WEST ELEVATION", 14, True)]
    captions += [(100 + 90 * (i % 8), 350 + 30 * (i // 8), f"{1200 + 50 * i}", 6) for i in range(24)]  # dimensions
    result = _resolve(_sheet(captions)[1])
    assert result.title == ""
    assert any(c.get("rejected") == "view caption" for c in result.candidates)


# 9. regulations / contract / general notes are not titles unless they genuinely are

_CLAUSES = [
    (60, 90, "BUILDING REGULATIONS", 16, True),
    (60, 110, "1. All work shall comply with the building regulations in force.", 7),
    (60, 122, "2. The contractor shall obtain all approvals before starting.", 7),
    (60, 200, "BUILDING CONTRACT", 16, True),
    (60, 220, "1. The works shall be carried out under the standard building contract.", 7),
    (60, 232, "2. Any variation shall be instructed in writing.", 7),
    (60, 300, "GENERAL NOTES", 16, True),
    (60, 320, "1. Do not scale from this drawing.", 7),
    (60, 332, "2. All dimensions are in millimetres unless otherwise stated.", 7),
]


def test_note_headings_do_not_become_the_title():
    result = _resolve(_sheet(_right_block(title_value="ROOF PLAN") + _CLAUSES)[1])
    assert result.title == "ROOF PLAN"


def test_note_headings_alone_fail_closed():
    result = _resolve(_sheet(_CLAUSES)[1])
    assert result.title == ""
    assert not any(c["score"] > 0 for c in result.candidates)


def test_general_notes_is_the_title_when_the_title_field_says_so():
    result = _resolve(_sheet(_right_block(title_value="GENERAL NOTES") + _CLAUSES[6:])[1])
    assert result.title == "GENERAL NOTES"
    assert result.source == "label"


def test_project_title_never_becomes_the_drawing_title():
    texts = [(1000, 520, "Project Title:", 9), (1000, 540, "PROPOSED CLASSROOM AND RESOURCE CENTRE", 12),
             (1000, 650, "Drawn:", 9), (1100, 650, "Checked:", 9), (1000, 690, "Scale:", 9), (1100, 690, "Date:", 9),
             (1000, 760, "Drawing Title:", 9), (1000, 776, "CLASSROOM BLOCK - TYPE B", 10),
             (1000, 800, "Drawing No.", 9), (1000, 814, "KS/08/2024-AD01", 10)]
    result = _resolve(_sheet(texts)[1])
    assert result.title == "CLASSROOM BLOCK - TYPE B"
    assert result.sheet_number == "KS/08/2024-AD01"


# 10. missing title fails closed

def test_missing_title_fails_closed_with_a_reason():
    result = _resolve(_sheet(_right_block(title_label="", title_value=""))[1])
    assert result.title == ""
    assert result.reason
    assert result.sheet_number == "A-201"
    assert authority.display_title(result.meta(), 7) == "A-201"


def test_text_page_gets_no_title():
    lines = [(50, 60 + 14 * i, f"Item {i}: supply and fix 100mm blockwork walling in cement mortar 1:4", 9) for i in range(40)]
    result = _resolve(_sheet([(50, 40, "BILL NO. 2 - WALLING", 11, True), *lines], size=A4)[1])
    assert result.title == ""
    assert authority.display_title(result.meta(), 12) == "Page 12"


# 11. missing sheet number: no code from elsewhere is promoted

def test_missing_sheet_number_is_not_invented():
    codes = [(80, 200, "REFER TO A-101 FOR SETTING OUT", 7), (80, 220, "T12 @ 200 C/C TO BS 4449", 7),
             (80, 240, "SECTION S01-S01", 12, True), (80, 260, "E-05", 12)]
    block = [item for item in _right_block() if item[2] not in ("DRAWING NO", "A-201")]
    result = _resolve(_sheet(block + codes)[1])
    assert result.title == "GROUND FLOOR PLAN"
    assert result.sheet_number == ""


def test_packed_drawing_number_and_revision_labels_stay_separate():
    texts = [(1000, 650, "DRAWN", 6), (1060, 650, "CHECKED", 6), (1120, 650, "SCALE", 6),
             (1000, 690, "DRAWING NUMBER", 7), (1078, 690, "REVISION", 7), (1010, 704, "S-100", 8), (1082, 704, "B", 8)]
    result = _resolve(_sheet(texts)[1])
    assert result.sheet_number == "S-100"


# 12. OCR-derived title

def _ocr_engine(lines_pt):
    from pb_drawing_ocr_evidence_layer import DrawingOCREngine

    def fake(image):
        scale = image.width / A3[0]
        return [{"text": text, "bounding_box": [x0 * scale, y0 * scale, x1 * scale, y1 * scale], "confidence": 0.99}
                for text, (x0, y0, x1, y1) in lines_pt]

    return DrawingOCREngine(custom_ocr_func=fake)


def test_ocr_title_when_the_sheet_has_no_text_layer():
    hatch = [(40 + 6 * i, 40, 42 + 6 * i, 800) for i in range(150)]
    doc, page = _sheet(boxes=hatch)
    engine = _ocr_engine([
        ("DRAWN", (1000, 640, 1030, 650)), ("CHECKED", (1060, 640, 1100, 650)), ("SCALE", (1120, 640, 1150, 650)),
        ("DRAWING TITLE", (1000, 600, 1070, 610)), ("SITE LAYOUT PLAN", (1000, 614, 1110, 628)),
        ("DRAWING NO", (1000, 680, 1060, 690)), ("S-01", (1000, 694, 1030, 706)),
    ])
    result = authority.resolve_page(page, 1, ocr_engine=engine)
    assert result.title == "SITE LAYOUT PLAN"
    assert result.sheet_number == "S-01"
    assert result.text_source == "ocr"


def test_native_text_is_not_sent_to_ocr():
    class Refuse:
        def recognize_page_rect(self, *args, **kwargs):
            raise AssertionError("native text was sufficient")

    doc, page = _sheet(_right_block())
    assert authority.resolve_page(page, 1, ocr_engine=Refuse()).title == "GROUND FLOOR PLAN"


# 13. several candidate phrases: positive structural evidence decides

def test_structural_evidence_beats_large_or_nearby_text():
    distractors = [(80, 60, "PERSPECTIVE VIEW", 26, True), (80, 700, "REFER TO GROUND FLOOR PLAN FOR SETTING OUT", 7),
                   (80, 760, "KENYA SCHOOL OF ARCHITECTS LTD", 14)]
    result = _resolve(_sheet(_right_block(title_value="FIRST FLOOR PLAN") + distractors)[1])
    assert result.title == "FIRST FLOOR PLAN"
    texts = [c["text"] for c in result.candidates]
    assert "PERSPECTIVE VIEW" in texts, "competing candidates are kept for review"


def test_title_inside_the_title_block_outranks_one_outside_it():
    stray = _right_block(title_value="GROUND FLOOR PLAN") + [(600, 596, "DRAWING TITLE", 6), (600, 612, "ROOF PLAN", 11)]
    assert _resolve(_sheet(stray)[1]).title == "GROUND FLOOR PLAN"


def test_equal_evidence_is_ambiguous_and_fails_closed():
    # One title block carrying two drawing-title fields with different values.
    two_fields = _right_block(title_value="GROUND FLOOR PLAN") + [(1100, 596, "DRAWING TITLE", 6), (1100, 612, "ROOF PLAN", 11)]
    result = _resolve(_sheet(two_fields)[1])
    assert result.title == ""
    assert result.reason.startswith("ambiguous")


# 14. repeated title-block layout across a multi-page set

def _document(pages):
    doc = fitz.open()
    for texts in pages:
        page = doc.new_page(width=A3[0], height=A3[1])
        for x, y, text, size, *bold in texts:
            page.insert_text((x, y), text, fontsize=size, fontname="hebo" if bold and bold[0] else "helv")
    return doc


def _resolve_document(doc):
    return authority.resolve_document([authority.analyse_page(page, i + 1) for i, page in enumerate(doc)])


def test_title_position_learned_from_sibling_sheets():
    pages = [_right_block(title_value=title, number=f"A-20{i}") for i, title in enumerate(("GROUND FLOOR PLAN", "FIRST FLOOR PLAN", "ROOF PLAN"))]
    unlabelled = [item for item in _right_block(title_value="SECTIONS A-A AND B-B", number="A-203") if item[2] != "DRAWING TITLE"]
    results = _resolve_document(_document(pages + [unlabelled]))
    assert [r.title for r in results[:3]] == ["GROUND FLOOR PLAN", "FIRST FLOOR PLAN", "ROOF PLAN"]
    assert results[3].title == "SECTIONS A-A AND B-B"
    assert results[3].source == "layout"


def test_text_repeated_on_every_sheet_is_not_a_title():
    def sheet(title):
        block = [item for item in _right_block(title_label="", title_value="", number="A-1")]
        return block + [(1000, 596, "STANDARD DETAILS SERIES", 11), (1000, 612, title, 11)]

    results = _resolve_document(_document([sheet(t) for t in ("GROUND FLOOR PLAN", "ROOF PLAN", "SITE PLAN", "DOOR SCHEDULE")]))
    assert [r.title for r in results] == ["GROUND FLOOR PLAN", "ROOF PLAN", "SITE PLAN", "DOOR SCHEDULE"]
    assert all(any("repeated on most sheets" in c.get("rejected", "") + c["reason"] for c in r.candidates) for r in results)


# Text shape

@pytest.mark.parametrize("text", ["45,000.00", "PAGE 3", "1 | P a g e", "AUG, 2018", "P.O. BOX 44600-00100",
                                  "6. All works to be carried out in accordance with local authority",
                                  "All fire Alarm cables used to be fire proof.", "Project", "REF", "KSHS.20"])
def test_non_titles_are_rejected_by_shape(text):
    assert authority.title_shape(text, bound=False)[0] == 0.0


@pytest.mark.parametrize("text", ["GROUND FLOOR PLAN", "Door Schedule", "SECTION A-A", "ELECTRICAL LIGHTING AND POWER"])
def test_titles_are_heading_shaped(text):
    assert authority.title_shape(text, bound=False)[0] > 0
    assert authority.has_title_vocabulary(text)


@pytest.mark.parametrize("text", ["AMOUNT", "BUILDING REGULATIONS", "BUILDING CONTRACT", "MINISTRY OF EDUCATION", "WORKING DRAWINGS"])
def test_free_text_without_drawing_vocabulary_is_never_a_heading_title(text):
    assert not authority.has_title_vocabulary(text)


# Production writers

def _app(tmp_path: Path, pdf: Path):
    db = tmp_path / "planreader.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE documents(id INTEGER PRIMARY KEY, workspace_id INTEGER, path TEXT, file_name TEXT);
        CREATE TABLE pages(id INTEGER PRIMARY KEY, workspace_id INTEGER, document_id INTEGER, page_no INTEGER, page_label TEXT,
            page_type TEXT, scale_text TEXT, extracted_text TEXT, selected INTEGER, image_path TEXT);
        CREATE TABLE register_items(id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id INTEGER, register_name TEXT, item_no TEXT,
            title TEXT, detail TEXT, priority TEXT, source_reference TEXT, status TEXT, created_at TEXT);
        """
    )
    conn.execute("INSERT INTO documents VALUES(1, 1, ?, 'plans.pdf')", (str(pdf),))
    with fitz.open(pdf) as doc:
        for index, page in enumerate(doc):
            conn.execute("INSERT INTO pages VALUES(?,1,1,?,?,?,?,?,1,'')",
                         (index + 1, index + 1, f"Page {index + 1}", "Other", "", page.get_text("text")))
    conn.commit()
    conn.close()

    class App:
        settings = {}
        fitz = __import__("fitz")

        def lquery(self, sql, params=()):
            c = sqlite3.connect(db)
            c.row_factory = sqlite3.Row
            try:
                return [dict(r) for r in c.execute(sql, tuple(params)).fetchall()]
            finally:
                c.close()

        def lexecute(self, sql, params=()):
            c = sqlite3.connect(db)
            try:
                cur = c.execute(sql, tuple(params))
                c.commit()
                return cur.lastrowid
            finally:
                c.close()

        def workspace_setting(self, workspace_id, key, default=""):
            return self.settings.get((int(workspace_id), str(key)), default)

        def set_workspace_setting(self, workspace_id, key, value):
            self.settings[(int(workspace_id), str(key))] = value

        def now_stamp(self):
            return "2026-09-27T00:00:00"

    return App()


def _plans_pdf(tmp_path: Path) -> Path:
    doc = _document([
        _right_block(title_value="GROUND FLOOR PLAN", number="A-201"),
        _right_block(title_label="", title_value="", number="A-202") + [(80, 200, "REFER TO A-101", 7)],
    ])
    path = tmp_path / "plans.pdf"
    doc.save(path)
    doc.close()
    return path


def test_index_time_registration_writes_the_authority_title(tmp_path):
    import pb_page_registration_v1225 as registration

    app = _app(tmp_path, _plans_pdf(tmp_path))
    registration.repair_document_registration(app, 1)

    meta = [json.loads(app.workspace_setting(1, registration._meta_key(pid))) for pid in (1, 2)]
    assert meta[0]["title"] == "GROUND FLOOR PLAN" and meta[0]["title_source"] == "label"
    assert meta[0]["sheet_number"] == "A-201"
    assert meta[1]["title"] == "" and meta[1]["title_reason"]
    labels = [r["page_label"] for r in app.lquery("SELECT page_label FROM pages ORDER BY id")]
    assert labels == ["A-201", "A-202"]
    assert [meta[0]["drawing_no"], meta[1]["drawing_no"]] == labels
    register = {r["source_reference"]: r["title"] for r in app.lquery("SELECT * FROM register_items")}
    assert register == {"plans.pdf p1": "GROUND FLOOR PLAN", "plans.pdf p2": "A-202"}


def test_post_processing_enhancement_writes_the_authority_title(tmp_path):
    import pb_page_registration_v1225 as registration
    import pb_plan_read_engine_v1228 as engine

    if not hasattr(registration, "_pb_v1228_base_title_reader"):
        registration._pb_v1228_base_title_reader = registration.title_block_evidence
    app = _app(tmp_path, _plans_pdf(tmp_path))
    engine.enhance_document_pages(app, 1, visual_budget=0)

    first = json.loads(app.workspace_setting(1, registration._meta_key(1)))
    second = json.loads(app.workspace_setting(1, registration._meta_key(2)))
    assert first["title"] == "GROUND FLOOR PLAN" and first["title_authority"] == authority.AUTHORITY
    assert second["title"] == "" and second["sheet_number"] == "A-202"
    labels = [r["page_label"] for r in app.lquery("SELECT page_label FROM pages ORDER BY id")]
    assert labels == ["A-201", "A-202"]
    assert [first["drawing_no"], second["drawing_no"]] == labels


def test_established_non_neutral_page_label_is_not_silently_renamed(tmp_path):
    import pb_page_registration_v1225 as registration

    app = _app(tmp_path, _plans_pdf(tmp_path))
    app.lexecute("UPDATE pages SET page_label=? WHERE id=?", ("BS5255", 1))
    registration.repair_document_registration(app, 1)

    row = app.lquery("SELECT page_label FROM pages WHERE id=?", (1,))[0]
    meta = json.loads(app.workspace_setting(1, registration._meta_key(1)))
    assert row["page_label"] == "BS5255"
    assert meta["sheet_number"] == "A-201"
    assert meta["drawing_no"] == "BS5255"


def test_neutral_label_fails_closed_without_sheet_number():
    import pb_page_registration_v1225 as registration

    assert registration._authoritative_page_label("", 8, "") == "Page 8"
    assert registration._authoritative_page_label("Page 8", 8, "") == "Page 8"
    assert registration._authoritative_page_label("Page 8", 8, "MC / 231 / 02-01E") == "MC/231/02-01E"

def test_manual_register_titles_are_never_overwritten(tmp_path):
    import pb_page_registration_v1225 as registration

    app = _app(tmp_path, _plans_pdf(tmp_path))
    app.set_workspace_setting(1, registration._manual_key(1), "1")
    app.set_workspace_setting(1, registration._meta_key(1), json.dumps({"title": "MY TITLE", "manual": True}))
    registration.repair_document_registration(app, 1)
    assert json.loads(app.workspace_setting(1, registration._meta_key(1)))["title"] == "MY TITLE"


def test_an_unlabelled_ocr_heading_is_not_trusted():
    hatch = [(40 + 6 * i, 40, 42 + 6 * i, 800) for i in range(150)]
    doc, page = _sheet(boxes=hatch)
    engine = _ocr_engine([("LENERALLABORATORY FLOOR PLAN", (300, 760, 700, 790)), ("1200", (300, 700, 330, 710)),
                          ("3450", (400, 700, 430, 710)), ("2200", (500, 700, 530, 710)), ("750", (600, 700, 625, 710))])
    result = authority.resolve_page(page, 1, ocr_engine=engine)
    assert result.title == ""
    assert result.text_source == "ocr"


def test_vector_title_block_on_an_a4_drawing_is_read_with_ocr():
    # Text elsewhere on the sheet is native, but the title block is drawn as vector lettering.
    hatch = [(40 + 0.7 * i, 40, 40.4 + 0.7 * i, 500) for i in range(1100)]  # a heavily drawn sheet
    notes = [(60, 60 + 12 * i, f"{i}. All reinforcement to be lapped at mid span.", 7) for i in range(1, 9)]
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    for box in hatch:
        page.draw_rect(fitz.Rect(*box), color=(0, 0, 0), width=0.3)
    for x, y, text, size in notes:
        page.insert_text((x, y), text, fontsize=size)

    from pb_drawing_ocr_evidence_layer import DrawingOCREngine

    def fake(image):
        scale = image.width / 842.0
        offset_y = 0.8 * 595 if image.height < 0.5 * image.width else 0.0  # bottom band renders from y = 80 %
        lines = [("Drg. Title", (20, 560, 60, 568)), ("GENERAL NOTES", (70, 560, 150, 568)),
                 ("Drawn", (300, 540, 330, 548)), ("Checked", (300, 552, 340, 560)), ("Scale", (300, 564, 325, 572)),
                 ("Drawing no", (400, 540, 450, 548)), ("C.G.L 01", (405, 552, 445, 562))]
        return [{"text": t, "bounding_box": [x0 * scale, (y0 - offset_y) * scale, x1 * scale, (y1 - offset_y) * scale], "confidence": 0.99}
                for t, (x0, y0, x1, y1) in lines if offset_y]

    result = authority.resolve_page(page, 1, ocr_engine=DrawingOCREngine(custom_ocr_func=fake))
    assert result.title == "GENERAL NOTES"
    assert result.sheet_number == "C.G.L 01"
    assert result.text_source == "native+ocr"


def test_a_four_line_title_value_is_read_whole():
    extra = [(1000, 625, "(UPLAND) & (COASTAL CLIMATES)", 11), (1000, 638, "FOUNDATION & ROOF LAYOUT &", 11), (1000, 651, "DETAILS", 11)]
    block = [item for item in _right_block(title_value="SCIENCE LAB TYPE 01A & 02A") if item[2] not in ("DRAWN", "CHECKED", "SCALE", "AB", "CD", "1:100")]
    block += [(1000, 690 - 4, "DRAWN", 6), (1060, 690 - 4, "CHECKED", 6)]
    result = _resolve(_sheet(block + extra)[1])
    assert result.title == "SCIENCE LAB TYPE 01A & 02A (UPLAND) & (COASTAL CLIMATES) FOUNDATION & ROOF LAYOUT & DETAILS"


def test_cross_sheet_resolution_scales_linearly():
    import time

    labelled = authority.analyse_cells(authority.cells_from_spans(
        [{"text": t, "bbox": (x, y, x + 60, y + 8), "size": 7} for x, y, t in (
            (1000, 600, "DRAWING TITLE"), (1000, 612, "GROUND FLOOR PLAN"), (1000, 650, "DRAWN"), (1060, 650, "CHECKED"),
            (1120, 650, "SCALE"), (1000, 690, "DRAWING NO"), (1000, 702, "A-1"))]), A3[0], A3[1], 1)
    text_page = authority.analyse_cells(authority.cells_from_spans(
        [{"text": f"Item {i} supply and fix blockwork", "bbox": (50, 40 + 12 * i, 400, 48 + 12 * i), "size": 9} for i in range(30)]),
        A4[0], A4[1], 2)
    pages = [labelled] * 20 + [text_page] * 3000
    started = time.perf_counter()
    results = authority.resolve_document(pages)
    assert time.perf_counter() - started < 1.5
    assert results[0].title == "GROUND FLOOR PLAN" and results[-1].title == ""
