"""Tesseract availability probe memoization must not invent OCR evidence."""
from __future__ import annotations

import pytest
import pytesseract
from pb_portable_raster_ocr_authority import TesseractOCRBackend


def test_successful_binary_probe_reused_until_executable_changes(monkeypatch, tmp_path):
    binary = tmp_path / "tesseract"
    binary.write_text("v1")
    backend = TesseractOCRBackend(tesseract_cmd=str(binary))
    calls = []
    def probe(*args, **kwargs):
        calls.append(1)
        return {"text": []}
    monkeypatch.setattr(pytesseract, "image_to_data", probe)
    assert backend.is_available() is True
    assert backend.is_available() is True
    assert backend.is_available() is True
    assert len(calls) == 1
    binary.write_text("v2 and different")
    assert backend.is_available() is True
    assert len(calls) == 2
    binary.unlink()
    assert backend.is_available() is False


def test_failed_probe_never_cached_and_original_backend_can_recover(monkeypatch, tmp_path):
    binary = tmp_path / "tesseract"
    binary.write_text("v1")
    backend = TesseractOCRBackend(tesseract_cmd=str(binary))
    calls = []
    def probe(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("engine unavailable")
        return {"text": []}
    monkeypatch.setattr(pytesseract, "image_to_data", probe)
    assert backend.is_available() is False
    assert backend.is_available() is True
    assert backend.is_available() is True
    assert len(calls) == 2


def test_real_engine_availability_signature_stable_when_present():
    backend = TesseractOCRBackend()
    if not backend.is_available():
        pytest.skip("Tesseract not installed")
    signature = backend._healthy_executable_signature
    assert signature is not None
    assert backend.is_available()
    assert backend._healthy_executable_signature == signature
