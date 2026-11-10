"""Synthetic proof for the source-owned input path of the elevation label -> kind proposal (words, strokes, outlines)."""
from __future__ import annotations

import hashlib
import random
from types import SimpleNamespace

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
import pb_elevation_label_kind_proposal_shadow as kp
import pb_elevation_source_owned_witness_adapter as adapter
from pb_elevation_door_vertical_witness_shadow import TEXT_CORROBORATED, TEXT_RAW_UNVERIFIED
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_elevation_door_vertical_witness_shadow_v1 import _synthetic_pdf, synthetic_page

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED


def W(x0, y0, x1, y1, text, rid, trust="corroborated"):
    return (x0, y0, x1, y1, text, rid, trust)


def entry_words(dx=0.0, dy=0.0, trust="corroborated"):
    # two stacked text lines (as on a real sheet), 8.7 pt high; the second line has two words
    return [W(150 + dx, 310 + dy, 185 + dx, 318.7 + dy, "ALUMINIUM", "w1", trust),
            W(150 + dx, 318.9 + dy, 168 + dx, 327.6 + dy, "ENTRY", "w2", trust),
            W(169.6 + dx, 318.9 + dy, 188 + dx, 327.6 + dy, "DOOR", "w3", trust)]


# ------------------------------------------------------------------------------------------------ words -> label blocks
def test_stacked_lines_form_one_label_and_a_distant_label_stays_separate():
    other = [W(300.0, 310.0, 320.0, 318.7, "GARAGE", "g1"), W(321.6, 310.0, 340.0, 318.7, "DOOR", "g2")]
    blocks = adapter.label_blocks(entry_words() + other)
    assert [b.text for b in blocks] == ["ALUMINIUM ENTRY DOOR", "GARAGE DOOR"]
    assert blocks[0].receipt_ids == ("w1", "w2", "w3") and blocks[0].text_trust == TEXT_CORROBORATED
    assert blocks[0].bbox == (150.0, 310.0, 188.0, 327.6)


def test_blocks_without_a_kind_token_are_dropped():
    words = entry_words() + [W(400.0, 100.0, 440.0, 108.7, "PIER", "p1"), W(442.0, 100.0, 470.0, 108.7, "CLAD", "p2")]
    assert [b.text for b in adapter.label_blocks(words)] == ["ALUMINIUM ENTRY DOOR"]


def test_label_trust_is_the_worst_of_its_words():
    words = entry_words()
    words[1] = W(*words[1][:6], "raw_unverified")
    assert adapter.label_blocks(words)[0].text_trust == TEXT_RAW_UNVERIFIED
    assert adapter.label_blocks(entry_words(trust=""))[0].text_trust == TEXT_RAW_UNVERIFIED       # unknown is never corroborated


def test_label_blocks_are_order_invariant_and_ignore_unusable_words():
    words = entry_words() + [W(300.0, 310.0, 320.0, 318.7, "GARAGE", "g1"), W(321.6, 310.0, 340.0, 318.7, "DOOR", "g2")]
    ref = adapter.label_blocks(words)
    rng = random.Random(3)
    for _ in range(20):
        shuffled = words[:]
        rng.shuffle(shuffled)
        assert adapter.label_blocks(shuffled) == ref
    junk = [W(float("nan"), 0.0, 1.0, 1.0, "DOOR", "j1"), W(5.0, 5.0, 4.0, 9.0, "DOOR", "j2"), W(0.0, 0.0, 5.0, 5.0, "  ", "j3")]
    assert adapter.label_blocks(words + junk) == ref


def test_translation_does_not_change_label_blocks():
    a = adapter.label_blocks(entry_words())
    b = adapter.label_blocks(entry_words(dx=900.0, dy=-250.0))
    assert [x.text for x in a] == [x.text for x in b] and a[0].receipt_ids == b[0].receipt_ids


def test_two_labels_one_above_the_other_with_a_real_gap_do_not_merge():
    a = [W(150.0, 310.0, 185.0, 318.7, "ENTRY", "a1"), W(186.5, 310.0, 205.0, 318.7, "DOOR", "a2")]
    b = [W(150.0, 330.0, 175.0, 338.7, "FIXED", "b1"), W(176.5, 330.0, 205.0, 338.7, "WINDOW", "b2")]   # 11.3 pt gap > 0.6 line heights
    assert [x.text for x in adapter.label_blocks(a + b)] == ["ENTRY DOOR", "FIXED WINDOW"]


def test_mixed_tokens_in_one_block_are_kept_so_the_core_can_abstain():
    blocks = adapter.label_blocks([W(150.0, 310.0, 175.0, 318.7, "DOOR", "a1"), W(176.5, 310.0, 205.0, 318.7, "WINDOW", "a2")])
    assert len(blocks) == 1 and kp.label_kind(blocks[0].text) == (None, kp.MIXED_KIND_TOKENS)


def test_trust_constants_agree_between_the_two_cores():
    assert TEXT_CORROBORATED == kp.TEXT_CORROBORATED and TEXT_RAW_UNVERIFIED == kp.TEXT_RAW


# ------------------------------------------------------------------------------------------------ outlines + strokes + words
def synthetic_elevation():
    lines, rects, words = synthetic_page()
    lines = [(*l, f"line{i}") for i, l in enumerate(lines)]
    rects = [(*r, (f"rect{i}a", f"rect{i}b")) for i, r in enumerate(rects)]
    words = [(*w, f"word{i}", "corroborated") for i, w in enumerate(words)]
    view = adapter.extract_views(lines, rects, words)[0]
    strokes = [(188.25, 314.2, 217.0, 314.2, "ls1"), (217.0, 314.2, 217.0, 270.0, "ls2")]
    return view, strokes


def _outline_id(view, x0, x1):
    return next(o.outline_id for o in view["outlines"] if abs(o.x0 - x0) < 0.01 and abs(o.x1 - x1) < 0.01)


def test_leader_from_the_stacked_label_proposes_the_kind_of_the_nested_door():
    view, strokes = synthetic_elevation()
    r = adapter.kind_proposal_for_outline("rec", _outline_id(view, 200.0, 234.0), view["outlines"], strokes, entry_words())
    assert r.status is CAND and r.kind == "door" and r.text_trust == "corroborated" and len(r.nested_outline_ids) >= 2
    assert {"w1", "w2", "w3", "ls1", "ls2"} <= set(r.source_observation_ids)
    window = _outline_id(view, 300.0, 349.0)
    assert adapter.kind_proposal_for_outline("w", window, view["outlines"], strokes, entry_words()).status is ABST   # not the window


def test_the_enclosing_frame_outline_is_the_same_physical_door():
    view, strokes = synthetic_elevation()
    frame = _outline_id(view, 198.4, 235.6)
    r = adapter.kind_proposal_for_outline("frame_rec", frame, view["outlines"], strokes, entry_words())
    assert r.status is CAND and r.kind == "door"


def test_raw_words_give_a_diagnostic_only_proposal():
    view, strokes = synthetic_elevation()
    r = adapter.kind_proposal_for_outline("rec", _outline_id(view, 200.0, 234.0), view["outlines"], strokes, entry_words(trust="raw_unverified"))
    assert r.status is CAND and r.text_trust == "raw_unverified_diagnostic_only"


def test_a_label_with_no_leader_never_gives_a_kind_to_a_door_shaped_outline():
    view, _ = synthetic_elevation()
    r = adapter.kind_proposal_for_outline("rec", _outline_id(view, 200.0, 234.0), view["outlines"], [], entry_words())
    assert r.status is ABST and r.kind is None


def test_a_window_label_with_a_leader_into_the_window_outline_does_not_label_the_door():
    view, _ = synthetic_elevation()
    words = [W(320.0, 310.0, 345.0, 318.7, "ALUMINIUM", "x1"), W(347.0, 310.0, 375.0, 318.7, "WINDOW", "x2")]
    strokes = [(376.0, 314.2, 390.0, 314.2, "t1"), (390.0, 314.2, 390.0, 290.0, "t2"), (390.0, 290.0, 330.0, 290.0, "t3"),
               (330.0, 290.0, 330.0, 270.0, "t4")]
    window = _outline_id(view, 300.0, 349.0)
    assert adapter.kind_proposal_for_outline("w", window, view["outlines"], strokes, words).kind == "window"
    assert adapter.kind_proposal_for_outline("d", _outline_id(view, 200.0, 234.0), view["outlines"], strokes, words).status is ABST


def test_the_outline_is_the_drawn_leaf_not_the_frame_that_gives_its_base():
    # The leaf stops 2.26 pt above the frame base; a leader tip in that band is inside the frame, not the leaf.
    view, _ = synthetic_elevation()
    strokes = [(188.25, 314.2, 217.0, 314.2, "ls1"), (217.0, 314.2, 217.0, 299.0, "ls2")]
    leaf = _outline_id(view, 200.0, 234.0)
    assert adapter.kind_proposal_for_outline("rec", leaf, view["outlines"], strokes, entry_words()).status is ABST
    assert adapter.kind_proposal_for_outline("fr", _outline_id(view, 198.4, 235.6), view["outlines"], strokes, entry_words()).status is CAND


def _fact(**kw):
    base = dict(fill=None, kind="line", stroke_color=(0.0, 0.0, 0.0), stroke_opacity=1.0, geometry=(0.0, 0.0, 10.0, 0.0))
    base.update(kw)
    return SimpleNamespace(**base)


def test_only_opaque_stroke_only_lines_are_stroke_ink():
    assert adapter.is_stroke_ink(_fact())
    assert not adapter.is_stroke_ink(_fact(fill=(0.9, 0.9, 0.9)))                 # fill + border: an edge of a painted shape
    assert not adapter.is_stroke_ink(_fact(kind="rect_edge"))
    assert not adapter.is_stroke_ink(_fact(stroke_color=None))                    # fill-only
    assert not adapter.is_stroke_ink(_fact(stroke_opacity=None))
    assert not adapter.is_stroke_ink(_fact(stroke_opacity=0.5))                   # translucent
    assert adapter.is_stroke_ink(_fact(stroke_opacity=0.99))
    assert not adapter.is_stroke_ink(_fact(geometry=(0.0, 0.0, 10.0)))


# ------------------------------------------------------------------------------------------------ real producers
def _kind_pdf() -> bytes:
    doc = fitz.open(stream=_synthetic_pdf(), filetype="pdf")
    page = doc[0]
    # a rectangle with BOTH a fill and a border: its four edges are the border of a painted shape, not leader strokes
    page.draw_polyline([(400.0, 100.0), (440.0, 100.0), (440.0, 140.0), (400.0, 140.0), (400.0, 100.0)],
                       color=(0, 0, 0), fill=(0.9, 0.9, 0.9), width=0.34, closePath=True)
    page.insert_text((150, 318), "ALUMINIUM", fontsize=7)
    page.insert_text((150, 326), "ENTRY DOOR", fontsize=7)
    page.draw_line((190.0, 314.0), (217.0, 314.0), color=(0, 0, 0), width=0.34)
    page.draw_line((217.0, 314.0), (217.0, 270.0), color=(0, 0, 0), width=0.34)
    page.draw_line((260.0, 330.0), (290.0, 330.0), color=(0, 0, 0), width=0.34, stroke_opacity=0.5)      # translucent: not ink
    return doc.tobytes()


def test_real_producers_give_opaque_stroke_only_segments_and_no_fill_edges():
    payload = _kind_pdf()
    source = SourceVisibilityProducer(producer_method="live-physical-net-wall", producer_version="1")
    sha = hashlib.sha256(payload).hexdigest()
    initial = source.ingest_native_pdf_bytes(document_id=f"live-source:{sha[:32]}", source_bytes=payload,
                                             source_locator="memory://kind.pdf", page_ids=(1,))
    page = adapter.read_source_owned_page(source, revision_id=initial.revision.revision_id, page_id="1")
    assert page.strokes
    rect_ids = {i for r in page.rects for i in r[5]}
    assert not ({s[4] for s in page.strokes} & rect_ids)                         # a filled rectangle's edges are not strokes
    near = [s for s in page.strokes if abs(s[0] - 217.0) < 0.1 or abs(s[2] - 217.0) < 0.1]
    assert len(near) == 2                                                         # both leader pieces
    assert not any(abs(s[1] - 330.0) < 0.1 and abs(s[0] - 260.0) < 0.1 for s in page.strokes)   # the translucent line is absent
    assert not any(abs(s[0] - 400.0) < 0.1 or abs(s[0] - 440.0) < 0.1 for s in page.strokes)    # the filled+bordered rectangle's edges
    assert page.strokes == tuple(sorted(page.strokes))
    view = adapter.source_owned_views(page)[0]
    leaf = _outline_id(view, 200.0, 234.0) if any(abs(o.x0 - 200.0) < 0.01 for o in view["outlines"]) else next(
        o.outline_id for o in view["outlines"] if abs(o.x0 - 200.0) < 0.1 and abs(o.x1 - 234.0) < 0.1)
    r = adapter.kind_proposal_for_outline("rec", leaf, view["outlines"], page.strokes, page.words)
    assert r.status is CAND and r.kind == "door", r.reason_codes
    assert r.text_trust in ("corroborated", "raw_unverified_diagnostic_only")
    assert all(r.source_observation_ids)
