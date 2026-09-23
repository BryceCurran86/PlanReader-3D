"""Producer-owned raster visibility -> physical wall candidate integration."""
from __future__ import annotations

from io import BytesIO
import inspect

import fitz
from PIL import Image, ImageDraw

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    RASTER_PDF_VISIBLE_SEGMENT,
    SourceVisibilityProducer,
)


def _double_rectangle_png() -> bytes:
    image = Image.new("RGB", (600, 400), "white")
    draw = ImageDraw.Draw(image)
    for box in ((80, 70, 520, 330), (110, 100, 490, 300)):
        draw.rectangle(box, outline="black", width=4)
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _image_only_wall_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    page.insert_image(page.rect, stream=_double_rectangle_png())
    payload = bytes(doc.tobytes())
    doc.close()
    return payload


def test_wall_candidate_producer_exposes_no_caller_raster_inputs() -> None:
    params = set(
        inspect.signature(
            PhysicalWallCandidateProducer.from_source_visibility_producer
        ).parameters
    )
    assert params == {"source_visibility_producer", "page_ids"}
    assert not params & {
        "png_bytes",
        "pixels",
        "segments",
        "dpi",
        "transform",
        "wall_candidates",
        "expected_count",
    }
    assert "page_ids" in params  # source addressing only; not raster evidence


def test_image_only_raster_wall_scope_is_built_from_producer_visibility() -> None:
    source = SourceVisibilityProducer(
        producer_method="raster-wall-source-test",
        producer_version="1.0",
    )
    initial = source.ingest_native_pdf_bytes(
        document_id="raster-wall-doc",
        source_bytes=_image_only_wall_pdf(),
        source_locator="memory://raster-wall-doc.pdf",
    )
    assert initial.visible_observation_ids == ()

    wall_producer = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source
    )
    augmented = source.published_snapshot_for_revision(initial.revision.revision_id)
    assert augmented is not None
    assert augmented.snapshot.snapshot_id != initial.snapshot.snapshot_id
    assert len(augmented.visible_observation_ids) >= 8

    visibility = source.authority()
    resolved_visible = [
        visibility.resolve_visible(
            ObservationSelector(
                document_id=augmented.revision.document_id,
                revision_id=augmented.revision.revision_id,
                source_sha256=augmented.revision.source_sha256,
                snapshot_id=augmented.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        for observation_id in augmented.visible_observation_ids
    ]
    assert all(
        result.status is EvidenceResolutionStatus.CORROBORATED
        and result.observation is not None
        and result.observation.observation_kind == RASTER_PDF_VISIBLE_SEGMENT
        for result in resolved_visible
    )

    result = wall_producer.authority().resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=augmented.revision.document_id,
            revision_id=augmented.revision.revision_id,
            source_sha256=augmented.revision.source_sha256,
            snapshot_id=augmented.snapshot.snapshot_id,
            page_id="1",
            decision_scope_id="wall-source:page-1",
        )
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED in result.reason_codes
    assert result.scope_complete is True
    assert result.records
    assert set(result.source_observation_ids) == set(
        augmented.visible_observation_ids
    )
    assert all(record.physical_identity.usable for record in result.records)
