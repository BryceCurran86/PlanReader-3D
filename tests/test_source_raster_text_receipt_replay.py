from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import fitz
import pytest

import pb_source_visibility_authority as visibility
from pb_migration_contracts import EvidenceResolutionStatus
from pb_pdf_text_integrity_authority import (
    NativeTextIntegrityDecision,
    TEXT_GLYPH_MAPPING_UNVERIFIED,
    build_pdf_text_integrity_receipt,
)
from pb_source_observation_authority import ObservationSelector


def _decisions():
    current = NativeTextIntegrityDecision(
        trusted=True, raw_text="ROOM", decode_status="validated_tounicode",
        visibility_status="proven_visible", reason_codes=(), font_xref=7,
        font_subtype="TrueType", font_name="Subset", sequence_number=1,
        trace_sequence_numbers=(1,),
    )
    original = replace(
        current, trusted=False, decode_status="tounicode_glyph_unverified",
        reason_codes=(TEXT_GLYPH_MAPPING_UNVERIFIED,),
    )
    return current, original


def _receipt(decision):
    return build_pdf_text_integrity_receipt(
        parent_observation_id="native-word", document_id="document",
        revision_id="revision", source_sha256="a" * 64, page_id="1",
        source_partition_id="page:1", geometry=(10, 10, 40, 20),
        decision=decision, block_no=0, line_no=0, word_no=0,
    )


def test_replay_reproduces_original_receipt_after_native_proof_becomes_available(monkeypatch):
    current, original = _decisions()
    available = False
    calls = []

    def classify(page, word, **kwargs):
        calls.append(dict(kwargs))
        return current if available and kwargs.get("source_symbol_font_chain_shadow") else original

    monkeypatch.setattr(visibility, "classify_native_word_integrity", classify)
    word = {"text": "ROOM", "bbox": (10, 10, 40, 20)}
    before = deepcopy(word)
    kwargs = dict(source_native_finish_text_shadow=True, source_raster_text_receipt_replay=True)
    prior = visibility._native_word_integrity_for_receipt(None, word, **kwargs)
    available = True
    replayed = visibility._native_word_integrity_for_receipt(None, word, **kwargs)
    assert _receipt(prior) == _receipt(replayed) == _receipt(original)
    assert _receipt(current).receipt_id != _receipt(original).receipt_id
    assert replayed.trusted is False
    assert word == before
    # The current native proof runs before any historical proof-stage replay.
    assert calls == [
        {"source_symbol_font_chain_shadow": True, "source_raw_no_active_text_clip_shadow": True},
        {"source_symbol_font_chain_shadow": True, "source_raw_no_active_text_clip_shadow": True},
        {"source_raw_no_active_text_clip_shadow": True},
    ]


@pytest.mark.parametrize("reason", [
    "text_glyph_unicode_mismatch", "text_clip_state_unresolved",
    "text_opacity_untrusted", "text_occluded_by_later_paint",
    "text_optional_content_unresolved", "text_trace_unavailable",
    TEXT_GLYPH_MAPPING_UNVERIFIED,
])
def test_current_native_failure_never_retries_a_different_proof(monkeypatch, reason):
    current, original = _decisions()
    blocked = replace(current, trusted=False, reason_codes=(reason,))
    calls = []

    def classify(page, word, **kwargs):
        calls.append(dict(kwargs))
        return blocked if kwargs.get("source_symbol_font_chain_shadow") else original

    monkeypatch.setattr(visibility, "classify_native_word_integrity", classify)
    selected = visibility._native_word_integrity_for_receipt(
        None, {}, source_native_finish_text_shadow=True,
        source_raster_text_receipt_replay=True,
    )
    assert selected is blocked
    assert len(calls) == 1


def test_default_profile_keeps_current_proof_and_receipt(monkeypatch):
    current, original = _decisions()
    calls = []

    def classify(page, word, **kwargs):
        calls.append(dict(kwargs))
        return current if kwargs.get("source_symbol_font_chain_shadow") else original

    monkeypatch.setattr(visibility, "classify_native_word_integrity", classify)
    selected = visibility._native_word_integrity_for_receipt(
        None, {}, source_native_finish_text_shadow=True,
        source_raster_text_receipt_replay=False,
    )
    assert selected is current
    assert len(calls) == 1


@pytest.mark.parametrize("value", [0, 1, None, "true", []])
def test_profile_requires_an_explicit_boolean(value):
    with pytest.raises(ValueError, match="explicit_bool"):
        visibility.SourceVisibilityProducer(
            producer_method="test", producer_version="1",
            source_native_finish_text_shadow=True,
            source_raster_text_receipt_replay=value,
        )
    with pytest.raises(ValueError, match="explicit_bool"):
        visibility._derive_visibility_page(
            None, native_page={"words": [], "segments": []},
            source_native_finish_text_shadow=True,
            source_raster_text_receipt_replay=value,
        )


def test_replay_requires_original_native_source_opt_in():
    with pytest.raises(ValueError, match="native_source_scope"):
        visibility.SourceVisibilityProducer(
            producer_method="test", producer_version="1",
            source_raster_text_receipt_replay=True,
        )
    with pytest.raises(ValueError, match="native_source_scope"):
        visibility._derive_visibility_page(
            None, native_page={}, source_raster_text_receipt_replay=True,
        )


def _payload(render_mode=0):
    with fitz.open() as doc:
        page = doc.new_page(width=120, height=120)
        page.insert_text((20, 50), "ROOM", render_mode=render_mode)
        return doc.tobytes()


def _ingest(payload):
    source = visibility.SourceVisibilityProducer(
        producer_method="raster-receipt-replay-test", producer_version="1",
        source_native_finish_text_shadow=True,
        source_raster_text_receipt_replay=True,
    )
    published = source.ingest_native_pdf_bytes(
        document_id="receipt-replay", source_bytes=payload,
        source_locator="memory://receipt-replay.pdf",
    )
    return source, published


def _resolved_words(source, published):
    return [source.text_integrity_authority().resolve_text(ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=oid,
    )) for oid in published.text_observation_ids]


def test_replayed_glyph_receipt_is_still_untrusted_in_published_source(monkeypatch):
    current, original = _decisions()

    def classify(page, word, **kwargs):
        return current if kwargs.get("source_symbol_font_chain_shadow") else original

    monkeypatch.setattr(visibility, "classify_native_word_integrity", classify)
    payload = _payload()
    source, published = _ingest(payload)
    resolved = _resolved_words(source, published)
    assert resolved
    assert all(r.status is EvidenceResolutionStatus.ABSTAINED for r in resolved)
    assert all(r.trusted_text is None for r in resolved)
    assert all(r.receipt.trusted is False for r in resolved)
    again = source.ingest_native_pdf_bytes(
        document_id="receipt-replay", source_bytes=payload,
        source_locator="memory://receipt-replay.pdf",
    )
    assert again is published


def test_invisible_original_text_stays_blocked_under_replay_profile():
    source, published = _ingest(_payload(render_mode=3))
    resolved = _resolved_words(source, published)
    assert resolved
    assert all(r.status is EvidenceResolutionStatus.ABSTAINED for r in resolved)
    assert all(r.trusted_text is None for r in resolved)

