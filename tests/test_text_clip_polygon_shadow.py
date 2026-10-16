"""Shadow clip verdicts: exact polygon clips and rotated pages are resolved only when proven; nothing the authority proves is contradicted."""
from __future__ import annotations

import random

import fitz
import pytest

import pb_pdf_text_integrity_authority as authority
import pb_text_clip_polygon_shadow as shadow
from pb_text_clip_polygon_shadow import CLIPPED, UNCLIPPED, UNRESOLVED, clip_region, scene_document, text_clip_verdict

H = 400.0
DOT = "0 0 5 5 re f"                       # a paint on each side of the text, as in the authority's own fixtures (gives must-apply)


def py(y: float) -> float:
    """Native top-left y -> PDF user-space y of the 600 x 400 fixture page."""
    return H - y


def content(clip_ops: str, x: float, y_native: float, *, text: str = "ABC", size: int = 14) -> bytes:
    return f"q {clip_ops} {DOT} BT /helv {size} Tf {x} {py(y_native)} Td ({text}) Tj ET {DOT} Q".encode("ascii")


def rect_ops(x0, y0, x1, y1, *, even_odd=False) -> str:
    return f"{x0} {py(y1)} {x1 - x0} {y1 - y0} re {'W*' if even_odd else 'W'} n"


def re_op(r) -> str:
    return f"{r[0]} {py(r[3])} {r[2] - r[0]} {r[3] - r[1]} re"


def rects_ops(*rects, even_odd=False) -> str:
    return " ".join(re_op(r) for r in rects) + f" {'W*' if even_odd else 'W'} n"


def subpath(points) -> str:
    """One closed ring drawn with straight segments in the given vertex order (native coordinates), no painting operator."""
    first, rest = points[0], points[1:]
    return f"{first[0]} {py(first[1])} m " + " ".join(f"{x} {py(y)} l" for x, y in rest) + " h"


def ring_ops(*rings, rule="W") -> str:
    return " ".join(subpath(r) for r in rings) + f" {rule} n"


def evaluate(clip_ops: str, x: float, y: float, *, rotation: int = 0, text: str = "ABC"):
    """(shadow verdict, authority reasons) for the word ``text`` drawn at native (x, y) under ``clip_ops``.

    MuPDF's extractor drops fully clipped text, so the word box comes from an unclipped twin page and the trace sequence number from the
    clipped page itself, which is how the authority's own fully-clipped fixture works."""
    doc = scene_document(content(clip_ops, x, y, text=text), rotation)
    twin = scene_document(content("", x, y, text=text), rotation)
    reference = [w for w in twin[0].get_text("words") if w[4] == text][0]
    bbox = tuple(float(v) for v in reference[:4])
    page = doc[0]
    spans = [s for s in page.get_texttrace() if "".join(chr(c[0]) for c in s["chars"]) == text]
    assert spans, "the trace must report the text even when it is clipped away"
    seqno = spans[0]["seqno"]
    listed = [w for w in page.get_text("words") if w[4] == text and all(abs(a - b) <= 1e-6 for a, b in zip(w[:4], bbox))]
    native = {"text": text, "bbox": bbox} if listed else None
    return (text_clip_verdict(page, bbox, seqno, native_word=native),
            authority._text_clip_reasons(page, bbox, seqno, native_word=native))


def verdict(clip_ops: str, x: float, y: float, rotation: int = 0) -> str:
    return evaluate(clip_ops, x, y, rotation=rotation)[0].verdict


def painted(pix, x: int, y: int) -> bool:
    """The green fill reached this pixel (the page is white, the fill is rgb 0 0.6 0)."""
    red, green, _blue = pix.pixel(x, y)[:3]
    return red < 100 and green > 100


# ---------------------------------------------------------------- rectangles: identical to the authority
def test_a_text_inside_one_rectangle_clip_is_unclipped_exactly_as_the_authority_says():
    v, reasons = evaluate(rect_ops(50, 50, 250, 120), 60, 100)
    assert v.verdict == UNCLIPPED and reasons == () and v.reasons == ()


def test_a_text_outside_the_only_rectangle_clip_is_clipped_exactly_as_the_authority_says():
    v, reasons = evaluate(rect_ops(50, 50, 250, 120), 300, 300)
    assert v.verdict == CLIPPED and authority.TEXT_CLIPPED_BY_CLIP_REGION in reasons


def test_a_text_straddling_a_rectangle_clip_edge_is_clipped_exactly_as_the_authority_says():
    v, reasons = evaluate(rect_ops(50, 50, 250, 120), 235, 100)
    assert v.verdict == CLIPPED and authority.TEXT_CLIPPED_BY_CLIP_REGION in reasons


# ---------------------------------------------------------------- exact polygons the authority refuses
A_RECT, B_RECT = (50, 50, 150, 120), (300, 200, 450, 300)


def test_the_union_of_two_disjoint_rectangles_proves_a_text_inside_either_and_clips_one_in_the_gap():
    ops = rects_ops(A_RECT, B_RECT)
    inside_a, reasons_a = evaluate(ops, 60, 100)
    assert inside_a.verdict == UNCLIPPED and authority.TEXT_CLIP_STATE_UNRESOLVED in reasons_a       # the authority cannot say
    assert evaluate(ops, 310, 260)[0].verdict == UNCLIPPED
    in_gap, reasons_gap = evaluate(ops, 200, 150)
    assert in_gap.verdict == CLIPPED and in_gap.reasons == (authority.TEXT_CLIPPED_BY_CLIP_REGION,)


def test_a_text_straddling_a_polygon_edge_is_never_proven_unclipped():
    assert verdict(rects_ops(A_RECT, B_RECT), 135, 100) in (CLIPPED, UNRESOLVED)


def test_an_even_odd_frame_clips_a_text_in_its_hole_and_keeps_one_in_its_band():
    ops = rects_ops((30, 30, 400, 350), (120, 120, 300, 250), even_odd=True)
    assert verdict(ops, 40, 60) == UNCLIPPED                                  # in the band
    assert verdict(ops, 150, 200) == CLIPPED                                  # in the hole


def test_overlapping_rectangles_under_the_non_zero_rule_prove_only_what_holds_for_any_winding():
    # PyMuPDF does not expose the winding of a rectangle, so the overlap (an even cover) can be a union or a hole and is never claimed
    ops = rects_ops((50, 50, 200, 150), (120, 100, 300, 250))
    assert verdict(ops, 60, 70) == UNCLIPPED                                  # covered once: inside whatever the windings are
    assert verdict(ops, 250, 200) == UNCLIPPED
    assert verdict(ops, 140, 130) == UNRESOLVED                               # covered twice: union or hole, unknown
    assert verdict(ops, 500, 350) == CLIPPED                                  # covered by none


def test_a_reversed_inner_rectangle_is_not_mistaken_for_a_union_because_it_really_cuts_a_hole():
    # outer 50..250 x 100..200; the inner rectangle is drawn with a negative width, so it winds the other way and punches a hole
    outer, inner_hole = (50, 100, 250, 200), (60, 130, 80, 150)
    ops = f"{re_op(outer)} {inner_hole[2]} {py(inner_hole[3])} {-(inner_hole[2] - inner_hole[0])} {inner_hole[3] - inner_hole[1]} re W n"
    doc = scene_document(f"q {ops} 0 0.6 0 rg 0 0 600 400 re f Q".encode())
    pix = doc[0].get_pixmap(dpi=72)
    assert not painted(pix, 70, 140)                                          # the renderer really leaves the inner rectangle unpainted
    assert painted(pix, 150, 150)
    assert verdict(ops, 62, 146) != UNCLIPPED                                 # text in the hole must never be reported visible


# Two overlapping triangles (not axis-aligned rectangles, which PyMuPDF folds into ``re`` items and so hides their winding).
T1 = [(40, 40), (380, 40), (40, 300)]
T2 = [(100, 100), (500, 100), (100, 360)]
T2_REVERSED = [(100, 100), (100, 360), (500, 100)]


def test_straight_segment_rings_of_the_same_winding_are_exactly_their_union_even_where_they_overlap():
    ops = ring_ops(T1, T2)
    assert verdict(ops, 110, 150) == UNCLIPPED                                # in the overlap: inside the union, because the windings are known equal
    assert verdict(ops, 50, 60) == UNCLIPPED                                  # only the first triangle
    assert verdict(ops, 450, 340) == CLIPPED                                  # in neither


def test_straight_segment_rings_of_opposed_winding_claim_nothing_in_the_overlap_but_keep_the_single_cover_regions():
    ops = ring_ops(T1, T2_REVERSED)
    pix = scene_document(f"q {ops} 0 0.6 0 rg 0 0 600 400 re f Q".encode())[0].get_pixmap(dpi=72)
    assert not painted(pix, 125, 147)                                         # the renderer leaves the overlap unpainted (winding 1 - 1 = 0)
    assert painted(pix, 60, 55)
    assert verdict(ops, 110, 150) != UNCLIPPED                                # in the overlap: never reported visible
    assert verdict(ops, 50, 60) == UNCLIPPED                                  # only the first triangle


def test_a_curved_clip_is_never_treated_as_a_polygon_and_keeps_the_authority_verdict():
    ops = f"50 {py(300)} m 250 {py(300)} 250 {py(100)} 50 {py(100)} c h W n"        # a curve
    v, reasons = evaluate(ops, 100, 150)
    assert v.verdict == UNRESOLVED and shadow.REASON_CLIP_NOT_AN_EXACT_POLYGON in v.reasons
    assert authority.TEXT_CLIP_STATE_UNRESOLVED in reasons


def test_a_clip_with_a_curved_edge_is_not_approximated_by_its_chords():
    # an arch: straight base, bezier top. The straight-chord ring of its items is the triangle (50,300) (250,300) (250,100),
    # which contains the text below although the arch itself does not.
    arch = f"50 {py(300)} m 250 {py(300)} l 250 {py(100)} 50 {py(100)} 50 {py(300)} c h W n"
    v, reasons = evaluate(arch, 215, 175)
    assert v.verdict == UNRESOLVED and shadow.REASON_CLIP_NOT_AN_EXACT_POLYGON in v.reasons
    assert authority.TEXT_CLIP_STATE_UNRESOLVED in reasons


def test_an_unexplained_clip_operator_fails_closed_exactly_as_the_authority_does():
    # no clip is surfaced by the device, but the content stream contains a standalone ``W`` token (here inside a string)
    for text, expected in (("A W B", UNRESOLVED), ("A B", UNCLIPPED)):
        doc = scene_document(f"BT /helv 14 Tf 60 {py(100)} Td ({text}) Tj ET".encode("ascii"))
        page = doc[0]
        word = page.get_text("words")[0]
        seqno = [s for s in page.get_texttrace()][0]["seqno"]
        v = text_clip_verdict(page, word[:4], seqno)
        assert v.verdict == expected
        assert (authority._text_clip_reasons(page, word[:4], seqno) != ()) == (expected == UNRESOLVED)
        if expected == UNRESOLVED:
            assert shadow.REASON_CLIP_STRUCTURE_UNRECONCILED in v.reasons


def test_a_self_intersecting_ring_is_not_an_exact_polygon():
    bow = ring_ops([(50, 50), (250, 250), (250, 50), (50, 250)])
    v, _ = evaluate(bow, 60, 70)
    assert v.verdict == UNRESOLVED and shadow.REASON_CLIP_NOT_AN_EXACT_POLYGON in v.reasons


def test_a_stepped_staircase_outline_is_an_exact_polygon_and_its_notch_clips():
    steps = [(50, 50), (200, 50), (200, 100), (250, 100), (250, 200), (50, 200)]
    ops = ring_ops(steps)
    assert verdict(ops, 60, 150) == UNCLIPPED
    assert verdict(ops, 215, 70) == CLIPPED                                   # in the notch the staircase cuts out


def word_box(x: float, y: float, text: str = "ABC"):
    twin = scene_document(content("", x, y, text=text))
    word = [w for w in twin[0].get_text("words") if w[4] == text][0]
    return tuple(float(v) for v in word[:4])


def test_the_polygon_proofs_use_exactly_the_half_point_tolerance_of_the_authority():
    x0, y0, x1, y1 = word_box(60, 100)
    far = (400, 250, 520, 330)
    for overhang, expected in ((0.4, UNCLIPPED), (0.6, UNRESOLVED)):        # the word reaches past the polygon's right edge by this much
        edge = rects_ops((x0 - 40, y0 - 30, x1 - overhang, y1 + 30), far)
        assert verdict(edge, 60, 100) == expected, overhang
    for gap, expected in ((0.4, UNRESOLVED), (0.6, CLIPPED)):               # the word sits in the gap between two rectangles, this far from the left one
        between = rects_ops((x0 - 150, y0 - 30, x0 - gap, y1 + 30), (x1 + 60, y0 - 30, x1 + 200, y1 + 30))
        assert verdict(between, 60, 100) == expected, gap


def test_a_polygon_clip_that_only_may_apply_never_clips_and_never_trusts_without_the_renderer_listing_the_word():
    polygon = [(300, 40), (500, 40), (500, 120), (420, 160), (300, 120)]       # a pentagon far from the word
    # clip closed before the text: the renderer still lists the word, so a disjoint may-only polygon cannot govern it
    closed_first = f"{DOT} q {ring_ops(polygon)} Q BT /helv 14 Tf 60 {py(100)} Td (ABC) Tj ET {DOT}".encode("ascii")
    doc = scene_document(closed_first)
    page = doc[0]
    word = page.get_text("words")[0]
    seqno = [s for s in page.get_texttrace()][0]["seqno"]
    native = {"text": "ABC", "bbox": tuple(float(v) for v in word[:4])}
    assert text_clip_verdict(page, word[:4], seqno, native_word=native).verdict == UNCLIPPED
    assert text_clip_verdict(page, word[:4], seqno).verdict == UNRESOLVED          # no renderer proof supplied: the clip may apply
    # clip wrapping the text: the renderer drops the word, nothing proves the clip does not apply, and it must not be reported clipped
    wrapping = f"{DOT} q {ring_ops(polygon)} BT /helv 14 Tf 60 {py(100)} Td (ABC) Tj ET Q {DOT}".encode("ascii")
    doc2 = scene_document(wrapping)
    page2 = doc2[0]
    seqno2 = [s for s in page2.get_texttrace()][0]["seqno"]
    assert text_clip_verdict(page2, word[:4], seqno2).verdict == UNRESOLVED


def test_a_clip_numbering_that_cannot_be_reconciled_with_the_authority_model_is_unresolved(monkeypatch):
    doc = scene_document(content(rects_ops(A_RECT, B_RECT), 60, 100))
    page = doc[0]
    word = page.get_text("words")[0]
    seqno = [s for s in page.get_texttrace()][0]["seqno"]
    assert text_clip_verdict(page, word[:4], seqno).verdict == UNCLIPPED
    doc = scene_document(content(rects_ops(A_RECT, B_RECT), 60, 100))
    page = doc[0]
    monkeypatch.setattr(shadow, "_clip_entries", lambda p: [])
    v = text_clip_verdict(page, word[:4], seqno)
    assert v.verdict == UNRESOLVED and shadow.REASON_CLIP_STRUCTURE_UNRECONCILED in v.reasons


# ---------------------------------------------------------------- rotated pages
@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_a_rotated_page_gets_the_same_verdicts_as_the_unrotated_page_while_the_authority_stays_conservative(rotation):
    ops = rects_ops(A_RECT, B_RECT)
    for x, y, expected in ((60, 100, UNCLIPPED), (310, 260, UNCLIPPED), (200, 150, CLIPPED)):
        v, reasons = evaluate(ops, x, y, rotation=rotation)
        assert v.verdict == expected, (x, y, rotation)
        assert authority.TEXT_CLIP_STATE_UNRESOLVED in reasons                # the authority blocks every rotated page
    plain, reasons = evaluate(rect_ops(50, 50, 250, 120), 60, 100, rotation=rotation)
    assert plain.verdict == UNCLIPPED and reasons == (authority.TEXT_CLIP_STATE_UNRESOLVED,)
    clipped, _ = evaluate(rect_ops(50, 50, 250, 120), 300, 300, rotation=rotation)
    assert clipped.verdict == CLIPPED


def test_the_frame_conventions_of_the_installed_library_are_verified():
    assert all(shadow.native_frame_conventions_verified(r) for r in (0, 90, 180, 270, 360, -90))
    assert shadow.native_frame_conventions_verified(45) is False and shadow.native_frame_conventions_verified(91) is False


def test_a_failed_frame_check_keeps_every_rotated_page_unresolved_and_leaves_unrotated_pages_alone(monkeypatch):
    monkeypatch.setattr(shadow, "native_frame_conventions_verified", lambda rotation: int(rotation) % 360 == 0)
    v, _ = evaluate(rect_ops(50, 50, 250, 120), 60, 100, rotation=90)
    assert v.verdict == UNRESOLVED and shadow.REASON_ROTATED_FRAMES_UNVERIFIED in v.reasons
    assert evaluate(rect_ops(50, 50, 250, 120), 60, 100, rotation=0)[0].verdict == UNCLIPPED


def _rotated_frame_text(original):
    def get_text(self, option="text", *args, **kwargs):
        out = original(self, option, *args, **kwargs)
        if option == "words" and self.rotation:
            m = self.rotation_matrix
            return [tuple(fitz.Rect(w[:4]) * m) + tuple(w[4:]) for w in out]
        return out
    return get_text


def _rotated_frame_drawings(original, *, scissors=True, items=True):
    def get_drawings(self, *args, **kwargs):
        out = original(self, *args, **kwargs)
        if self.rotation and kwargs.get("extended"):
            m = self.rotation_matrix
            moved = []
            for e in out:
                e = dict(e)
                if e.get("type") == "clip":
                    if scissors:
                        e["scissor"] = fitz.Rect(e["scissor"]) * m
                    if items:
                        e["items"] = [(i[0], i[1] * m, i[2] * m) if i[0] == "l" else (i[0], fitz.Rect(i[1]) * m) + tuple(i[2:]) for i in e["items"]]
                moved.append(e)
            return moved
        return out
    return get_drawings


@pytest.mark.parametrize("which", ["words", "drawings", "polygon-items-only", "scissors-only"])
def test_a_library_that_reported_the_rotated_frame_would_be_detected_and_would_not_unlock_rotated_pages(monkeypatch, which):
    shadow._frame_check_cache.clear()
    try:
        if which == "words":
            monkeypatch.setattr(fitz.Page, "get_text", _rotated_frame_text(fitz.Page.get_text))
        elif which == "drawings":
            monkeypatch.setattr(fitz.Page, "get_drawings", _rotated_frame_drawings(fitz.Page.get_drawings))
        elif which == "polygon-items-only":
            monkeypatch.setattr(fitz.Page, "get_drawings", _rotated_frame_drawings(fitz.Page.get_drawings, scissors=False))
        else:
            monkeypatch.setattr(fitz.Page, "get_drawings", _rotated_frame_drawings(fitz.Page.get_drawings, items=False))
        assert shadow.native_frame_conventions_verified(90) is False
        assert shadow.native_frame_conventions_verified(180) is False
        assert shadow.native_frame_conventions_verified(0) is True
    finally:
        monkeypatch.undo()
        shadow._frame_check_cache.clear()
    assert shadow.native_frame_conventions_verified(90) is True


def test_a_rotated_page_with_an_offset_crop_box_still_resolves_in_the_native_frame():
    doc = scene_document(content(rect_ops(50, 50, 250, 120), 60, 100))
    page = doc[0]
    page.set_cropbox(fitz.Rect(20, 20, 580, 380))
    page.set_rotation(90)
    twin = scene_document(content("", 60, 100))
    twin[0].set_cropbox(fitz.Rect(20, 20, 580, 380))
    twin[0].set_rotation(90)
    reference = [w for w in twin[0].get_text("words") if w[4] == "ABC"][0]
    spans = [s for s in page.get_texttrace() if "".join(chr(c[0]) for c in s["chars"]) == "ABC"]
    result = text_clip_verdict(page, reference[:4], spans[0]["seqno"], native_word={"text": "ABC", "bbox": tuple(reference[:4])})
    assert result.verdict == UNCLIPPED


@pytest.mark.parametrize("rotation", [90, 180, 270])
@pytest.mark.parametrize("which", ["words", "trace", "both"])
@pytest.mark.parametrize("axis", [0, 1], ids=["horizontal", "vertical"])
def test_shifted_text_apis_cannot_verify_the_native_frame(monkeypatch, rotation, which, axis):
    original_words = fitz.Page.get_text
    original_trace = fitz.Page.get_texttrace

    def shifted_box(values):
        return tuple(value + (10.0 if i in (axis, axis + 2) else 0.0)
                     for i, value in enumerate(values))

    def get_text(self, option="text", *args, **kwargs):
        result = original_words(self, option, *args, **kwargs)
        if self.rotation and option == "words":
            return [shifted_box(word[:4]) + tuple(word[4:]) for word in result]
        return result

    def get_trace(self, *args, **kwargs):
        result = original_trace(self, *args, **kwargs)
        if self.rotation:
            return [dict(span, bbox=shifted_box(span["bbox"])) for span in result]
        return result

    shadow._frame_check_cache.clear()
    try:
        if which in ("words", "both"):
            monkeypatch.setattr(fitz.Page, "get_text", get_text)
        if which in ("trace", "both"):
            monkeypatch.setattr(fitz.Page, "get_texttrace", get_trace)
        assert shadow.native_frame_conventions_verified(rotation) is False
        result, _ = evaluate(rect_ops(50, 50, 250, 120), 60, 100, rotation=rotation)
        assert result.verdict == UNRESOLVED
        assert shadow.REASON_ROTATED_FRAMES_UNVERIFIED in result.reasons
        assert shadow.native_frame_conventions_verified(0) is True
    finally:
        monkeypatch.undo()
        shadow._frame_check_cache.clear()


# ---------------------------------------------------------------- differential safety against the authority
def test_on_rectangle_only_scenes_the_shadow_makes_exactly_the_authority_decision():
    rng = random.Random(17)
    seen = set()
    for _ in range(80):
        x0, y0 = rng.uniform(20, 250), rng.uniform(20, 250)
        x1, y1 = x0 + rng.uniform(30, 300), y0 + rng.uniform(15, 140)
        tx, ty = rng.uniform(20, 480), rng.uniform(40, 380)
        v, reasons = evaluate(rect_ops(x0, y0, x1, y1), tx, ty)
        if authority.TEXT_CLIPPED_BY_CLIP_REGION in reasons:
            assert v.verdict == CLIPPED
        elif reasons == ():
            assert v.verdict == UNCLIPPED
        else:
            assert v.verdict == UNRESOLVED
        seen.add(v.verdict)
    assert {CLIPPED, UNCLIPPED} <= seen


def test_what_the_authority_proves_clipped_is_never_reported_unclipped_on_polygon_scenes():
    rng = random.Random(23)
    for _ in range(40):
        a = (rng.uniform(20, 200), rng.uniform(20, 150), rng.uniform(220, 380), rng.uniform(170, 260))
        b = (rng.uniform(300, 420), rng.uniform(200, 280), rng.uniform(430, 560), rng.uniform(290, 370))
        tx, ty = rng.uniform(20, 480), rng.uniform(40, 380)
        v, reasons = evaluate(rects_ops(a, b), tx, ty)
        if authority.TEXT_CLIPPED_BY_CLIP_REGION in reasons:
            assert v.verdict != UNCLIPPED
        if reasons == ():
            assert v.verdict == UNCLIPPED


# ---------------------------------------------------------------- invariance, determinism, shadow flags
def test_translating_the_whole_scene_keeps_every_verdict():
    probes = ((60, 100), (200, 150), (135, 100))
    base = [verdict(rects_ops(A_RECT, B_RECT), x, y) for x, y in probes]
    assert base[0] == UNCLIPPED and base[1] == CLIPPED and base[2] in (CLIPPED, UNRESOLVED)
    shift = 37.0
    moved = tuple((a + shift, b, c + shift, d) for a, b, c, d in (A_RECT, B_RECT))
    assert [verdict(rects_ops(*moved), x + shift, y) for x, y in probes] == base


def test_the_order_of_the_rectangles_in_the_clip_path_does_not_change_the_verdict():
    probes = ((60, 100), (310, 260), (200, 150))
    assert [verdict(rects_ops(A_RECT, B_RECT), x, y) for x, y in probes] == [verdict(rects_ops(B_RECT, A_RECT), x, y) for x, y in probes]


def test_the_verdict_is_deterministic_flags_nothing_live_and_a_missing_sequence_number_is_unresolved():
    first, second = evaluate(rect_ops(50, 50, 250, 120), 60, 100)[0], evaluate(rect_ops(50, 50, 250, 120), 60, 100)[0]
    assert first == second and first.shadow_only is True and first.live_effect is False and first.text_trust_granted is False
    doc = scene_document(content(rect_ops(50, 50, 250, 120), 60, 100))
    page = doc[0]
    word = page.get_text("words")[0]
    assert text_clip_verdict(page, word[:4], None).verdict == UNRESOLVED


def test_the_shadow_does_not_change_what_the_authority_decides_for_the_same_page_object():
    doc = scene_document(content(rects_ops(A_RECT, B_RECT), 60, 100))
    page = doc[0]
    word = page.get_text("words")[0]
    seqno = [s for s in page.get_texttrace()][0]["seqno"]
    before = authority._text_clip_reasons(page, word[:4], seqno)
    text_clip_verdict(page, word[:4], seqno)
    assert authority._text_clip_reasons(page, word[:4], seqno) == before == (authority.TEXT_CLIP_STATE_UNRESOLVED,)


def test_a_zero_area_subject_is_never_proven_against_a_polygon():
    doc = scene_document(content(rects_ops(A_RECT, B_RECT), 60, 100))
    page = doc[0]
    seqno = [s for s in page.get_texttrace()][0]["seqno"]
    assert text_clip_verdict(page, (70.0, 90.0, 70.0, 100.0), seqno).verdict == UNRESOLVED


# ---------------------------------------------------------------- the region builder alone
class _P:
    def __init__(self, x, y):
        self.x, self.y = x, y


def _line(a, b):
    return ("l", _P(*a), _P(*b))


SQUARE = [_line((0, 0), (10, 0)), _line((10, 0), (10, 10)), _line((10, 10), (0, 10)), _line((0, 10), (0, 0))]


def test_clip_region_builds_polygons_from_segments_rectangles_and_quads_and_refuses_everything_else():
    one = clip_region({"items": SQUARE, "even_odd": False})
    assert one.exact and one.inside.area == pytest.approx(100.0) and one.reach.area == pytest.approx(100.0)
    assert clip_region({"items": SQUARE[:-1]}).inside.area == pytest.approx(100.0)               # a clip path is closed by the fill
    assert clip_region({"items": [("c", _P(0, 0), _P(1, 1), _P(2, 2), _P(3, 3))]}) is None
    assert clip_region({"items": []}) is None
    assert clip_region({"items": [_line((0, 0), (1, 1)), _line((1, 1), (2, 2))]}) is None           # fewer than three points
    assert clip_region({"items": [("qu", fitz.Rect(0, 0, 4, 4).quad)]}).inside.area == pytest.approx(16.0)
    assert clip_region({"items": [("re", fitz.Rect(0, 0, 0, 5), 1)]}) is None                       # an empty rectangle


def test_clip_region_even_odd_is_the_symmetric_difference_and_non_zero_with_unknown_winding_is_a_sound_pair():
    nested = SQUARE + [("re", fitz.Rect(2, 2, 8, 8), 1)]
    eo = clip_region({"items": nested, "even_odd": True})
    assert eo.exact and eo.inside.area == pytest.approx(100.0 - 36.0) and eo.reach.equals(eo.inside)
    nz = clip_region({"items": nested, "even_odd": False})                                         # the rectangle's winding is unknown
    assert not nz.exact and nz.inside.area == pytest.approx(64.0) and nz.reach.area == pytest.approx(100.0)
    side_by_side = SQUARE + [("re", fitz.Rect(20, 0, 30, 10), 1)]
    for rule in (True, False):
        both_squares = clip_region({"items": side_by_side, "even_odd": rule})
        assert both_squares.inside.area == pytest.approx(200.0) and both_squares.reach.area == pytest.approx(200.0)


def test_clip_region_known_equal_windings_give_the_union_and_known_mixed_windings_do_not():
    same = SQUARE + [_line((5, 5), (15, 5)), _line((15, 5), (15, 15)), _line((15, 15), (5, 15)), _line((5, 15), (5, 5))]
    union = clip_region({"items": same, "even_odd": False})
    assert union.exact and union.inside.area == pytest.approx(175.0)                              # 100 + 100 - 25
    opposed = SQUARE + [_line((5, 5), (5, 15)), _line((5, 15), (15, 15)), _line((15, 15), (15, 5)), _line((15, 5), (5, 5))]
    mixed = clip_region({"items": opposed, "even_odd": False})
    assert not mixed.exact and mixed.inside.area == pytest.approx(150.0) and mixed.reach.area == pytest.approx(175.0)


def test_clip_region_never_builds_a_polygon_from_a_self_touching_or_bow_tie_ring():
    bow = [_line((0, 0), (10, 10)), _line((10, 10), (10, 0)), _line((10, 0), (0, 10)), _line((0, 10), (0, 0))]
    assert clip_region({"items": bow}) is None


def test_clip_region_refuses_a_clip_made_of_more_subpaths_than_the_bound():
    many = [("re", fitz.Rect(20 * i, 0, 20 * i + 10, 10), 1) for i in range(shadow.MAX_CLIP_RINGS)]
    assert clip_region({"items": many, "even_odd": True}) is not None
    assert clip_region({"items": many + [("re", fitz.Rect(5000, 0, 5010, 10), 1)], "even_odd": True}) is None
