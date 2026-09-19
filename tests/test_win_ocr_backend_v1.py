"""Tests for the real WinOCRBackend.extract_lines implementation (Item 24/F25
follow-up: turn the portable OCR authority contract into a working Windows
backend).

All WinRT interfaces are mocked via ``sys.modules`` injection so this suite
runs identically on Linux CI (``ubuntu-latest``) and on a real Windows
machine -- it never depends on an actual ``winrt`` install or real Windows
OCR being present. ``os.name`` is patched to ``"nt"`` so the same code path
(the platform gate in ``is_available()``) is exercised regardless of the
host running the test.
"""
from __future__ import annotations

import sys
import types

import pytest
from PIL import Image

import pb_portable_raster_ocr_authority as ocr_module
from pb_portable_raster_ocr_authority import (
    EvidenceResolutionStatus,
    OCR_BACKEND_UNAVAILABLE,
    OCR_CONFIDENCE_UNAVAILABLE_FROM_BACKEND,
    PortableRasterOCRProducer,
    PortableRasterOCRSelector,
    WinOCRBackend,
)


class _FakeRect:
    def __init__(self, x: float, y: float, width: float, height: float) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class _FakeWord:
    def __init__(self, text: str, rect: _FakeRect) -> None:
        self.text = text
        self.bounding_rect = rect


class _FakeLine:
    def __init__(self, text: str, words: list[_FakeWord]) -> None:
        self.text = text
        self.words = words


class _FakeOcrResult:
    def __init__(self, lines: list[_FakeLine]) -> None:
        self.lines = lines
        self.text = " ".join(l.text for l in lines)


def _install_fake_winrt(
    monkeypatch: pytest.MonkeyPatch,
    *,
    line_specs: tuple[tuple[str, tuple[float, float, float, float]], ...] = (),
    engine_available: bool = True,
    recognize_error: BaseException | None = None,
    decode_error: BaseException | None = None,
    get_bitmap_error: BaseException | None = None,
) -> None:
    """Register fake winrt.* modules in sys.modules for the duration of a test."""
    fake_lines = [
        _FakeLine(text, [_FakeWord(text, _FakeRect(x, y, w, h))])
        for text, (x, y, w, h) in line_specs
    ]

    class FakeOcrEngine:
        @staticmethod
        def try_create_from_user_profile_languages():
            if not engine_available:
                return None
            return FakeOcrEngine()

        async def recognize_async(self, bitmap):
            if recognize_error is not None:
                raise recognize_error
            return _FakeOcrResult(fake_lines)

    class FakeBitmapPixelFormat:
        GRAY8 = 1

    class FakeSoftwareBitmap:
        @staticmethod
        def convert(bitmap, fmt):
            return bitmap

    class FakeBitmap:
        pass

    class FakeBitmapDecoder:
        @staticmethod
        async def create_async(stream):
            if decode_error is not None:
                raise decode_error
            return FakeBitmapDecoder()

        async def get_software_bitmap_async(self):
            if get_bitmap_error is not None:
                raise get_bitmap_error
            return FakeBitmap()

    class FakeStream:
        def seek(self, pos: int) -> None:
            pass

    class FakeDataWriter:
        def __init__(self, stream) -> None:
            self._buf = bytearray()

        def write_bytes(self, data: bytes) -> None:
            self._buf.extend(data)

        async def store_async(self) -> int:
            return len(self._buf)

        async def flush_async(self) -> bool:
            return True

        def detach_stream(self):
            return None

    mod_ocr = types.ModuleType("winrt.windows.media.ocr")
    mod_ocr.OcrEngine = FakeOcrEngine
    mod_imaging = types.ModuleType("winrt.windows.graphics.imaging")
    mod_imaging.BitmapDecoder = FakeBitmapDecoder
    mod_imaging.BitmapPixelFormat = FakeBitmapPixelFormat
    mod_imaging.SoftwareBitmap = FakeSoftwareBitmap
    mod_streams = types.ModuleType("winrt.windows.storage.streams")
    mod_streams.DataWriter = FakeDataWriter
    mod_streams.InMemoryRandomAccessStream = FakeStream

    for name, mod in (
        ("winrt", None),
        ("winrt.windows", None),
        ("winrt.windows.media", None),
        ("winrt.windows.media.ocr", mod_ocr),
        ("winrt.windows.graphics", None),
        ("winrt.windows.graphics.imaging", mod_imaging),
        ("winrt.windows.storage", None),
        ("winrt.windows.storage.streams", mod_streams),
    ):
        monkeypatch.setitem(sys.modules, name, mod if mod is not None else types.ModuleType(name))

    monkeypatch.setattr(ocr_module.os, "name", "nt")


def _sample_img() -> Image.Image:
    return Image.new("RGB", (200, 100), "white")


# ── 1. Windows backend unavailable ──────────────────────────────────────────


def test_windows_backend_unavailable_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr_module.os, "name", "posix")
    backend = WinOCRBackend()
    assert backend.is_available() is False
    with pytest.raises(RuntimeError, match="not available"):
        backend.extract_lines(_sample_img())


def test_windows_backend_unavailable_no_winrt_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr_module.os, "name", "nt")
    # A None entry in sys.modules forces the import machinery to raise
    # ImportError -- the standard way to simulate "package not installed"
    # even on a machine (like this real dev box) where winrt genuinely IS
    # installed; simply deleting the cache entry would let Python re-import
    # the real package from disk.
    monkeypatch.setitem(sys.modules, "winrt.windows.media.ocr", None)
    backend = WinOCRBackend()
    assert backend.is_available() is False


# ── 2. Windows backend available ────────────────────────────────────────────


def test_windows_backend_available_with_fake_winrt(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_winrt(monkeypatch)
    backend = WinOCRBackend()
    assert backend.is_available() is True


# ── 3. OCR engine creation failure ──────────────────────────────────────────


def test_ocr_engine_creation_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_winrt(monkeypatch, engine_available=False)
    backend = WinOCRBackend()
    with pytest.raises(RuntimeError, match="no Windows OCR language"):
        backend.extract_lines(_sample_img())


# ── 4. Image conversion failure ─────────────────────────────────────────────


def test_image_decode_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_winrt(monkeypatch, decode_error=RuntimeError("bad image data"))
    backend = WinOCRBackend()
    with pytest.raises(RuntimeError, match="bad image data"):
        backend.extract_lines(_sample_img())


def test_bitmap_conversion_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_winrt(monkeypatch, get_bitmap_error=RuntimeError("bitmap decode failed"))
    backend = WinOCRBackend()
    with pytest.raises(RuntimeError, match="bitmap decode failed"):
        backend.extract_lines(_sample_img())


# ── 5. Empty image / no recognized text ─────────────────────────────────────


def test_empty_image_returns_no_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_winrt(monkeypatch, line_specs=())
    backend = WinOCRBackend()
    lines = backend.extract_lines(_sample_img())
    assert lines == ()


# ── 6. Multiple OCR lines ────────────────────────────────────────────────────


def test_multiple_ocr_lines_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_winrt(
        monkeypatch,
        line_specs=(
            ("SCHEDULE", (10.0, 10.0, 80.0, 15.0)),
            ("GENERAL LABORATORY", (10.0, 40.0, 150.0, 15.0)),
            ("18.1", (10.0, 70.0, 20.0, 15.0)),
        ),
    )
    backend = WinOCRBackend()
    lines = backend.extract_lines(_sample_img(), dpi=150)
    assert [l.text for l in lines] == ["SCHEDULE", "GENERAL LABORATORY", "18.1"]


# ── 7/8. bbox and DPI transformation ────────────────────────────────────────


@pytest.mark.parametrize("dpi,expected_scale", [(72, 1.0), (150, 72.0 / 150.0), (300, 72.0 / 300.0)])
def test_dpi_transformation_scales_bbox_pt(monkeypatch: pytest.MonkeyPatch, dpi: int, expected_scale: float) -> None:
    _install_fake_winrt(monkeypatch, line_specs=(("W-1", (100.0, 200.0, 40.0, 20.0)),))
    backend = WinOCRBackend()
    lines = backend.extract_lines(_sample_img(), dpi=dpi)
    assert len(lines) == 1
    line = lines[0]
    assert line.bbox_px == (100.0, 200.0, 140.0, 220.0)
    assert line.bbox_pt == pytest.approx(
        (100.0 * expected_scale, 200.0 * expected_scale, 140.0 * expected_scale, 220.0 * expected_scale)
    )


# ── 9. Cropped target region (end to end through the producer) ─────────────


def test_cropped_target_region_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_winrt(monkeypatch, line_specs=(("W-1", (5.0, 5.0, 30.0, 10.0)),))
    backend = WinOCRBackend()
    img = Image.new("RGB", (800, 800), "white")
    producer = PortableRasterOCRProducer.from_backend(
        backend=backend,
        page_images={"page_1": img},
        default_dpi=144,
    )
    sel = PortableRasterOCRSelector(
        document_id="doc1", revision_id="rev1", source_sha256="a" * 64,
        snapshot_id="snap1", page_id="page_1", target_region_pt=(50.0, 50.0, 200.0, 200.0),
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert res.record is not None
    line = res.record.lines[0]
    # crop offset (50pt, 50pt) at 144dpi must be added back onto the
    # backend's own (crop-relative) bbox_pt.
    scale = 72.0 / 144.0
    assert line.bbox_pt[0] == pytest.approx(50.0 + 5.0 * scale)
    assert line.bbox_pt[1] == pytest.approx(50.0 + 5.0 * scale)


# ── 10. No matching OCR language installed (fail closed, no silent fallback) ─


def test_no_matching_language_fails_closed_not_silently(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_winrt(monkeypatch, engine_available=False)
    backend = WinOCRBackend()
    img = Image.new("RGB", (100, 100), "white")
    producer = PortableRasterOCRProducer.from_backend(
        backend=backend, page_images={"page_1": img},
    )
    sel = PortableRasterOCRSelector(
        document_id="doc1", revision_id="rev1", source_sha256="a" * 64,
        snapshot_id="snap1", page_id="page_1",
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert any("no Windows OCR language" in r for r in res.reason_codes)
    assert res.record is None


# ── 11. Deterministic result ordering ───────────────────────────────────────


def test_result_ordering_is_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_winrt(
        monkeypatch,
        line_specs=(
            ("ZEBRA", (0.0, 0.0, 10.0, 10.0)),
            ("APPLE", (0.0, 20.0, 10.0, 10.0)),
            ("MANGO", (0.0, 40.0, 10.0, 10.0)),
        ),
    )
    backend = WinOCRBackend()
    lines = backend.extract_lines(_sample_img())
    # Must preserve the engine's own return order -- never alphabetized or
    # otherwise silently reordered.
    assert [l.text for l in lines] == ["ZEBRA", "APPLE", "MANGO"]


# ── 12. Backend provenance ───────────────────────────────────────────────────


def test_backend_provenance_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_winrt(monkeypatch, line_specs=(("W-1", (0.0, 0.0, 10.0, 10.0)),))
    backend = WinOCRBackend()
    img = Image.new("RGB", (100, 100), "white")
    producer = PortableRasterOCRProducer.from_backend(backend=backend, page_images={"page_1": img})
    sel = PortableRasterOCRSelector(
        document_id="doc1", revision_id="rev1", source_sha256="a" * 64,
        snapshot_id="snap1", page_id="page_1",
    )
    res = producer.publish(sel)
    assert res.record is not None
    assert res.record.backend_name == "win_ocr"
    assert res.record.backend_version == "windows_media_ocr_1.0"


# ── 13. No silent CORROBORATED publication ──────────────────────────────────


def test_winocr_never_publishes_corroborated(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_winrt(monkeypatch, line_specs=(("W-1", (0.0, 0.0, 10.0, 10.0)),))
    backend = WinOCRBackend()
    img = Image.new("RGB", (100, 100), "white")
    producer = PortableRasterOCRProducer.from_backend(backend=backend, page_images={"page_1": img})
    sel = PortableRasterOCRSelector(
        document_id="doc1", revision_id="rev1", source_sha256="a" * 64,
        snapshot_id="snap1", page_id="page_1",
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert res.status is not EvidenceResolutionStatus.CORROBORATED


# ── Confidence must never be fabricated ─────────────────────────────────────


def test_winocr_lines_carry_no_fabricated_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_winrt(monkeypatch, line_specs=(("W-1", (0.0, 0.0, 10.0, 10.0)),))
    backend = WinOCRBackend()
    lines = backend.extract_lines(_sample_img())
    assert lines[0].confidence is None


def test_record_confidence_unavailable_reason_code_when_no_backend_score(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_winrt(monkeypatch, line_specs=(("W-1", (0.0, 0.0, 10.0, 10.0)),))
    backend = WinOCRBackend()
    img = Image.new("RGB", (100, 100), "white")
    producer = PortableRasterOCRProducer.from_backend(backend=backend, page_images={"page_1": img})
    sel = PortableRasterOCRSelector(
        document_id="doc1", revision_id="rev1", source_sha256="a" * 64,
        snapshot_id="snap1", page_id="page_1",
    )
    res = producer.publish(sel)
    assert res.record is not None
    assert res.record.confidence is None
    assert OCR_CONFIDENCE_UNAVAILABLE_FROM_BACKEND in res.reason_codes


def test_backend_unavailable_still_fails_closed_through_producer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr_module.os, "name", "posix")
    backend = WinOCRBackend()
    img = Image.new("RGB", (100, 100), "white")
    producer = PortableRasterOCRProducer.from_backend(backend=backend, page_images={"page_1": img})
    sel = PortableRasterOCRSelector(
        document_id="doc1", revision_id="rev1", source_sha256="a" * 64,
        snapshot_id="snap1", page_id="page_1",
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert OCR_BACKEND_UNAVAILABLE in res.reason_codes
    assert res.record is None
