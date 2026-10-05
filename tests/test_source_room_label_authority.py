from __future__ import annotations

import fitz

from pb_live_canonical_room_composition import compose_live_canonical_rooms
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_room_label_authority import (
    SOURCE_ROOM_LABEL_RESOLVED,
    SOURCE_ROOM_LABEL_TEXT_CONFLICT,
    SOURCE_ROOM_LABEL_UNAVAILABLE,
    bind_source_room_labels,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _labelled_source(*labels: tuple[str, tuple[float, float]]):
    doc = fitz.open()
    try:
        page = doc.new_page(width=300, height=200)
        for first, second in (
            ((50.0, 50.0), (250.0, 50.0)),
            ((250.0, 50.0), (250.0, 150.0)),
            ((250.0, 150.0), (50.0, 150.0)),
            ((50.0, 150.0), (50.0, 50.0)),
            ((150.0, 50.0), (150.0, 150.0)),
        ):
            page.draw_line(
                fitz.Point(*first),
                fitz.Point(*second),
                color=(0, 0, 0),
                width=1,
            )
        for text, point in labels:
            page.insert_text(fitz.Point(*point), text, fontsize=10)
        payload = doc.tobytes()
    finally:
        doc.close()

    source = SourceVisibilityProducer(
        producer_method="room-label-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="room-label-test-doc",
        source_bytes=payload,
        source_locator="memory://room-label-test.pdf",
    )
    from pb_live_wall_opening_authority_composition import (
        compose_live_wall_opening_authority,
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
    return source, result.rooms


def test_trusted_label_binds_only_to_existing_room() -> None:
    source, rooms = _labelled_source(("OFFICE", (85.0, 100.0)))

    assert len(rooms) == 2
    labelled = [room for room in rooms if room.room_label == "OFFICE"]
    assert len(labelled) == 1
    room = labelled[0]
    assert room.room_label_binding_record_id
    assert room.room_label_evidence_ids
    assert room.room_label_reason_codes == (SOURCE_ROOM_LABEL_RESOLVED,)
    assert room.canonical_room_id == room.physical_room_id
    assert room.polygon_pdf_pts

    bindings = bind_source_room_labels(source, rooms)
    binding = bindings[room.canonical_room_id]
    assert binding.status is EvidenceResolutionStatus.CORROBORATED
    assert binding.record_id == room.room_label_binding_record_id
    assert binding.evidence_ids == room.room_label_evidence_ids


def test_two_distinct_authenticated_labels_in_one_room_conflict() -> None:
    source, rooms = _labelled_source(
        ("OFFICE", (80.0, 95.0)),
        ("LAUNDRY", (80.0, 120.0)),
    )
    target = min(
        rooms,
        key=lambda room: min(x for x, _y in room.polygon_pdf_pts),
    )
    bindings = bind_source_room_labels(source, rooms)
    binding = bindings[target.canonical_room_id]

    assert binding.status is EvidenceResolutionStatus.CONFLICT
    assert binding.label is None
    assert binding.reason_codes == (SOURCE_ROOM_LABEL_TEXT_CONFLICT,)
    assert target.room_label is None
    assert target.canonical_room_id == target.physical_room_id


def test_duplicate_same_label_deduplicates_to_one_binding() -> None:
    source, rooms = _labelled_source(
        ("OFFICE", (80.0, 95.0)),
        ("OFFICE", (80.0, 120.0)),
    )
    target = min(
        rooms,
        key=lambda room: min(x for x, _y in room.polygon_pdf_pts),
    )
    binding = bind_source_room_labels(source, rooms)[target.canonical_room_id]

    assert binding.status is EvidenceResolutionStatus.CORROBORATED
    assert binding.label == "OFFICE"
    assert len(binding.evidence_ids) >= 2


def test_label_outside_proven_rooms_creates_nothing() -> None:
    _source, rooms = _labelled_source(("OFFICE", (275.0, 180.0)))

    assert len(rooms) == 2
    assert all(room.room_label is None for room in rooms)
    assert all(
        room.room_label_reason_codes == (SOURCE_ROOM_LABEL_UNAVAILABLE,)
        for room in rooms
    )


def test_room_ids_and_geometry_stay_stable_when_label_text_changes() -> None:
    _source_a, rooms_a = _labelled_source(("OFFICE", (85.0, 100.0)))
    _source_b, rooms_b = _labelled_source(("LAUNDRY", (85.0, 100.0)))

    assert [room.canonical_room_id for room in rooms_a] == [
        room.canonical_room_id for room in rooms_b
    ]
    assert [room.physical_room_id for room in rooms_a] == [
        room.physical_room_id for room in rooms_b
    ]
    assert [room.polygon_pdf_pts for room in rooms_a] == [
        room.polygon_pdf_pts for room in rooms_b
    ]
    assert [room.source_room_face_record_id for room in rooms_a] != [
        room.source_room_face_record_id for room in rooms_b
    ]


def test_unlabelled_room_remains_explicitly_unavailable() -> None:
    _source, rooms = _labelled_source(("OFFICE", (85.0, 100.0)))

    unlabelled = [room for room in rooms if room.room_label is None]
    assert len(unlabelled) == 1
    assert unlabelled[0].room_label_binding_record_id is None
    assert unlabelled[0].room_label_reason_codes == (
        SOURCE_ROOM_LABEL_UNAVAILABLE,
    )
