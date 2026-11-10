"""word_glyphs reads characters along the trace span's OWN text direction (rotated words recover), and nothing else changes."""
from __future__ import annotations

import copy
import math
import random
from typing import Iterable, Mapping, Optional, Sequence

import fitz
import pytest

import pb_font_glyph_mapping_corroboration_shadow as shadow
from pb_font_glyph_mapping_corroboration_shadow import WordGlyphs, word_glyphs
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_glyph_ledger_text_trust import GlyphTextCandidate, decide_glyph_text_trust

TEXT = "1,200"
GIDS = (49, 44, 50, 48, 48)
EXPECTED = WordGlyphs("o1", TEXT, "F", tuple(zip(GIDS, TEXT)))
DIRECTIONS = {"0": (1.0, 0.0), "90": (0.0, 1.0), "180": (-1.0, 0.0), "270": (0.0, -1.0), "45": (math.sqrt(0.5), math.sqrt(0.5))}


def old_word_glyphs(observation_id, text, font_key, bbox, spans: Iterable[Mapping], *, tolerance=shadow.CENTRE_TOLERANCE_PT) -> Optional[WordGlyphs]:
    """The implementation before direction was used (x-centre order only): the regression oracle for horizontal words."""
    x0, y0, x1, y1 = (float(v) for v in tuple(bbox)[:4])
    found = []
    for span in spans:
        for char in span.get("chars") or ():
            try:
                codepoint, gid = int(char[0]), int(char[1])
                cx = (float(char[3][0]) + float(char[3][2])) / 2.0
                cy = (float(char[3][1]) + float(char[3][3])) / 2.0
            except (IndexError, TypeError, ValueError):
                return None
            if x0 - tolerance <= cx <= x1 + tolerance and y0 - tolerance <= cy <= y1 + tolerance:
                if gid >= 0:
                    found.append((cx, gid, chr(codepoint)))
    found.sort(key=lambda item: item[0])
    if "".join(c for _x, _g, c in found) != text or not found:
        return None
    return WordGlyphs(str(observation_id), str(text), str(font_key), tuple((gid, char) for _x, gid, char in found))


def make_span(text, gids, origin, direction, *, adv=5.0, size=6.0, font="F1", dir_value="same", offset=0):
    dx, dy = direction
    chars = []
    for i, (c, g) in enumerate(zip(text, gids)):
        cx, cy = origin[0] + (i + offset) * adv * dx, origin[1] + (i + offset) * adv * dy
        chars.append((ord(c), g, (cx, cy), (cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2)))
    span = {"font": font, "chars": tuple(chars)}
    if isinstance(dir_value, str) and dir_value == "same":
        span["dir"] = direction
    elif dir_value is not None:
        span["dir"] = dir_value                      # an explicit (possibly invalid) direction; None means the span has no dir
    return span


def box_of(spans):
    xs0 = [c[3][0] for s in spans for c in s["chars"]]
    ys0 = [c[3][1] for s in spans for c in s["chars"]]
    xs1 = [c[3][2] for s in spans for c in s["chars"]]
    ys1 = [c[3][3] for s in spans for c in s["chars"]]
    return (min(xs0), min(ys0), max(xs1), max(ys1))


def recover(spans, text=TEXT, bbox=None):
    return word_glyphs("o1", text, "F", bbox or box_of(spans), spans)


# ------------------------------------------------------------------------------------------------ the defect and the fix
@pytest.mark.parametrize("name", ["0", "90", "180", "270", "45"])
def test_a_word_is_recovered_in_the_order_of_its_own_text_direction(name):
    spans = [make_span(TEXT, GIDS, (100.0, 200.0), DIRECTIONS[name], adv=7.0 if name == "45" else 5.0)]
    assert recover(spans) == EXPECTED


@pytest.mark.parametrize("name", ["90", "180", "270"])
def test_the_old_order_could_not_recover_these_words(name):
    # The x-centre order is undefined for a vertical word (every character shares one x, so the order is whatever float noise or the
    # trace sequence gives) and reversed for a right-to-left word. With noise that runs against the reading order the old function fails.
    span = make_span(TEXT, GIDS, (100.0, 200.0), DIRECTIONS[name])
    span["chars"] = tuple((c[0], c[1], c[2], (c[3][0] - i * 1e-9, c[3][1], c[3][2] - i * 1e-9, c[3][3])) for i, c in enumerate(span["chars"]))
    assert old_word_glyphs("o1", TEXT, "F", box_of([span]), [span]) is None
    assert recover([span]) == EXPECTED


def test_the_bottom_to_top_word_on_one_x_is_read_by_height_not_by_float_noise():
    spans = [make_span(TEXT, GIDS, (943.065, 324.0), (-1.03e-13, -1.0), adv=3.9, size=6.0)]
    spans[0]["chars"] = tuple((c[0], c[1], c[2], (c[3][0] + i * 1e-12, c[3][1], c[3][2] + i * 1e-12, c[3][3])) for i, c in enumerate(spans[0]["chars"]))
    assert recover(spans) == EXPECTED


# ------------------------------------------------------------------------------------------------ invariances
@pytest.mark.parametrize("name", ["0", "90", "180", "270", "45"])
def test_translation_and_uniform_scale_do_not_change_the_recovered_glyphs(name):
    d = DIRECTIONS[name]
    ref = recover([make_span(TEXT, GIDS, (100.0, 200.0), d)])
    assert recover([make_span(TEXT, GIDS, (-4321.5, 9876.25), d)]) == ref
    assert recover([make_span(TEXT, GIDS, (300.0, 600.0), d, adv=15.0, size=18.0)]) == ref


def test_rotating_the_whole_page_recovers_the_same_glyph_pairs():
    pairs = {recover([make_span(TEXT, GIDS, (50.0, 80.0), d)]).glyphs for d in DIRECTIONS.values()}
    assert pairs == {EXPECTED.glyphs}


@pytest.mark.parametrize("name", ["0", "90", "180", "270"])
def test_span_order_char_order_and_splitting_do_not_matter(name):
    d = DIRECTIONS[name]
    one = make_span(TEXT, GIDS, (100.0, 200.0), d)
    ref = recover([one])
    rng = random.Random(5)
    for _ in range(20):
        chars = list(one["chars"])
        rng.shuffle(chars)
        assert recover([{**one, "chars": tuple(chars)}]) == ref
    split = [{**one, "chars": (c,)} for c in one["chars"]]
    for _ in range(10):
        rng.shuffle(split)
        assert recover(split, bbox=box_of([one])) == ref
    two = [{**one, "chars": one["chars"][:2]}, {**one, "chars": one["chars"][2:]}]
    assert recover(two, bbox=box_of([one])) == ref and recover(list(reversed(two)), bbox=box_of([one])) == ref


def test_unrelated_spans_far_from_the_box_do_not_change_the_result():
    word = make_span(TEXT, GIDS, (100.0, 200.0), DIRECTIONS["270"])
    noise = [make_span("ABC", (1, 2, 3), (500.0 + 40 * i, 50.0), DIRECTIONS["0"]) for i in range(5)]
    noise += [make_span("XYZ", (7, 8, 9), (900.0, 40.0 + 30 * i), DIRECTIONS["90"]) for i in range(5)]
    assert recover([word] + noise, bbox=box_of([word])) == EXPECTED


def test_replay_is_deterministic_and_inputs_are_not_mutated():
    spans = [make_span(TEXT, GIDS, (100.0, 200.0), DIRECTIONS["270"])]
    snap = copy.deepcopy(spans)
    first, second = recover(spans), recover(spans)
    assert first == second == EXPECTED and spans == snap


# ------------------------------------------------------------------------------------------------ refusals
def test_a_wrong_or_reversed_claimed_text_is_refused_and_no_other_order_is_tried():
    spans = [make_span(TEXT, GIDS, (100.0, 200.0), DIRECTIONS["270"])]
    assert recover(spans, text="2,100") is None
    assert recover(spans, text="002,1") is None                      # the reverse spelling: the trace order is the only order tried
    assert recover(spans, text="1,20") is None and recover(spans, text="1,2000") is None


def test_characters_from_spans_with_different_directions_abstain():
    a = make_span(TEXT[:3], GIDS[:3], (100.0, 200.0), DIRECTIONS["270"])
    b = make_span(TEXT[3:], GIDS[3:], (100.0, 200.0), DIRECTIONS["270"], offset=3)
    b["dir"] = DIRECTIONS["0"]
    assert recover([a, b], bbox=box_of([a, b])) is None


def test_characters_from_spans_in_different_fonts_abstain():
    a = make_span(TEXT[:3], GIDS[:3], (100.0, 200.0), DIRECTIONS["270"])
    b = make_span(TEXT[3:], GIDS[3:], (100.0, 200.0), DIRECTIONS["270"], offset=3, font="OTHER")
    assert recover([a, b], bbox=box_of([a, b])) is None
    b["font"] = "F1"
    assert recover([a, b], bbox=box_of([a, b])) == EXPECTED


@pytest.mark.parametrize("bad", [(float("nan"), -1.0), (float("inf"), 0.0), (0.0, 0.0), (2.0, 0.0), (0.0, -1.0, 0.0), "up", (None, 1.0), 5])
def test_an_invalid_direction_abstains(bad):
    span = make_span(TEXT, GIDS, (100.0, 200.0), DIRECTIONS["270"])
    span["dir"] = bad
    assert recover([span]) is None


@pytest.mark.parametrize("bad", [(2.0, 0.0), (0.5, 0.0), (1.01, 0.0), (0.0, 0.99), (1.0, 1.0)])
def test_a_direction_that_is_not_a_unit_vector_abstains_even_when_the_order_would_be_unambiguous(bad):
    span = make_span(TEXT, GIDS, (100.0, 200.0), DIRECTIONS["0"])                 # a horizontal word whose x order is clear
    span["dir"] = bad
    assert recover([span]) is None


def test_a_direction_within_the_unit_tolerance_is_accepted():
    for good in ((1.0005, 0.0), (0.9995, 0.0), (1.0, 2e-4)):
        span = make_span(TEXT, GIDS, (100.0, 200.0), DIRECTIONS["0"])
        span["dir"] = good
        assert recover([span]) == EXPECTED


def test_a_missing_direction_keeps_the_historical_horizontal_reading():
    horizontal = make_span(TEXT, GIDS, (100.0, 200.0), DIRECTIONS["0"], dir_value=None)
    assert "dir" not in horizontal and recover([horizontal]) == EXPECTED
    vertical = make_span(TEXT, GIDS, (100.0, 200.0), DIRECTIONS["270"], dir_value=None)
    assert "dir" not in vertical and recover([vertical]) is None             # unchanged: without a direction nothing is assumed beyond x


def test_two_characters_at_one_position_have_no_defined_order():
    span = make_span("12", (49, 50), (100.0, 200.0), DIRECTIONS["270"], adv=0.0)
    assert recover([span], text="12") is None and recover([span], text="21") is None


def test_text_of_another_direction_inside_the_box_abstains():
    word = make_span(TEXT, GIDS, (100.0, 200.0), DIRECTIONS["270"])
    stray = make_span("9", (57,), (100.0, 190.0), DIRECTIONS["0"])
    assert recover([word, stray], bbox=box_of([word, stray])) is None


# ------------------------------------------------------------------------------------------------ the horizontal baseline is unchanged
def test_horizontal_words_are_recovered_exactly_as_before():
    rng = random.Random(2026)
    for case in range(300):
        n = rng.randint(1, 8)
        text = "".join(rng.choice("0123456789,ABCxyz") for _ in range(n))
        gids = tuple(rng.randint(1, 200) for _ in range(n))
        adv = rng.uniform(2.0, 9.0)
        origin = (rng.uniform(-500, 500), rng.uniform(-500, 500))
        use_dir = rng.random() < 0.5
        span = make_span(text, gids, origin, (1.0, 0.0), adv=adv, size=adv * 0.9, dir_value="same" if use_dir else None)
        spans = [span] + [make_span("Q", (3,), (rng.uniform(2000, 3000), rng.uniform(2000, 3000)), (1.0, 0.0))]
        rng.shuffle(spans)
        bbox = box_of([span])
        new = word_glyphs("o", text, "F", bbox, spans)
        assert new == old_word_glyphs("o", text, "F", bbox, spans), case
        assert new is not None


def test_existing_refusals_are_unchanged_for_horizontal_words():
    spans = [make_span("AB", (36, 37), (4.0, 6.0), DIRECTIONS["0"], adv=8.0, size=8.0, dir_value=None)]
    for text, bbox in (("ABC", (0.0, 0.0, 16.0, 12.0)), ("AB", (0.0, 0.0, 8.0, 12.0)), ("BA", (0.0, 0.0, 16.0, 12.0)), ("AB", (500.0, 0.0, 520.0, 12.0))):
        assert word_glyphs("o", text, "F", bbox, spans) == old_word_glyphs("o", text, "F", bbox, spans)
    bad = [{"chars": ((65, "gid?", (0, 0), (0, 0, 8, 12)),)}]
    assert word_glyphs("o", "A", "F", (0.0, 0.0, 8.0, 12.0), bad) is None


# ------------------------------------------------------------------------------------------------ real PDF text in every rotation
def _rotated_text_pdf():
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    for rotate, (x, y) in ((0, (30, 40)), (90, (120, 120)), (180, (260, 60)), (270, (330, 200))):
        page.insert_text((x, y), "1,200", fontsize=8, rotate=rotate)
    return doc


def test_real_pdf_text_in_all_four_rotations_is_recovered_with_one_consistent_glyph_sequence():
    page = _rotated_text_pdf()[0]
    spans = page.get_texttrace()
    words = [w for w in page.get_text("words") if w[4] == "1,200"]
    assert len(words) == 4
    got = [word_glyphs("w", "1,200", "F", w[:4], spans) for w in words]
    assert all(g is not None for g in got)
    assert len({g.glyphs for g in got}) == 1 and "".join(c for _g, c in got[0].glyphs) == "1,200"
    dirs = {(round(s["dir"][0]), round(s["dir"][1])) for s in spans if s.get("dir")}
    assert dirs >= {(1, 0), (0, -1), (-1, 0), (0, 1)}                         # the four rotations really are in the trace


def test_the_old_order_fails_the_right_to_left_real_word_that_the_new_order_recovers():
    page = _rotated_text_pdf()[0]
    spans = page.get_texttrace()
    words = [w for w in page.get_text("words") if w[4] == "1,200"]
    new = [word_glyphs("w", "1,200", "F", w[:4], spans) for w in words]
    old = [old_word_glyphs("w", "1,200", "F", w[:4], spans) for w in words]
    assert all(n is not None for n in new)
    assert any(o is None for o in old)                                         # at least the reversed (180 degree) word


# ------------------------------------------------------------------------------------------------ the ledger decision with rotated words
def _candidates(recovered: bool):
    out = []
    for i, text in enumerate(("1,200", "1,200", "2,100", "1,020")):
        gids = {"1,200": GIDS, "2,100": (50, 44, 49, 48, 48), "1,020": (49, 48, 44, 50, 48)}[text] if text != "1,200" else GIDS
        span = make_span(text, gids, (100.0 + 40 * i, 200.0), DIRECTIONS["270"])
        word = word_glyphs(f"w{i}", text, "F", box_of([span]), [span]) if recovered else None
        out.append(GlyphTextCandidate(f"w{i}", word))
    return out


def test_rotated_words_now_reach_the_existing_ledger_decision_and_the_trust_gates_still_apply():
    decided = decide_glyph_text_trust(_candidates(recovered=True), lambda oid: oid in ("w0", "w1"), min_words=2)
    d = decided.decisions
    assert d["w0"].status is EvidenceResolutionStatus.CORROBORATED and d["w0"].method == "direct_raster"
    assert d["w2"].reason_codes == ("amortized_glyph_verified",)             # every glyph read by two corroborated words
    # a glyph that only one corroborated word read is NOT verified, so a word using it stays under-supported
    only_one = decide_glyph_text_trust(_candidates(recovered=True), lambda oid: oid == "w0", min_words=2)
    assert all(v.status is not EvidenceResolutionStatus.CORROBORATED or v.method == "direct_raster" for v in only_one.decisions.values())
    assert only_one.decisions["w3"].reason_codes == ("glyph_mapping_under_supported",)
    # before the fix the same words were unrecovered and could not be trusted at all
    before = decide_glyph_text_trust(_candidates(recovered=False), lambda oid: False, min_words=2)
    assert {v.reason_codes for v in before.decisions.values()} == {("glyphs_not_recovered",)}


def test_a_contradicting_rotated_word_still_vetoes():
    a = make_span("1", (49,), (100.0, 200.0), DIRECTIONS["270"])
    b = make_span("7", (49,), (140.0, 200.0), DIRECTIONS["270"])                 # the same glyph id read as another character
    c = make_span("1", (49,), (180.0, 200.0), DIRECTIONS["270"])
    cands = [GlyphTextCandidate(f"w{i}", word_glyphs(f"w{i}", t, "F", box_of([s]), [s])) for i, (t, s) in enumerate((("1", a), ("7", b), ("1", c)))]
    decided = decide_glyph_text_trust(cands, lambda oid: True, min_words=2)
    assert {v.status for v in decided.decisions.values()} == {EvidenceResolutionStatus.CONFLICT}
