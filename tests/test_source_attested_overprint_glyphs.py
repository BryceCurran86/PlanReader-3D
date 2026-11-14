"""Source-attested complementary paints remain one logical glyph candidate."""
from copy import deepcopy
from dataclasses import replace
import hashlib

import fitz
import pytest

import pb_pdf_text_integrity_authority as integrity
import pb_raster_text_corroboration_authority as raster
import pb_source_visibility_authority as visibility
from pb_font_glyph_mapping_corroboration_shadow import word_glyphs
from pb_portable_raster_ocr_authority import MockOCRBackend
from tests.test_source_glyph_ledger_text_trust_integration_v1 import _Reader, _results

WORDS = ("IM", "MW", "IW", "IMW", "MIM", "WIM")


def _pdf(rotation=0, duplicate=False):
    doc = fitz.open()
    page = doc.new_page(width=600, height=1200)
    page.insert_font(fontname="NimbusSans-Regular", fontbuffer=fitz.Font("helv").buffer)
    for index, text in enumerate(WORDS):
        kwargs = dict(fontname="NimbusSans-Regular", fontsize=14, render_mode=2, rotate=rotation)
        page.insert_text((200, 200 + index * 100), text, **kwargs)
        if duplicate:
            page.insert_text((200, 200 + index * 100), text, **kwargs)
    raw = doc.tobytes()
    doc.close()
    return raw


def _setup(monkeypatch, *, rotation=0, native=True, ledger=True, duplicate=False):
    monkeypatch.setattr(integrity, "_font_for_glyph_validation", lambda *args: None)
    backend = MockOCRBackend(responder=_Reader())
    monkeypatch.setattr(raster, "select_production_ocr_backend", lambda: (backend, "synthetic-overprint"))
    source = visibility.SourceVisibilityProducer(
        producer_method="source-overprint-glyph-test", producer_version="1",
        source_native_finish_text_shadow=native, source_glyph_ledger_text_trust=ledger,
    )
    raw = _pdf(rotation, duplicate)
    published = source.ingest_native_pdf_bytes(
        document_id="synthetic-overprint", source_bytes=raw, source_locator="memory://synthetic.pdf",
    )
    return source, published, raw


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_native_producer_uses_attested_overprints_without_weakening_generic_glyphs(monkeypatch, rotation):
    source, published, raw = _setup(monkeypatch, rotation=rotation)
    values = _results(source, published)
    assert {r.receipt.raw_text for r in values.values()} == set(WORDS)
    assert all(r.receipt.trusted and r.trusted_text == r.receipt.raw_text for r in values.values())
    assert any(r.receipt.decode_status == "amortized_glyph_verified" for r in values.values())
    with fitz.open(stream=raw, filetype="pdf") as doc:
        traces = integrity._texttrace_spans(doc[0])
        assert all(word_glyphs(r.receipt.parent_observation_id, r.receipt.raw_text, "same-font",
                               r.receipt.geometry, traces) is None for r in values.values())
    assert hashlib.sha256(raw).hexdigest() == published.revision.source_sha256


@pytest.mark.parametrize("native,ledger", [(False, False), (False, True), (True, False)])
def test_overprint_glyph_recovery_requires_both_existing_opt_ins(monkeypatch, native, ledger):
    source, published, _raw = _setup(monkeypatch, native=native, ledger=ledger)
    assert all(not r.receipt.trusted for r in _results(source, published).values())


def test_multiple_independent_overprints_remain_ambiguous(monkeypatch):
    source, published, _raw = _setup(monkeypatch, duplicate=True)
    values = _results(source, published)
    assert values and all(not r.receipt.trusted for r in values.values())


@pytest.mark.parametrize("mutation", ["none", "foreign_span", "missing_paint", "glyph", "font", "sequence", "program"])
def test_source_adapter_rejects_foreign_or_mismatched_trace_evidence(monkeypatch, mutation):
    source, published, raw = _setup(monkeypatch, ledger=False)
    values = _results(source, published)
    receipt = next(r.receipt for r in values.values() if r.receipt.raw_text == "IMW")
    before = deepcopy(receipt)
    with fitz.open(stream=raw, filetype="pdf") as doc:
        page = doc[0]
        spans = deepcopy(integrity._texttrace_spans(page))
        owned = [s for s in spans if s["seqno"] in receipt.trace_sequence_numbers]
        assert len(owned) == 2
        if mutation == "foreign_span":
            other = deepcopy(owned[0]); other["seqno"] = 999999; spans.append(other)
        elif mutation == "missing_paint":
            spans.remove(owned[0])
        elif mutation == "glyph":
            chars = list(owned[0]["chars"])
            changed = list(chars[0]); changed[1] += 1; chars[0] = tuple(changed)
            owned[0]["chars"] = tuple(chars)
        elif mutation == "font":
            owned[0]["font"] = "foreign-font"
        elif mutation == "sequence":
            receipt = replace(receipt, trace_sequence_numbers=(*receipt.trace_sequence_numbers, 999999))
        program = doc.extract_font(receipt.font_xref)[3]
        key = hashlib.sha256(program).hexdigest() if mutation != "program" else "f" * 64
        result = visibility._source_attested_overprint_word_glyphs(
            page=page, receipt=receipt, font_key=key, spans=spans,
        )
        assert (result is not None) is (mutation == "none")
        if result is not None:
            assert result == visibility._source_attested_overprint_word_glyphs(
                page=page, receipt=receipt, font_key=key, spans=tuple(reversed(spans)),
            )
    assert next(r.receipt for r in values.values() if r.receipt.raw_text == "IMW") == before
