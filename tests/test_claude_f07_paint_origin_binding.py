"""F07 paint ownership binds a word's paint to its OWN native characters (exact pen origin), not to a rectangle proxy.

Synthetic pages only, except the last test, which needs the private original and skips without it.  No project number, name or
expected quantity is used anywhere in this file.
"""
from __future__ import annotations

import copy
import hashlib
import math
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

import pb_source_material_semantic_authority as semantic
from pb_source_material_semantic_authority import (
    _TrustedTextWord,
    _bbox_fully_inside,
    _float32,
    _native_word_chars_by_address,
    _original_native_word_paint_within_parent,
)
from pb_viewport_segmentation import segment_source_page_viewports
from test_source_owned_physical_plan_view import _sheet, _source
from tests.test_gpt2_native_plan_paint_viewport_ownership import _owned


def _page_with(text: str, *, rotation: int = 0, origin=(120, 135), width=600, height=300):
    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    page.insert_text(origin, text, fontsize=14)
    if rotation:
        page.set_rotation(rotation)
    return doc, page


def _native(page):
    rows = {}
    for row in page.get_text("words", sort=False):
        rows.setdefault(tuple(row[5:8]), []).append(row)
    return rows


def _setup(page, index: int = 0):
    """(word, receipt, kwargs) for the index-th native word, with the production characters and a parent that holds its paint."""
    native = _native(page)
    row = sorted(page.get_text("words", sort=False), key=lambda r: (r[5], r[6], r[7]))[index]
    span = next(s for s in page.get_texttrace() if len(s["chars"]) >= len(row[4]))
    word = _TrustedTextWord(
        observation_id=f"word-{index}", page_id="1", source_partition_id="partition",
        text=row[4], bbox=tuple(row[:4]), block_no=row[5], line_no=row[6], word_no=row[7],
        trusted=True, reason_codes=())
    receipt = SimpleNamespace(
        trusted=True, raw_text=row[4], page_id="1", source_partition_id="partition", geometry=tuple(row[:4]),
        sequence_number=span["seqno"], trace_sequence_numbers=())
    paint = tuple(float(v) for v in page.get_bboxlog()[span["seqno"]][1])
    # The check is for words whose native CELL leaves the parent: keep the paint inside, let the cell stick out.
    parent = (paint[0] - 5.0, paint[1] - 0.3, paint[2] + 5.0, paint[3] + 0.3)
    kwargs = dict(
        native_words_by_address=native, trace_by_seq={span["seqno"]: [span]}, bboxlog=page.get_bboxlog(), parent_bbox=parent)
    return word, receipt, kwargs, span


def _with_chars(span, mutate):
    chars = [list(c) for c in span["chars"]]
    mutate(chars)
    return {**span, "chars": tuple(tuple(c) for c in chars)}


# ------------------------------------------------------------------ the production characters

def test_every_ordinary_word_gets_its_native_characters():
    doc, page = _page_with("ALPHA BETA GAMMA")
    try:
        chars = _native_word_chars_by_address(page, _native(page))
        assert sorted("".join(c for c, _ in v) for v in chars.values()) == ["ALPHA", "BETA", "GAMMA"]
        assert all(len(origin) == 2 and all(math.isfinite(x) for x in origin) for v in chars.values() for _, origin in v)
    finally:
        doc.close()


def test_a_word_whose_native_row_disagrees_with_its_characters_gets_no_entry():
    doc, page = _page_with("ALPHA BETA")
    try:
        native = _native(page)
        address, rows = next(iter(native.items()))
        wrong_text = {**native, address: [(*rows[0][:4], "XXXXX", *rows[0][5:])]}
        assert address not in _native_word_chars_by_address(page, wrong_text)
        wrong_box = {**native, address: [(rows[0][0] + 0.5, *rows[0][1:])]}
        assert address not in _native_word_chars_by_address(page, wrong_box)
        assert address not in _native_word_chars_by_address(page, {**native, address: rows * 2})
        assert address in _native_word_chars_by_address(page, native)
    finally:
        doc.close()


def test_building_the_characters_does_not_change_the_native_words():
    doc, page = _page_with("ALPHA BETA")
    try:
        native = _native(page)
        before = copy.deepcopy(native)
        _native_word_chars_by_address(page, native)
        assert native == before
    finally:
        doc.close()


# ------------------------------------------------------------------ the binding

def test_a_word_is_owned_by_its_own_glyphs():
    doc, page = _page_with("OFFICE")
    try:
        word, receipt, kwargs, _ = _setup(page)
        assert _owned(page, word, receipt, **kwargs)
    finally:
        doc.close()


@pytest.mark.parametrize("noise", [0.0008, 0.0018, 0.004])
def test_float_noise_between_glyph_and_word_cell_does_not_reject_a_word_whose_paint_is_inside(noise):
    """The original p11 case: the glyph rectangle starts a few thousandths of a point outside the native word cell."""
    doc, page = _page_with("OFFICE")
    try:
        word, receipt, kwargs, span = _setup(page)

        def widen(chars):
            first, last = chars[0], chars[-1]
            first[3] = (first[3][0] - noise, *first[3][1:])
            last[3] = (*last[3][:2], last[3][2] + noise, last[3][3])

        noisy = _with_chars(span, widen)
        rect = noisy["chars"][0][3]
        assert not _bbox_fully_inside(rect, word.bbox, tolerance=1e-6), "the former rectangle proxy would have rejected this word"
        kwargs["trace_by_seq"] = {span["seqno"]: [noisy]}
        assert _owned(page, word, receipt, **kwargs)
    finally:
        doc.close()


@pytest.mark.parametrize("shift", [1e-3, 0.05, 1.0, 40.0])
def test_a_glyph_whose_origin_differs_from_the_native_character_is_not_the_words_glyph(shift):
    doc, page = _page_with("OFFICE")
    try:
        word, receipt, kwargs, span = _setup(page)
        moved = _with_chars(span, lambda chars: chars[2].__setitem__(2, (chars[2][2][0] + shift, chars[2][2][1])))
        kwargs["trace_by_seq"] = {span["seqno"]: [moved]}
        assert not _owned(page, word, receipt, **kwargs)
    finally:
        doc.close()


def test_the_same_text_elsewhere_in_the_operation_cannot_be_taken_for_this_word():
    doc, page = _page_with("OFFICE OFFICE")
    try:
        first, receipt0, kwargs, span = _setup(page, 0)
        second, receipt1, _, _ = _setup(page, 1)
        assert first.text == second.text == "OFFICE" and first.bbox != second.bbox
        # each word is owned by its own run of the one 13-character operation
        assert _owned(page, first, receipt0, **kwargs)
        assert _owned(page, second, receipt1, **kwargs)
        # move the first run away: the second run (same text) must not be accepted for the first word
        away = _with_chars(span, lambda chars: [c.__setitem__(2, (c[2][0] + 90.0, c[2][1])) for c in chars[:6]])
        kwargs["trace_by_seq"] = {span["seqno"]: [away]}
        assert not _owned(page, first, receipt0, **kwargs)
        assert _owned(page, second, receipt1, **kwargs)
    finally:
        doc.close()


def test_a_different_character_at_the_same_origin_is_not_the_word():
    doc, page = _page_with("OFFICE")
    try:
        word, receipt, kwargs, span = _setup(page)
        changed = _with_chars(span, lambda chars: chars[1].__setitem__(0, ord("X")))
        kwargs["trace_by_seq"] = {span["seqno"]: [changed]}
        assert not _owned(page, word, receipt, **kwargs)
    finally:
        doc.close()


def test_missing_or_altered_native_characters_abstain():
    doc, page = _page_with("OFFICE")
    try:
        word, receipt, kwargs, _ = _setup(page)
        address = (word.block_no, word.line_no, word.word_no)
        good = _native_word_chars_by_address(page, kwargs["native_words_by_address"])
        assert address in good
        assert not _original_native_word_paint_within_parent(word, receipt, native_chars_by_address={}, **kwargs)
        wrong_text = {address: tuple(("Z", origin) for _, origin in good[address])}
        assert not _original_native_word_paint_within_parent(word, receipt, native_chars_by_address=wrong_text, **kwargs)
        shifted = {address: tuple((c, (origin[0] + 0.5, origin[1])) for c, origin in good[address])}
        assert not _original_native_word_paint_within_parent(word, receipt, native_chars_by_address=shifted, **kwargs)
        short = {address: good[address][:-1]}
        assert not _original_native_word_paint_within_parent(word, receipt, native_chars_by_address=short, **kwargs)
        junk = {address: (("O", ("x", "y")),) * len(word.text)}
        assert not _original_native_word_paint_within_parent(word, receipt, native_chars_by_address=junk, **kwargs)
        nan = {address: tuple((c, (float("nan"), origin[1])) for c, origin in good[address])}
        assert not _original_native_word_paint_within_parent(word, receipt, native_chars_by_address=nan, **kwargs)
        assert _original_native_word_paint_within_parent(word, receipt, native_chars_by_address=good, **kwargs)
    finally:
        doc.close()


def test_paint_that_really_leaves_the_parent_is_still_refused():
    doc, page = _page_with("OFFICE")
    try:
        word, receipt, kwargs, span = _setup(page)
        paint = tuple(float(v) for v in page.get_bboxlog()[span["seqno"]][1])
        kwargs["parent_bbox"] = (paint[0] + 3.0, paint[1] - 0.3, paint[2] + 5.0, paint[3] + 0.3)   # cuts the first glyphs off
        assert not _owned(page, word, receipt, **kwargs)
        kwargs["parent_bbox"] = (paint[0] - 5.0, paint[1] - 0.3, paint[2] - 3.0, paint[3] + 0.3)   # cuts the last glyphs off
        assert not _owned(page, word, receipt, **kwargs)
    finally:
        doc.close()


def test_a_foreign_glyph_over_the_word_still_refuses_it():
    doc, page = _page_with("OFFICE")
    try:
        word, receipt, kwargs, span = _setup(page)
        foreign = _with_chars(span, lambda chars: chars.append([ord("X"), ord("X"), (word.bbox[0] + 1.0, word.bbox[3] - 1.0), tuple(word.bbox)]))
        kwargs["trace_by_seq"] = {span["seqno"]: [foreign]}
        assert not _owned(page, word, receipt, **kwargs)
    finally:
        doc.close()


def test_two_independent_traces_of_one_word_stay_ambiguous():
    doc, page = _page_with("OFFICE")
    try:
        word, receipt, kwargs, span = _setup(page)
        kwargs["trace_by_seq"] = {span["seqno"]: [span, span]}
        assert not _owned(page, word, receipt, **kwargs)
    finally:
        doc.close()


def test_noise_in_the_trace_origin_below_float32_resolution_is_not_a_difference():
    doc, page = _page_with("OFFICE")
    try:
        word, receipt, kwargs, span = _setup(page)
        x = span["chars"][2][2][0]
        ulp = 2.0 ** (math.floor(math.log2(abs(x))) - 23)

        def at(delta):
            return _with_chars(span, lambda chars: chars[2].__setitem__(2, (x + delta, chars[2][2][1])))

        kwargs["trace_by_seq"] = {span["seqno"]: [at(0.25 * ulp)]}
        assert _owned(page, word, receipt, **kwargs)
        kwargs["trace_by_seq"] = {span["seqno"]: [at(3 * ulp)]}
        assert not _owned(page, word, receipt, **kwargs)
    finally:
        doc.close()


def test_a_non_finite_origin_never_binds():
    doc, page = _page_with("OFFICE")
    try:
        word, receipt, kwargs, span = _setup(page)
        address = (word.block_no, word.line_no, word.word_no)
        good = _native_word_chars_by_address(page, kwargs["native_words_by_address"])[address]
        inf = float("inf")
        poisoned_native = {address: tuple((c, (inf if i == 2 else o[0], o[1])) for i, (c, o) in enumerate(good))}
        poisoned_trace = _with_chars(span, lambda chars: chars[2].__setitem__(2, (inf, chars[2][2][1])))
        kwargs["trace_by_seq"] = {span["seqno"]: [poisoned_trace]}
        assert not _original_native_word_paint_within_parent(word, receipt, native_chars_by_address=poisoned_native, **kwargs)
    finally:
        doc.close()


def test_a_glyph_without_area_is_not_paint():
    doc, page = _page_with("OFFICE")
    try:
        word, receipt, kwargs, span = _setup(page)
        flat = _with_chars(span, lambda chars: chars[2].__setitem__(3, (chars[2][3][0], chars[2][3][1], chars[2][3][0], chars[2][3][3])))
        kwargs["trace_by_seq"] = {span["seqno"]: [flat]}
        assert not _owned(page, word, receipt, **kwargs)
    finally:
        doc.close()


def test_characters_are_found_on_every_line_of_a_block():
    doc, page = _page_with("ALPHA BETA" + chr(10) + "GAMMA DELTA")
    try:
        native = _native(page)
        chars = _native_word_chars_by_address(page, native)
        assert {addr[1] for addr in native} == {0, 1}
        assert set(chars) == set(native)
        for address, rows in native.items():
            assert "".join(c for c, _ in chars[address]) == rows[0][4]
    finally:
        doc.close()


# ------------------------------------------------------------------ through the producer's caller

def _edge_plan(paint_bottom_offset):
    """A source-owned plan view with one trusted label whose paint bottom sits ``paint_bottom_offset`` pt above (negative: below) the view's bottom edge."""
    base = _sheet(role="FLOOR FINISH PLAN")
    source, published = _source(base)
    (view,) = [v for v in segment_source_page_viewports(
        source, revision_id=published.revision.revision_id, page_id="1", physical_plan_view_shadow=True)
        if v.provenance.get("source_owned_plan_view_proven") is True]
    bottom = view.bounding_box[3]
    with fitz.open(stream=base, filetype="pdf") as doc:
        page = doc[0]
        before = len(page.get_bboxlog())
        page.insert_text((200.0, bottom - 6.0), "FT9", fontsize=8)
        painted = [e[1] for e in page.get_bboxlog()[before:] if e[0] == "fill-text"][-1]
    shift = (bottom - paint_bottom_offset) - painted[3]
    with fitz.open(stream=base, filetype="pdf") as doc:
        doc[0].insert_text((200.0, bottom - 6.0 + shift), "FT9", fontsize=8)
        data = doc.tobytes()
    source, published = _source(data)
    (view,) = [v for v in segment_source_page_viewports(
        source, revision_id=published.revision.revision_id, page_id="1", physical_plan_view_shadow=True)
        if v.provenance.get("source_owned_plan_view_proven") is True]
    assert tuple(view.bounding_box) == (50.0, 50.0, 350.0, 350.0), "the label must not change the authenticated view"
    return source, published, view, semantic._trusted_words_by_page(source, published)["1"]


def test_through_the_producer_a_label_whose_cell_crosses_but_whose_paint_is_inside_is_owned():
    source, published, view, words = _edge_plan(0.3)
    crossing = [w for w in words if semantic._bbox_intersects(w.bbox, view.bounding_box)
                and not semantic._bbox_fully_inside(w.bbox, view.bounding_box)]
    assert len(crossing) == 1 and crossing[0].trusted and crossing[0].text == "FT9"
    owned = semantic._original_paint_owned_plan_word_ids(source, published, 1, view, words)
    assert owned == frozenset({crossing[0].observation_id})
    assert semantic._complete_source_plan_lines(words, view)[1] is False
    assert semantic._complete_source_plan_lines(words, view, original_paint_owned_ids=owned)[1] is True


def test_through_the_producer_a_label_whose_paint_leaves_the_view_is_not_owned():
    source, published, view, words = _edge_plan(-0.5)
    crossing = [w for w in words if semantic._bbox_intersects(w.bbox, view.bounding_box)
                and not semantic._bbox_fully_inside(w.bbox, view.bounding_box)]
    assert len(crossing) == 1 and crossing[0].trusted
    owned = semantic._original_paint_owned_plan_word_ids(source, published, 1, view, words)
    assert owned == frozenset()
    assert semantic._complete_source_plan_lines(words, view, original_paint_owned_ids=owned)[1] is False


# ------------------------------------------------------------------ invariance

def test_the_result_is_the_same_on_a_rotated_page():
    for rotation in (0, 90, 180, 270):
        doc, page = _page_with("OFFICE", rotation=rotation)
        try:
            word, receipt, kwargs, _ = _setup(page)
            assert _owned(page, word, receipt, **kwargs), rotation
        finally:
            doc.close()


def test_translating_the_text_changes_nothing():
    for origin in ((30, 60), (120, 135), (300, 250)):
        doc, page = _page_with("OFFICE", origin=origin)
        try:
            word, receipt, kwargs, _ = _setup(page)
            assert _owned(page, word, receipt, **kwargs), origin
        finally:
            doc.close()


def test_unrelated_text_on_the_page_changes_nothing():
    doc, page = _page_with("OFFICE")
    try:
        page.insert_text((300, 40), "UNRELATED NOTE OFFICE", fontsize=14)
        words = sorted(page.get_text("words", sort=False), key=lambda r: (r[5], r[6], r[7]))
        index = next(i for i, r in enumerate(words) if r[4] == "OFFICE" and r[0] < 200)
        word, receipt, kwargs, _ = _setup(page, index)
        assert _owned(page, word, receipt, **kwargs)
    finally:
        doc.close()


def test_the_order_of_spans_in_one_operation_does_not_matter():
    doc, page = _page_with("OFFICE")
    try:
        word, receipt, kwargs, span = _setup(page)
        far = {**span, "chars": ((ord("X"), ord("X"), (450.0, 200.0), (450.0, 200.0, 458.0, 213.0)),) * 2, "bbox": (450.0, 200.0, 458.0, 213.0)}
        for order in ([span, far], [far, span]):
            kwargs["trace_by_seq"] = {span["seqno"]: order}
            assert _owned(page, word, receipt, **kwargs)
    finally:
        doc.close()


def test_the_check_does_not_mutate_its_inputs_and_is_deterministic():
    doc, page = _page_with("OFFICE")
    try:
        word, receipt, kwargs, _ = _setup(page)
        chars = _native_word_chars_by_address(page, kwargs["native_words_by_address"])
        frozen = copy.deepcopy((kwargs, chars, receipt.__dict__))
        results = {_original_native_word_paint_within_parent(word, receipt, native_chars_by_address=chars, **kwargs) for _ in range(3)}
        assert results == {True}
        assert (kwargs, chars, receipt.__dict__) == frozen
    finally:
        doc.close()


def test_float32_rounding_is_the_source_precision_and_idempotent():
    for value in (0.0, 1045.7823486328125, 989.60595703125, -3.25):
        assert _float32(value) == _float32(_float32(value))
    assert _float32(1045.7823486328125) == 1045.7823486328125
    assert _float32(1045.7823486328125 + 1e-7) == 1045.7823486328125   # below float32 resolution here


# ------------------------------------------------------------------ original source (skips without the private PDF)

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
ORIGINAL_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


@pytest.fixture(scope="module")
def original_p11():
    if not ORIGINAL.is_file():
        pytest.skip("PRIVATE ORIGINAL SOURCE UNAVAILABLE: original p11 F07 paint ownership NOT VERIFIED")
    data = ORIGINAL.read_bytes()
    assert hashlib.sha256(data).hexdigest() == ORIGINAL_SHA
    from pb_source_visibility_authority import SourceVisibilityProducer
    from pb_viewport_segmentation import segment_source_page_viewports

    source = SourceVisibilityProducer(producer_method="claude-f07-paint-binding-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="private-source-test-only", source_bytes=data, source_locator="memory:original-p11", page_ids=("11",))
    views = [v for v in segment_source_page_viewports(
        source, revision_id=published.revision.revision_id, page_id="11", physical_plan_view_shadow=True)
        if v.provenance.get("source_owned_plan_view_proven") is True and v.bounding_box]
    assert len(views) == 1
    doc = fitz.open(stream=data, filetype="pdf")
    yield doc[10], tuple(float(v) for v in views[0].bounding_box)
    doc.close()


def test_original_p11_every_word_crossing_the_f07_cell_edge_has_its_paint_inside_the_viewport(original_p11):
    page, parent = original_p11
    native = _native(page)
    traces = {}
    for span in page.get_texttrace():
        traces.setdefault(span["seqno"], []).append(span)
    bboxlog = page.get_bboxlog()
    crossing = [
        row for row in page.get_text("words", sort=False)
        if row[0] < parent[2] and row[2] > parent[0] and row[1] < parent[3] and row[3] > parent[1]
        and not _bbox_fully_inside(tuple(row[:4]), parent, tolerance=1e-6)
    ]
    assert crossing, "the original scope has boundary-crossing word cells"
    chars = _native_word_chars_by_address(page, native)
    owned = 0
    for row in crossing:
        centre = ((row[0] + row[2]) / 2, (row[1] + row[3]) / 2)
        spans = [(seq, span) for seq, group in traces.items() for span in group
                 if row[4] in "".join(chr(int(c[0])) for c in span["chars"])
                 and span["bbox"][0] <= centre[0] <= span["bbox"][2] and span["bbox"][1] <= centre[1] <= span["bbox"][3]]
        if len(spans) != 1:
            continue
        seq, span = spans[0]
        word = _TrustedTextWord(
            observation_id="o", page_id="11", source_partition_id="p", text=row[4], bbox=tuple(row[:4]),
            block_no=row[5], line_no=row[6], word_no=row[7], trusted=True, reason_codes=())
        receipt = SimpleNamespace(
            trusted=True, raw_text=row[4], page_id="11", source_partition_id="p", geometry=tuple(row[:4]),
            sequence_number=seq, trace_sequence_numbers=())
        if _original_native_word_paint_within_parent(
                word, receipt, native_words_by_address=native, native_chars_by_address=chars,
                trace_by_seq={seq: [span]}, bboxlog=bboxlog, parent_bbox=parent):
            owned += 1
    # The words whose glyph paint is inside the viewport are all admitted; none is excluded by float noise.
    assert owned == len(crossing)
