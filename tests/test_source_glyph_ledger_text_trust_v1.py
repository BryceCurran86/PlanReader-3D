"""Glyph-ledger text trust: which glyph-only-untrusted words may become trusted text (pure decision logic, default-off).

A word whose ONLY blocker is ``text_glyph_mapping_unverified`` becomes trusted when (a) the raster corroboration authority itself read it, or
(b) every glyph in it has a (font program, glyph id) -> character mapping supported by at least two independently corroborated words and
contradicted by none. Corroboration outcomes are an injected, boolean-returning function (production wires it to sealed CORROBORATED records);
synthetic words only, no project value is an oracle.
"""
from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import asdict

import pytest

from pb_font_glyph_mapping_corroboration_shadow import WordGlyphs
from pb_migration_contracts import EvidenceResolutionStatus
from pb_pdf_text_integrity_authority import (
    TEXT_GLYPH_MAPPING_UNVERIFIED,
    PdfTextIntegrityReceipt,
)
from pb_source_glyph_ledger_text_trust import (
    DECODE_STATUS_AMORTIZED_GLYPH,
    DECODE_STATUS_DIRECT_RASTER,
    GlyphTextCandidate,
    decide_glyph_text_trust,
    is_glyph_only_untrusted,
    upgraded_text_integrity_receipt,
)

CORROBORATED = EvidenceResolutionStatus.CORROBORATED
ABSTAINED = EvidenceResolutionStatus.ABSTAINED
CONFLICT = EvidenceResolutionStatus.CONFLICT


def _word(oid: str, text: str, *, font: str = "font-1", shift: int = 0) -> WordGlyphs:
    return WordGlyphs(oid, text, font, tuple((ord(c) - 29 + shift, c) for c in text))


def _cand(oid: str, text: str, **kw) -> GlyphTextCandidate:
    return GlyphTextCandidate(observation_id=oid, word=_word(oid, text, **kw))


def _receipt(reasons=(TEXT_GLYPH_MAPPING_UNVERIFIED,), trusted=False, **kw) -> PdfTextIntegrityReceipt:
    fields = dict(
        receipt_id="rcpt-1", parent_observation_id="obs-1", document_id="doc", revision_id="rev", source_sha256="a" * 64,
        page_id="3", source_partition_id="page:3", raw_text="WINDOW", geometry=(1.0, 2.0, 30.0, 12.0), trusted=trusted,
        decode_status="tounicode_glyph_unverified", visibility_status="proven_visible", reason_codes=tuple(reasons),
        font_xref=7, font_subtype="Type0", font_name="ArialMT", sequence_number=5,
    )
    fields.update(kw)
    return PdfTextIntegrityReceipt(**fields)


# ---------------------------------------------------------------- which receipts may be upgraded at all
def test_only_a_receipt_whose_sole_blocker_is_the_glyph_proof_is_upgradable():
    assert is_glyph_only_untrusted(_receipt()) is True
    for extra in ("text_clip_state_unresolved", "text_occluded_by_later_paint", "text_font_binding_ambiguous",
                  "text_trace_unavailable", "text_unicode_untrusted", "text_low_contrast_default_page"):
        assert is_glyph_only_untrusted(_receipt(reasons=(TEXT_GLYPH_MAPPING_UNVERIFIED, extra))) is False
    assert is_glyph_only_untrusted(_receipt(reasons=("text_font_binding_ambiguous",))) is False
    assert is_glyph_only_untrusted(_receipt(reasons=())) is False
    assert is_glyph_only_untrusted(_receipt(reasons=(), trusted=True)) is False
    assert is_glyph_only_untrusted(_receipt(trusted=True)) is False


# ---------------------------------------------------------------- the vote rule
def test_two_corroborated_words_verify_their_shared_glyphs_for_an_unread_word():
    cands = [_cand("a", "AB"), _cand("b", "BA"), _cand("c", "AAB")]
    result = decide_glyph_text_trust(cands, lambda oid: oid in {"a", "b"})
    assert result.decisions["c"].status is CORROBORATED
    assert result.decisions["c"].method == "amortized_glyph"
    assert set(result.decisions["c"].corroborating_observation_ids) == {"a", "b"}
    for oid in ("a", "b"):
        assert result.decisions[oid].status is CORROBORATED and result.decisions[oid].method == "direct_raster"


def test_one_corroborated_word_never_verifies_anything_else():
    cands = [_cand("a", "AB"), _cand("b", "AB")]
    result = decide_glyph_text_trust(cands, lambda oid: oid == "a")
    assert result.decisions["a"].status is CORROBORATED
    assert result.decisions["b"].status is ABSTAINED
    assert "glyph_mapping_under_supported" in result.decisions["b"].reason_codes


def test_a_glyph_seen_in_only_one_corroborated_word_leaves_other_words_with_it_untrusted():
    cands = [_cand("a", "AB"), _cand("b", "AC"), _cand("c", "AD"), _cand("d", "BA")]
    result = decide_glyph_text_trust(cands, lambda oid: oid in {"a", "b", "d"})
    # D occurs only in the unread word: not verified, so that word stays untrusted.
    assert result.decisions["c"].status is ABSTAINED
    assert "glyph_mapping_under_supported" in result.decisions["c"].reason_codes


def test_failed_attempts_cast_no_vote():
    cands = [_cand("a", "AB"), _cand("b", "AB"), _cand("c", "AB")]
    result = decide_glyph_text_trust(cands, lambda oid: oid == "a")     # b and c are attempted and fail
    assert result.decisions["a"].status is CORROBORATED
    assert result.decisions["b"].status is ABSTAINED and result.decisions["c"].status is ABSTAINED
    assert "b" in result.attempted_observation_ids and "b" not in result.corroborated_observation_ids


def test_contradicted_glyph_marks_every_word_that_uses_it_as_conflict():
    # glyph id 36 is read as 'A' by one word and as 'C' by another: neither wins.
    p = WordGlyphs("p", "AB", "font-1", ((36, "A"), (37, "B")))
    q = WordGlyphs("q", "CD", "font-1", ((36, "C"), (38, "D")))
    r = WordGlyphs("r", "AE", "font-1", ((36, "A"), (40, "E")))
    result = decide_glyph_text_trust(
        [GlyphTextCandidate("p", p), GlyphTextCandidate("q", q), GlyphTextCandidate("r", r)],
        lambda oid: oid in {"p", "q"})
    assert result.decisions["r"].status is CONFLICT and "glyph_contradicted" in result.decisions["r"].reason_codes
    assert result.decisions["p"].status is CONFLICT and result.decisions["q"].status is CONFLICT
    assert result.contradicted_glyph_count == 1


def test_a_word_spelled_differently_from_a_verified_mapping_is_a_conflict():
    cands = [_cand("a", "AB"), _cand("b", "AB"), _cand("c", "AB")]
    odd = WordGlyphs("odd", "XB", "font-1", ((36, "X"), (37, "B")))     # gid 36 is verified as 'A'
    result = decide_glyph_text_trust([*cands, GlyphTextCandidate("odd", odd)], lambda oid: oid in {"a", "b"})
    assert result.decisions["odd"].status is CONFLICT


def test_a_mapping_in_one_font_program_never_transfers_to_another():
    cands = [_cand("a", "AB", font="f1"), _cand("b", "BA", font="f1"), _cand("c", "AB", font="f2")]
    result = decide_glyph_text_trust(cands, lambda oid: oid in {"a", "b"})
    assert result.decisions["c"].status is ABSTAINED


def test_words_without_recovered_glyphs_are_abstained_not_guessed():
    cands = [_cand("a", "AB"), _cand("b", "BA"), GlyphTextCandidate("ghost", None)]
    result = decide_glyph_text_trust(cands, lambda oid: oid in {"a", "b"})
    assert result.decisions["ghost"].status is ABSTAINED
    assert "glyphs_not_recovered" in result.decisions["ghost"].reason_codes


# ---------------------------------------------------------------- budget, determinism, purity
def test_attempt_budget_is_respected_and_leaves_the_rest_untrusted():
    cands = [_cand(f"w{i}", "AB") for i in range(6)]
    calls: list[str] = []

    def corroborate(oid: str) -> bool:
        calls.append(oid)
        return True

    result = decide_glyph_text_trust(cands, corroborate, max_attempts=1)
    assert len(calls) == 1 == len(result.attempted_observation_ids)
    assert sum(1 for d in result.decisions.values() if d.status is CORROBORATED) == 1


def test_planning_stops_once_every_glyph_is_settled_instead_of_reading_every_word():
    cands = [_cand(f"w{i}", "AB") for i in range(10)]
    calls: list[str] = []
    decide_glyph_text_trust(cands, lambda oid: calls.append(oid) or True)
    assert len(calls) == 2                                               # two votes settle both glyphs


def test_decisions_and_attempt_order_do_not_depend_on_input_order():
    base = [_cand("a", "AB"), _cand("b", "BC"), _cand("c", "ABC"), _cand("d", "CA"), _cand("e", "AAB"), _cand("f", "BBC")]
    reference = decide_glyph_text_trust(base, lambda oid: oid in {"a", "b", "c", "d"})
    for seed in range(8):
        shuffled = list(base)
        random.Random(seed).shuffle(shuffled)
        again = decide_glyph_text_trust(shuffled, lambda oid: oid in {"a", "b", "c", "d"})
        assert again.attempted_observation_ids == reference.attempted_observation_ids
        assert dict(again.decisions) == dict(reference.decisions)
        assert list(again.decisions) == list(reference.decisions) == sorted(reference.decisions)   # stable serialisation order


def test_inputs_are_not_mutated_and_replay_is_identical():
    cands = [_cand("a", "AB"), _cand("b", "BA"), _cand("c", "AAB")]
    before = deepcopy([asdict(c) for c in cands])
    first = decide_glyph_text_trust(cands, lambda oid: oid in {"a", "b"})
    second = decide_glyph_text_trust(cands, lambda oid: oid in {"a", "b"})
    assert first == second and before == [asdict(c) for c in cands]


def test_corroborate_must_return_a_real_bool():
    cands = [_cand("a", "AB"), _cand("b", "BA")]
    for bad in ("yes", 1, None):
        with pytest.raises(TypeError):
            decide_glyph_text_trust(cands, lambda oid, bad=bad: bad)


@pytest.mark.parametrize("min_words", [0, 1, True, 2.0, "2"])
def test_one_word_can_never_verify_a_glyph(min_words):
    with pytest.raises(ValueError):
        decide_glyph_text_trust([_cand("a", "AB")], lambda oid: True, min_words=min_words)


def test_duplicate_or_mismatched_candidates_are_rejected():
    with pytest.raises(ValueError):
        decide_glyph_text_trust([_cand("a", "AB"), _cand("a", "AB")], lambda oid: True)
    with pytest.raises(ValueError):
        decide_glyph_text_trust([GlyphTextCandidate("a", _word("b", "AB"))], lambda oid: True)


# ---------------------------------------------------------------- the receipt upgrade
def _decisions():
    cands = [_cand("a", "AB"), _cand("b", "BA"), _cand("c", "AAB")]
    return decide_glyph_text_trust(cands, lambda oid: oid in {"a", "b"}).decisions


def _receipt_for(decision, **kw) -> PdfTextIntegrityReceipt:
    return _receipt(parent_observation_id=decision.observation_id, **kw)


def test_an_upgraded_receipt_is_trusted_with_a_new_id_and_the_same_text_and_geometry():
    decisions = _decisions()
    amortized, direct = decisions["c"], decisions["a"]
    base = _receipt_for(amortized)
    new = upgraded_text_integrity_receipt(base, amortized)
    assert new.trusted is True and new.reason_codes == () and new.decode_status == DECODE_STATUS_AMORTIZED_GLYPH
    assert new.receipt_id != base.receipt_id
    assert (new.raw_text, new.geometry, new.parent_observation_id, new.page_id, new.source_sha256) == (
        base.raw_text, base.geometry, base.parent_observation_id, base.page_id, base.source_sha256)
    assert new.visibility_status == base.visibility_status == "proven_visible"
    assert (new.font_xref, new.font_subtype, new.font_name, new.sequence_number) == (7, "Type0", "ArialMT", 5)
    assert base.trusted is False and base.reason_codes == (TEXT_GLYPH_MAPPING_UNVERIFIED,)      # base is untouched
    direct_receipt = upgraded_text_integrity_receipt(_receipt_for(direct), direct)
    assert direct_receipt.decode_status == DECODE_STATUS_DIRECT_RASTER and direct_receipt.receipt_id != new.receipt_id


def test_the_receipt_id_is_deterministic():
    decision = _decisions()["c"]
    assert upgraded_text_integrity_receipt(_receipt_for(decision), decision) == upgraded_text_integrity_receipt(
        _receipt_for(decision), decision)


@pytest.mark.parametrize("extra", ["text_clip_state_unresolved", "text_occluded_by_later_paint", "text_font_binding_ambiguous"])
def test_a_receipt_with_any_other_blocker_is_never_upgraded(extra):
    decision = _decisions()["c"]
    with pytest.raises(ValueError):
        upgraded_text_integrity_receipt(_receipt_for(decision, reasons=(TEXT_GLYPH_MAPPING_UNVERIFIED, extra)), decision)


def test_a_receipt_whose_visibility_is_not_proven_is_never_upgraded():
    decision = _decisions()["c"]
    with pytest.raises(ValueError):
        upgraded_text_integrity_receipt(_receipt_for(decision, visibility_status="unresolved_or_blocked"), decision)


def test_a_decision_for_another_word_cannot_upgrade_this_receipt():
    decision = _decisions()["c"]
    with pytest.raises(ValueError):
        upgraded_text_integrity_receipt(_receipt(parent_observation_id="some-other-word"), decision)


def test_only_a_corroborated_decision_can_upgrade_a_receipt():
    cands = [_cand("a", "AB"), _cand("b", "AB")]
    result = decide_glyph_text_trust(cands, lambda oid: oid == "a")
    under_supported = result.decisions["b"]
    with pytest.raises(ValueError):
        upgraded_text_integrity_receipt(_receipt_for(under_supported), under_supported)
    already_trusted = _receipt_for(_decisions()["c"], reasons=(), trusted=True)
    with pytest.raises(ValueError):
        upgraded_text_integrity_receipt(already_trusted, _decisions()["c"])
