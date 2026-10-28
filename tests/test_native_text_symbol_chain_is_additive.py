"""The source symbol-font chain must EXTEND the default glyph proof, never replace it.

Measured defect (original Lot16, default vs opt-in on every page): the opt-in turned 4,516 trusted
words into 0, because with the flag on the default embedded-Unicode-cmap proof was skipped and the
symbol chain (which only understands one-byte symbol TrueType subsets) reported "unverified" for every
ordinary font. These tests pin the corrected rule on the glyph proof itself, with its two collaborators
replaced so each branch is exercised exactly once:

* default verifies          -> verified, the chain is not consulted (ordinary fonts keep their trust);
* default contradicts       -> contradiction stays a contradiction (no rescue by the chain);
* default cannot decide     -> the independent chain decides (the subset-font CAD case);
* flag off                  -> byte-for-byte the previous behaviour.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

import pb_pdf_text_integrity_authority as authority
from pb_pdf_text_integrity_authority import (
    TEXT_GLYPH_MAPPING_UNVERIFIED,
    TEXT_GLYPH_UNICODE_MISMATCH,
)

ROOT = Path(__file__).resolve().parents[1]
SPAN = {"chars": ((0x34, 17, (0, 0, 1, 1)), (0x31, 12, (1, 0, 2, 1)))}  # '4', '1'
FONT = (7, "ttf", "TrueType", "BASE", "F1", "")


class _Font:
    """Embedded-font view whose own Unicode cmap says which glyph each code point owns."""

    def __init__(self, table):
        self._table = table

    def has_glyph(self, codepoint, fallback=0):
        return self._table.get(codepoint, 0)


def _arrange(monkeypatch, *, font_table, chain):
    calls = []
    monkeypatch.setattr(authority, "_font_for_glyph_validation",
                        lambda page, font: None if font_table is None else _Font(font_table))

    def fake_chain(page, span, font):
        calls.append("chain")
        return chain

    monkeypatch.setattr(authority, "_source_embedded_symbol_byte_glyph_reasons", fake_chain)
    return calls


def _reasons(*, shadow):
    return authority._glyph_unicode_consistency_reasons(
        object(), SPAN, FONT, **({"source_symbol_font_chain_shadow": True} if shadow else {}))


def test_default_verified_font_stays_verified_with_the_opt_in_and_the_chain_is_not_consulted(monkeypatch):
    calls = _arrange(monkeypatch, font_table={0x34: 17, 0x31: 12}, chain=(TEXT_GLYPH_MAPPING_UNVERIFIED,))
    assert _reasons(shadow=False) == ()
    assert _reasons(shadow=True) == ()
    assert calls == []


def test_default_contradiction_is_not_rescued_by_a_verifying_chain(monkeypatch):
    calls = _arrange(monkeypatch, font_table={0x34: 17, 0x31: 99}, chain=())
    assert _reasons(shadow=False) == (TEXT_GLYPH_UNICODE_MISMATCH,)
    assert _reasons(shadow=True) == (TEXT_GLYPH_UNICODE_MISMATCH,)
    assert calls == []


@pytest.mark.parametrize("font_table", [None, {}, {0x34: 17}])
def test_when_the_default_proof_cannot_decide_the_independent_chain_decides(monkeypatch, font_table):
    for chain in ((), (TEXT_GLYPH_MAPPING_UNVERIFIED,), (TEXT_GLYPH_UNICODE_MISMATCH,)):
        calls = _arrange(monkeypatch, font_table=font_table, chain=chain)
        assert _reasons(shadow=False) == (TEXT_GLYPH_MAPPING_UNVERIFIED,)
        assert _reasons(shadow=True) == chain
        assert calls == ["chain"]


def test_without_the_opt_in_the_chain_is_never_consulted(monkeypatch):
    calls = _arrange(monkeypatch, font_table=None, chain=())
    assert _reasons(shadow=False) == (TEXT_GLYPH_MAPPING_UNVERIFIED,)
    assert calls == []


def test_a_span_with_no_decidable_character_stays_unverified_even_with_a_chain_that_would_pass(monkeypatch):
    # A glyph id of -1 (ligature continuation) alone proves nothing; the default proof abstains and
    # the chain, given nothing to verify, also abstains.
    calls = _arrange(monkeypatch, font_table={0x34: 17}, chain=(TEXT_GLYPH_MAPPING_UNVERIFIED,))
    span = {"chars": ((0x34, -1, (0, 0, 1, 1)),)}
    assert authority._glyph_unicode_consistency_reasons(object(), span, FONT) == (TEXT_GLYPH_MAPPING_UNVERIFIED,)
    assert authority._glyph_unicode_consistency_reasons(
        object(), span, FONT, source_symbol_font_chain_shadow=True) == (TEXT_GLYPH_MAPPING_UNVERIFIED,)
    assert calls == ["chain"]


ORIGINAL = ROOT / "documents" / "sources" / "1. Construction Plans - Lot 16 Power (REV E).pdf"


@pytest.mark.skipif(not ORIGINAL.is_file(), reason="private original Lot16 not provisioned: NOT VERIFIED")
def test_original_lot16_opt_in_is_never_less_trusting_than_default():
    # p4 has no clip-unresolved words, so this isolates the glyph proof: default trusts all of them.
    from pb_pdf_text_integrity_authority import classify_native_word_integrity

    with fitz.open(ORIGINAL) as document:
        page = document[3]
        words = [{"text": w[4], "bbox": tuple(w[:4]), "block_no": w[5], "line_no": w[6], "word_no": w[7]}
                 for w in page.get_text("words")]
        default = sum(classify_native_word_integrity(page, w).trusted for w in words)
        opted = sum(classify_native_word_integrity(
            page, w, source_symbol_font_chain_shadow=True,
            source_raw_no_active_text_clip_shadow=True).trusted for w in words)
    assert default == len(words) > 0
    assert opted >= default
