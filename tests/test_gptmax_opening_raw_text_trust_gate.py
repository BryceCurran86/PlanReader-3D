"""Fail closed on missing or contradictory raw-text integrity receipts for opening labels.

Generated-PDF source-neutral tests only. They exercise both the native text
collection and the independent word authentication gate. No benchmark truth.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

import pb_opening_label_dimension_authority as labels
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_pdf_text_integrity_authority import (
    TEXT_CLIP_STATE_UNRESOLVED,
    TEXT_GLYPH_MAPPING_UNVERIFIED,
)
from tests.test_opening_label_dimension_authority import (
    _ingest, _opening_selector, _pdf, _selector,
)


def _untrusted_case(monkeypatch, *, reasons, status=Status.ABSTAINED,
                    trusted=False, token="900"):
    source, published = _ingest(
        _pdf(labels=((88.0, 124.0, "900 - 1200 asw"),)),
        "raw-text-first-gate-synthetic",
    )
    physical = source.physical_opening_authority()
    opening_selector = _opening_selector(source, published)
    existence = physical.prove_existence(opening_selector).existence_record
    assert existence is not None
    observation_id = published.text_observation_ids[0]
    real_integrity = source.text_integrity_authority()
    existing = real_integrity.resolve_text(_selector(published, observation_id))
    assert existing.receipt is not None
    receipt = replace(
        existing.receipt, trusted=trusted, reason_codes=tuple(reasons),
        raw_text=token,
    )
    resolved = SimpleNamespace(
        status=status, trusted_text=None, receipt=receipt,
    )

    class Doubt:
        def resolve_text(self, _selector):
            return resolved

    class RasterPositive:
        def publish(self, _selector):
            # Deliberately make the raster gate positive. It must NEVER
            # override a missing/unknown text-integrity failure reason.
            return SimpleNamespace(
                status=Status.CORROBORATED, corroborated_text=token,
            )

    monkeypatch.setattr(source, "text_integrity_authority", lambda: Doubt())
    source._raster_corroboration_producer = RasterPositive()
    return source, existence, observation_id, resolved


@pytest.mark.parametrize(
    ("reasons", "status", "trusted"),
    (
        ((), Status.ABSTAINED, False),
        (("unknown_reason",), Status.ABSTAINED, False),
        ((TEXT_GLYPH_MAPPING_UNVERIFIED, "unknown_reason"), Status.ABSTAINED, False),
        ((TEXT_CLIP_STATE_UNRESOLVED, "unknown_reason"), Status.ABSTAINED, False),
        ((TEXT_GLYPH_MAPPING_UNVERIFIED,), Status.CONFLICT, False),
        ((TEXT_GLYPH_MAPPING_UNVERIFIED,), Status.CORROBORATED, False),
        ((TEXT_CLIP_STATE_UNRESOLVED,), Status.ABSTAINED, True),
    ),
)
def test_untrusted_missing_or_invalid_receipts_cannot_become_dimensions(
    monkeypatch, reasons, status, trusted,
):
    source, opening, observation_id, resolved = _untrusted_case(
        monkeypatch, reasons=reasons, status=status, trusted=trusted,
    )
    assert labels._raw_text_fallback_permitted(resolved) is False
    assert labels._trusted_text_lines(source, opening) == ()
    producer = labels.OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    assert producer._authenticate_word_observation(opening, observation_id) is False


@pytest.mark.parametrize("token", ("-", "x", "900"))
def test_empty_reason_set_never_authenticates_separator_or_number(monkeypatch, token):
    source, opening, observation_id, resolved = _untrusted_case(
        monkeypatch, reasons=(), token=token,
    )
    assert not labels._raw_text_fallback_permitted(resolved)
    producer = labels.OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    assert producer._authenticate_word_observation(opening, observation_id) is False


@pytest.mark.parametrize(
    "reasons",
    (
        (TEXT_GLYPH_MAPPING_UNVERIFIED,),
        (TEXT_CLIP_STATE_UNRESOLVED,),
        (TEXT_GLYPH_MAPPING_UNVERIFIED, TEXT_CLIP_STATE_UNRESOLVED),
    ),
)
def test_explicit_approved_abstention_still_requires_corroboration(monkeypatch, reasons):
    source, opening, observation_id, resolved = _untrusted_case(
        monkeypatch, reasons=reasons,
    )
    assert labels._raw_text_fallback_permitted(resolved) is True
    producer = labels.OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    # Independently source-owned text must pass a positive raster comparison.
    assert producer._authenticate_word_observation(opening, observation_id) is True


def test_explicit_raw_reason_does_not_override_negative_raster(monkeypatch):
    source, opening, observation_id, resolved = _untrusted_case(
        monkeypatch, reasons=(TEXT_GLYPH_MAPPING_UNVERIFIED,),
    )
    assert labels._raw_text_fallback_permitted(resolved)

    class RasterNegative:
        def publish(self, _selector):
            return SimpleNamespace(
                status=Status.ABSTAINED, corroborated_text=None,
            )

    source._raster_corroboration_producer = RasterNegative()
    producer = labels.OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    assert producer._authenticate_word_observation(opening, observation_id) is False
