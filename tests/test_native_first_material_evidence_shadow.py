"""Focused tests for generic native-first material evidence with bounded OCR fallback."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_native_first_material_evidence_shadow import (
    MaterialBlockWord,
    MaterialEvidenceRoute,
    classify_material_block_route,
    resolve_material_block_native_first_shadow,
)


def _w(oid: str, text: str, *, trusted: bool, reasons: tuple[str, ...] = ()) -> MaterialBlockWord:
    return MaterialBlockWord(
        observation_id=oid, page_id="7", text=text, trusted=trusted, reason_codes=reasons,
    )


def test_native_trusted_vector_block_uses_zero_ocr_calls() -> None:
    words = (_w("w1", "FINISHES", trusted=True), _w("w2", "SCHEDULE", trusted=True))

    def _forbidden_ocr(_word):
        pytest.fail("native-trusted block must not invoke OCR")

    res = resolve_material_block_native_first_shadow(words, corroborate_word=_forbidden_ocr)
    assert res.route is MaterialEvidenceRoute.NATIVE_TRUSTED
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.ocr_calls_attempted == 0
    assert res.shadow_only is True
    assert res.commercial_authority_granted is False
    assert res.resolved_words == words


def test_unverified_native_block_corroborates_all_words_identically() -> None:
    words = (
        _w("w1", "F1", trusted=False, reasons=("text_glyph_mapping_unverified",)),
        _w("w2", "VINYL", trusted=False, reasons=("text_glyph_mapping_unverified",)),
    )
    res = resolve_material_block_native_first_shadow(
        words, corroborate_word=lambda w: w.text,
    )
    assert res.route is MaterialEvidenceRoute.NATIVE_UNVERIFIED_TARGETED_OCR
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.ocr_calls_attempted == 2
    assert res.ocr_calls_corroborated == 2
    assert res.ocr_calls_skipped_fail_fast == 0
    assert all(w.trusted for w in res.resolved_words)


def test_fail_fast_all_or_nothing_block_skips_remaining_ocr_with_exact_equivalence() -> None:
    words = tuple(
        _w(f"w{i}", f"TOK{i}", trusted=False, reasons=("text_glyph_mapping_unverified",))
        for i in range(10)
    )
    calls = []

    def _corroborate(w: MaterialBlockWord):
        calls.append(w.observation_id)
        return None if w.observation_id == "w1" else w.text

    res = resolve_material_block_native_first_shadow(
        words, corroborate_word=_corroborate, require_all_words_trusted=True,
    )
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert calls == ["w0", "w1"]
    assert res.ocr_calls_attempted == 2
    assert res.ocr_calls_corroborated == 1
    assert res.ocr_calls_skipped_fail_fast == 8
    assert res.reason_codes == ("targeted_ocr_word_uncorroborated_fail_fast",)


def test_scanned_empty_and_corrupted_glyph_blocks_always_route_to_ocr_fallback() -> None:
    # Scanned / image-only page (no native words)
    scanned = resolve_material_block_native_first_shadow((), corroborate_word=lambda w: w.text)
    assert scanned.route is MaterialEvidenceRoute.SCANNED_OR_CORRUPTED_OCR_REQUIRED
    assert scanned.status is EvidenceResolutionStatus.ABSTAINED
    assert scanned.ocr_calls_attempted == 0

    # Corrupted glyph stream (replacement char U+FFFD) — even if marked trusted!
    garbled = (_w("g1", "F1 \ufffd EPOXY", trusted=True),)
    assert classify_material_block_route(garbled) is MaterialEvidenceRoute.SCANNED_OR_CORRUPTED_OCR_REQUIRED
    garbled_res = resolve_material_block_native_first_shadow(garbled, corroborate_word=lambda w: w.text)
    assert garbled_res.status is EvidenceResolutionStatus.ABSTAINED


def test_bounded_ocr_budget_fails_closed_when_exhausted() -> None:
    words = tuple(
        _w(f"w{i}", f"T{i}", trusted=False, reasons=("text_glyph_mapping_unverified",))
        for i in range(5)
    )
    res = resolve_material_block_native_first_shadow(
        words, corroborate_word=lambda w: w.text, max_ocr_calls=2,
    )
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert res.ocr_calls_attempted == 2
    assert res.ocr_calls_skipped_fail_fast == 3
    assert res.reason_codes == ("targeted_ocr_budget_exhausted",)


def test_recover_native_material_block_fail_fast_shadow_default_off_and_wired() -> None:
    """Verify _recover_native_material_block wires default-off fail_fast_all_trusted_block_shadow."""
    import inspect
    import pb_source_material_semantic_authority as mat

    sig_block = inspect.signature(mat._recover_native_material_block)
    sig_lines = inspect.signature(mat._recover_admissible_viewport_lines)
    assert sig_block.parameters["fail_fast_all_trusted_block_shadow"].default is False
    assert sig_lines.parameters["fail_fast_all_trusted_block_shadow"].default is False

    # All-trusted native block returns identically with zero OCR regardless of flag.
    trusted_word = mat._TrustedTextWord(
        observation_id="obs-1",
        page_id="1",
        source_partition_id="p1",
        text="FINISHES",
        bbox=(10.0, 10.0, 60.0, 20.0),
        block_no=0,
        line_no=0,
        word_no=0,
        trusted=True,
        reason_codes=(),
    )
    out_off = mat._recover_native_material_block(
        source=None,  # type: ignore[arg-type]
        published=None,
        raster=None,  # type: ignore[arg-type]
        block_words=(trusted_word,),
        fail_fast_all_trusted_block_shadow=False,
    )
    out_on = mat._recover_native_material_block(
        source=None,  # type: ignore[arg-type]
        published=None,
        raster=None,  # type: ignore[arg-type]
        block_words=(trusted_word,),
        fail_fast_all_trusted_block_shadow=True,
    )
    assert out_off == out_on == (trusted_word,)
