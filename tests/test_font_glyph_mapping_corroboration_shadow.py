"""Glyph mapping bookkeeping: a (font, glyph id) -> character mapping is verified only by agreeing, independent, corroborated words."""
from __future__ import annotations

import copy
import random

import fitz
import pytest

from pb_font_glyph_mapping_corroboration_shadow import (
    ALL_GLYPHS_VERIFIED,
    GLYPH_CONTRADICTED,
    GLYPH_NOT_YET_VERIFIED,
    GLYPHS_NOT_RECOVERED,
    GlyphMappingLedger,
    WordGlyphs,
    classify_word,
    coverage,
    verify_glyph_mappings,
    word_glyphs,
)


def word(oid: str, text: str, gids, font: str = "F") -> WordGlyphs:
    assert len(text) == len(gids)
    return WordGlyphs(oid, text, font, tuple(zip(gids, text)))


# ---------------------------------------------------------------- recovering glyphs from the trace
def span(chars, **extra):
    """A trace span: each char is (codepoint, glyph id, origin, bbox)."""
    return {"chars": tuple((ord(c), gid, (x, 10.0), (x, 0.0, x + 8.0, 12.0)) for c, gid, x in chars), **extra}


def test_word_glyphs_reads_gids_in_text_order_from_the_characters_standing_in_the_word_box():
    spans = [span([("A", 36, 0.0), ("B", 37, 8.0), ("C", 38, 16.0)]), span([("Z", 99, 200.0)])]
    got = word_glyphs("o1", "ABC", "F", (0.0, 0.0, 24.0, 12.0), spans)
    assert got == WordGlyphs("o1", "ABC", "F", ((36, "A"), (37, "B"), (38, "C")))
    assert word_glyphs("o1", "ABC", "F", (0.0, 0.0, 24.0, 12.0), list(reversed(spans))) == got


def test_word_glyphs_refuses_a_word_it_cannot_spell_exactly():
    spans = [span([("A", 36, 0.0), ("B", 37, 8.0)])]
    assert word_glyphs("o", "ABC", "F", (0.0, 0.0, 16.0, 12.0), spans) is None                   # a character is missing
    assert word_glyphs("o", "AB", "F", (0.0, 0.0, 8.0, 12.0), spans) is None                     # the box holds only the first character
    assert word_glyphs("o", "BA", "F", (0.0, 0.0, 16.0, 12.0), spans) is None                    # reordered
    assert word_glyphs("o", "AB", "F", (500.0, 0.0, 520.0, 12.0), spans) is None                 # nothing stands in the box
    bad = [{"chars": ((65, "gid?", (0, 0), (0, 0, 8, 12)),)}]
    assert word_glyphs("o", "A", "F", (0.0, 0.0, 8.0, 12.0), bad) is None                        # malformed trace


def test_word_glyphs_uses_the_half_point_centre_tolerance_and_reads_in_visual_order():
    spans = [span([("A", 36, 0.0), ("B", 37, 8.0)])]
    assert word_glyphs("o", "AB", "F", (0.0, 0.0, 11.6, 12.0), spans) is not None            # second centre at 12.0, box edge 11.6 + 0.6 tolerance
    assert word_glyphs("o", "AB", "F", (0.0, 0.0, 11.3, 12.0), spans) is None                # 0.7 away: outside the tolerance
    drawn_backwards = [span([("C", 38, 16.0), ("B", 37, 8.0), ("A", 36, 0.0)])]
    got = word_glyphs("o", "ABC", "F", (0.0, 0.0, 24.0, 12.0), drawn_backwards)
    assert got is not None and got.glyphs == ((36, "A"), (37, "B"), (38, "C"))                 # visual order, not draw order


def test_word_glyphs_refuses_a_trace_with_a_malformed_character_instead_of_skipping_it():
    good = span([("A", 36, 0.0), ("B", 37, 8.0)])
    bad = {"chars": ((88, "not-a-glyph", (0.0, 0.0), (16.0, 0.0, 24.0, 12.0)),)}
    assert word_glyphs("o", "AB", "F", (0.0, 0.0, 24.0, 12.0), [good]) is not None
    assert word_glyphs("o", "AB", "F", (0.0, 0.0, 24.0, 12.0), [good, bad]) is None


def test_word_glyphs_skips_continuation_glyphs_and_keeps_the_leading_one():
    spans = [span([("f", 70, 0.0), ("i", -1, 8.0), ("x", 71, 16.0)])]
    got = word_glyphs("o", "fix", "F", (0.0, 0.0, 24.0, 12.0), spans)
    assert got is None                                                                           # the text has three characters, two glyphs were traced
    only = word_glyphs("o", "fx", "F", (0.0, 0.0, 24.0, 12.0), [span([("f", 70, 0.0), ("x", 71, 16.0), ("i", -1, 8.0)])])
    assert only is not None and only.glyphs == ((70, "f"), (71, "x"))


def test_word_glyphs_on_a_real_trace_spells_the_word_with_one_glyph_id_per_character():
    doc = fitz.open()
    page = doc.new_page(width=300, height=100)
    page.insert_text((20, 50), "A1B2C3", fontname="helv", fontsize=14)
    words = page.get_text("words")
    assert len(words) == 1
    got = word_glyphs("o", words[0][4], "helv", words[0][:4], page.get_texttrace())
    assert got is not None and "".join(c for _g, c in got.glyphs) == "A1B2C3" and len(got.glyphs) == 6
    assert len({g for g, _c in got.glyphs}) == 6


# ---------------------------------------------------------------- verification
def test_a_mapping_needs_the_minimum_number_of_agreeing_words_and_one_word_is_not_enough():
    words = [word("a", "12", [10, 11]), word("b", "1", [10])]
    v = verify_glyph_mappings(words)
    assert v.verified == {("F", 10): "1"}
    assert v.under_supported == {("F", 11): 1}
    assert v.contradicted == {}
    assert verify_glyph_mappings(words[:1]).verified == {}
    assert verify_glyph_mappings(words[:1], min_words=1).verified == {("F", 10): "1", ("F", 11): "2"}
    with pytest.raises(ValueError):
        verify_glyph_mappings(words, min_words=0)


def test_a_glyph_repeated_inside_one_word_and_a_repeated_observation_are_one_vote_each():
    assert verify_glyph_mappings([word("a", "111", [10, 10, 10])]).verified == {}
    assert verify_glyph_mappings([word("a", "1", [10]), word("a", "1", [10])]).verified == {}
    assert verify_glyph_mappings([word("a", "111", [10, 10, 10]), word("b", "1", [10])]).verified == {("F", 10): "1"}


def test_disagreeing_words_verify_nothing_and_a_majority_does_not_win():
    words = [word(f"w{i}", "1", [10]) for i in range(5)] + [word("x", "7", [10])]
    v = verify_glyph_mappings(words)
    assert v.verified == {} and v.contradicted == {("F", 10): ("1", "7")}


def test_fonts_are_separate_and_unrelated_words_do_not_change_a_verified_mapping():
    base = [word("a", "12", [10, 11]), word("b", "12", [10, 11])]
    other_font = [word("c", "7", [10], font="G"), word("d", "7", [10], font="G")]
    v = verify_glyph_mappings(base + other_font)
    assert v.verified == {("F", 10): "1", ("F", 11): "2", ("G", 10): "7"}
    assert {k: c for k, c in verify_glyph_mappings(base).verified.items()} == {k: c for k, c in v.verified.items() if k[0] == "F"}


def test_verification_is_independent_of_input_order_deterministic_and_does_not_mutate_its_input():
    rng = random.Random(5)
    words = [word(f"w{i}", "".join(rng.choice("0123456789") for _ in range(4)), [rng.randrange(40, 50) for _ in range(4)]) for i in range(40)]
    words = [WordGlyphs(w.observation_id, w.text, w.font_key, tuple((g, c) for (g, _), c in zip(w.glyphs, w.text))) for w in words]
    before = copy.deepcopy(words)
    first = verify_glyph_mappings(words)
    shuffled = list(words)
    rng.shuffle(shuffled)
    assert verify_glyph_mappings(shuffled) == first == verify_glyph_mappings(words)
    assert words == before


def test_every_result_is_shadow_only_and_grants_nothing():
    v = verify_glyph_mappings([word("a", "1", [10])])
    assert v.shadow_only is True and v.live_effect is False and v.text_trust_granted is False


def test_relabelling_glyph_ids_changes_nothing_but_the_ids():
    words = [word("a", "123", [10, 11, 12]), word("b", "321", [12, 11, 10]), word("c", "11", [10, 10])]
    relabel = {10: 500, 11: 7, 12: 91}
    moved = [WordGlyphs(w.observation_id, w.text, w.font_key, tuple((relabel[g], c) for g, c in w.glyphs)) for w in words]
    original = verify_glyph_mappings(words)
    after = verify_glyph_mappings(moved)
    assert {relabel[g]: c for (_f, g), c in original.verified.items()} == {g: c for (_f, g), c in after.verified.items()}


# ---------------------------------------------------------------- word status
def test_a_word_is_verified_only_when_every_glyph_is_verified_as_the_character_it_is_spelled_with():
    v = verify_glyph_mappings([word("a", "12", [10, 11]), word("b", "12", [10, 11])])
    assert classify_word(word("t", "21", [11, 10]), v) == ALL_GLYPHS_VERIFIED
    assert classify_word(word("t", "13", [10, 12]), v) == GLYPH_NOT_YET_VERIFIED              # glyph 12 has no evidence
    assert classify_word(word("t", "17", [10, 11]), v) == GLYPH_CONTRADICTED                  # glyph 11 is verified as '2', this word says '7'
    assert classify_word(None, v) == GLYPHS_NOT_RECOVERED
    assert classify_word(WordGlyphs("e", "", "F", ()), v) == GLYPHS_NOT_RECOVERED


def test_a_contradicted_glyph_dominates_an_unverified_one_in_the_same_word():
    v = verify_glyph_mappings([word("a", "1", [10]), word("b", "7", [10])])
    assert classify_word(word("t", "91", [99, 10]), v) == GLYPH_CONTRADICTED
    assert classify_word(word("t", "1", [10]), v) == GLYPH_CONTRADICTED                       # nobody wins a disagreement


def test_coverage_counts_every_status():
    v = verify_glyph_mappings([word("a", "1", [10]), word("b", "1", [10])])
    words = [word("t1", "11", [10, 10]), word("t2", "12", [10, 12]), word("t3", "7", [10])]
    counts = coverage(words, v)
    assert counts == {ALL_GLYPHS_VERIFIED: 1, GLYPH_NOT_YET_VERIFIED: 1, GLYPH_CONTRADICTED: 1, GLYPHS_NOT_RECOVERED: 0}


# ---------------------------------------------------------------- the ledger and the order of attempts
def test_the_next_attempt_is_the_word_that_adds_the_most_still_needed_votes_and_ties_do_not_depend_on_input_order():
    ledger = GlyphMappingLedger()
    long_word = word("l", "1234", [10, 11, 12, 13])
    short_word = word("s", "12", [10, 11])
    twin_a, twin_b = word("a", "56", [14, 15]), word("b", "56", [14, 15])
    for order in ([long_word, short_word, twin_a, twin_b], [twin_b, twin_a, short_word, long_word]):
        assert ledger.next_candidate(order) == long_word
    assert ledger.next_candidate([twin_b, twin_a]).observation_id == "a"                       # equal gain and length: the smaller id, in either order
    assert ledger.next_candidate([twin_a, twin_b]).observation_id == "a"
    assert ledger.next_candidate([word("z", "123", [10, 11, 12]), word("y", "12", [10, 11])]).observation_id == "z"


def test_attempts_that_failed_cast_no_vote_but_are_not_repeated():
    ledger = GlyphMappingLedger()
    w1, w2 = word("a", "12", [10, 11]), word("b", "12", [10, 11])
    ledger.record(w1, False)
    assert ledger.verification().verified == {} and ledger.attempts == 1 and ledger.corroborated_count == 0
    assert ledger.next_candidate([w1, w2]) == w2
    ledger.record(w2, True)
    ledger.record(w2, True)                                                                      # idempotent
    assert ledger.attempts == 2 and ledger.corroborated_count == 1
    with pytest.raises(ValueError):
        ledger.record(w2, False)
    assert ledger.verification().under_supported == {("F", 10): 1, ("F", 11): 1}


def test_a_contradicted_glyph_is_not_chased_with_more_attempts():
    ledger = GlyphMappingLedger(min_words=3)
    ledger.record(word("a", "1", [10]), True)
    ledger.record(word("b", "7", [10]), True)
    assert ledger.verification().contradicted == {("F", 10): ("1", "7")}
    assert ledger.next_candidate([word("c", "1", [10])]) is None                              # a third vote could not settle the disagreement
    assert ledger.next_candidate([word("c", "1", [10]), word("d", "2", [11])]).observation_id == "d"


def test_the_ledger_reaches_full_coverage_of_what_can_be_read_with_far_fewer_attempts_than_words():
    rng = random.Random(11)
    alphabet = {gid: ch for gid, ch in zip(range(40, 60), "0123456789ABCDEFGHIJ")}
    unreadable = {41, 57}                                                                         # glyphs the recogniser cannot read
    words = []
    for i in range(300):
        gids = [rng.choice(list(alphabet)) for _ in range(rng.randrange(2, 7))]
        words.append(WordGlyphs(f"w{i:03d}", "".join(alphabet[g] for g in gids), "F", tuple((g, alphabet[g]) for g in gids)))
    ledger = GlyphMappingLedger(min_words=2)
    while True:
        candidate = ledger.next_candidate(words)
        if candidate is None:
            break
        ledger.record(candidate, not any(g in unreadable for g, _c in candidate.glyphs))
    verified = ledger.verification().verified
    assert {g for (_f, g) in verified} == set(alphabet) - unreadable
    assert all(verified[("F", g)] == alphabet[g] for (_f, g) in verified)
    assert ledger.attempts < len(words) / 2                      # attempts spent on the unreadable glyphs are the waste
    counts = coverage(words, ledger.verification())
    assert counts[GLYPH_CONTRADICTED] == 0
    assert counts[ALL_GLYPHS_VERIFIED] == sum(1 for w in words if not any(g in unreadable for g, _c in w.glyphs))


def test_a_mislabelled_glyph_is_never_verified_because_no_word_with_it_is_corroborated():
    # glyph 20 is drawn as '7' but claimed as '1'; a recogniser reads what is drawn, so no word spelled with the claim '1' there is corroborated
    shape = {10: "0", 11: "2", 20: "7"}
    claim = {10: "0", 11: "2", 20: "1"}
    words = [WordGlyphs(f"w{i}", "".join(claim[g] for g in gids), "F", tuple((g, claim[g]) for g in gids))
             for i, gids in enumerate([(10, 11), (11, 20), (20, 10), (20, 20, 11), (10, 20, 11), (11, 10)])]
    ledger = GlyphMappingLedger(min_words=2)
    while (candidate := ledger.next_candidate(words)) is not None:
        ledger.record(candidate, all(shape[g] == claim[g] for g, _c in candidate.glyphs))
    assert ("F", 20) not in ledger.verification().verified
    assert {k for k in ledger.verification().verified} == {("F", 10), ("F", 11)}
    assert classify_word(words[1], ledger.verification()) == GLYPH_NOT_YET_VERIFIED


def test_verification_cannot_be_lowered_to_one_word_or_noninteger_threshold():
    single = [word("solo", "A", [10])]
    for invalid in (0, 1, True, 1.5, "2"):
        with pytest.raises(ValueError, match="min_words"):
            verify_glyph_mappings(single, min_words=invalid)
    assert verify_glyph_mappings(single, min_words=2).verified == {}


def test_duplicate_observation_with_changed_glyph_evidence_blocks_instead_of_hiding_order_conflict():
    first = word("same", "A", [10])
    second = word("same", "B", [10])
    for records in ([first, second], [second, first]):
        with pytest.raises(ValueError, match="conflicting glyph evidence"):
            verify_glyph_mappings(records)
    assert verify_glyph_mappings([first, first]).under_supported == {("F", 10): 1}
    ledger = GlyphMappingLedger()
    ledger.record(first, True)
    with pytest.raises(ValueError, match="conflicting glyph evidence"):
        ledger.record(second, True)
    assert ledger.verification().under_supported == {("F", 10): 1}
