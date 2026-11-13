"""Material readings preserve their actual text; native Unicode stays strict."""
from copy import deepcopy

import pytest

import pb_raster_text_corroboration_authority as raster
import pb_source_material_semantic_authority as material
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_raster_text_corroboration_authority_v1 import (
    _Setup, _glyph_unverified_pdf, _reads,
)
from pb_portable_raster_ocr_authority import MockOCRBackend


def _case(monkeypatch, native, by_dpi):
    raw = native.translate(str.maketrans({'“': '[', '”': ']', '‘': '{', '’': '}'}))
    setup = _Setup(_glyph_unverified_pdf(
        [(raw, 40, 120)],
        code_to_unicode={ord('['): ord('“'), ord(']'): ord('”'),
                         ord('{'): ord('‘'), ord('}'): ord('’')},
    ), MockOCRBackend(responder=_reads(by_dpi)))
    monkeypatch.setattr(raster, 'select_production_ocr_backend',
                        lambda: (setup.backend, 'synthetic-material-test'))
    setup.svp._source_native_finish_text_shadow = True
    producer = material.SourceMaterialSemanticProducer.for_physical_plan_view_shadow(
        setup.svp, page_ids=('1',),
    )
    return setup, producer._raster, setup.selector(setup.oid_of(native))


@pytest.mark.parametrize('native,reading', [
    ('“MARBLE', '"MARBLE'), ('GREY”', 'GREY"'),
    ('“CERAMIC”', '"CERAMIC"'), ('‘STONE', "'STONE"),
    ('WHITE’.', "WHITE'."),
])
def test_opted_in_material_reading_retains_actual_quotes_and_native_claim(monkeypatch, native, reading):
    setup, producer, selector = _case(monkeypatch, native, {300: reading, 450: reading})
    before = deepcopy(setup._receipts)
    result = producer.publish(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.corroborated_text == result.record.corroborated_text == reading
    assert tuple(v.ocr_reading for v in result.record.views) == (reading, reading)
    proof = producer.material_quote_comparison_proof(selector)
    assert proof['native_claim'] == native and proof['raster_reading'] == reading
    assert proof['policy_id'] in result.record.backend_version
    assert setup._receipts == before
    assert not setup.text_authority.resolve_text(setup._observation_selector(selector.observation_id)).receipt.trusted
    assert setup.producer.publish(selector).status is EvidenceResolutionStatus.ABSTAINED


@pytest.mark.parametrize('native,reading', [
    ('“MARBLE', 'MARBLE'), ('GREY”', 'GREY'),
    ('“MARBLE', '"MABLE'), ('“MARBLE', '"marble'),
    ('“2100”', '"2100"'), ('“FT3”', '"FT3"'),
    ('“A1”', '"A1"'), ('“ALPHA-BETA”', '"ALPHA-BETA"'),
    ('“NO”', '"YES"'), ('“NAME”', "'NAME'"),
])
def test_material_quote_policy_never_removes_quotes_or_corrects_content(monkeypatch, native, reading):
    _setup, producer, selector = _case(monkeypatch, native, {300: reading, 450: reading})
    result = producer.publish(selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert raster.RASTER_TEXT_NATIVE_MISMATCH in result.reason_codes
    assert result.record is None and producer.material_quote_comparison_proof(selector) is None


def test_literal_two_view_agreement_is_required_before_material_comparison(monkeypatch):
    _setup, producer, selector = _case(monkeypatch, '“MARBLE', {300: '"MARBLE', 450: '“MARBLE'})
    result = producer.publish(selector)
    assert raster.RASTER_TEXT_VIEW_DISAGREEMENT in result.reason_codes
    assert result.record is None


def test_material_reading_cache_revalidates_source_and_keeps_modes_separate(monkeypatch):
    setup, producer, selector = _case(monkeypatch, '“MARBLE', {300: '"MARBLE', 450: '"MARBLE'})
    ordinary = material._ordinary_source_word_raster(setup.svp)
    native = material._ordinary_source_word_raster(setup.svp, native_word_recognition_shadow=True)
    assert len({id(ordinary), id(native), id(producer)}) == 3
    assert producer.publish(selector).record is not None
    setup.svp._producer._store.source_bytes_by_revision[selector.revision_id] = b'foreign'
    assert producer.material_quote_comparison_proof(selector) is None


@pytest.mark.parametrize('native_flag,ledger_flag', [(False, False), (True, False),
                                                    (False, True), (True, True)])
def test_source_receipt_issuer_uses_strict_word_mode_only_with_both_opt_ins(monkeypatch, native_flag, ledger_flag):
    import pb_pdf_text_integrity_authority as integrity
    from pb_source_visibility_authority import SourceVisibilityProducer
    from tests.test_source_glyph_ledger_text_trust_integration_v1 import (
        _pdf, _layout, _Reader, _results,
    )
    monkeypatch.setattr(integrity, '_font_for_glyph_validation', lambda *args: None)
    backend = MockOCRBackend(responder=_Reader())
    monkeypatch.setattr(raster, 'select_production_ocr_backend', lambda: (backend, 'test-only'))
    source = SourceVisibilityProducer(
        producer_method='material-source-receipt-integration', producer_version='1',
        source_native_finish_text_shadow=native_flag,
        source_glyph_ledger_text_trust=ledger_flag,
    )
    published = source.ingest_native_pdf_bytes(
        document_id='material-source-receipt', source_bytes=_pdf([_layout()]),
        source_locator='memory://material-source-receipt.pdf',
    )
    receipts = _results(source, published)
    if not ledger_flag:
        assert source._glyph_ledger_raster_producer is None
        assert all(not r.receipt.trusted for r in receipts.values())
    else:
        proof = source._glyph_ledger_raster_producer
        assert proof._recognize_native_words_shadow is native_flag
        assert proof._material_quote_comparison_shadow is False
        assert proof._allow_clip_only_shadow is False
        assert all(r.receipt.trusted for r in receipts.values())
        assert all(r.receipt.raw_text == r.trusted_text for r in receipts.values())
        source._source_native_finish_text_shadow = not native_flag
        with pytest.raises(ValueError, match='proof_policy_already_fixed'):
            source.upgrade_glyph_only_text(published.revision.revision_id)
        assert _results(source, published) == receipts
