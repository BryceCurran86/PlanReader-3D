"""Independent GPT-2 red-team for physical-scale ratio corroboration provenance.

TEST ONLY / EXPECTED RED / DO NOT MERGE.

A textual ratio may corroborate a source-native graphic scale bar, but it must not
replace the bar's measured geometry in the published evidence.  This attack uses
a bar that agrees with 1:100 inside the producer's accepted tolerance while being
deliberately, measurably non-identical to the exact ratio-implied span.
"""
from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_page_scale_calibration_authority import POINTS_PER_METRE_AT_1_1
from pb_physical_scale_authority import PhysicalScaleProducer, PhysicalScaleSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _near_agreeing_bar_pdf() -> tuple[bytes, float]:
    expected_span = POINTS_PER_METRE_AT_1_1 / 100.0
    # Production currently accepts relative disagreement <= 1e-5.  Use half
    # that amount so the ratio genuinely corroborates rather than conflicts,
    # while remaining large enough to survive PDF coordinate serialization.
    measured_span = expected_span * (1.0 + 5.0e-6)

    doc = fitz.open()
    try:
        page = doc.new_page(width=420.0, height=260.0)
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


def test_agreeing_ratio_cannot_rewrite_native_bar_measurement() -> None:
    payload, measured_span = _near_agreeing_bar_pdf()
    source = SourceVisibilityProducer(
        producer_method="gpt2-physical-scale-ratio-provenance",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="gpt2-physical-scale-ratio-provenance",
        source_bytes=payload,
        source_locator="memory://gpt2-physical-scale-ratio-provenance.pdf",
    )
    producer = PhysicalScaleProducer.from_source_visibility_producer(source)
    selector = PhysicalScaleSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
    )

    result = producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None

    # Ratio text can establish agreement, but the evidence must still report
    # the actual source-native bar measurement and its geometry-derived mapping.
    assert abs(result.evidence.source_span_pt - measured_span) <= 5.0e-5
    assert abs(result.evidence.points_per_mm - measured_span / 1000.0) <= 5.0e-8

    exact_ratio_span = POINTS_PER_METRE_AT_1_1 / 100.0
    assert abs(measured_span - exact_ratio_span) > 1.0e-4
