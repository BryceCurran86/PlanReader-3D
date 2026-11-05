"""Exact original native text paint within a F07 viewport, not font-cell expansion."""
from types import SimpleNamespace

import fitz
import pytest

from pb_drawing_evidence_binding import DrawingViewType
from pb_source_material_semantic_authority import (
    _TrustedTextWord, _complete_source_plan_lines,
    _original_native_word_paint_within_parent,
)
from pb_viewport_segmentation import SegmentedViewport, ViewportSegmentationStatus


def _page():
    doc = fitz.open()
    page = doc.new_page(width=600, height=300)
    page.insert_text((120,135), "OFFICE", fontsize=14)
    return doc, page


def _inputs(page):
    native_word = page.get_text("words", sort=False)[0]
    original_bbox = tuple(native_word[:4])
    word = _TrustedTextWord(
        observation_id="native-original-word", page_id="1",
        source_partition_id="source-partition", text="OFFICE",
        bbox=original_bbox, block_no=native_word[5],
        line_no=native_word[6], word_no=native_word[7],
        trusted=True, reason_codes=(),
    )
    span = page.get_texttrace()[0]
    receipt = SimpleNamespace(
        trusted=True, raw_text="OFFICE", page_id="1",
        source_partition_id="source-partition",
        geometry=original_bbox,
        sequence_number=span["seqno"], trace_sequence_numbers=(),
    )
    native={tuple(native_word[5:8]): [native_word]}
    trace={span["seqno"]:[span]}
    bboxlog=page.get_bboxlog()
    # Native font cell extends beyond this exact, unchanged paint-owned scope.
    view=(119.,123.,173.,137.)
    assert not (view[1] <= original_bbox[1] and view[3] >= original_bbox[3])
    return word, receipt, native, trace, bboxlog, view


def _viewport(bbox):
    return SegmentedViewport(
        view_id="original-physical-finish-plan",
        page_number=1, view_type=DrawingViewType.FLOOR_FINISH_PLAN.value,
        label="SOURCE-OWNED PLAN", title_bbox=bbox, bounding_box=bbox,
        status=ViewportSegmentationStatus.RESOLVED.value,
        boundary_source="native_original_plan", confidence=1.,
    )


def test_original_painted_glyph_inside_parent_cannot_be_rejected_for_font_cell():
    doc, page = _page()
    try:
        word,receipt,native,trace,bboxlog,view = _inputs(page)
        assert _original_native_word_paint_within_parent(
            word,receipt,native_words_by_address=native,
            trace_by_seq=trace,bboxlog=bboxlog,parent_bbox=view)
        _, before, reasons, unresolved = _complete_source_plan_lines(
            (word,), _viewport(view))
        assert not before
        assert unresolved==("native-original-word",)
        lines, after, reasons, unresolved = _complete_source_plan_lines(
            (word,), _viewport(view),
            original_paint_owned_ids=frozenset((word.observation_id,)),
        )
        assert after and not unresolved
        assert len(lines)==1 and lines[0][0]=="OFFICE"
        assert lines[0][2]==("native-original-word",)
        # The public material issuer receives no metric, W4 or threshold here.
    finally:
        doc.close()


@pytest.mark.parametrize("tamper",[
    "paint_clipped","different_word","wrong_address","missing_seq",
    "duplicate_seq","invalid_seq","wrong_trace","untrusted",
    "tampered_geometry","tampered_partition",
])
def test_original_paint_exception_abstains_for_unproven_word_or_paint(tamper):
    doc,page=_page()
    try:
        word,receipt,native,trace,bboxlog,view=_inputs(page)
        if tamper=="paint_clipped":
            view=(119.,127.,173.,137.)
        elif tamper=="different_word":
            word=_TrustedTextWord(**{**vars(word),"text":"FOOD"})
        elif tamper=="wrong_address":
            word=_TrustedTextWord(**{**vars(word),"word_no":word.word_no+1})
        elif tamper=="missing_seq":
            receipt=SimpleNamespace(**{**vars(receipt),"sequence_number":None})
        elif tamper=="duplicate_seq":
            receipt=SimpleNamespace(**{
                **vars(receipt),"trace_sequence_numbers":(0,0)})
        elif tamper=="invalid_seq":
            receipt=SimpleNamespace(**{
                **vars(receipt),"trace_sequence_numbers":(99,)})
        elif tamper=="wrong_trace":
            trace={0:[{**trace[0][0],"type":99}]}
        elif tamper=="untrusted":
            word=_TrustedTextWord(**{**vars(word),"trusted":False})
        elif tamper=="tampered_geometry":
            word=_TrustedTextWord(**{
                **vars(word),"bbox":(word.bbox[0]+1.,*word.bbox[1:])})
        else:
            receipt=SimpleNamespace(**{
                **vars(receipt),"source_partition_id":"foreign"})
        assert not _original_native_word_paint_within_parent(
            word,receipt,native_words_by_address=native,trace_by_seq=trace,
            bboxlog=bboxlog,parent_bbox=view)
    finally:
        doc.close()


def test_foreign_original_text_or_changed_paint_cannot_be_admitted_as_mark():
    doc,page=_page()
    try:
        word,receipt,native,trace,bboxlog,view=_inputs(page)
        # Two separate native words claiming one source address are ambiguous.
        native={k:v*2 for k,v in native.items()}
        assert not _original_native_word_paint_within_parent(
            word,receipt,native_words_by_address=native,
            trace_by_seq=trace,bboxlog=bboxlog,parent_bbox=view)
        # Even a trusted word may not be promoted with an unverified token.
        _,complete,_,unresolved=_complete_source_plan_lines(
            (word,),_viewport(view),
        )
        assert not complete and unresolved==(word.observation_id,)
    finally:
        doc.close()
