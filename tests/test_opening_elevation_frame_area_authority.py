from __future__ import annotations

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_elevation_frame_area_authority import (
    OPENING_ELEVATION_FRAME_AREA_UNAVAILABLE,
    OpeningElevationFrameAreaProducer,
    OpeningElevationFrameAreaSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _elevation_pdf(*, composite: bool = False, far_width_dimension: bool = False) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=500.0, height=400.0)
        page.insert_text((30.0, 30.0), "WINDOW ELEVATIONS", fontsize=10.0)

        # Closed source frame: 150pt x 120pt. Figured dimensions are 3000 x
        # 2400, preserving the same aspect ratio without requiring page scale.
        page.draw_rect(fitz.Rect(150.0, 120.0, 300.0, 240.0), width=1.0)
        page.insert_text((215.0, 185.0), "W1", fontsize=9.0)

        if composite:
            page.insert_text((258.0, 185.0), "D1", fontsize=9.0)

        # Horizontal figured dimension with two witness lines.  The optional
        # far placement simulates a valid dimension chain belonging to another
        # nearby elevation: it remains witness-bound but is not local enough to
        # authorize this frame.
        width_y = 45.0 if far_width_dimension else 80.0
        page.draw_line((150.0, width_y), (300.0, width_y), width=0.7)
        page.draw_line((150.0, width_y - 10.0), (150.0, 125.0), width=0.7)
        page.draw_line((300.0, width_y - 10.0), (300.0, 125.0), width=0.7)
        page.insert_text((212.0, width_y + 3.0), "3000", fontsize=8.0)

        # Vertical figured dimension with two witness lines.
        page.draw_line((110.0, 120.0), (110.0, 240.0), width=0.7)
        page.draw_line((100.0, 120.0), (155.0, 120.0), width=0.7)
        page.draw_line((100.0, 240.0), (155.0, 240.0), width=0.7)
        page.insert_text((113.0, 196.0), "2400", fontsize=8.0, rotate=90)

        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _authority(payload: bytes):
    source = SourceVisibilityProducer(
        producer_method="opening-elevation-frame-area-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="opening-elevation-frame-area",
        source_bytes=payload,
        source_locator="memory://opening-elevation-frame-area.pdf",
    )
    producer = OpeningElevationFrameAreaProducer.from_source_visibility_producer(source)
    return published, producer.authority()


def _selector(published, mark: str) -> OpeningElevationFrameAreaSelector:
    return OpeningElevationFrameAreaSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        type_mark=mark,
    )


def test_marked_window_elevation_proves_closed_gross_frame_area() -> None:
    published, authority = _authority(_elevation_pdf())

    result = authority.resolve(_selector(published, "W1"))

    assert result.status is EvidenceResolutionStatus.CORROBORATED, result.reason_codes
    assert result.record is not None
    record = result.record
    assert record.type_mark == "W1"
    assert record.opening_kind == "window"
    assert record.area_m2 == pytest.approx(7.2)
    assert sorted((record.axis_x_mm, record.axis_y_mm)) == [2400.0, 3000.0]
    assert record.mark_observation_id in record.source_observation_ids
    assert set(record.dimension_observation_ids).issubset(record.source_observation_ids)
    assert record.dimension_line_ids
    assert len(record.witness_line_ids) >= 4
    assert record.frame_geometry_ids


def test_composite_window_door_outer_frame_cannot_become_single_window_area() -> None:
    published, authority = _authority(_elevation_pdf(composite=True))

    result = authority.resolve(_selector(published, "W1"))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert OPENING_ELEVATION_FRAME_AREA_UNAVAILABLE in result.reason_codes


def test_remote_witness_bound_dimension_cannot_be_borrowed_by_frame() -> None:
    published, authority = _authority(
        _elevation_pdf(far_width_dimension=True)
    )

    result = authority.resolve(_selector(published, "W1"))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert OPENING_ELEVATION_FRAME_AREA_UNAVAILABLE in result.reason_codes


def test_unknown_mark_never_inherits_another_elevation_frame() -> None:
    published, authority = _authority(_elevation_pdf())

    result = authority.resolve(_selector(published, "W2"))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
