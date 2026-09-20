"""Raster source-visibility and G17 physical-opening integration tests."""
from __future__ import annotations

from io import BytesIO
import inspect

import fitz
from PIL import Image, ImageDraw

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
)
from pb_raster_visible_segment_detector import (
    detect_axis_aligned_raster_segments,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    NATIVE_PDF_VISIBLE_SEGMENT,
    RASTER_PDF_VISIBLE_SEGMENT,
    SourceVisibilityProducer,
)


def _opening_png() -> bytes:
    image = Image.new("RGB", (600, 400), "white")
    draw = ImageDraw.Draw(image)
    width = 3
    for first, second in (
        ((50, 120), (220, 120)),
        ((300, 120), (550, 120)),
        ((50, 150), (220, 150)),
        ((300, 150), (550, 150)),
        ((220, 120), (220, 150)),
        ((300, 120), (300, 150)),
    ):
        draw.line((first, second), fill="black", width=width)
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _image_only_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    page.insert_image(page.rect, stream=_opening_png())
    payload = doc.tobytes()
    doc.close()
    return payload


def _vector_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    for first, second in (
        ((25.0, 60.0), (110.0, 60.0)),
        ((150.0, 60.0), (275.0, 60.0)),
        ((25.0, 75.0), (110.0, 75.0)),
        ((150.0, 75.0), (275.0, 75.0)),
        ((110.0, 60.0), (110.0, 75.0)),
        ((150.0, 60.0), (150.0, 75.0)),
    ):
        page.draw_line(
            fitz.Point(*first),
            fitz.Point(*second),
            color=(0, 0, 0),
            width=1,
        )
    payload = doc.tobytes()
    doc.close()
    return payload


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def test_detector_recovers_axis_aligned_g17_segments_from_pixels() -> None:
    segments = detect_axis_aligned_raster_segments(_opening_png(), dpi=144)
    assert len(segments) >= 6

    horizontal = [item for item in segments if item.orientation == "horizontal"]
    vertical = [item for item in segments if item.orientation == "vertical"]
    assert len(horizontal) >= 4
    assert len(vertical) >= 2


def test_raster_augmentation_accepts_no_caller_segment_or_dpi_inputs() -> None:
    params = set(
        inspect.signature(
            SourceVisibilityProducer.augment_with_raster_visible_segments
        ).parameters
    )
    assert params == {"self", "revision_id"}


def test_image_only_pdf_gets_producer_owned_raster_visible_segments() -> None:
    source = SourceVisibilityProducer(
        producer_method="raster-visibility-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="raster-opening",
        source_bytes=_image_only_pdf(),
        source_locator="memory://raster-opening.pdf",
    )
    assert published.visible_observation_ids == ()

    augmented = source.augment_with_raster_visible_segments(
        published.revision.revision_id
    )
    assert augmented.snapshot.snapshot_id != published.snapshot.snapshot_id
    assert len(augmented.visible_observation_ids) >= 6

    authority = source.authority()
    resolved = [
        authority.resolve_visible(_selector(augmented, observation_id))
        for observation_id in augmented.visible_observation_ids
    ]
    assert all(
        item.status is EvidenceResolutionStatus.CORROBORATED
        for item in resolved
    )
    assert all(
        item.observation is not None
        and item.observation.observation_kind == RASTER_PDF_VISIBLE_SEGMENT
        for item in resolved
    )
    assert len(
        {
            item.observation.derivation_parent_ids[0]
            for item in resolved
            if item.observation is not None
        }
    ) == len(resolved)


def test_existing_g17_authority_can_prove_raster_opening_without_ocr_or_schedule() -> None:
    source = SourceVisibilityProducer(
        producer_method="raster-visibility-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="raster-g17",
        source_bytes=_image_only_pdf(),
        source_locator="memory://raster-g17.pdf",
    )
    augmented = source.augment_with_raster_visible_segments(
        published.revision.revision_id
    )

    physical = PhysicalOpeningAuthority(source.authority())
    results = [
        physical.prove_existence(_selector(augmented, observation_id))
        for observation_id in augmented.visible_observation_ids
    ]
    corroborated = [
        item
        for item in results
        if item.status is EvidenceResolutionStatus.CORROBORATED
        and item.proposition == PHYSICAL_OPENING_EXISTS
        and item.existence_record is not None
    ]
    assert corroborated
    record_ids = {
        item.existence_record.record_id
        for item in corroborated
        if item.existence_record is not None
    }
    assert len(record_ids) == 1


def test_native_vector_visibility_prevents_raster_fallback_duplication() -> None:
    source = SourceVisibilityProducer(
        producer_method="raster-visibility-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="native-g17",
        source_bytes=_vector_pdf(),
        source_locator="memory://native-g17.pdf",
    )
    assert len(published.visible_observation_ids) >= 6

    augmented = source.augment_with_raster_visible_segments(
        published.revision.revision_id
    )
    assert augmented.snapshot.snapshot_id == published.snapshot.snapshot_id
    assert augmented.visible_observation_ids == published.visible_observation_ids

    authority = source.authority()
    for observation_id in augmented.visible_observation_ids:
        resolved = authority.resolve_visible(_selector(augmented, observation_id))
        assert resolved.status is EvidenceResolutionStatus.CORROBORATED
        assert resolved.observation is not None
        assert resolved.observation.observation_kind == NATIVE_PDF_VISIBLE_SEGMENT
