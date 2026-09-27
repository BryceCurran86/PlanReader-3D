"""Raster title blocks: targeted OCR recovers a drawing title and sheet number only through field labels.

Every sheet here is synthetic: vector linework, native text and plain raster
images drawn with PyMuPDF. The OCR engine is a fake that "reads" the text a
test places in its raster images, so every region the authority asks it to
read is visible and counted. No real project, benchmark or expected title is
used.
"""
from __future__ import annotations

import io
import os
from typing import Dict, List, Sequence, Tuple

import fitz
import pytest

import pb_page_title_authority as authority

A3 = (1191.0, 842.0)
A4 = (595.0, 842.0)
Box = Tuple[float, float, float, float]

PANEL: Box = (990.0, 505.0, 1185.0, 720.0)   # a pasted title-block image at the right edge


class RasterOCR:
    """A fake OCR engine: returns the lines printed in the page's raster images whose centre lies in the region rendered."""

    def __init__(self, lines, confidence: float = 0.95):
        self.lines: Dict[int, List[Tuple[str, Box]]] = lines if isinstance(lines, dict) else {0: list(lines)}
        self.confidence = confidence
        self.calls: List[Tuple[int, Box, int]] = []

    def recognize_page_rect(self, page, clip_rect=None, dpi=150):
        clip = tuple(clip_rect) if clip_rect is not None else (0.0, 0.0, page.rect.width, page.rect.height)
        self.calls.append((page.number + 1, clip, dpi))
        lines = self.lines.get(page.number + 1, self.lines.get(0, []))
        return [{"text": text, "bounding_box": list(box), "confidence": self.confidence} for text, box in lines
                if clip[0] <= (box[0] + box[2]) / 2 <= clip[2] and clip[1] <= (box[1] + box[3]) / 2 <= clip[3]]


def _block(x=1000.0, y=500.0, title="GROUND FLOOR PLAN", number="A-201", title_label="DRAWING TITLE",
           number_label="DRAWING NO"):
    """OCR lines of a title block (text, box in page points), laid out like a typical right-edge block."""
    rows = [(0, 20, "PROJECT TITLE", 6), (0, 32, "PROPOSED OFFICE BLOCK", 9), (0, 56, "CLIENT", 6), (0, 68, "ACME HOLDINGS", 9),
            (0, 150, "DRAWN", 6), (60, 150, "CHECKED", 6), (120, 150, "SCALE", 6),
            (0, 162, "AB", 8), (60, 162, "CD", 8), (120, 162, "1:100", 8), (120, 190, "REVISION", 6), (120, 204, "C", 10)]
    if title_label:
        rows.append((0, 96, title_label, 6))
    if title:
        rows.append((0, 112, title, 11))
    if number_label:
        rows.append((0, 190, number_label, 6))
    if number:
        rows.append((0, 204, number, 10))
    return [(text, (x + dx, y + dy - size, x + dx + 0.55 * size * len(text), y + dy + 0.25 * size)) for dx, dy, text, size in rows]


def _image(page, rect: Box, grey: int = 235, px_per_pt: float = 2.0, striped: bool = False):
    """A plain raster image placed at a visual page rectangle (a scan tile or a pasted title block)."""
    from PIL import Image, ImageDraw

    size = (max(8, int((rect[2] - rect[0]) * px_per_pt)), max(8, int((rect[3] - rect[1]) * px_per_pt)))
    image = Image.new("L", size, grey)
    if striped:  # texture, so the OCR layer's image-quality check sees a sharp image
        draw = ImageDraw.Draw(image)
        for x in range(0, size[0], 4):
            draw.line([(x, 0), (x, size[1])], fill=max(0, grey - 50), width=2)
            draw.line([(x + 2, 0), (x + 2, size[1])], fill=min(255, grey + 50), width=2)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    page.insert_image(fitz.Rect(*rect) * page.derotation_matrix, stream=buffer.getvalue(), rotate=page.rotation, keep_proportion=False)


def _text(page, x, y, text, size=7):
    page.insert_text(fitz.Point(x, y) * page.derotation_matrix, text, fontsize=size, rotate=page.rotation)


def _notes(page, n=8, x=60.0, y=60.0):
    for i in range(1, n + 1):
        _text(page, x, y + 12 * i, f"{i}. All reinforcement shall be lapped at mid span unless noted otherwise.")


def _linework(page, n=1100):
    """A heavily drawn sheet: many short vector strokes away from the title-block bands."""
    for i in range(n):
        x, y = 40 + (i % 100) * 8.5, 330 + (i // 100) * 25
        page.draw_line(fitz.Point(x, y) * page.derotation_matrix, fitz.Point(x + 6, y + 18) * page.derotation_matrix, width=0.3)


def _sheet(size=A3, *, paths=0, notes=True, images: Sequence[Box] = (), rotation=0, doc=None):
    doc = doc if doc is not None else fitz.open()
    if rotation in (90, 270):
        page = doc.new_page(width=size[1], height=size[0])
        page.set_rotation(rotation)
    else:
        page = doc.new_page(width=size[0], height=size[1])
    if paths:
        _linework(page, paths)
    if notes:
        _notes(page)
    for rect in images:
        _image(page, rect)
    return doc, page


def _native_block(page, x=1000.0, y=500.0, title="GROUND FLOOR PLAN", number="A-201"):
    """The same title block written as native text (a sibling sheet)."""
    for text, box in _block(x, y, title, number):
        _text(page, box[0], box[3] - 0.25 * (box[3] - box[1]) / 1.25, text, size=(box[3] - box[1]) / 1.25)


def _inside(clip: Box, box: Box, tol: float = 1.0) -> bool:
    return clip[0] >= box[0] - tol and clip[1] >= box[1] - tol and clip[2] <= box[2] + tol and clip[3] <= box[3] + tol


def _covers(clip: Box, point: Tuple[float, float]) -> bool:
    return clip[0] <= point[0] <= clip[2] and clip[1] <= point[1] <= clip[3]


def _regions(result):
    """The strategies of the regions OCR read for a page, in order (check reads of single values excluded)."""
    return [read["strategy"] for read in result.ocr.get("reads", [])]


def _resolve(doc, engine):
    return authority.resolve_document([authority.analyse_page(page, i + 1, ocr_engine=engine) for i, page in enumerate(doc)])


# 1. vector drawing + raster title block

def test_vector_drawing_with_a_raster_title_block():
    doc, page = _sheet(paths=1100, images=[PANEL])
    engine = RasterOCR(_block())
    result = authority.resolve_page(page, 1, ocr_engine=engine)
    assert result.title == "GROUND FLOOR PLAN"
    assert result.sheet_number == "A-201"
    assert result.source == "label" and result.text_source == "native+ocr"
    assert _regions(result) == ["image in the title-block band"]
    assert all(_inside(clip, PANEL) for _p, clip, _d in engine.calls), "only the pasted title-block image is read"


# 2. native body text + raster title block

def test_native_body_text_with_a_raster_title_block():
    doc, page = _sheet(images=[PANEL])
    engine = RasterOCR(_block(title="GENERAL NOTES", number="S-001"))
    result = authority.resolve_page(page, 1, ocr_engine=engine)
    assert (result.title, result.sheet_number) == ("GENERAL NOTES", "S-001")
    assert len(_regions(result)) == 1


# 3. an embedded title-block image in the bottom-right corner is read whole, at its own resolution

def test_corner_title_block_image_is_read_whole_not_cut_at_the_band_edge():
    corner = (950.0, 630.0, 1185.0, 838.0)   # straddles both the bottom and the right band edges
    doc, page = _sheet(images=[corner])
    engine = RasterOCR(_block(x=960.0, y=630.0, title="SECTION A-A", number="A-301"))
    result = authority.resolve_page(page, 1, ocr_engine=engine)
    assert (result.title, result.sheet_number) == ("SECTION A-A", "A-301")
    assert len(_regions(result)) == 1
    page_no, clip, dpi = engine.calls[0]
    assert _inside(clip, corner) and _inside(corner, clip)
    assert 150 <= dpi <= 300


# 4. a title-block image in another position, learned from sibling sheets

def _top_left_siblings(doc, count=2):
    for i in range(count):
        page = doc.new_page(width=A3[0], height=A3[1])
        _native_block(page, x=40.0, y=20.0, title=f"PLAN {i + 1}", number=f"A-10{i}")
        _linework(page)
    return doc


TOP_LEFT: Box = (30.0, 25.0, 225.0, 240.0)


def test_title_block_image_in_a_position_learned_from_siblings():
    doc = _top_left_siblings(fitz.open())
    _, page = _sheet(paths=1100, notes=False, images=[TOP_LEFT], doc=doc)
    _notes(page, x=400.0)
    engine = RasterOCR({3: _block(x=40.0, y=20.0, title="ROOF PLAN", number="A-204")})
    results = _resolve(doc, engine)
    assert (results[2].title, results[2].sheet_number) == ("ROOF PLAN", "A-204")
    assert {call[0] for call in engine.calls} == {3}, "native sibling sheets are never OCR'd"
    assert results[2].ocr["strategy"] == "title-block region of sibling sheets"
    assert _covers(engine.calls[0][1], ((TOP_LEFT[0] + TOP_LEFT[2]) / 2, (TOP_LEFT[1] + TOP_LEFT[3]) / 2))


def test_without_siblings_a_title_block_outside_the_edge_bands_is_not_found():
    doc, page = _sheet(paths=1100, notes=False, images=[TOP_LEFT])
    _notes(page, x=400.0)
    engine = RasterOCR(_block(x=40.0, y=20.0, title="ROOF PLAN", number="A-204"))
    result = authority.resolve_page(page, 1, ocr_engine=engine)
    assert (result.title, result.sheet_number) == ("", "")
    centre = ((TOP_LEFT[0] + TOP_LEFT[2]) / 2, (TOP_LEFT[1] + TOP_LEFT[3]) / 2)
    assert not any(_covers(clip, centre) for _p, clip, _d in engine.calls), "no blind whole-page OCR"


# 5. sibling sheets teach the region; the raster sibling is recovered from its own pixels

def _right_siblings(doc, count=2):
    for i in range(count):
        page = doc.new_page(width=A3[0], height=A3[1])
        _native_block(page, title=f"FLOOR PLAN LEVEL {i + 1}", number=f"A-20{i}")
        _notes(page)
    return doc


def _raster_sheet(doc, header=True):
    page = doc.new_page(width=A3[0], height=A3[1])
    _image(page, (0.0, 0.0, A3[0], A3[1]), px_per_pt=1.0)
    if header:
        _text(page, 1000, 20, "MINISTRY OF PUBLIC WORKS STATE DEPARTMENT", 5)
    return page


def test_raster_sibling_is_read_at_the_region_its_siblings_demonstrate():
    doc = _right_siblings(fitz.open())
    _raster_sheet(doc)
    engine = RasterOCR({3: _block(title="SECTIONS A-A AND B-B", number="A-205")})
    results = _resolve(doc, engine)
    assert (results[2].title, results[2].sheet_number) == ("SECTIONS A-A AND B-B", "A-205")
    assert _regions(results[2]) == ["title-block region of sibling sheets"]
    _page, clip, _dpi = engine.calls[0]
    assert (clip[2] - clip[0]) * (clip[3] - clip[1]) < 0.15 * A3[0] * A3[1], "a region, not the sheet"
    assert results[2].ocr["strategy"] == "title-block region of sibling sheets"


def test_siblings_say_where_to_look_never_what_the_title_is():
    doc = _right_siblings(fitz.open())
    _raster_sheet(doc)
    engine = RasterOCR({3: _block(title="", number="")})   # the raster block's fields are blank
    results = _resolve(doc, engine)
    assert (results[2].title, results[2].sheet_number) == ("", "")
    assert results[0].title == "FLOOR PLAN LEVEL 1"
    assert "OCR read" in results[2].reason


# 6. a raster image elsewhere on the page does not trigger the title authority

def test_an_image_away_from_the_title_block_bands_is_never_read():
    photo = (300.0, 200.0, 700.0, 500.0)
    doc, page = _sheet(images=[photo])
    engine = RasterOCR(_block(x=320.0, y=210.0, title="SITE PLAN", number="A-9"))
    result = authority.resolve_page(page, 1, ocr_engine=engine)
    assert (result.title, result.sheet_number) == ("", "")
    assert engine.calls == []


# 7. a code in body text inside an image is not a sheet number

def test_a_code_in_raster_body_text_is_not_a_sheet_number():
    doc, page = _sheet(images=[PANEL])
    lines = [("REFER TO DRAWING A-101 FOR DETAILS", (1000, 520, 1170, 530)), ("BS 5255", (1000, 560, 1040, 570)),
             ("A-102", (1000, 600, 1030, 612)), ("GROUND FLOOR PLAN", (1000, 640, 1110, 655))]
    result = authority.resolve_page(page, 1, ocr_engine=RasterOCR(lines))
    assert (result.title, result.sheet_number) == ("", "")
    assert result.text_source == "native" and result.ocr["result"] == "no title-block evidence in the regions read"


def test_run_together_ocr_labels_do_not_hand_a_revision_to_the_drawing_number():
    # OCR reads "DRAWING NUMBER" and "REVISION" as one line; the revision's value must stay the revision's.
    lines = [(text, box) for text, box in _block(number="", number_label="") if text not in ("REVISION", "C")]
    lines += [("DRAWING NUMBER REVISION", (1000.0, 684.0, 1150.0, 691.5)), ("02", (1125.0, 694.0, 1136.0, 706.5))]
    doc, page = _sheet(images=[PANEL])
    result = authority.resolve_page(page, 1, ocr_engine=RasterOCR(lines))
    assert result.title == "GROUND FLOOR PLAN"
    assert result.sheet_number == ""


# 8. several embedded images

def test_only_the_title_block_image_among_several_is_read():
    logo, photo = (40.0, 780.0, 70.0, 810.0), (300.0, 200.0, 700.0, 500.0)
    doc, page = _sheet(images=[logo, photo, PANEL])
    lines = _block() + [("LOGO", (45, 790, 65, 800)), ("PHOTO OF EXISTING SITE PLAN", (320, 300, 520, 312))]
    engine = RasterOCR(lines)
    result = authority.resolve_page(page, 1, ocr_engine=engine)
    assert (result.title, result.sheet_number) == ("GROUND FLOOR PLAN", "A-201")
    assert len(_regions(result)) == 1
    for point in ((55, 795), (500, 350)):
        assert not any(_covers(clip, point) for _p, clip, _d in engine.calls)


# 9. a rotated sheet: regions are rendered in the page's visual orientation

def test_rotated_sheet_raster_title_block_is_rendered_where_it_is_seen():
    from pb_drawing_ocr_evidence_layer import DrawingOCREngine

    doc, page = _sheet(images=[], rotation=90)
    _image(page, PANEL, grey=90, striped=True)
    lines = _block()
    seen = []

    class Rendering(DrawingOCREngine):
        def recognize_page_rect(self, page, clip_rect=None, dpi=150):
            seen.append((tuple(clip_rect) if clip_rect is not None else tuple(page.rect), dpi))
            return super().recognize_page_rect(page, clip_rect, dpi)

    def read(image):
        clip, dpi = seen[-1]
        scale = dpi / 72.0
        grey = image.convert("L")
        out = []
        for text, box in lines:
            cx, cy = int(((box[0] + box[2]) / 2 - clip[0]) * scale), int(((box[1] + box[3]) / 2 - clip[1]) * scale)
            patch = [grey.getpixel((x, y)) for x in range(cx - 4, cx + 4) for y in range(cy - 4, cy + 4)
                     if 0 <= x < grey.width and 0 <= y < grey.height]
            if patch and abs(sum(patch) / len(patch) - 90) < 15:  # the panel is there, in visual orientation
                out.append({"text": text, "bounding_box": [(v - o) * scale for v, o in zip(box, (clip[0], clip[1], clip[0], clip[1]))],
                            "confidence": 0.95})
        return out

    result = authority.resolve_page(page, 1, ocr_engine=Rendering(custom_ocr_func=read))
    assert page.rotation == 90
    assert (result.title, result.sheet_number) == ("GROUND FLOOR PLAN", "A-201")


# 10. no OCR engine on the host

def test_no_ocr_backend_fails_closed(monkeypatch):
    monkeypatch.setattr(authority, "ocr_available", lambda: False)
    doc = _right_siblings(fitz.open())
    _raster_sheet(doc)
    results = authority.resolve_document([authority.analyse_page(page, i + 1) for i, page in enumerate(doc)])
    assert (results[2].title, results[2].sheet_number) == ("", "")
    assert results[2].reason and results[2].ocr == {}


# 11. low-confidence OCR

def test_low_confidence_ocr_fails_closed():
    doc, page = _sheet(images=[PANEL])
    result = authority.resolve_page(page, 1, ocr_engine=RasterOCR(_block(), confidence=0.2))
    assert (result.title, result.sheet_number) == ("", "")


# 12. an OCR title without a structural label

def test_ocr_heading_without_a_field_label_fails_closed():
    doc = fitz.open()
    _raster_sheet(doc)
    lines = [("GROUND FLOOR PLAN", (400, 700, 800, 740)), ("SCALE 1:100", (500, 745, 600, 760)),
             ("3450", (300, 300, 330, 310)), ("1200", (400, 300, 430, 310))]
    result = authority.resolve_page(doc[0], 1, ocr_engine=RasterOCR(lines))
    assert result.title == ""


# 13. DRAWING TITLE and DRAWING NO labels inside the image bind their values

def test_labels_inside_the_image_bind_title_and_number_marked_as_ocr():
    doc, page = _sheet(images=[PANEL])
    raster = authority.resolve_page(page, 1, ocr_engine=RasterOCR(_block()))
    native_doc, native_page = _sheet()
    _native_block(native_page)
    native = authority.resolve_page(native_page, 1, allow_ocr=False)
    assert raster.title == native.title == "GROUND FLOOR PLAN"
    assert raster.sheet_number == native.sheet_number == "A-201"
    assert raster.reason.endswith("read with OCR)") and raster.sheet_number_source.endswith("read with OCR")
    assert raster.confidence < native.confidence, "read letters rank below extracted text"


# empty title-block field with its value pasted in as an image

def test_empty_native_field_with_an_image_value_is_read_there_only():
    doc, page = _sheet()
    for text, box in _block(title=""):
        _text(page, box[0], box[3] - 0.25 * (box[3] - box[1]) / 1.25, text, size=(box[3] - box[1]) / 1.25)
    value, logo = (995.0, 598.0, 1150.0, 616.0), (1120.0, 505.0, 1180.0, 545.0)
    _image(page, value)
    _image(page, logo)
    engine = RasterOCR([("FIRST FLOOR PLAN", (1000.0, 601.0, 1100.0, 614.0)), ("STUDIO LOGO", (1125.0, 520.0, 1175.0, 530.0))])
    result = authority.resolve_page(page, 1, ocr_engine=engine)
    assert result.title == "FIRST FLOOR PLAN" and result.sheet_number == "A-201"
    assert _regions(result) == ["empty title-block field over an image"]
    assert not any(_covers(clip, (1150.0, 525.0)) for _p, clip, _d in engine.calls)


def test_a_field_whose_value_lies_beyond_the_region_read_is_completed():
    # Siblings demonstrate a shorter title block; this raster sheet's drawing-title field sits below that region.
    doc = _right_siblings(fitz.open())
    _raster_sheet(doc)
    lines = [(text, box) for text, box in _block(title="", title_label="")]
    # The label lies inside the region the siblings demonstrate (it ends about 723 pt down); its value below it.
    lines += [("DRAWING TITLE", (1000.0, 711.0, 1043.0, 718.5)), ("ELEVATIONS", (1000.0, 730.0, 1060.0, 743.0))]
    engine = RasterOCR({3: lines})
    results = _resolve(doc, engine)
    assert (results[2].title, results[2].sheet_number) == ("ELEVATIONS", "A-201")
    assert [read["strategy"] for read in results[2].ocr["reads"]] == [
        "title-block region of sibling sheets", "value area of a title-block field read with OCR"]


# 14. OCR stays targeted

def test_ocr_reads_only_the_sheets_that_need_it():
    doc = fitz.open()
    raster_pages = []
    lines = {}
    for i in range(30):
        if i % 6 == 5:
            _raster_sheet(doc)
            raster_pages.append(i + 1)
            blank = len(raster_pages) > 3
            lines[i + 1] = _block(title="" if blank else f"DETAIL SHEET {i + 1}", number="" if blank else f"D-{i + 1}")
        elif i == 28:
            doc.new_page(width=A4[0], height=A4[1])   # blank
        elif i % 3 == 0:
            page = doc.new_page(width=A3[0], height=A3[1])
            _native_block(page, title=f"PLAN {i + 1}", number=f"A-{i + 1}")
        else:
            page = doc.new_page(width=A4[0], height=A4[1])
            for row in range(40):
                _text(page, 50, 40 + 18 * row, f"Item {row}: supply and fix 200 mm blockwork in cement mortar 1:4.", 8)
            _image(page, (50.0, 780.0, 545.0, 830.0))   # a letterhead footer on a text page
    engine = RasterOCR(lines)
    results = _resolve(doc, engine)
    assert sorted({call[0] for call in engine.calls}) == raster_pages, "only raster drawing sheets are read"
    reads = {p: [read["strategy"] for read in results[p - 1].ocr["reads"]] for p in raster_pages}
    for p in raster_pages[:3]:
        assert reads[p] == ["title-block region of sibling sheets"], "one targeted region when it answers"
        assert (results[p - 1].title, results[p - 1].sheet_number) == (f"DETAIL SHEET {p}", f"D-{p}")
    for p in raster_pages[3:]:
        # A blank block: at most one more read, of an empty field's value area, then it fails closed.
        assert reads[p][0] == "title-block region of sibling sheets" and len(reads[p]) <= 2
        assert set(reads[p][1:]) <= {"value area of a title-block field read with OCR"}
        assert (results[p - 1].title, results[p - 1].sheet_number) == ("", "")
    assert len(engine.calls) <= 4 * len(raster_pages), "region reads plus one check read per value"


def test_ocr_results_are_cached_per_file_region_and_resolution(tmp_path, monkeypatch):
    import pb_drawing_ocr_evidence_layer as layer

    doc = _right_siblings(fitz.open())
    _raster_sheet(doc)
    path = tmp_path / "set.pdf"
    doc.save(path)
    fake = RasterOCR({3: _block(title="ELEVATIONS", number="A-206")})
    monkeypatch.setattr(layer, "DrawingOCREngine", lambda *a, **k: fake)
    monkeypatch.setattr(authority, "ocr_available", lambda: True)
    authority.reset_ocr_stats()
    for _ in range(2):
        with fitz.open(path) as pdf:
            results = authority.resolve_document([authority.analyse_page(page, i + 1) for i, page in enumerate(pdf)])
        assert results[2].title == "ELEVATIONS"
    stats = authority.ocr_stats()
    first_run = 1 + 2   # the sibling region, then one check read each for the title and the sheet number
    assert len(fake.calls) == first_run and stats["calls"] == first_run and stats["cache_hits"] == first_run
    assert stats["pixels"] > 0


# document lifetime, determinism, no mutation

def test_a_closed_document_is_reopened_and_a_changed_file_fails_closed(tmp_path):
    doc = _right_siblings(fitz.open())
    _raster_sheet(doc)
    path = tmp_path / "set.pdf"
    doc.save(path)
    engine = RasterOCR({3: _block(title="ELEVATIONS", number="A-206")})
    pdf = fitz.open(path)
    analyses = [authority.analyse_page(page, i + 1, ocr_engine=engine) for i, page in enumerate(pdf)]
    pdf.close()   # the post-processing writer closes the PDF before resolving titles
    assert authority.resolve_document(analyses)[2].title == "ELEVATIONS"

    pdf = fitz.open(path)
    analyses = [authority.analyse_page(page, i + 1, ocr_engine=engine) for i, page in enumerate(pdf)]
    pdf.close()
    stat = os.stat(path)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10_000_000_000))
    result = authority.resolve_document(analyses)[2]
    assert (result.title, result.sheet_number) == ("", "")
    assert result.ocr["result"] == "the document could not be re-read"


def test_page_order_does_not_change_the_result():
    def build(order):
        doc = fitz.open()
        for kind in order:
            if kind == "raster":
                _raster_sheet(doc)
            else:
                _native_block(doc.new_page(width=A3[0], height=A3[1]), title=f"PLAN {kind}", number=f"A-{kind}")
        return doc

    lines = _block(title="SECTIONS", number="A-9")
    forward = _resolve(build(["1", "2", "raster"]), RasterOCR(lines))
    backward = _resolve(build(["raster", "2", "1"]), RasterOCR(lines))
    assert (forward[2].title, forward[2].sheet_number) == (backward[0].title, backward[0].sheet_number) == ("SECTIONS", "A-9")


def test_resolution_does_not_mutate_the_page_analyses():
    doc = _right_siblings(fitz.open())
    _raster_sheet(doc)
    engine = RasterOCR({3: _block(title="ELEVATIONS", number="A-206")})
    analyses = [authority.analyse_page(page, i + 1, ocr_engine=engine) for i, page in enumerate(doc)]
    before = [(a.source, list(a.candidates), list(a.sheet_numbers), a.title_block, a.recovery is not None) for a in analyses]
    first = authority.resolve_document(analyses)
    after = [(a.source, list(a.candidates), list(a.sheet_numbers), a.title_block, a.recovery is not None) for a in analyses]
    assert before == after
    assert [r.title for r in authority.resolve_document(analyses)] == [r.title for r in first]


def test_text_pages_are_never_read_even_with_a_footer_image():
    doc = fitz.open()
    page = doc.new_page(width=A4[0], height=A4[1])
    for row in range(40):
        _text(page, 50, 40 + 18 * row, f"Item {row}: supply and fix 200 mm blockwork in cement mortar 1:4.", 8)
    _image(page, (50.0, 760.0, 545.0, 830.0))
    engine = RasterOCR([("DRAWING TITLE", (60, 770, 120, 778)), ("GROUND FLOOR PLAN", (60, 782, 160, 794))])
    assert authority.resolve_page(page, 1, ocr_engine=engine).title == ""
    assert engine.calls == []


@pytest.mark.parametrize("text", ["DRAWING NUMBER REVISION", "DRAWN CHECKED SCALE", "PROJECT NUMBER DRAWING NUMBER REVISION"])
def test_run_together_labels_are_split(text):
    pieces = authority.split_label_runs(authority.Cell(text, 0.0, 0.0, 300.0, 10.0, 8.0, source="ocr"))
    assert len(pieces) >= 2 and all(authority.parse_label(piece) is not None for piece in pieces)
    assert pieces[0].x1 < pieces[1].x0 <= pieces[-1].x0


@pytest.mark.parametrize("text", ["PROJECT TITLE", "DRAWING TITLE SITE PLAN", "DRAWING TITLE GENERAL NOTES AND REVISIONS",
                                  "Drawing No. : 1 of 3", "GROUND FLOOR PLAN"])
def test_labels_and_titles_are_not_split(text):
    assert len(authority.split_label_runs(authority.Cell(text, 0.0, 0.0, 300.0, 10.0, 8.0, source="ocr"))) == 1


# native text: a value centred under its label (centred title blocks)

def test_a_value_centred_under_its_label_is_read_whole():
    doc = fitz.open()
    page = doc.new_page(width=A3[0], height=A3[1])
    centre = 1110.0

    def centred(y, text, size=6):
        page.insert_text((centre - fitz.get_text_length(text, fontname="helv", fontsize=size) / 2, y), text, fontsize=size)

    for y, text in ((520, "PROJECT"), (528, "PROPOSED CLASSROOM"), (560, "CLIENT"), (568, "COUNTY GOVERNMENT"),
                    (600, "DRAWING TITLE"), (608, "DESIGN SCHEME"), (616, "( Elevations, Sections & Plans )"),
                    (650, "DRAWN"), (670, "CHECKED"), (690, "SCALE"), (698, "1 : 100")):
        centred(y, text)
    result = authority.resolve_page(page, 1, allow_ocr=False)
    assert result.title == "DESIGN SCHEME ( Elevations, Sections & Plans )"


# OCR line heights are rough: a multi-line value still reads whole

def test_an_ocr_value_whose_line_heights_vary_is_read_whole():
    lines = [(text, box) for text, box in _block(title="")]
    lines += [("GENERAL LABORATORIES - ROOF FLOOR", (1000.0, 606.0, 1130.0, 611.1)),     # 5 pt box
              ("COLD WATER PLUMBING &", (1000.0, 612.3, 1080.0, 619.8)),                 # 7.5 pt box
              ("TANKS LAYOUT", (1000.0, 619.8, 1050.0, 627.8))]
    doc, page = _sheet(images=[PANEL])
    result = authority.resolve_page(page, 1, ocr_engine=RasterOCR(lines))
    assert result.title == "GENERAL LABORATORIES - ROOF FLOOR COLD WATER PLUMBING & TANKS LAYOUT"


# OCR text never makes a native heading look dominant

def test_ocr_text_does_not_promote_a_native_heading():
    doc, page = _sheet(notes=False, images=[PANEL])
    for i in range(1, 9):
        _text(page, 60, 60 + 14 * i, f"{i}. All reinforcement shall be lapped at mid span unless noted otherwise.", 9)
    _text(page, 400, 400, "SITE LAYOUT", 12)   # 1.33 x the native body text: not a dominant heading
    # Many small OCR lines inside the panel (a revision table): read text must not lower the body-text size.
    tiny = [(f"Ref {i}: see schedule", (1150.0, 507.0 + 2.2 * i, 1183.0, 509.0 + 2.2 * i)) for i in range(30)]
    engine = RasterOCR(_block(title="") + tiny)
    result = authority.resolve_page(page, 1, ocr_engine=engine)
    assert result.title == "" and result.sheet_number == "A-201"


# a sibling with another layout: the raster block runs past the region the siblings demonstrate

def test_a_title_block_running_past_the_sibling_region_is_read_to_its_end():
    doc = _right_siblings(fitz.open())
    _raster_sheet(doc)
    # The siblings' region ends about 723 pt down. Here a DATE field sits at that edge and the
    # drawing-number field below it, outside the region.
    lines = [(text, box) for text, box in _block(number="", number_label="")]
    lines += [("DATE", (1000.0, 708.0, 1020.0, 715.5)), ("DRAWING NO", (1000.0, 735.0, 1033.0, 742.5)),
              ("A-207", (1000.0, 748.0, 1030.0, 760.5))]
    engine = RasterOCR({3: lines})
    results = _resolve(doc, engine)
    assert (results[2].title, results[2].sheet_number) == ("GROUND FLOOR PLAN", "A-207")
    strategies = [read["strategy"] for read in results[2].ocr["reads"]]
    assert strategies == ["title-block region of sibling sheets", "title block continued past the region read"]
    first, extension = (read["region"] for read in results[2].ocr["reads"])
    assert extension[1] == pytest.approx(first[3], abs=0.002), "the strip continues from the region's edge"


def test_a_complete_block_inside_the_sibling_region_is_not_extended():
    doc = _right_siblings(fitz.open())
    _raster_sheet(doc)
    lines = [(text, box) for text, box in _block(number="", number_label="")]   # no drawing-number field at all
    results = _resolve(doc, RasterOCR({3: lines}))
    assert (results[2].title, results[2].sheet_number) == ("GROUND FLOOR PLAN", "")
    assert [read["strategy"] for read in results[2].ocr["reads"]] == ["title-block region of sibling sheets"]


# a value only OCR supplies is accepted once a second, independent read agrees

class Rereads(RasterOCR):
    """Reads some text differently when it is read again on its own at a finer resolution."""

    def __init__(self, lines, changes):
        super().__init__(lines)
        self.changes = changes

    def recognize_page_rect(self, page, clip_rect=None, dpi=150):
        lines = super().recognize_page_rect(page, clip_rect, dpi)
        if dpi >= 400:
            for old, new in self.changes.items():
                lines = [dict(line, text=line["text"].replace(old, new)) for line in lines]
        return lines


def test_a_sheet_number_whose_second_read_disagrees_fails_closed():
    doc, page = _sheet(images=[PANEL])
    result = authority.resolve_page(page, 1, ocr_engine=Rereads(_block(), {"A-201": "A-2O1"}))
    assert result.title == "GROUND FLOOR PLAN"
    assert result.sheet_number == "" and "disagrees" in result.sheet_number_source
    assert {check["field"]: check["agree"] for check in result.ocr["checks"]} == {"title": True, "sheet_number": False}


def test_a_title_whose_second_read_disagrees_fails_closed():
    doc, page = _sheet(images=[PANEL])
    result = authority.resolve_page(page, 1, ocr_engine=Rereads(_block(), {"GROUND FLOOR PLAN": "GROUND FL00R PLAN"}))
    assert result.title == "" and result.sheet_number == "A-201"
    rejected = [c for c in result.candidates if c.get("rejected") == "a second OCR read of it disagrees"]
    assert [c["text"] for c in rejected] == ["GROUND FLOOR PLAN"]


# native text wins over OCR of the same text

def test_native_text_wins_over_a_misread_of_it():
    doc, page = _sheet(images=[PANEL])
    _text(page, 1000, 690, "DRAWING NO", 6)
    _text(page, 1000, 704, "A-201", 10)
    # OCR boxes sit a little off the native text, as they do in practice.
    lines = [(text.replace("A-201", "A-2O1"), (box[0] + 3.0, box[1], box[2] + 3.0, box[3]) if text in ("DRAWING NO", "A-201") else box)
             for text, box in _block()]
    result = authority.resolve_page(page, 1, ocr_engine=RasterOCR(lines))
    assert result.title == "GROUND FLOOR PLAN"
    assert result.sheet_number == "A-201" and "OCR" not in result.sheet_number_source


# OCR text never joins a native heading

def test_ocr_text_does_not_extend_a_native_heading():
    doc = fitz.open()
    page = _raster_sheet(doc)
    _text(page, 400, 760, "LABORATORY", 14)   # native, large, but not a drawing-title phrase on its own
    lines = _block(title="") + [("FLOOR PLAN", (400.0, 764.0, 480.0, 781.5))]
    result = authority.resolve_page(page, 1, ocr_engine=RasterOCR(lines))
    assert result.title == "" and result.sheet_number == "A-201"


# a sibling's field position never supplies OCR text as a title

def test_a_learned_field_position_never_supplies_ocr_text():
    doc = _right_siblings(fitz.open())
    _raster_sheet(doc)
    lines = [(text, box) for text, box in _block(title="ELEVATIONS", title_label="")]   # a title with no label
    results = _resolve(doc, RasterOCR({3: lines}))
    assert results[2].title == "" and results[2].source != "layout"
    assert results[2].sheet_number == "A-201"


def test_the_second_read_leaves_a_margin_round_the_value():
    # OCR detection garbles text that touches the edge of its image, so the check read keeps a margin.
    doc, page = _sheet(images=[PANEL])
    engine = RasterOCR(_block())
    result = authority.resolve_page(page, 1, ocr_engine=engine)
    assert result.sheet_number == "A-201"
    value = next(box for text, box in _block() if text == "A-201")
    checks = [clip for _p, clip, dpi in engine.calls if dpi == 400]
    assert any(clip[0] <= value[0] - 6 and clip[1] <= value[1] - 6 and clip[2] >= value[2] + 6 and clip[3] >= value[3] + 6
               for clip in checks)


def test_a_stray_mark_in_the_second_read_of_a_title_is_tolerated_but_not_in_a_code():
    # Ruling lines round a field often read as a stray mark; words survive it, codes must not.
    doc, page = _sheet(images=[PANEL])
    result = authority.resolve_page(page, 1, ocr_engine=Rereads(_block(), {"GROUND FLOOR PLAN": "GROUND1 FLOOR PLAN", "A-201": "No.:A-201"}))
    assert result.title == "GROUND FLOOR PLAN"
    assert result.sheet_number == "A-201", "the whole code is read again, beside other words"
    for second in ("A-2B1", "A-2011"):
        doc, page = _sheet(images=[PANEL])
        result = authority.resolve_page(page, 1, ocr_engine=Rereads(_block(), {"A-201": second}))
        assert result.sheet_number == "", f"{second!r} is another code"

