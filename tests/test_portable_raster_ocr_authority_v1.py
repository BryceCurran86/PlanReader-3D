"""Comprehensive unit tests for Item 24 Portable Raster OCR Authority (F25).

Tests:
1. Capability detection across environments without hardcoded paths or crashing.
2. NullOCRBackend, MockOCRBackend, WinOCRBackend, TesseractOCRBackend interfaces.
3. Fail-closed behavior when OCR backend is unavailable (never fakes text).
4. Missing source page image failure behavior.
5. Lineage verification against snapshot (fails closed on mismatch).
6. Target region point-to-pixel cropping and coordinate offset adjustments.
7. Explicit provenance: backend name, version, DPI, page, viewport, target_region.
8. Provisional status tracking: OCR output is never silent FIRM authority.
9. Native vs. OCR text reconciliation:
   - Exact/normalized match -> confirmed
   - Contradiction -> conflict_manual_review (fails closed with CONFLICT)
   - Native only -> confirmed
   - OCR only -> provisional
10. Authority lookup, sealing, and immutability.
11. Clean handling of empty/whitespace-only text.
12. Zero project-name or benchmark-specific heuristics.
"""
from __future__ import annotations

import pytest
from PIL import Image

from pb_migration_contracts import EvidenceResolutionStatus
from pb_portable_raster_ocr_authority import (
    DocumentSnapshotLineage,
    MockOCRBackend,
    NullOCRBackend,
    OCRBackend,
    OCRCapabilityReport,
    OCRLine,
    OCR_BACKEND_UNAVAILABLE,
    OCR_EXTRACTION_RESOLVED,
    OCR_LINEAGE_MISMATCH,
    OCR_NATIVE_CONFLICT,
    OCR_NO_TEXT_DETECTED,
    OCR_SCOPE_UNAVAILABLE,
    OCR_SOURCE_IMAGE_MISSING,
    PORTABLE_RASTER_OCR_SCHEMA_VERSION,
    PortableRasterOCRAuthority,
    PortableRasterOCRProducer,
    PortableRasterOCRResult,
    PortableRasterOCRSelector,
    RasterOCRBackend,
    RasterOCREvidenceRecord,
    TesseractOCRBackend,
    WinOCRBackend,
    detect_ocr_capabilities,
    normalize_text_for_reconciliation,
    reconcile_native_and_ocr_text,
)


def _sample_snapshot() -> DocumentSnapshotLineage:
    return DocumentSnapshotLineage(
        document_id="doc_test_100",
        revision_id="rev_test_001",
        source_sha256="a" * 64,
        snapshot_id="snap_test_001",
    )


def _sample_selector(
    page_id: str = "page_1",
    viewport_id: str | None = "vp_floor_plan",
    target_region_pt: tuple[float, float, float, float] | None = None,
) -> PortableRasterOCRSelector:
    return PortableRasterOCRSelector(
        document_id="doc_test_100",
        revision_id="rev_test_001",
        source_sha256="a" * 64,
        snapshot_id="snap_test_001",
        page_id=page_id,
        viewport_id=viewport_id,
        target_region_pt=target_region_pt,
    )


def test_capability_detection_is_safe_and_portable() -> None:
    report = detect_ocr_capabilities()
    assert isinstance(report, OCRCapabilityReport)
    assert isinstance(report.available_backends, tuple)
    assert isinstance(report.pillow_available, bool)
    assert isinstance(report.tesseract_available, bool)
    assert report.pillow_available is True


def test_backend_interfaces() -> None:
    null_be = NullOCRBackend()
    assert null_be.name == "null_backend"
    assert null_be.version == "0.0.0"
    assert null_be.is_available() is False
    assert null_be.extract_lines(Image.new("RGB", (10, 10))) == ()

    mock_be = MockOCRBackend(
        canned_lines=[OCRLine(text="W01", confidence=0.95, bbox_px=(10, 10, 50, 30))],
        is_ready=True,
    )
    assert mock_be.name == "mock_ocr"
    assert mock_be.is_available() is True
    lines = mock_be.extract_lines(Image.new("RGB", (100, 100)))
    assert len(lines) == 1
    assert lines[0].text == "W01"

    win_be = WinOCRBackend()
    assert win_be.name == "win_ocr"
    assert isinstance(win_be.is_available(), bool)

    tess_be = TesseractOCRBackend()
    assert tess_be.name == "tesseract"
    assert isinstance(tess_be.is_available(), bool)

    assert OCRBackend is RasterOCRBackend


def test_fail_closed_when_backend_unavailable() -> None:
    null_be = NullOCRBackend()
    img = Image.new("RGB", (100, 100), "white")
    producer = PortableRasterOCRProducer.from_backend(
        backend=null_be,
        page_images={"page_1": img},
        snapshot=_sample_snapshot(),
    )
    sel = _sample_selector()
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert OCR_BACKEND_UNAVAILABLE in res.reason_codes
    assert res.record is None


def test_fail_closed_when_page_image_missing() -> None:
    mock_be = MockOCRBackend(is_ready=True)
    producer = PortableRasterOCRProducer.from_backend(
        backend=mock_be,
        page_images={},
        snapshot=_sample_snapshot(),
    )
    sel = _sample_selector(page_id="page_1")
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert OCR_SOURCE_IMAGE_MISSING in res.reason_codes
    assert res.record is None


def test_lineage_mismatch_fails_closed() -> None:
    mock_be = MockOCRBackend(
        canned_lines=[OCRLine(text="D01", confidence=0.9, bbox_px=(0, 0, 10, 10))],
        is_ready=True,
    )
    img = Image.new("RGB", (100, 100), "white")
    producer = PortableRasterOCRProducer.from_backend(
        backend=mock_be,
        page_images={"page_1": img},
        snapshot=_sample_snapshot(),
    )
    bad_sel = PortableRasterOCRSelector(
        document_id="doc_test_100",
        revision_id="rev_test_001",
        source_sha256="b" * 64,
        snapshot_id="snap_test_001",
        page_id="page_1",
    )
    res = producer.publish(bad_sel)
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert OCR_LINEAGE_MISMATCH in res.reason_codes
    assert res.record is None


def test_successful_ocr_extraction_with_provisional_status() -> None:
    canned = [
        OCRLine(text="SCHEDULE", confidence=0.90, bbox_px=(10, 10, 100, 30), bbox_pt=(5, 5, 50, 15)),
        OCRLine(text="W01", confidence=0.80, bbox_px=(10, 40, 50, 60), bbox_pt=(5, 20, 25, 30)),
    ]
    mock_be = MockOCRBackend(canned_lines=canned, is_ready=True)
    img = Image.new("RGB", (200, 200), "white")
    producer = PortableRasterOCRProducer.from_backend(
        backend=mock_be,
        page_images={"page_1": img},
        snapshot=_sample_snapshot(),
        default_dpi=150,
    )
    sel = _sample_selector()
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert OCR_EXTRACTION_RESOLVED in res.reason_codes
    rec = res.record
    assert rec is not None
    assert rec.is_ocr_derived is True
    assert rec.extraction_method == "raster_ocr"
    assert rec.reconciliation_status == "provisional"
    assert rec.full_text == "SCHEDULE W01"
    assert rec.backend_name == "mock_ocr"
    assert rec.dpi == 150
    assert rec.confidence == 0.85
    assert rec.schema_version == PORTABLE_RASTER_OCR_SCHEMA_VERSION


def test_native_and_ocr_reconciliation_confirmed() -> None:
    canned = [OCRLine(text="BEDROOM 1", confidence=0.95, bbox_px=(10, 10, 80, 25))]
    mock_be = MockOCRBackend(canned_lines=canned, is_ready=True)
    img = Image.new("RGB", (200, 200), "white")
    producer = PortableRasterOCRProducer.from_backend(
        backend=mock_be,
        page_images={"page_1": img},
        native_texts={("page_1", "vp_floor_plan"): "Bedroom 1"},
        snapshot=_sample_snapshot(),
    )
    sel = _sample_selector()
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.reconciliation_status == "confirmed"
    assert res.record.full_text == "Bedroom 1"


def test_native_and_ocr_reconciliation_conflict_fails_closed() -> None:
    canned = [OCRLine(text="KITCHEN", confidence=0.95, bbox_px=(10, 10, 80, 25))]
    mock_be = MockOCRBackend(canned_lines=canned, is_ready=True)
    img = Image.new("RGB", (200, 200), "white")
    producer = PortableRasterOCRProducer.from_backend(
        backend=mock_be,
        page_images={"page_1": img},
        native_texts={("page_1", "vp_floor_plan"): "BATHROOM"},
        snapshot=_sample_snapshot(),
    )
    sel = _sample_selector()
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert OCR_NATIVE_CONFLICT in res.reason_codes
    assert res.record is None


def test_target_region_cropping_and_coordinate_adjustment() -> None:
    canned = [
        OCRLine(text="W02", confidence=0.88, bbox_px=(10, 10, 30, 30), bbox_pt=(5, 5, 15, 15))
    ]
    mock_be = MockOCRBackend(canned_lines=canned, is_ready=True)
    img = Image.new("RGB", (400, 400), "white")
    producer = PortableRasterOCRProducer.from_backend(
        backend=mock_be,
        page_images={"page_1": img},
        snapshot=_sample_snapshot(),
        default_dpi=144,
    )
    sel = _sample_selector(target_region_pt=(50.0, 50.0, 100.0, 100.0))
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert len(res.record.lines) == 1
    line = res.record.lines[0]
    assert line.bbox_pt is not None
    assert line.bbox_pt[0] == 55.0
    assert line.bbox_pt[1] == 55.0
    assert line.bbox_pt[2] == 65.0
    assert line.bbox_pt[3] == 65.0


def test_empty_ocr_text_fails_closed() -> None:
    mock_be = MockOCRBackend(
        canned_lines=[OCRLine(text="   ", confidence=0.5, bbox_px=(0, 0, 10, 10))],
        is_ready=True,
    )
    img = Image.new("RGB", (100, 100), "white")
    producer = PortableRasterOCRProducer.from_backend(
        backend=mock_be,
        page_images={"page_1": img},
        snapshot=_sample_snapshot(),
    )
    sel = _sample_selector()
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert OCR_NO_TEXT_DETECTED in res.reason_codes
    assert res.record is None


def test_authority_lookup_and_immutability() -> None:
    canned = [OCRLine(text="DOOR D01", confidence=0.92, bbox_px=(5, 5, 50, 20))]
    mock_be = MockOCRBackend(canned_lines=canned, is_ready=True)
    img = Image.new("RGB", (100, 100), "white")
    producer = PortableRasterOCRProducer.from_backend(
        backend=mock_be,
        page_images={"page_1": img},
        snapshot=_sample_snapshot(),
    )
    sel = _sample_selector()
    producer.publish(sel)

    auth = producer.authority()
    resolved = auth.resolve(sel)
    assert resolved.status == EvidenceResolutionStatus.CORROBORATED
    assert resolved.record is not None
    assert resolved.record.full_text == "DOOR D01"

    unknown_sel = _sample_selector(page_id="page_999")
    unknown_res = auth.resolve(unknown_sel)
    assert unknown_res.status == EvidenceResolutionStatus.ABSTAINED
    assert OCR_SCOPE_UNAVAILABLE in unknown_res.reason_codes

    with pytest.raises(TypeError, match="producer-owned"):
        PortableRasterOCRAuthority({})


def test_reconciliation_helper_variants() -> None:
    t, status, reasons = reconcile_native_and_ocr_text("", "")
    assert status == "unresolved"

    t, status, reasons = reconcile_native_and_ocr_text("W-01", "")
    assert status == "confirmed"
    assert t == "W-01"

    t, status, reasons = reconcile_native_and_ocr_text("", "W-01")
    assert status == "provisional"
    assert t == "W-01"

    t, status, reasons = reconcile_native_and_ocr_text("W 01", "w-01")
    assert status == "confirmed"

    t, status, reasons = reconcile_native_and_ocr_text("W 01", "D 01")
    assert status == "conflict_manual_review"


def test_producer_snapshot_record_duck_typing() -> None:
    from pb_source_observation_authority import ProducerSnapshotRecord
    snap_rec = ProducerSnapshotRecord(
        snapshot_id="snap_duck_001",
        document_id="doc_duck_100",
        revision_id="rev_duck_001",
        source_sha256="c" * 64,
        observation_ids=(),
        producer_method="test",
        producer_version="1.0.0",
        producer_generation=1,
    )
    mock_be = MockOCRBackend(
        canned_lines=[OCRLine(text="LEVEL 1", confidence=0.9, bbox_px=(0, 0, 10, 10))],
        is_ready=True,
    )
    producer = PortableRasterOCRProducer.from_backend(
        backend=mock_be,
        page_images={"page_1": Image.new("RGB", (100, 100), "white")},
        snapshot=snap_rec,
    )
    matching_sel = PortableRasterOCRSelector(
        document_id="doc_duck_100",
        revision_id="rev_duck_001",
        source_sha256="c" * 64,
        snapshot_id="snap_duck_001",
        page_id="page_1",
    )
    res = producer.publish(matching_sel)
    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.full_text == "LEVEL 1"


def test_backend_exception_fails_closed_with_conflict() -> None:
    class FailingBackend(RasterOCRBackend):
        @property
        def name(self) -> str:
            return "failing"
        @property
        def version(self) -> str:
            return "0.0.1"
        def is_available(self) -> bool:
            return True
        def extract_lines(self, image: Image.Image, dpi: int = 150) -> tuple[OCRLine, ...]:
            raise RuntimeError("Engine segmentation fault simulation")

    producer = PortableRasterOCRProducer.from_backend(
        backend=FailingBackend(),
        page_images={"page_1": Image.new("RGB", (50, 50), "white")},
        snapshot=_sample_snapshot(),
    )
    res = producer.publish(_sample_selector())
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert OCR_BACKEND_UNAVAILABLE in res.reason_codes
    assert any("extraction_error" in r for r in res.reason_codes)


def test_invalid_target_region_pt_validation() -> None:
    with pytest.raises(ValueError, match="target_region_pt must be a 4-tuple"):
        PortableRasterOCRSelector(
            document_id="doc_1",
            revision_id="rev_1",
            source_sha256="a" * 64,
            snapshot_id="snap_1",
            page_id="p1",
            target_region_pt=(0.0, 0.0, 10.0),  # type: ignore
        )

    with pytest.raises(ValueError, match="positive span"):
        PortableRasterOCRSelector(
            document_id="doc_1",
            revision_id="rev_1",
            source_sha256="a" * 64,
            snapshot_id="snap_1",
            page_id="p1",
            target_region_pt=(10.0, 10.0, 5.0, 20.0),  # x1 <= x0
        )


def test_ocr_line_confidence_validation() -> None:
    with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
        OCRLine(text="TEST", confidence=1.5, bbox_px=(0, 0, 10, 10))

