"""Material readings preserve their actual text; native Unicode stays strict."""
from copy import deepcopy
from dataclasses import replace

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


def _glyph_case(monkeypatch, texts=None):
    import pb_pdf_text_integrity_authority as integrity
    from pb_source_visibility_authority import SourceVisibilityProducer
    from tests.test_source_glyph_ledger_text_trust_integration_v1 import _pdf, _layout, _Reader
    monkeypatch.setattr(integrity, '_font_for_glyph_validation', lambda *args: None)
    source = SourceVisibilityProducer(producer_method='material-glyph-test', producer_version='1',
                                     source_native_finish_text_shadow=True)
    layout = _layout() if texts is None else [(t, 30.0 + 70.0 * i, 60.0) for i, t in enumerate(texts)]
    published = source.ingest_native_pdf_bytes(document_id='material-glyph',
                                               source_bytes=_pdf([layout]),
                                               source_locator='memory://material-glyph.pdf')
    backend = MockOCRBackend(responder=_Reader())
    monkeypatch.setattr(raster, 'select_production_ocr_backend', lambda: (backend, 'test-only'))
    producer = material._ordinary_source_word_raster(
        source, native_word_recognition_shadow=True, material_quote_comparison_shadow=True,
    )
    words = material._trusted_words_by_page(source, published)['1']
    assert all(not w.trusted for w in words)
    return source, published, producer, words


def _selector(published, word):
    return raster.RasterTextCorroborationSelector(
        document_id=published.revision.document_id, revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
        observation_id=word.observation_id,
    )


@pytest.mark.parametrize('voters,expected', [(('IM',), False), (('IM', 'MW'), False),
                                          (('IM', 'MW', 'IW'), True)])
def test_cached_material_glyph_reuse_requires_two_votes_per_glyph(monkeypatch, voters, expected):
    source, published, producer, words = _glyph_case(monkeypatch)
    for word in words:
        if word.text in voters:
            assert producer.publish(_selector(published, word)).record is not None
    before = deepcopy(words)
    result = material._reuse_cached_material_word_proofs(
        source=source, published=published, raster=producer, words=words,
    )
    assert next(w for w in result if w.text == 'IMW').trusted is expected
    assert words == before
    # This is material-scope recovery, never an in-place native receipt upgrade.
    assert all(not w.trusted for w in material._trusted_words_by_page(source, published)['1'])
    replay = material._reuse_cached_material_word_proofs(
        source=source, published=published, raster=producer, words=tuple(reversed(words)),
    )
    assert {w.observation_id: w for w in result} == {w.observation_id: w for w in replay}


def test_foreign_or_competing_cached_reading_cannot_vote_for_glyphs(monkeypatch):
    source, published, producer, words = _glyph_case(monkeypatch)
    for word in words:
        if word.text in ('IM', 'MW', 'IW'):
            selector = _selector(published, word)
            result = producer.publish(selector)
            if word.text == 'IW':
                producer._results[selector.key] = replace(
                    result, record=replace(result.record, source_sha256='f' * 64),
                )
    result = material._reuse_cached_material_word_proofs(
        source=source, published=published, raster=producer, words=words,
    )
    assert not next(w for w in result if w.text == 'IMW').trusted


def test_material_quote_variant_cannot_vote_for_any_native_glyph(monkeypatch):
    from pb_portable_raster_ocr_authority import OCRLine
    source, published, producer, words = _glyph_case(monkeypatch, ('“IM', 'MW', 'IW', 'IMW'))
    for word in words:
        if word.text == 'IMW':
            continue
        reading = word.text.replace('“', '"')
        producer._backend = MockOCRBackend(responder=lambda image, dpi, text=reading: (
            OCRLine(text=text, confidence=None, bbox_px=(1, 1, image.width - 1, image.height - 1)),
        ))
        assert producer.publish(_selector(published, word)).record is not None
    result = material._reuse_cached_material_word_proofs(
        source=source, published=published, raster=producer, words=words,
    )
    assert next(w for w in result if w.text == '"IM').trusted
    # If the quoted word cast native votes, I and M would each have two.
    assert not next(w for w in result if w.text == 'IMW').trusted


def test_contradicted_glyph_vetoes_even_a_direct_material_reading(monkeypatch):
    import pb_font_glyph_mapping_corroboration_shadow as glyphs
    source, published, producer, words = _glyph_case(monkeypatch)
    for word in words:
        if word.text in ('IM', 'MW', 'IW'):
            assert producer.publish(_selector(published, word)).record is not None
    real_word_glyphs = glyphs.word_glyphs
    def competing_trace(*args, **kwargs):
        value = real_word_glyphs(*args, **kwargs)
        if value is not None and value.text == 'IW':
            # A competing Unicode claim for the same source font/glyph.
            reference = next(w for w in words if w.text == 'IM')
            other = real_word_glyphs(reference.observation_id, reference.text,
                                     value.font_key, reference.bbox, args[-1])
            return replace(value, glyphs=(value.glyphs[0], (other.glyphs[1][0], 'W')))
        return value
    monkeypatch.setattr(glyphs, 'word_glyphs', competing_trace)
    result = material._reuse_cached_material_word_proofs(
        source=source, published=published, raster=producer, words=words,
    )
    assert not next(w for w in result if w.text == 'IM').trusted
    assert 'glyph_contradicted' in next(w for w in result if w.text == 'IM').reason_codes
    assert not next(w for w in result if w.text == 'IMW').trusted


def test_material_proof_never_crosses_embedded_font_programs(monkeypatch):
    import pb_font_glyph_mapping_corroboration_shadow as glyphs
    source, published, producer, words = _glyph_case(monkeypatch)
    for word in words:
        if word.text in ('IM', 'MW', 'IW'):
            assert producer.publish(_selector(published, word)).record is not None
    real_word_glyphs = glyphs.word_glyphs
    def another_font(*args, **kwargs):
        value = real_word_glyphs(*args, **kwargs)
        return replace(value, font_key='other-embedded-font') if value and value.text == 'IMW' else value
    monkeypatch.setattr(glyphs, 'word_glyphs', another_font)
    result = material._reuse_cached_material_word_proofs(
        source=source, published=published, raster=producer, words=words,
    )
    assert not next(w for w in result if w.text == 'IMW').trusted


def test_duplicate_word_universe_and_changed_original_bytes_fail_closed(monkeypatch):
    source, published, producer, words = _glyph_case(monkeypatch)
    for values in (words + words[:1],):
        with pytest.raises(RuntimeError, match=material.SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE):
            material._reuse_cached_material_word_proofs(
                source=source, published=published, raster=producer, words=values,
            )
    source._producer._store.source_bytes_by_revision[published.revision.revision_id] = b'changed'
    with pytest.raises(RuntimeError, match=material.SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE):
        material._reuse_cached_material_word_proofs(
            source=source, published=published, raster=producer, words=words,
        )

