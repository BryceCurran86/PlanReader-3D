"""Comprehensive unit and regression tests for pb_source_amortized_glyph_text_corroboration_shadow (Items 22 & 23)."""
from __future__ import annotations

import pytest

from pb_font_glyph_mapping_corroboration_shadow import WordGlyphs
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_amortized_glyph_text_corroboration_shadow import (
    AMORTIZED_GLYPH_CORROBORATED,
    AMORTIZED_TEXT_RECORD_UNAVAILABLE,
    DIRECT_OCR_CORROBORATED,
    GLYPH_CONTRADICTED_CODE,
    GLYPH_MAPPING_UNDER_SUPPORTED,
    GLYPHS_NOT_RECOVERED_CODE,
    OCR_CORROBORATION_FAILED,
    SOURCE_AMORTIZED_GLYPH_TEXT_SCHEMA_VERSION,
    SourceAmortizedGlyphTextAuthority,
    SourceAmortizedGlyphTextProducer,
    SourceAmortizedGlyphTextRecord,
    SourceAmortizedGlyphTextSelector,
)

DOC = "doc-3laurel"
REV = "rev-001"
SHA = "c" * 64
SNAP = "snap-001"
PAGE = "3"
SCOPE = f"wall-source:page-{PAGE}"
FONT = "font-arial-cff-01"


def _make_selector(obs_id: str) -> SourceAmortizedGlyphTextSelector:
    return SourceAmortizedGlyphTextSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
        observation_id=obs_id,
    )


def test_positive_direct_ocr_corroboration() -> None:
    selector = _make_selector("obs-1")
    producer = SourceAmortizedGlyphTextProducer.create(min_words=2)

    word1 = WordGlyphs("obs-1", "ROOM", FONT, ((1, "R"), (2, "O"), (2, "O"), (3, "M")))
    producer.register_word(word1)
    producer.record_direct_ocr_result("obs-1", True)

    res = producer.evaluate_and_publish(selector)

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert DIRECT_OCR_CORROBORATED in res.reason_codes
    assert res.record is not None
    assert res.record.corroboration_method == "DIRECT_OCR"
    assert res.record.text == "ROOM"
    assert res.record.commercial_projection_allowed is False
    assert res.record.takeoff_eligible is False


def test_positive_amortized_glyph_corroboration_without_ocr() -> None:
    producer = SourceAmortizedGlyphTextProducer.create(min_words=2)

    # Word 1: "BED" -> glyphs (1: 'B', 2: 'E', 3: 'D')
    word1 = WordGlyphs("obs-1", "BED", FONT, ((1, "B"), (2, "E"), (3, "D")))
    # Word 2: "RED" -> glyphs (4: 'R', 2: 'E', 3: 'D')
    word2 = WordGlyphs("obs-2", "RED", FONT, ((4, "R"), (2, "E"), (3, "D")))
    # Word 3: "BEE" -> glyphs (1: 'B', 2: 'E', 2: 'E')
    word3 = WordGlyphs("obs-3", "BEE", FONT, ((1, "B"), (2, "E"), (2, "E")))

    producer.register_word(word1)
    producer.register_word(word2)
    producer.register_word(word3)

    # Run direct OCR on word1, word2, word3
    # Now glyph 1 ('B') has 2 votes (word1, word3)
    # Glyph 2 ('E') has 3 votes (word1, word2, word3)
    # Glyph 3 ('D') has 2 votes (word1, word2)
    # All glyphs {1, 2, 3} are fully verified!
    producer.record_direct_ocr_result("obs-1", True)
    producer.record_direct_ocr_result("obs-2", True)
    producer.record_direct_ocr_result("obs-3", True)

    # Word 4: "DEED" -> glyphs (3: 'D', 2: 'E', 2: 'E', 3: 'D')
    # NEVER evaluated with OCR!
    word4 = WordGlyphs("obs-4", "DEED", FONT, ((3, "D"), (2, "E"), (2, "E"), (3, "D")))
    producer.register_word(word4)

    sel4 = _make_selector("obs-4")
    res4 = producer.evaluate_and_publish(sel4)

    assert res4.status == EvidenceResolutionStatus.CANDIDATE
    assert AMORTIZED_GLYPH_CORROBORATED in res4.reason_codes
    assert res4.record is not None
    assert res4.record.corroboration_method == "AMORTIZED_GLYPH"
    assert res4.record.text == "DEED"
    assert res4.record.verified_glyphs_count == 4
    assert res4.record.commercial_projection_allowed is False
    assert res4.record.takeoff_eligible is False


def test_under_supported_glyph_abstains() -> None:
    producer = SourceAmortizedGlyphTextProducer.create(min_words=2)

    # Word 1: "BATH" -> glyphs (1: 'B', 2: 'A', 3: 'T', 4: 'H')
    word1 = WordGlyphs("obs-1", "BATH", FONT, ((1, "B"), (2, "A"), (3, "T"), (4, "H")))
    producer.register_word(word1)
    producer.record_direct_ocr_result("obs-1", True)

    # Word 2: "BAT" -> glyph 1, 2, 3 have 2 votes, but glyph 4 ('H') only has 1 vote
    word2 = WordGlyphs("obs-2", "BAT", FONT, ((1, "B"), (2, "A"), (3, "T")))
    producer.register_word(word2)
    producer.record_direct_ocr_result("obs-2", True)

    # Word 3: "HAT" -> glyph 4 ('H') is under-supported (only 1 vote from word1)
    word3 = WordGlyphs("obs-3", "HAT", FONT, ((4, "H"), (2, "A"), (3, "T")))
    producer.register_word(word3)

    sel3 = _make_selector("obs-3")
    res3 = producer.evaluate_and_publish(sel3)

    assert res3.status == EvidenceResolutionStatus.ABSTAINED
    assert GLYPH_MAPPING_UNDER_SUPPORTED in res3.reason_codes
    assert res3.record is None


def test_contradicted_glyph_fails_closed_with_conflict() -> None:
    producer = SourceAmortizedGlyphTextProducer.create(min_words=2)

    # Glyph 1 is claimed as 'B' in word 1, but claimed as 'D' in word 2
    word1 = WordGlyphs("obs-1", "BEE", FONT, ((1, "B"), (2, "E"), (2, "E")))
    word2 = WordGlyphs("obs-2", "DEE", FONT, ((1, "D"), (2, "E"), (2, "E")))

    producer.register_word(word1)
    producer.register_word(word2)

    producer.record_direct_ocr_result("obs-1", True)
    producer.record_direct_ocr_result("obs-2", True)

    # Word 3 contains conflicting glyph 1
    word3 = WordGlyphs("obs-3", "BED", FONT, ((1, "B"), (2, "E"), (3, "D")))
    producer.register_word(word3)

    sel3 = _make_selector("obs-3")
    res3 = producer.evaluate_and_publish(sel3)

    assert res3.status == EvidenceResolutionStatus.CONFLICT
    assert GLYPH_CONTRADICTED_CODE in res3.reason_codes
    assert res3.record is None


def test_failed_ocr_reading_abstains() -> None:
    producer = SourceAmortizedGlyphTextProducer.create(min_words=2)

    word1 = WordGlyphs("obs-1", "NOISE", FONT, ((1, "N"), (2, "O"), (3, "I"), (4, "S"), (5, "E")))
    producer.register_word(word1)
    # OCR failed / mismatched
    producer.record_direct_ocr_result("obs-1", False)

    sel1 = _make_selector("obs-1")
    res1 = producer.evaluate_and_publish(sel1)

    assert res1.status == EvidenceResolutionStatus.ABSTAINED
    assert OCR_CORROBORATION_FAILED in res1.reason_codes
    assert res1.record is None


def test_optimal_ocr_planning_maximizes_glyph_gain() -> None:
    producer = SourceAmortizedGlyphTextProducer.create(min_words=2)

    # Pool of 5 words
    w1 = WordGlyphs("o1", "ABCDE", FONT, ((1, "A"), (2, "B"), (3, "C"), (4, "D"), (5, "E")))
    w2 = WordGlyphs("o2", "FGHIJ", FONT, ((6, "F"), (7, "G"), (8, "H"), (9, "I"), (10, "J")))
    w3 = WordGlyphs("o3", "A", FONT, ((1, "A"),))
    w4 = WordGlyphs("o4", "ABCDE", FONT, ((1, "A"), (2, "B"), (3, "C"), (4, "D"), (5, "E")))
    w5 = WordGlyphs("o5", "FGHIJ", FONT, ((6, "F"), (7, "G"), (8, "H"), (9, "I"), (10, "J")))

    sample = producer.plan_optimal_ocr_sample([w1, w2, w3, w4, w5], budget=4)

    # First choices should be w1 and w2 (which each introduce 5 new glyphs), then w4 and w5 (which give the second votes)
    obs_order = [w.observation_id for w in sample]
    assert len(obs_order) == 4
    assert set(obs_order) == {"o1", "o2", "o4", "o5"}
    assert "o3" not in obs_order  # single character word deferred in favor of high-yield words


def test_authority_lookup_and_unknown_selector() -> None:
    selector = _make_selector("obs-known")
    producer = SourceAmortizedGlyphTextProducer.create(min_words=2)

    word = WordGlyphs("obs-known", "HALL", FONT, ((1, "H"), (2, "A"), (3, "L"), (3, "L")))
    producer.register_word(word)
    producer.record_direct_ocr_result("obs-known", True)

    producer.evaluate_and_publish(selector)

    auth = producer.authority()
    assert type(auth) is SourceAmortizedGlyphTextAuthority

    res_known = auth.resolve(selector)
    assert res_known.status == EvidenceResolutionStatus.CANDIDATE
    assert res_known.record is not None

    unknown_sel = _make_selector("obs-unknown")
    res_unknown = auth.resolve(unknown_sel)
    assert res_unknown.status == EvidenceResolutionStatus.ABSTAINED
    assert AMORTIZED_TEXT_RECORD_UNAVAILABLE in res_unknown.reason_codes


def test_sealed_record_and_authority_forbids_direct_construction() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        SourceAmortizedGlyphTextRecord(
            record_id="r1",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            observation_id="obs-1",
            text="TEST",
            font_key=FONT,
            corroboration_method="AMORTIZED_GLYPH",
            verified_glyphs_count=4,
            total_glyphs_count=4,
            corroborating_evidence_ids=(),
        )

    with pytest.raises(TypeError, match="producer-owned"):
        SourceAmortizedGlyphTextAuthority({})

    with pytest.raises(TypeError, match="create()"):
        SourceAmortizedGlyphTextProducer()
