"""The glyph-mapping diagnostic spends few attempts, carries verified fonts across pages, and writes counts only."""
from __future__ import annotations

import json

import fitz
import pytest

import pb_pdf_text_integrity_authority as authority
from tools import diag_font_glyph_mapping_corroboration as tool

FONT_ALIAS = "NimbusSans-Regular"                         # the alias must equal the name the text trace reports, or the binding is ambiguous
VOCABULARY = ["12", "21", "112", "ABC", "CAB", "A1B2", "BAC1", "2C", "B21", "ZQ9"]


def two_page_pdf() -> bytes:
    program = fitz.Font("helv").buffer
    doc = fitz.open()
    for _ in range(2):
        page = doc.new_page(width=800, height=200)
        page.insert_font(fontname=FONT_ALIAS, fontbuffer=program)
        for i, word in enumerate(VOCABULARY):
            page.insert_text((20 + 70 * i, 60), word, fontname=FONT_ALIAS, fontsize=14)
        page.insert_text((20, 150), "TRUSTED", fontname="helv", fontsize=14)
    return doc.tobytes()


@pytest.fixture(autouse=True)
def glyphs_cannot_be_verified_by_the_font_program(monkeypatch):
    """Make the embedded program unable to answer, as a CID-keyed CFF or symbolic TrueType subset cannot (base-14 text stays trusted)."""
    monkeypatch.setattr(authority, "_font_for_glyph_validation", lambda page, font: None)


def everything(svp, published):
    return lambda observation_id: True


def nothing(svp, published):
    return lambda observation_id: False


UNIQUE_WORD = "ZQ9"                                                      # its three glyphs occur in no other word of the page
DISTINCT_GLYPHS = len({c for w in VOCABULARY for c in w})


def test_few_attempts_verify_every_glyph_that_two_words_share_and_leave_a_glyph_seen_once_unverified():
    result = tool.analyse(two_page_pdf(), [1], corroborator_factory=everything)
    row = result["pages"][0]
    assert row["words"] == len(VOCABULARY) + 1 and row["natively_trusted"] == 1
    assert row["blocked_only_by_glyph_mapping_or_clip"] == len(VOCABULARY)
    assert row["glyph_blocked_words_with_recovered_glyphs"] == len(VOCABULARY)
    assert row["distinct_font_glyph_pairs"] == DISTINCT_GLYPHS
    assert row["words_fully_verified_before_any_attempt_on_this_page"] == 0
    assert 0 < row["attempts_on_this_page"] < len(VOCABULARY)
    assert result["verified_font_glyph_pairs"] == DISTINCT_GLYPHS - 3 and result["under_supported_font_glyph_pairs"] == 3
    assert row["words_fully_verified_after"] == len(VOCABULARY) - 1                          # everything but the word with three one-off glyphs
    assert row["words_with_an_unverified_glyph_after"] == 1 and row["words_with_a_contradicted_glyph_after"] == 0
    assert result["contradicted_font_glyph_pairs"] == 0


def test_a_font_verified_on_one_page_carries_to_the_next_even_as_a_different_font_object():
    result = tool.analyse(two_page_pdf(), [1, 2], corroborator_factory=everything)
    first, second = result["pages"]
    assert first["attempts_on_this_page"] > 0
    assert second["words_fully_verified_before_any_attempt_on_this_page"] == len(VOCABULARY) - 1
    assert second["attempts_on_this_page"] == 1                                              # only the word that carries the one-off glyphs again
    assert second["words_fully_verified_after"] == len(VOCABULARY)
    assert result["font_programs_seen"] == 1 and result["verified_font_glyph_pairs"] == DISTINCT_GLYPHS


def test_when_nothing_can_be_read_nothing_is_verified_and_the_budget_is_respected():
    result = tool.analyse(two_page_pdf(), [1], budget=4, corroborator_factory=nothing)
    row = result["pages"][0]
    assert row["attempts_on_this_page"] == 4 and row["corroborated_on_this_page"] == 0
    assert result["verified_font_glyph_pairs"] == 0 and row["words_fully_verified_after"] == 0


def test_one_corroborated_word_per_glyph_is_not_enough_with_the_default_minimum():
    single = tool.analyse(two_page_pdf(), [1], budget=1, corroborator_factory=everything)
    assert single["verified_font_glyph_pairs"] == 0 and single["under_supported_font_glyph_pairs"] > 0
    relaxed = tool.analyse(two_page_pdf(), [1], budget=1, min_words=1, corroborator_factory=everything)
    assert relaxed["verified_font_glyph_pairs"] > 0


def test_the_report_has_counts_only_and_grants_nothing(tmp_path, capsys):
    payload = two_page_pdf()
    result = tool.analyse(payload, [1], corroborator_factory=everything)
    text = json.dumps(result)
    assert "ABC" not in text and "TRUSTED" not in text and "ZQ9" not in text
    assert result["shadow_only"] is True and result["live_effect"] is False and result["text_trust_granted"] is False
    assert len(result["pdf_sha256"]) == 64
    source = tmp_path / "doc.pdf"
    source.write_bytes(payload)
    with pytest.raises(ValueError):
        tool.analyse(payload, [3], corroborator_factory=everything)
    assert tool.font_program_key(fitz.open(stream=payload, filetype="pdf"), None) is None


def test_the_font_program_key_identifies_shapes_not_font_objects():
    doc = fitz.open(stream=two_page_pdf(), filetype="pdf")
    keys = {tool.font_program_key(doc, f[0]) for page in doc for f in page.get_fonts(full=True) if f[3] == "Nimbus Sans Regular"}
    assert len(keys) == 1 and None not in keys
    assert all(len(k) == 24 for k in keys)
