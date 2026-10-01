from __future__ import annotations

import fitz

from pb_live_canonical_room_composition import (
    LIVE_CANONICAL_ROOM_PARTIAL,
    LIVE_CANONICAL_ROOM_RESOLVED,
    LIVE_CANONICAL_ROOM_UNAVAILABLE,
    compose_live_canonical_rooms,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer


def _page(doc: fitz.Document, *, with_partition: bool) -> None:
    page = doc.new_page(width=300, height=200)
    lines = [
        ((50.0, 50.0), (250.0, 50.0)),
        ((250.0, 50.0), (250.0, 150.0)),
        ((250.0, 150.0), (50.0, 150.0)),
        ((50.0, 150.0), (50.0, 50.0)),
    ]
    if with_partition:
        lines.append(((150.0, 50.0), (150.0, 150.0)))
    for first, second in lines:
        page.draw_line(
            fitz.Point(*first),
            fitz.Point(*second),
            color=(0, 0, 0),
            width=1,
        )
def _source(*, page_partitions: tuple[bool, ...]):
    doc = fitz.open()
    try:
        for with_partition in page_partitions:
            _page(doc, with_partition=with_partition)
        payload = doc.tobytes()
    finally:
        doc.close()

    source = SourceVisibilityProducer(
        producer_method="live-canonical-room-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="live-canonical-room-test-doc",
        source_bytes=payload,
        source_locator="memory://live-canonical-room-test.pdf",
    )
    page_ids = tuple(str(index + 1) for index in range(len(page_partitions)))
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=page_ids,
    )
    return source, wall_opening


def test_two_room_source_publishes_stable_canonical_room_objects() -> None:
    source, wall_opening = _source(page_partitions=(True,))

    result = compose_live_canonical_rooms(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (LIVE_CANONICAL_ROOM_RESOLVED,)
    assert result.source_pages == (1,)
    assert len(result.rooms) == 2
    ids = {room.canonical_room_id for room in result.rooms}
    assert len(ids) == 2
    for room in result.rooms:
        assert room.canonical_room_id == room.physical_room_id
        assert room.page_id == "1"
        assert room.viewport_id is None
        assert room.coordinate_unit == "pdf_pt"
        assert room.geometry_complete is True
        assert room.metric_geometry_complete is False
        assert len(room.polygon_pdf_pts) >= 4
        assert room.bounding_wall_ids
        assert room.area_page_pts2 > 0.0
        assert room.evidence_ids == (room.source_room_face_record_id,)
        payload = room.to_dict()
        assert payload["canonical_room_id"] == room.canonical_room_id
        assert payload["polygon_pdf_pts"]
        assert payload["bounding_wall_ids"]


def test_single_box_fails_closed_without_minting_room_object() -> None:
    source, wall_opening = _source(page_partitions=(False,))

    result = compose_live_canonical_rooms(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert LIVE_CANONICAL_ROOM_UNAVAILABLE in result.reason_codes
    assert result.rooms == ()
    assert result.source_pages == ()


def test_mixed_page_resolution_is_candidate_not_corroborated() -> None:
    source, wall_opening = _source(page_partitions=(True, False))

    result = compose_live_canonical_rooms(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.reason_codes[0] == LIVE_CANONICAL_ROOM_PARTIAL
    assert result.source_pages == (1,)
    assert len(result.rooms) == 2
