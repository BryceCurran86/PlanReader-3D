"""PhysicalScaleAuthority -> existing ScaleCalibration bridge tests."""
from __future__ import annotations

import fitz

from pb_geometry_takeoff_model import AuthorityStatus
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_page_scale_calibration_authority import (
    POINTS_PER_METRE_AT_1_1,
    measurement_authority_for_page_scale,
)
from pb_physical_scale_authority import (
    PhysicalScaleProducer,
    PhysicalScaleSelector,
)
from pb_physical_scale_calibration_bridge import (
    PHYSICAL_SCALE_CALIBRATION_CONTEXT_MISMATCH,
    PHYSICAL_SCALE_CALIBRATION_RESOLVED,
    PHYSICAL_SCALE_CALIBRATION_UNAVAILABLE,
    build_physical_scale_calibration,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _scale_bar_pdf(*, include_bar: bool = True) -> tuple[bytes, float]:
    expected_span = POINTS_PER_METRE_AT_1_1 / 100.0
    measured_span = expected_span * (1.0 + 5.0e-6)
    doc = fitz.open()
    try:
        page = doc.new_page(width=420.0, height=260.0)
        if include_bar:
            x0 = 60.0
            x1 = x0 + measured_span
            y = 100.0
            shape = page.new_shape()
            shape.draw_line(fitz.Point(x0, y), fitz.Point(x1, y))
            shape.draw_line(fitz.Point(x0, y - 8.0), fitz.Point(x0, y + 8.0))
            shape.draw_line(fitz.Point(x1, y - 8.0), fitz.Point(x1, y + 8.0))
            shape.finish(width=1.0)
            shape.commit()
            page.insert_text(fitz.Point(x0 - 2.0, y + 24.0), "0")
            page.insert_text(fitz.Point(x1 - 4.0, y + 24.0), "1m")
        page.insert_text(fitz.Point(260.0, 60.0), "SCALE 1:100")
        return bytes(doc.tobytes(garbage=4, deflate=True)), measured_span
    finally:
        doc.close()


def _setup(*, include_bar: bool = True):
    payload, measured_span = _scale_bar_pdf(include_bar=include_bar)
    source = SourceVisibilityProducer(
        producer_method="physical-scale-calibration-bridge-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="physical-scale-calibration-bridge-doc",
        source_bytes=payload,
        source_locator="memory://physical-scale-calibration-bridge.pdf",
    )
    producer = PhysicalScaleProducer.from_source_visibility_producer(source)
    selector = PhysicalScaleSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
    )
    producer.publish_scope(selector)
    authority = producer.authority()
    context = ProviderContext(
        run_id="run-physical-scale-calibration",
        workspace_id="workspace-physical-scale-calibration",
        project_id="project-physical-scale-calibration",
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
        current_revision_id=published.revision.revision_id,
        selected_pages=(0,),
        owned_viewport_ids=("vp-whole-page",),
        evidence_snapshot_id=published.snapshot.snapshot_id,
        owned_page_numbers=(1,),
        viewport_page_ownership=(("vp-whole-page", 1),),
    )
    viewport = ViewportEvidence(
        viewport_id="vp-whole-page",
        document_id=published.revision.document_id,
        page_id="1",
        bbox=(0.0, 0.0, 420.0, 260.0),
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        evidence_ids=(),
        confidence=1.0,
    )
    return published, selector, authority, context, viewport, measured_span


def test_native_graphic_scale_bar_reuses_existing_firm_calibration() -> None:
    published, selector, authority, context, viewport, measured_span = _setup()

    result = build_physical_scale_calibration(
        physical_scale_authority=authority,
        selector=selector,
        context=context,
        viewport=viewport,
        page_no=1,
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (PHYSICAL_SCALE_CALIBRATION_RESOLVED,)
    assert result.calibration is not None
    assert result.physical_scale_evidence is not None
    assert result.physical_scale_evidence.record_id
    assert result.physical_scale_evidence.source_segment_observation_ids
    assert result.physical_scale_evidence.source_text_observation_ids
    expected_px_per_m = measured_span
    assert abs(result.calibration.px_per_m - expected_px_per_m) <= 5.0e-5
    assert (
        measurement_authority_for_page_scale(result.calibration)
        == AuthorityStatus.FIRM.value
    )
    assert result.calibration.revision_id == published.revision.revision_id


def test_title_ratio_without_graphic_bar_does_not_mint_calibration() -> None:
    _published, selector, authority, context, viewport, _span = _setup(
        include_bar=False
    )

    result = build_physical_scale_calibration(
        physical_scale_authority=authority,
        selector=selector,
        context=context,
        viewport=viewport,
        page_no=1,
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (PHYSICAL_SCALE_CALIBRATION_UNAVAILABLE,)
    assert result.calibration is None
    assert result.physical_scale_evidence is None


def test_context_mismatch_blocks_before_scale_resolution() -> None:
    _published, selector, authority, context, viewport, _span = _setup()
    wrong_viewport = ViewportEvidence(
        viewport_id="vp-not-owned",
        document_id=viewport.document_id,
        page_id=viewport.page_id,
        bbox=viewport.bbox,
        view_type=viewport.view_type,
        status=viewport.status,
        evidence_ids=viewport.evidence_ids,
        confidence=viewport.confidence,
    )

    result = build_physical_scale_calibration(
        physical_scale_authority=authority,
        selector=selector,
        context=context,
        viewport=wrong_viewport,
        page_no=1,
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (PHYSICAL_SCALE_CALIBRATION_CONTEXT_MISMATCH,)
    assert result.calibration is None
