"""Tests for RapidOCRBackend -- the cross-platform (Windows/Linux/macOS)
backend added after empirical evaluation showed it recognizes short
hyphenated architectural marks ("W-1", "D-2", etc.) that WinOCR does not.

The real ``rapidocr``/``onnxruntime`` packages are mocked via ``sys.modules``
injection so this suite never needs the real ~30MB ONNX models or network
access, and runs identically everywhere. ``RapidOCRBackend._engine_cache``
is reset before/after every test so one test's mock engine can never leak
into another.
"""
from __future__ import annotations

import sys
import types

import pytest
from PIL import Image

from pb_portable_raster_ocr_authority import (
    EvidenceResolutionStatus,
    PortableRasterOCRProducer,
    PortableRasterOCRSelector,
    RapidOCRBackend,
)


@pytest.fixture(autouse=True)
def _reset_engine_cache():
    RapidOCRBackend._reset_engine_cache_for_tests()
    yield
    RapidOCRBackend._reset_engine_cache_for_tests()


class _FakeResult:
    def __init__(self, txts, boxes, scores):
        self.txts = txts
        self.boxes = boxes
        self.scores = scores


def _install_fake_rapidocr(
    monkeypatch: pytest.MonkeyPatch,
    *,
    detections: tuple[tuple[str, tuple[float, float, float, float], float], ...] = (),
    construction_error: BaseException | None = None,
    call_error: BaseException | None = None,
    import_error: bool = False,
) -> None:
    if import_error:
        monkeypatch.setitem(sys.modules, "rapidocr", None)
        monkeypatch.setitem(sys.modules, "onnxruntime", None)
        return

    txts = [d[0] for d in detections]
    boxes = [
        [[d[1][0], d[1][1]], [d[1][2], d[1][1]], [d[1][2], d[1][3]], [d[1][0], d[1][3]]]
        for d in detections
    ]
    scores = [d[2] for d in detections]

    class FakeRapidOCR:
        def __init__(self):
            if construction_error is not None:
                raise construction_error

        def __call__(self, array):
            if call_error is not None:
                raise call_error
            if not txts:
                return None
            return _FakeResult(txts, boxes, scores)

    mod_rapidocr = types.ModuleType("rapidocr")
    mod_rapidocr.RapidOCR = FakeRapidOCR
    mod_rapidocr.__version__ = "test-1.0.0"
    mod_onnxruntime = types.ModuleType("onnxruntime")

    monkeypatch.setitem(sys.modules, "rapidocr", mod_rapidocr)
    monkeypatch.setitem(sys.modules, "onnxruntime", mod_onnxruntime)


def _sample_selector() -> PortableRasterOCRSelector:
    return PortableRasterOCRSelector(
        document_id="doc1", revision_id="rev1", source_sha256="a" * 64,
        snapshot_id="snap1", page_id="page_1",
    )


def test_unavailable_when_package_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_rapidocr(monkeypatch, import_error=True)
    backend = RapidOCRBackend()
    assert backend.is_available() is False
    with pytest.raises(RuntimeError, match="not available"):
        backend.extract_lines(Image.new("RGB", (50, 50), "white"))


def test_available_when_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_rapidocr(monkeypatch)
    backend = RapidOCRBackend()
    assert backend.is_available() is True


def test_is_available_does_not_construct_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """is_available() must be cheap -- it never pays the real ~30MB model
    construction cost just to answer a yes/no question."""
    construction_calls = {"count": 0}

    class TrackingRapidOCR:
        def __init__(self):
            construction_calls["count"] += 1

        def __call__(self, array):
            return None

    mod = types.ModuleType("rapidocr")
    mod.RapidOCR = TrackingRapidOCR
    monkeypatch.setitem(sys.modules, "rapidocr", mod)
    monkeypatch.setitem(sys.modules, "onnxruntime", types.ModuleType("onnxruntime"))

    backend = RapidOCRBackend()
    assert backend.is_available() is True
    assert construction_calls["count"] == 0


def test_recognizes_short_architectural_marks(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_rapidocr(
        monkeypatch,
        detections=(("W-1", (10.0, 10.0, 40.0, 30.0), 0.998), ("D-2", (10.0, 50.0, 40.0, 70.0), 0.995)),
    )
    backend = RapidOCRBackend()
    lines = backend.extract_lines(Image.new("RGB", (100, 100), "white"), dpi=300)
    assert [l.text for l in lines] == ["W-1", "D-2"]
    assert lines[0].confidence == pytest.approx(0.998)


def test_real_confidence_not_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unlike WinOCR, RapidOCR genuinely provides a per-detection score --
    it must be used as-is, not discarded."""
    _install_fake_rapidocr(monkeypatch, detections=(("W-1", (0.0, 0.0, 10.0, 10.0), 0.87),))
    backend = RapidOCRBackend()
    lines = backend.extract_lines(Image.new("RGB", (50, 50), "white"))
    assert lines[0].confidence == pytest.approx(0.87)


def test_bbox_dpi_transformation(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_rapidocr(monkeypatch, detections=(("W-1", (100.0, 200.0, 140.0, 220.0), 0.9),))
    backend = RapidOCRBackend()
    lines = backend.extract_lines(Image.new("RGB", (300, 300), "white"), dpi=150)
    scale = 72.0 / 150.0
    assert lines[0].bbox_px == (100.0, 200.0, 140.0, 220.0)
    assert lines[0].bbox_pt == pytest.approx(
        (100.0 * scale, 200.0 * scale, 140.0 * scale, 220.0 * scale)
    )


def test_empty_detection_result(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_rapidocr(monkeypatch, detections=())
    backend = RapidOCRBackend()
    lines = backend.extract_lines(Image.new("RGB", (50, 50), "white"))
    assert lines == ()


def test_engine_construction_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_rapidocr(monkeypatch, construction_error=RuntimeError("model files corrupt"))
    backend = RapidOCRBackend()
    with pytest.raises(RuntimeError, match="model files corrupt"):
        backend.extract_lines(Image.new("RGB", (50, 50), "white"))


def test_inference_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_rapidocr(monkeypatch, call_error=RuntimeError("inference crashed"))
    backend = RapidOCRBackend()
    with pytest.raises(RuntimeError, match="inference crashed"):
        backend.extract_lines(Image.new("RGB", (50, 50), "white"))


def test_engine_cached_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    construction_calls = {"count": 0}

    class TrackingRapidOCR:
        def __init__(self):
            construction_calls["count"] += 1

        def __call__(self, array):
            return _FakeResult(["W-1"], [[[0, 0], [10, 0], [10, 10], [0, 10]]], [0.9])

    mod = types.ModuleType("rapidocr")
    mod.RapidOCR = TrackingRapidOCR
    monkeypatch.setitem(sys.modules, "rapidocr", mod)
    monkeypatch.setitem(sys.modules, "onnxruntime", types.ModuleType("onnxruntime"))

    backend = RapidOCRBackend()
    img = Image.new("RGB", (50, 50), "white")
    backend.extract_lines(img)
    backend.extract_lines(img)
    backend.extract_lines(img)
    assert construction_calls["count"] == 1


def test_never_publishes_corroborated(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_rapidocr(monkeypatch, detections=(("W-1", (0.0, 0.0, 10.0, 10.0), 0.9),))
    backend = RapidOCRBackend()
    producer = PortableRasterOCRProducer.from_backend(
        backend=backend, page_images={"page_1": Image.new("RGB", (50, 50), "white")},
    )
    res = producer.publish(_sample_selector())
    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert res.status is not EvidenceResolutionStatus.CORROBORATED


def test_backend_provenance_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_rapidocr(monkeypatch, detections=(("W-1", (0.0, 0.0, 10.0, 10.0), 0.9),))
    backend = RapidOCRBackend()
    producer = PortableRasterOCRProducer.from_backend(
        backend=backend, page_images={"page_1": Image.new("RGB", (50, 50), "white")},
    )
    res = producer.publish(_sample_selector())
    assert res.record is not None
    assert res.record.backend_name == "rapid_ocr"


def test_whitespace_only_detections_filtered(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_rapidocr(
        monkeypatch,
        detections=(("   ", (0.0, 0.0, 10.0, 10.0), 0.9), ("W-1", (0.0, 20.0, 10.0, 30.0), 0.9)),
    )
    backend = RapidOCRBackend()
    lines = backend.extract_lines(Image.new("RGB", (50, 50), "white"))
    assert [l.text for l in lines] == ["W-1"]
