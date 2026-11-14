"""Dispatch/source-proof regressions for the explicitly opt-in word-crop path."""
from __future__ import annotations

import pytest

import pb_raster_text_corroboration_authority as raster
from pb_migration_contracts import EvidenceResolutionStatus
from pb_portable_raster_ocr_authority import RapidOCRBackend, OCRLine
from tests.test_raster_text_corroboration_authority_v1 import (
    _Setup, _both, _glyph_unverified_pdf,
)


def _case(monkeypatch, *, shadow=True, readings=None, fail=False, invalid_geometry=False):
    setup = _Setup(_glyph_unverified_pdf([("FT3", 40, 120)]), _both("FT3"))
    backend = RapidOCRBackend()
    calls = []
    monkeypatch.setattr(RapidOCRBackend, "is_available", lambda self: True)

    def extract(self, image, dpi=150, *, detect=True):
        calls.append({"dpi": dpi, "detect": detect, "size": image.size})
        if fail:
            raise RuntimeError("backend-unavailable")
        texts = ("FT3",) if readings is None else tuple(readings.get(dpi, ()))
        bbox = (0, 0, image.width + 100, image.height + 100) if invalid_geometry else (
            2, 2, image.width - 2, image.height - 2,
        )
        return tuple(OCRLine(text=text, confidence=0.99, bbox_px=bbox) for text in texts)

    monkeypatch.setattr(RapidOCRBackend, "extract_lines", extract)
    monkeypatch.setattr(raster, "select_production_ocr_backend", lambda: (backend, "synthetic-dispatch-test"))
    factory = (raster.RasterTextCorroborationProducer.for_physical_plan_view_shadow
               if shadow else raster.RasterTextCorroborationProducer.from_source_visibility_producer)
    producer = factory(setup.svp)
    selector = setup.selector(setup.oid_of("FT3"))
    return setup, producer, selector, calls


def test_physical_plan_crop_uses_recognition_only_at_both_independent_dpis(monkeypatch):
    _setup, producer, selector, calls = _case(monkeypatch)
    result = producer.publish(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.corroborated_text == "FT3"
    assert [(call["dpi"], call["detect"]) for call in calls] == [(300, False), (450, False)]
    assert calls[0]["size"] != calls[1]["size"]
    assert "native-word-recognition-shadow:detect=False" in result.record.backend_version


def test_ordinary_production_word_path_preserves_detector_and_receipt(monkeypatch):
    _setup, producer, selector, calls = _case(monkeypatch, shadow=False)
    result = producer.publish(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert [(call["dpi"], call["detect"]) for call in calls] == [(300, True), (450, True)]
    assert "native-word-recognition-shadow" not in result.record.backend_version


@pytest.mark.parametrize("readings,reason", [
    ({300: (), 450: ()}, raster.RASTER_TEXT_NO_READING),
    ({300: ("FT3",), 450: ("FT2",)}, raster.RASTER_TEXT_VIEW_DISAGREEMENT),
    ({300: ("EPX",), 450: ("EPX",)}, raster.RASTER_TEXT_NATIVE_MISMATCH),
    ({300: ("FT3", "EPX"), 450: ("FT3", "EPX")}, raster.RASTER_TEXT_COMPETING_READINGS),
])
def test_word_mode_keeps_missing_conflicting_foreign_and_competing_reading_vetoes(monkeypatch, readings, reason):
    _setup, producer, selector, calls = _case(monkeypatch, readings=readings)
    result = producer.publish(selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert reason in result.reason_codes
    assert all(call["detect"] is False for call in calls)
    assert result.record is None


def test_failed_recognition_is_not_retried_with_detector_or_native_guess(monkeypatch):
    _setup, producer, selector, calls = _case(monkeypatch, fail=True)
    first = producer.publish(selector)
    second = producer.publish(selector)
    assert first == second
    assert first.status is EvidenceResolutionStatus.ABSTAINED
    assert raster.RASTER_TEXT_BACKEND_ERROR in first.reason_codes
    assert [(call["dpi"], call["detect"]) for call in calls] == [(300, False)]


def test_recognition_only_cannot_bypass_ocr_geometry_gate(monkeypatch):
    _setup, producer, selector, calls = _case(monkeypatch, invalid_geometry=True)
    result = producer.publish(selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert raster.RASTER_TEXT_OCR_GEOMETRY_INVALID in result.reason_codes
    assert len(calls) == 1 and calls[0]["detect"] is False


def test_source_tamper_still_blocks_before_any_recognition(monkeypatch):
    setup, producer, selector, calls = _case(monkeypatch)
    setup.svp._producer._store.source_bytes_by_revision[selector.revision_id] = b"not-the-source"
    result = producer.publish(selector)
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert calls == []
