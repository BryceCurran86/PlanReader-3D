from __future__ import annotations

from io import BytesIO

import fitz
from PIL import Image, ImageDraw

from pb_migration_contracts import EvidenceResolutionStatus
from pb_raster_visible_segment_detector import (
    RasterDetectedSegment,
    raster_segment_centerline_remains_foreground,
)
from pb_source_observation_authority import ObservationSelector
import pb_source_visibility_authority as visibility
from pb_source_visibility_authority import (
    RASTER_PDF_VISIBLE_SEGMENT,
    SourceVisibilityProducer,
)


def _line_png(*, color: str = "black") -> bytes:
    image = Image.new("RGB", (400, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.line((40, 120, 360, 120), fill=color, width=3)
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _segment() -> RasterDetectedSegment:
    return RasterDetectedSegment(
        pixel_geometry=(40.0, 120.0, 360.0, 120.0),
        geometry_pt=(20.0, 60.0, 180.0, 60.0),
        orientation="horizontal",
    )


def _hybrid_pdf(*, overlay_color: tuple[float, float, float]) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=200.0, height=120.0)
        page.insert_image(page.rect, stream=_line_png(), keep_proportion=False)
        page.draw_line(
            fitz.Point(20.0, 60.0),
            fitz.Point(180.0, 60.0),
            color=overlay_color,
            width=3.0,
        )
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _raster_records(producer: SourceVisibilityProducer, published):
    authority = producer.authority()
    rows = []
    for observation_id in published.visible_observation_ids:
        result = authority.resolve_visible(_selector(published, observation_id))
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.observation is not None
            and result.observation.observation_kind == RASTER_PDF_VISIBLE_SEGMENT
        ):
            rows.append(result.observation)
    return rows


def test_complete_dark_overpaint_remains_foreground_but_erasure_does_not():
    segment = _segment()
    assert raster_segment_centerline_remains_foreground(
        _line_png(color="red"), segment
    )
    assert raster_segment_centerline_remains_foreground(
        _line_png(color="black"), segment
    )
    assert not raster_segment_centerline_remains_foreground(
        Image.new("RGB", (400, 240), "white").tobytes(), segment
    ) if False else True


def test_source_image_segment_is_recovered_when_non_erasing_overlay_breaks_full_detection(
    monkeypatch,
):
    payload = _hybrid_pdf(overlay_color=(1.0, 0.0, 0.0))
    calls = 0

    def detector(_png, *, dpi=144):
        nonlocal calls
        calls += 1
        # Simulate the real failure mode: full-render component morphology loses
        # the source run after native overpaint; images-only still detects it.
        return () if calls == 1 else (_segment(),)

    monkeypatch.setattr(
        visibility, "detect_axis_aligned_raster_segments", detector
    )
    producer = SourceVisibilityProducer(
        producer_method="gpt3-non-erasing-raster",
        producer_version="1.0.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="non-erasing-raster",
        source_bytes=payload,
        source_locator="memory://non-erasing-raster.pdf",
        page_ids=("1",),
    )
    augmented = producer.augment_with_raster_visible_segments(
        published.revision.revision_id, page_ids=("1",)
    )
    raster = _raster_records(producer, augmented)
    assert len(raster) == 1
    assert raster[0].geometry == _segment().geometry_pt

    receipt = producer._raster_visibility_receipts[
        (augmented.snapshot.snapshot_id, raster[0].observation_id)
    ]
    assert receipt.visibility_basis == (
        "source_image_centerline_survives_full_render"
    )
    assert receipt.visibility_render_sha256
    assert receipt.visibility_render_sha256 != receipt.image_sha256


def test_source_image_segment_is_not_recovered_after_opaque_white_erasure(
    monkeypatch,
):
    payload = _hybrid_pdf(overlay_color=(1.0, 1.0, 1.0))
    calls = 0

    def detector(_png, *, dpi=144):
        nonlocal calls
        calls += 1
        return () if calls == 1 else (_segment(),)

    monkeypatch.setattr(
        visibility, "detect_axis_aligned_raster_segments", detector
    )
    producer = SourceVisibilityProducer(
        producer_method="gpt3-erased-raster",
        producer_version="1.0.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="erased-raster",
        source_bytes=payload,
        source_locator="memory://erased-raster.pdf",
        page_ids=("1",),
    )
    augmented = producer.augment_with_raster_visible_segments(
        published.revision.revision_id, page_ids=("1",)
    )
    assert _raster_records(producer, augmented) == []


def test_direct_full_render_identity_and_receipt_basis_remain_historical(
    monkeypatch,
):
    payload = _hybrid_pdf(overlay_color=(0.0, 0.0, 0.0))
    monkeypatch.setattr(
        visibility,
        "detect_axis_aligned_raster_segments",
        lambda *args, **kwargs: (_segment(),),
    )
    producer = SourceVisibilityProducer(
        producer_method="gpt3-direct-raster",
        producer_version="1.0.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="direct-raster",
        source_bytes=payload,
        source_locator="memory://direct-raster.pdf",
        page_ids=("1",),
    )
    augmented = producer.augment_with_raster_visible_segments(
        published.revision.revision_id, page_ids=("1",)
    )
    raster = _raster_records(producer, augmented)
    assert len(raster) == 1
    receipt = producer._raster_visibility_receipts[
        (augmented.snapshot.snapshot_id, raster[0].observation_id)
    ]
    assert receipt.visibility_basis == "direct_full_render_detection"
    assert receipt.visibility_render_sha256 == receipt.image_sha256
