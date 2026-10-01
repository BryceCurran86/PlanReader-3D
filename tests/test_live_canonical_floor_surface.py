from __future__ import annotations

from pb_live_canonical_floor_surface import (
    LIVE_CANONICAL_FLOOR_SURFACE_RESOLVED,
    LIVE_CANONICAL_FLOOR_SURFACE_UNAVAILABLE,
    compose_live_canonical_floor_surfaces,
)
from pb_live_canonical_room_composition import compose_live_canonical_rooms
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_live_canonical_room_composition import _source


def test_two_authenticated_rooms_create_two_floor_surface_objects() -> None:
    source, wall_opening = _source(page_partitions=(True,))
    rooms = compose_live_canonical_rooms(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    floors = compose_live_canonical_floor_surfaces(rooms)

    assert floors.status is EvidenceResolutionStatus.CORROBORATED
    assert floors.reason_codes == (LIVE_CANONICAL_FLOOR_SURFACE_RESOLVED,)
    assert floors.source_pages == (1,)
    assert len(floors.floors) == 2
    assert len({floor.canonical_floor_id for floor in floors.floors}) == 2

    room_ids = {room.canonical_room_id for room in rooms.rooms}
    assert {floor.room_entity_id for floor in floors.floors} == room_ids

    for floor in floors.floors:
        assert floor.geometry_complete is True
        assert floor.metric_geometry_complete is False
        assert floor.metric_area_m2 is None
        assert floor.metric_area_quantity_id is None
        assert floor.metric_area_authority is None
        assert floor.finish_descriptor is None
        assert floor.structural_slab_id is None
        assert floor.physical_floor_surface_identity_resolved is False
        assert floor.commercial_quantity_authority is False
        assert floor.polygon_pdf_pts
        assert floor.area_page_pts2 > 0.0
        assert floor.source_room_face_record_id
        assert floor.evidence_ids == (floor.source_room_face_record_id,)
        payload = floor.to_dict()
        assert payload["canonical_floor_id"] == floor.canonical_floor_id
        assert payload["room_entity_id"] == floor.room_entity_id
        assert payload["coordinate_space"] == "source_page_points"


def test_unresolved_room_scope_does_not_create_floor_surface() -> None:
    source, wall_opening = _source(page_partitions=(False,))
    rooms = compose_live_canonical_rooms(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    floors = compose_live_canonical_floor_surfaces(rooms)

    assert floors.status is EvidenceResolutionStatus.ABSTAINED
    assert floors.reason_codes == (LIVE_CANONICAL_FLOOR_SURFACE_UNAVAILABLE,)
    assert floors.floors == ()
    assert floors.source_pages == ()


def test_floor_projection_is_deterministic_for_same_room_identity() -> None:
    source, wall_opening = _source(page_partitions=(True,))
    rooms = compose_live_canonical_rooms(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    first = compose_live_canonical_floor_surfaces(rooms)
    second = compose_live_canonical_floor_surfaces(rooms)

    assert [floor.to_dict() for floor in first.floors] == [
        floor.to_dict() for floor in second.floors
    ]
