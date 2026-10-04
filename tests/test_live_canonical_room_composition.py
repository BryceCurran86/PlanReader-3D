from __future__ import annotations

import fitz

from pb_live_canonical_room_composition import (
    LIVE_CANONICAL_ROOM_PARTIAL,
    LIVE_CANONICAL_ROOM_FACE_UNIVERSE_PARTIAL,
    LIVE_CANONICAL_ROOM_RESOLVED,
    LIVE_CANONICAL_ROOM_UNAVAILABLE,
    LIVE_CANONICAL_ROOM_VIEWPORT_FALLBACK_RESOLVED,
    compose_live_canonical_rooms,
)
from pb_live_canonical_wall_composition import compose_live_canonical_walls
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

    wall_core = compose_live_canonical_walls(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    result = compose_live_canonical_rooms(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
        canonical_wall_ids_by_candidate=(
            wall_core.candidate_to_canonical_wall_id
        ),
        unresolved_wall_candidate_ids=(
            wall_core.unresolved_wall_candidate_ids
        ),
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
        assert room.canonical_bounding_wall_ids
        assert room.wall_relationships_complete is False
        assert room.area_page_pts2 > 0.0
        assert room.evidence_ids == (room.source_room_face_record_id,)
        payload = room.to_dict()
        assert payload["canonical_room_id"] == room.canonical_room_id
        assert payload["polygon_pdf_pts"]
        assert payload["bounding_wall_ids"]
        assert payload["canonical_bounding_wall_ids"]
        assert payload["wall_relationships_complete"] is False


def test_valid_rooms_publish_but_partial_face_universe_stays_candidate() -> None:
    doc = fitz.open()
    try:
        page = doc.new_page(width=400, height=250)
        for first, second in (
            ((50.0, 50.0), (250.0, 50.0)),
            ((250.0, 50.0), (250.0, 150.0)),
            ((250.0, 150.0), (50.0, 150.0)),
            ((50.0, 150.0), (50.0, 50.0)),
            ((150.0, 50.0), (150.0, 150.0)),
            # A speck larger than the wall graph's 2.5pt gap-snap tolerance (a
            # smaller one is snapped away and never becomes a face) yet far under
            # 1% of the largest face, so it is a genuine degenerate face.
            ((300.0, 50.0), (306.0, 50.0)),
            ((306.0, 50.0), (306.0, 56.0)),
            ((306.0, 56.0), (300.0, 56.0)),
            ((300.0, 56.0), (300.0, 50.0)),
        ):
            page.draw_line(
                fitz.Point(*first),
                fitz.Point(*second),
                color=(0, 0, 0),
                width=1,
            )
        payload = doc.tobytes()
    finally:
        doc.close()

    source = SourceVisibilityProducer(
        producer_method="live-canonical-room-partial-universe-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="live-canonical-room-partial-universe-doc",
        source_bytes=payload,
        source_locator="memory://live-canonical-room-partial-universe.pdf",
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )

    result = compose_live_canonical_rooms(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert LIVE_CANONICAL_ROOM_PARTIAL in result.reason_codes
    assert LIVE_CANONICAL_ROOM_FACE_UNIVERSE_PARTIAL in result.reason_codes
    assert result.source_pages == (1,)
    assert len(result.rooms) == 2


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


def _viewport_fallback_source():
    doc = fitz.open()
    try:
        page = doc.new_page(width=400.0, height=300.0)

        # Positive physical drawing ownership: one real native vector frame.
        page.draw_rect(
            fitz.Rect(30.0, 30.0, 300.0, 270.0),
            color=(0, 0, 0),
            width=1.0,
        )
        page.insert_text((80.0, 60.0), "GROUND FLOOR PLAN", fontsize=10.0)

        # Reference content exists elsewhere on the same sheet. The title is
        # explicit but intentionally unbounded, and one source line sits in
        # that reference region. Whole-page wall ownership must therefore fail
        # closed rather than absorbing it into the floor-plan topology.
        page.insert_text((325.0, 70.0), "LEGEND", fontsize=10.0)
        page.draw_line(
            fitz.Point(325.0, 150.0),
            fitz.Point(385.0, 150.0),
            color=(0, 0, 0),
            width=1.0,
        )

        # Two closed rooms wholly inside the authenticated floor-plan frame.
        for first, second in (
            ((70.0, 90.0), (270.0, 90.0)),
            ((270.0, 90.0), (270.0, 240.0)),
            ((270.0, 240.0), (70.0, 240.0)),
            ((70.0, 240.0), (70.0, 90.0)),
            ((170.0, 90.0), (170.0, 240.0)),
        ):
            page.draw_line(
                fitz.Point(*first),
                fitz.Point(*second),
                color=(0, 0, 0),
                width=1.0,
            )

        payload = doc.tobytes()
    finally:
        doc.close()

    source = SourceVisibilityProducer(
        producer_method="live-canonical-room-viewport-fallback-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="live-canonical-room-viewport-fallback-doc",
        source_bytes=payload,
        source_locator="memory://live-canonical-room-viewport-fallback.pdf",
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    return source, wall_opening


def test_unresolved_page_room_scope_falls_back_to_authenticated_floor_plan_viewport() -> None:
    source, wall_opening = _viewport_fallback_source()

    result = compose_live_canonical_rooms(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (
        LIVE_CANONICAL_ROOM_RESOLVED,
        LIVE_CANONICAL_ROOM_VIEWPORT_FALLBACK_RESOLVED,
    )
    assert result.source_pages == (1,)
    assert len(result.rooms) == 2
    assert all(room.viewport_id for room in result.rooms)
    assert all(
        room.decision_scope_id.startswith("wall-source:viewport:1:")
        for room in result.rooms
    )
    assert all(room.geometry_complete is True for room in result.rooms)
    assert all(room.metric_geometry_complete is False for room in result.rooms)
    # The fallback does not guess a relationship to page-wide canonical walls.
    assert all(room.canonical_bounding_wall_ids == () for room in result.rooms)
    assert all(room.wall_relationships_complete is False for room in result.rooms)
