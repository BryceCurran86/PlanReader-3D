"""Authenticated raster visibility -> physical wall candidate integration."""
from __future__ import annotations

from io import BytesIO

import fitz
import pytest
from PIL import Image, ImageDraw

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
    PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE,
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_visibility_authority import (
    RASTER_PDF_VISIBLE_SEGMENT,
    SourceVisibilityProducer,
)
from pb_source_observation_authority import ObservationSelector


def _wall_png() -> bytes:
    image = Image.new("RGB", (800, 600), "white")
    draw = ImageDraw.Draw(image)
    width = 4
    # Two parallel skins around a simple rectangular room plus one internal
    # double-line partition. This is geometry only; no tag or benchmark data.
    for first, second in (
        ((100, 100), (700, 100)),
        ((100, 130), (700, 130)),
        ((100, 470), (700, 470)),
        ((100, 500), (700, 500)),
        ((100, 100), (100, 500)),
        ((130, 130), (130, 470)),
        ((700, 100), (700, 500)),
        ((670, 130), (670, 470)),
        ((385, 130), (385, 470)),
        ((415, 130), (415, 470)),
    ):
        draw.line((first, second), fill="black", width=width)
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _image_only_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_image(page.rect, stream=_wall_png(), keep_proportion=False)
    payload = doc.tobytes()
    doc.close()
    return payload


def _selector(published) -> PhysicalWallCandidateSelector:
    return PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )


def test_physical_wall_candidates_accept_only_authenticated_raster_visibility() -> None:
    source = SourceVisibilityProducer(
        producer_method="raster-wall-source-test",
        producer_version="1.0",
    )
    initial = source.ingest_native_pdf_bytes(
        document_id="raster-wall-doc",
        source_bytes=_image_only_pdf(),
        source_locator="memory://raster-wall.pdf",
    )
    assert initial.visible_observation_ids == ()

    augmented = source.augment_with_raster_visible_segments(
        initial.revision.revision_id,
        page_ids=("1",),
    )
    assert augmented.visible_observation_ids

    visibility = source.authority()
    for observation_id in augmented.visible_observation_ids:
        resolved = visibility.resolve_visible(
            ObservationSelector(
                document_id=augmented.revision.document_id,
                revision_id=augmented.revision.revision_id,
                source_sha256=augmented.revision.source_sha256,
                snapshot_id=augmented.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        assert resolved.status is EvidenceResolutionStatus.CORROBORATED
        assert resolved.observation is not None
        assert resolved.observation.observation_kind == RASTER_PDF_VISIBLE_SEGMENT

    producer = PhysicalWallCandidateProducer.from_source_visibility_producer(source)
    result = producer.authority().resolve_scope(_selector(augmented))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proposition == PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED
    assert result.records
    assert set(result.source_observation_ids) == set(
        augmented.visible_observation_ids
    )
    visible_ids = set(augmented.visible_observation_ids)
    assert all(
        set(record.physical_identity.source_primitive_ids) <= visible_ids
        for record in result.records
    )


def test_physical_wall_raster_source_fails_closed_when_receipt_is_missing() -> None:
    source = SourceVisibilityProducer(
        producer_method="raster-wall-source-test",
        producer_version="1.0",
    )
    initial = source.ingest_native_pdf_bytes(
        document_id="raster-wall-tamper",
        source_bytes=_image_only_pdf(),
        source_locator="memory://raster-wall-tamper.pdf",
    )
    augmented = source.augment_with_raster_visible_segments(
        initial.revision.revision_id,
        page_ids=("1",),
    )
    assert augmented.visible_observation_ids

    victim = augmented.visible_observation_ids[0]
    source._raster_visibility_receipts.pop(
        (augmented.snapshot.snapshot_id, victim)
    )

    with pytest.raises(
        RuntimeError,
        match=PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE,
    ):
        PhysicalWallCandidateProducer.from_source_visibility_producer(source)
