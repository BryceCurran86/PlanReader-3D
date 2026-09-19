"""Tests for OCR capability detection, production backend auto-selection
(PortableRasterOCRProducer.from_environment), and event-loop-safe WinOCR
execution.

Backend availability is mocked at the ``is_available`` method level (not by
injecting real winrt/pytesseract) since these tests care about SELECTION
LOGIC, not backend internals -- those are covered separately in
test_win_ocr_backend_v1.py and test_portable_raster_ocr_authority_v1.py.
"""
from __future__ import annotations

import asyncio
import threading

import pytest
from PIL import Image

from pb_migration_contracts import EvidenceResolutionStatus
from pb_portable_raster_ocr_authority import (
    MockOCRBackend,
    NullOCRBackend,
    OCRLine,
    OCR_BACKEND_SELECTED_NONE_AVAILABLE,
    OCR_BACKEND_SELECTED_RAPIDOCR_AVAILABLE,
    OCR_BACKEND_SELECTED_TESSERACT_AVAILABLE,
    OCR_BACKEND_SELECTED_WINOCR_AVAILABLE,
    PortableRasterOCRProducer,
    PortableRasterOCRSelector,
    RapidOCRBackend,
    TesseractOCRBackend,
    WinOCRBackend,
    detect_ocr_capabilities,
)


def _patch_availability(
    monkeypatch: pytest.MonkeyPatch, *, tesseract: bool, winocr: bool, rapidocr: bool = False,
) -> None:
    monkeypatch.setattr(TesseractOCRBackend, "is_available", lambda self: tesseract)
    monkeypatch.setattr(WinOCRBackend, "is_available", lambda self: winocr)
    monkeypatch.setattr(RapidOCRBackend, "is_available", lambda self: rapidocr)


def _sample_selector() -> PortableRasterOCRSelector:
    return PortableRasterOCRSelector(
        document_id="doc1", revision_id="rev1", source_sha256="a" * 64,
        snapshot_id="snap1", page_id="page_1",
    )


# ── Capability detection ────────────────────────────────────────────────────


def test_capability_windows_winocr_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_availability(monkeypatch, tesseract=False, winocr=True)
    report = detect_ocr_capabilities()
    assert report.winocr_available is True
    assert report.tesseract_available is False
    assert report.available_backends == ("win_ocr",)
    assert report.default_backend == "win_ocr"
    assert report.has_active_ocr is True


def test_capability_windows_tesseract_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_availability(monkeypatch, tesseract=True, winocr=False)
    report = detect_ocr_capabilities()
    assert report.tesseract_available is True
    assert report.winocr_available is False
    assert report.available_backends == ("tesseract",)
    assert report.default_backend == "tesseract"


def test_capability_windows_both_available(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_availability(monkeypatch, tesseract=True, winocr=True)
    report = detect_ocr_capabilities()
    assert report.tesseract_available is True
    assert report.winocr_available is True
    # Deterministic order: tesseract preferred first.
    assert report.available_backends == ("tesseract", "win_ocr")
    assert report.default_backend == "tesseract"


def test_capability_neither_available(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_availability(monkeypatch, tesseract=False, winocr=False)
    report = detect_ocr_capabilities()
    assert report.available_backends == ()
    assert report.default_backend is None
    assert report.has_active_ocr is False


def test_capability_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    # WinOCRBackend.is_available() itself returns False off Windows (its own
    # os.name check) -- simulate that real behavior directly here rather
    # than forcing it, to prove the capability report reflects whatever the
    # backend's own probe says.
    monkeypatch.setattr(TesseractOCRBackend, "is_available", lambda self: False)
    monkeypatch.setattr(WinOCRBackend, "is_available", lambda self: False)
    monkeypatch.setattr(RapidOCRBackend, "is_available", lambda self: False)
    report = detect_ocr_capabilities()
    assert report.winocr_available is False
    assert report.available_backends == ()


def test_capability_rapidocr_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_availability(monkeypatch, tesseract=False, winocr=False, rapidocr=True)
    report = detect_ocr_capabilities()
    assert report.rapidocr_available is True
    assert report.available_backends == ("rapid_ocr",)
    assert report.default_backend == "rapid_ocr"


def test_capability_all_three_available_rapidocr_ranks_first(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_availability(monkeypatch, tesseract=True, winocr=True, rapidocr=True)
    report = detect_ocr_capabilities()
    assert report.available_backends == ("rapid_ocr", "tesseract", "win_ocr")
    assert report.default_backend == "rapid_ocr"


# ── from_environment() selection ────────────────────────────────────────────


def test_from_environment_prefers_rapidocr_over_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_availability(monkeypatch, tesseract=True, winocr=True, rapidocr=True)
    producer = PortableRasterOCRProducer.from_environment(
        page_images={"page_1": Image.new("RGB", (10, 10), "white")},
    )
    assert type(producer._backend) is RapidOCRBackend
    assert producer.backend_selection_provenance == OCR_BACKEND_SELECTED_RAPIDOCR_AVAILABLE


def test_from_environment_prefers_tesseract_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_availability(monkeypatch, tesseract=True, winocr=True)
    producer = PortableRasterOCRProducer.from_environment(
        page_images={"page_1": Image.new("RGB", (10, 10), "white")},
    )
    assert type(producer._backend) is TesseractOCRBackend
    assert producer.backend_selection_provenance == OCR_BACKEND_SELECTED_TESSERACT_AVAILABLE


def test_from_environment_windows_winocr_when_no_tesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_availability(monkeypatch, tesseract=False, winocr=True)
    producer = PortableRasterOCRProducer.from_environment(
        page_images={"page_1": Image.new("RGB", (10, 10), "white")},
    )
    assert type(producer._backend) is WinOCRBackend
    assert producer.backend_selection_provenance == OCR_BACKEND_SELECTED_WINOCR_AVAILABLE


def test_from_environment_windows_neither_available_falls_back_null(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_availability(monkeypatch, tesseract=False, winocr=False)
    producer = PortableRasterOCRProducer.from_environment(
        page_images={"page_1": Image.new("RGB", (10, 10), "white")},
    )
    assert type(producer._backend) is NullOCRBackend
    assert producer.backend_selection_provenance == OCR_BACKEND_SELECTED_NONE_AVAILABLE
    res = producer.publish(_sample_selector())
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert res.record is None


def test_from_environment_linux_no_tesseract_is_null(monkeypatch: pytest.MonkeyPatch) -> None:
    # WinOCRBackend.is_available() would be False on real Linux regardless
    # of mocking -- modeled here directly.
    _patch_availability(monkeypatch, tesseract=False, winocr=False)
    producer = PortableRasterOCRProducer.from_environment(
        page_images={"page_1": Image.new("RGB", (10, 10), "white")},
    )
    assert type(producer._backend) is NullOCRBackend


def test_explicit_backend_choice_overrides_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit from_backend(backend=WinOCRBackend()) is honored exactly as
    given, regardless of what from_environment() would have picked."""
    _patch_availability(monkeypatch, tesseract=True, winocr=True)
    producer = PortableRasterOCRProducer.from_backend(
        backend=WinOCRBackend(),
        page_images={"page_1": Image.new("RGB", (10, 10), "white")},
    )
    assert type(producer._backend) is WinOCRBackend
    # Explicit selection carries no auto-selection provenance.
    assert producer.backend_selection_provenance is None


def test_explicit_tesseract_choice_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_availability(monkeypatch, tesseract=False, winocr=True)
    producer = PortableRasterOCRProducer.from_backend(
        backend=TesseractOCRBackend(),
        page_images={"page_1": Image.new("RGB", (10, 10), "white")},
    )
    assert type(producer._backend) is TesseractOCRBackend


def test_mock_backend_still_prohibited_from_environment_path() -> None:
    """from_environment() has no parameter to inject a backend at all --
    a MockOCRBackend can never reach the production selection path."""
    import inspect

    sig = inspect.signature(PortableRasterOCRProducer.from_environment)
    assert "backend" not in sig.parameters


def test_mock_backend_still_rejected_by_from_backend() -> None:
    with pytest.raises(TypeError, match="from_backend_for_tests"):
        PortableRasterOCRProducer.from_backend(
            backend=MockOCRBackend(is_ready=True),
            page_images={"page_1": Image.new("RGB", (10, 10), "white")},
        )


def test_selection_provenance_recorded_in_publish_reason_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_availability(monkeypatch, tesseract=False, winocr=False)
    producer = PortableRasterOCRProducer.from_environment(
        page_images={"page_1": Image.new("RGB", (10, 10), "white")},
    )
    res = producer.publish(_sample_selector())
    assert OCR_BACKEND_SELECTED_NONE_AVAILABLE in res.reason_codes


# ── Event-loop safety ────────────────────────────────────────────────────────


def test_winocr_sync_context_no_running_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.test_win_ocr_backend_v1 import _install_fake_winrt

    _install_fake_winrt(monkeypatch, line_specs=(("HELLO", (0.0, 0.0, 10.0, 10.0)),))
    backend = WinOCRBackend()
    lines = backend.extract_lines(Image.new("RGB", (50, 50), "white"))
    assert [l.text for l in lines] == ["HELLO"]


def test_winocr_from_within_running_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.test_win_ocr_backend_v1 import _install_fake_winrt

    _install_fake_winrt(monkeypatch, line_specs=(("W-1", (0.0, 0.0, 10.0, 10.0)),))
    backend = WinOCRBackend()
    img = Image.new("RGB", (50, 50), "white")

    async def call_from_loop():
        # extract_lines() is a SYNC method; calling it here means a loop is
        # already running in this thread when it internally tries to run
        # the coroutine -- this must not raise "cannot be called from a
        # running event loop".
        return backend.extract_lines(img)

    lines = asyncio.run(call_from_loop())
    assert [l.text for l in lines] == ["W-1"]


def test_winocr_exceptions_propagate_from_running_loop_bridge(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.test_win_ocr_backend_v1 import _install_fake_winrt

    _install_fake_winrt(monkeypatch, recognize_error=RuntimeError("engine exploded"))
    backend = WinOCRBackend()
    img = Image.new("RGB", (50, 50), "white")

    async def call_from_loop():
        return backend.extract_lines(img)

    with pytest.raises(RuntimeError, match="engine exploded"):
        asyncio.run(call_from_loop())


def test_winocr_no_leaked_thread_after_running_loop_call(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.test_win_ocr_backend_v1 import _install_fake_winrt

    _install_fake_winrt(monkeypatch, line_specs=(("W-1", (0.0, 0.0, 10.0, 10.0)),))
    backend = WinOCRBackend()
    img = Image.new("RGB", (50, 50), "white")

    before = threading.active_count()

    async def call_from_loop():
        return backend.extract_lines(img)

    asyncio.run(call_from_loop())

    after = threading.active_count()
    assert after == before


def test_winocr_deterministic_lines_both_contexts(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.test_win_ocr_backend_v1 import _install_fake_winrt

    _install_fake_winrt(
        monkeypatch,
        line_specs=(("ALPHA", (0.0, 0.0, 10.0, 10.0)), ("BETA", (0.0, 20.0, 10.0, 10.0))),
    )
    backend = WinOCRBackend()
    img = Image.new("RGB", (50, 50), "white")

    sync_lines = backend.extract_lines(img)

    async def call_from_loop():
        return backend.extract_lines(img)

    loop_lines = asyncio.run(call_from_loop())

    assert [l.text for l in sync_lines] == [l.text for l in loop_lines] == ["ALPHA", "BETA"]
