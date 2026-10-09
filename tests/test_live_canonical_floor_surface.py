from __future__ import annotations

from dataclasses import replace

from pb_live_canonical_floor_surface import (
    LIVE_CANONICAL_FLOOR_METRIC_AREA_CONFLICT,
    LIVE_CANONICAL_FLOOR_METRIC_AREA_RESOLVED,
    LIVE_CANONICAL_FLOOR_METRIC_AREA_PARTIAL,
    LIVE_CANONICAL_FLOOR_METRIC_AREA_UNAVAILABLE,
    LIVE_CANONICAL_FLOOR_SURFACE_RESOLVED,
    LIVE_CANONICAL_FLOOR_SURFACE_PARTIAL,
    LIVE_CANONICAL_FLOOR_SURFACE_UNAVAILABLE,
    LiveCanonicalFloorSurfaceComposition,
    LiveCanonicalFloorSurfaceObject,
    compose_live_canonical_floor_surfaces,
    enrich_live_canonical_floor_metric_areas,
)
from pb_live_canonical_room_composition import compose_live_canonical_rooms
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_live_canonical_room_composition import _source
from tests.test_source_room_area_bridge_v1 import (
    _authority,
    _context,
    _document,
    _explicit_area,
    _firm_scale,
    _viewport,
    _write_plan,
)
from pb_source_room_area_bridge import build_source_room_area_bridge


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
        assert floor.physical_floor_surface_identity_resolved is True
        assert floor.commercial_quantity_authority is False
        assert floor.polygon_pdf_pts
        assert floor.area_page_pts2 > 0.0
        assert floor.source_room_face_record_id
        assert floor.evidence_ids == (floor.source_room_face_record_id,)
        payload = floor.to_dict()
        assert payload["canonical_floor_id"] == floor.canonical_floor_id
        assert payload["physical_floor_surface_id"] == floor.physical_floor_surface_id
        assert floor.canonical_floor_id == floor.physical_floor_surface_id
        assert payload["room_entity_id"] == floor.room_entity_id
        assert payload["coordinate_space"] == "source_page_points"


def test_floor_identity_is_stable_across_room_evidence_revision_churn() -> None:
    source, wall_opening = _source(page_partitions=(True,))
    rooms = compose_live_canonical_rooms(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    first = compose_live_canonical_floor_surfaces(rooms)

    changed_rooms = replace(
        rooms,
        rooms=tuple(
            replace(
                room,
                canonical_room_id=f"changed-canonical:{room.canonical_room_id}",
                revision_id="revision-2",
                source_sha256="f" * 64,
                snapshot_id="snapshot-2",
                source_room_face_record_id=f"changed-face:{room.source_room_face_record_id}",
                evidence_ids=(f"changed-evidence:{room.source_room_face_record_id}",),
            )
            for room in rooms.rooms
        ),
    )
    second = compose_live_canonical_floor_surfaces(changed_rooms)

    assert [floor.physical_floor_surface_id for floor in first.floors] == [
        floor.physical_floor_surface_id for floor in second.floors
    ]
    assert [floor.canonical_floor_id for floor in first.floors] == [
        floor.canonical_floor_id for floor in second.floors
    ]


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



def _floor_composition_from_bridge(published, bridge):
    assert bridge.room_index is not None
    floors = []
    for room in bridge.room_index.rooms():
        evidence_ids = tuple(room.evidence)
        floors.append(
            LiveCanonicalFloorSurfaceObject(
                canonical_floor_id=f"floor:{room.room_ref}",
                physical_floor_surface_id=f"floor:{room.room_ref}",
                room_entity_id=f"physical-room:{room.room_ref}",
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id="1",
                viewport_id=None,
                polygon_pdf_pts=tuple(room.polygon_pdf_pts),
                area_page_pts2=float(room.area_page_pts2),
                bounding_wall_ids=(),
                canonical_bounding_wall_ids=(),
                source_room_face_record_id=evidence_ids[0],
                evidence_ids=evidence_ids,
                geometry_complete=True,
                metric_geometry_complete=False,
                metric_area_m2=None,
                metric_area_quantity_id=None,
                metric_area_authority=None,
                finish_descriptor=None,
                structural_slab_id=None,
                physical_floor_surface_identity_resolved=False,
                commercial_quantity_authority=False,
            )
        )
    return LiveCanonicalFloorSurfaceComposition(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(LIVE_CANONICAL_FLOOR_SURFACE_RESOLVED,),
        floors=tuple(floors),
        source_pages=(1,),
    )


def test_firm_source_room_area_enriches_same_floor_identity(tmp_path) -> None:
    path = tmp_path / "metric-floor-area.pdf"
    _write_plan(path)
    published, room_faces, selector = _authority(path)
    bridge = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=_document(published),
        viewport=_viewport(published),
        page_no=1,
        scale_calibration=_firm_scale(published),
    )
    floors = _floor_composition_from_bridge(published, bridge)
    before_ids = [floor.canonical_floor_id for floor in floors.floors]

    enriched = enrich_live_canonical_floor_metric_areas(floors, bridge)

    assert enriched.status is EvidenceResolutionStatus.CORROBORATED
    assert LIVE_CANONICAL_FLOOR_METRIC_AREA_RESOLVED in enriched.reason_codes
    assert [floor.canonical_floor_id for floor in enriched.floors] == before_ids
    assert len(enriched.floors) == 2
    quantities = {
        quantity.input_entity_ids[0]: quantity
        for quantity in bridge.quantities
        if not quantity.abstained
    }
    entities = {entity.candidate_entity_id: entity for entity in bridge.entities}
    for floor in enriched.floors:
        source_room_id = next(
            room_id
            for room_id, entity in entities.items()
            if floor.source_room_face_record_id in entity.evidence_ids
        )
        quantity = quantities[source_room_id]
        assert floor.room_entity_id != source_room_id
        assert floor.metric_area_m2 == quantity.value
        assert floor.metric_area_quantity_id == quantity.quantity_id
        assert floor.metric_area_authority == quantity.authority
        assert floor.metric_geometry_complete is False
        assert floor.commercial_quantity_authority is False
        assert floor.finish_descriptor is None
        assert floor.structural_slab_id is None


def test_explicit_room_area_without_scale_enriches_physical_room_floor(
    tmp_path,
) -> None:
    path = tmp_path / "metric-floor-explicit-area.pdf"
    _write_plan(path)
    published, room_faces, selector = _authority(path)
    baseline = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=_document(published),
        viewport=_viewport(published),
        page_no=1,
    )
    assert baseline.room_index is not None
    target_room = baseline.room_index.rooms()[0].room_ref
    evidence = _explicit_area(
        published,
        evidence_id="cross-view-explicit-floor-area",
        value=12.345,
    )
    bridge = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=_document(published),
        viewport=_viewport(published),
        page_no=1,
        explicit_area_evidence_by_room_id={target_room: evidence},
    )
    floors = _floor_composition_from_bridge(published, bridge)

    enriched = enrich_live_canonical_floor_metric_areas(floors, bridge)

    target_entity = next(
        entity for entity in bridge.entities
        if entity.candidate_entity_id == target_room
    )
    target_floor = next(
        floor for floor in enriched.floors
        if floor.source_room_face_record_id in target_entity.evidence_ids
    )
    assert target_floor.room_entity_id != target_room
    assert target_floor.metric_area_m2 == 12.345
    assert target_floor.metric_area_quantity_id
    assert target_floor.metric_area_authority

    other_floors = [
        floor for floor in enriched.floors
        if floor.canonical_floor_id != target_floor.canonical_floor_id
    ]
    assert other_floors
    assert all(floor.metric_area_m2 is None for floor in other_floors)


def test_missing_scale_keeps_floor_identity_but_metric_area_unresolved(
    tmp_path,
) -> None:
    path = tmp_path / "metric-floor-no-scale.pdf"
    _write_plan(path)
    published, room_faces, selector = _authority(path)
    bridge = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=_document(published),
        viewport=_viewport(published),
        page_no=1,
        scale_calibration=None,
    )
    floors = _floor_composition_from_bridge(published, bridge)

    enriched = enrich_live_canonical_floor_metric_areas(floors, bridge)

    assert enriched.status is EvidenceResolutionStatus.CORROBORATED
    assert LIVE_CANONICAL_FLOOR_METRIC_AREA_UNAVAILABLE in enriched.reason_codes
    assert all(floor.metric_area_m2 is None for floor in enriched.floors)
    assert all(
        floor.canonical_floor_id == original.canonical_floor_id
        for floor, original in zip(enriched.floors, floors.floors)
    )


def test_metric_area_lineage_mismatch_does_not_attach(tmp_path) -> None:
    path = tmp_path / "metric-floor-lineage.pdf"
    _write_plan(path)
    published, room_faces, selector = _authority(path)
    bridge = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=_document(published),
        viewport=_viewport(published),
        page_no=1,
        scale_calibration=_firm_scale(published),
    )
    floors = _floor_composition_from_bridge(published, bridge)
    wrong = replace(
        floors,
        floors=tuple(
            replace(floor, revision_id="different-revision")
            for floor in floors.floors
        ),
    )

    enriched = enrich_live_canonical_floor_metric_areas(wrong, bridge)

    assert LIVE_CANONICAL_FLOOR_METRIC_AREA_UNAVAILABLE in enriched.reason_codes
    assert all(floor.metric_area_m2 is None for floor in enriched.floors)


def test_canonical_floor_enrichment_rejects_alien_room_snapshot_or_face(
    tmp_path,
) -> None:
    path = tmp_path / "floor-area-room-source-ownership.pdf"
    _write_plan(path)
    published, room_faces, selector = _authority(path)
    bridge = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=_document(published),
        viewport=_viewport(published),
        page_no=1,
        scale_calibration=_firm_scale(published),
    )
    floors = _floor_composition_from_bridge(published, bridge)
    source = next(
        q for q in bridge.quantities
        if not q.abstained and q.value is not None
    )
    entity = next(
        e for e in bridge.entities
        if e.candidate_entity_id == source.input_entity_ids[0]
    )
    target_floor = next(
        floor for floor in floors.floors
        if floor.source_room_face_record_id in entity.evidence_ids
    )

    # Positive source ownership: the room snapshot matches, while a separate
    # dimension-support snapshot remains legitimate and independent.
    valid = replace(
        source,
        metadata={
            **dict(source.metadata or {}),
            "room_snapshot_id": target_floor.snapshot_id,
            "source_room_face_record_id": target_floor.source_room_face_record_id,
            "source_dimension_snapshot_id": "independent-dimension-support",
        },
    )
    accepted = replace(
        bridge,
        quantities=tuple(valid if q is source else q for q in bridge.quantities),
    )
    positive = enrich_live_canonical_floor_metric_areas(floors, accepted)
    positive_floor = next(
        floor for floor in positive.floors
        if floor.canonical_floor_id == target_floor.canonical_floor_id
    )
    assert positive_floor.metric_area_m2 == float(source.value)

    for corrupt in (
        {"room_snapshot_id": "alien-room-snapshot"},
        {"source_room_face_record_id": "alien-physical-room-face"},
    ):
        mismatched = replace(
            valid, metadata={**dict(valid.metadata), **corrupt}
        )
        rejected = replace(
            bridge,
            quantities=tuple(
                mismatched if q is source else q
                for q in bridge.quantities
            ),
        )
        enriched = enrich_live_canonical_floor_metric_areas(floors, rejected)
        rejected_floor = next(
            floor for floor in enriched.floors
            if floor.canonical_floor_id == target_floor.canonical_floor_id
        )
        assert rejected_floor.metric_area_m2 is None
        assert rejected_floor.metric_area_quantity_id is None
        assert rejected_floor.metric_area_authority is None


def test_duplicate_identical_room_area_authority_is_idempotent(tmp_path) -> None:
    path = tmp_path / "metric-floor-duplicate.pdf"
    _write_plan(path)
    published, room_faces, selector = _authority(path)
    bridge = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=_document(published),
        viewport=_viewport(published),
        page_no=1,
        scale_calibration=_firm_scale(published),
    )
    floors = _floor_composition_from_bridge(published, bridge)
    duplicated = replace(
        bridge,
        quantities=(
            bridge.quantities[0],
            bridge.quantities[0],
            *bridge.quantities[1:],
        ),
    )

    enriched = enrich_live_canonical_floor_metric_areas(floors, duplicated)

    # A byte-for-byte replay is the same source authority, not two claims.
    baseline = enrich_live_canonical_floor_metric_areas(floors, bridge)
    assert enriched == baseline
    assert enriched.status is EvidenceResolutionStatus.CORROBORATED


def test_sequential_room_area_bridges_replay_or_conflict_without_overwrite(
    tmp_path,
) -> None:
    path = tmp_path / "metric-floor-sequential-authority.pdf"
    _write_plan(path)
    published, room_faces, selector = _authority(path)
    bridge = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=_document(published),
        viewport=_viewport(published),
        page_no=1,
        scale_calibration=_firm_scale(published),
    )
    original = _floor_composition_from_bridge(published, bridge)
    measured = enrich_live_canonical_floor_metric_areas(original, bridge)
    assert all(floor.metric_area_quantity_id for floor in measured.floors)

    # Repeating the identical producer-owned claim is idempotent.
    replay = enrich_live_canonical_floor_metric_areas(measured, bridge)
    assert replay.status is EvidenceResolutionStatus.CORROBORATED
    assert replay.floors == measured.floors

    # An independently supplied FIRM record for the same physical floor
    # must not replace the first authenticated quantity.
    contradictory = replace(
        bridge,
        quantities=tuple(
            replace(
                quantity,
                quantity_id=f"conflicting:{quantity.quantity_id}",
                value=float(quantity.value) + 1.0,
            )
            if not quantity.abstained
            else quantity
            for quantity in bridge.quantities
        ),
    )
    result = enrich_live_canonical_floor_metric_areas(measured, contradictory)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.reason_codes == (LIVE_CANONICAL_FLOOR_METRIC_AREA_CONFLICT,)
    assert all(floor.metric_area_m2 is None for floor in result.floors)
    assert all(floor.metric_area_quantity_id is None for floor in result.floors)
    assert all(floor.metric_area_authority is None for floor in result.floors)
    assert [floor.physical_floor_surface_id for floor in result.floors] == [
        floor.physical_floor_surface_id for floor in measured.floors
    ]
    assert enrich_live_canonical_floor_metric_areas(result, bridge) == result

    # Even a changed value under a replayed identifier cannot remeasure
    # an already attached floor.
    tampered_replay = replace(
        bridge,
        quantities=tuple(
            replace(quantity, value=float(quantity.value) + 1.0)
            if not quantity.abstained
            else quantity
            for quantity in bridge.quantities
        ),
    )
    result = enrich_live_canonical_floor_metric_areas(measured, tampered_replay)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert all(floor.metric_area_quantity_id is None for floor in result.floors)
    assert all(floor.metric_area_m2 is None for floor in result.floors)


def test_blocked_or_model_derived_firm_area_cannot_enrich_canonical_floor(tmp_path) -> None:
    path = tmp_path / "floor-measurement-authority-failclosed.pdf"
    _write_plan(path)
    published, room_faces, selector = _authority(path)
    bridge = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=_document(published),
        viewport=_viewport(published),
        page_no=1,
        scale_calibration=_firm_scale(published),
    )
    floors = _floor_composition_from_bridge(published, bridge)
    assert any(not q.abstained for q in bridge.quantities)

    for mutate in (
        lambda q: replace(q, blocking_reasons=("unresolved_measurement",)),
        lambda q: replace(q, authority="model_derived"),
        lambda q: replace(q, authority="schedule_extracted"),
    ):
        suspect = replace(
            bridge,
            quantities=tuple(
                mutate(q) if not q.abstained else q
                for q in bridge.quantities
            ),
        )
        enriched = enrich_live_canonical_floor_metric_areas(floors, suspect)
        assert all(floor.metric_area_m2 is None for floor in enriched.floors)
        assert all(floor.metric_area_quantity_id is None for floor in enriched.floors)
        assert all(floor.metric_area_authority is None for floor in enriched.floors)

    # The same real producer-owned FIRM scaled evidence still enriches.
    accepted = enrich_live_canonical_floor_metric_areas(floors, bridge)
    assert all(floor.metric_area_m2 for floor in accepted.floors)


def test_metric_floor_status_closes_after_separate_source_bridges(tmp_path) -> None:
    path = tmp_path / "separate-room-bridge-metric-closure.pdf"
    _write_plan(path)
    published, room_faces, selector = _authority(path)
    bridge = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=_document(published),
        viewport=_viewport(published),
        page_no=1,
        scale_calibration=_firm_scale(published),
    )
    original = _floor_composition_from_bridge(published, bridge)
    firm = tuple(q for q in bridge.quantities if not q.abstained)
    assert len(original.floors) == len(firm) == 2

    first = replace(bridge, quantities=(firm[0],))
    second = replace(bridge, quantities=(firm[1],))
    partial = enrich_live_canonical_floor_metric_areas(original, first)
    assert partial.status is EvidenceResolutionStatus.CANDIDATE
    assert partial.reason_codes == (
        LIVE_CANONICAL_FLOOR_SURFACE_RESOLVED,
        LIVE_CANONICAL_FLOOR_METRIC_AREA_PARTIAL,
    )
    assert sum(bool(floor.metric_area_quantity_id) for floor in partial.floors) == 1

    complete = enrich_live_canonical_floor_metric_areas(partial, second)
    assert complete.status is EvidenceResolutionStatus.CORROBORATED
    assert complete.reason_codes == (
        LIVE_CANONICAL_FLOOR_SURFACE_RESOLVED,
        LIVE_CANONICAL_FLOOR_METRIC_AREA_RESOLVED,
    )
    assert all(floor.metric_area_quantity_id for floor in complete.floors)
    assert enrich_live_canonical_floor_metric_areas(complete, first) == complete

    # Independent source-bridge order must not alter complete floor state.
    other_order = enrich_live_canonical_floor_metric_areas(
        enrich_live_canonical_floor_metric_areas(original, second),
        first,
    )
    assert other_order == complete


def test_metric_completion_does_not_override_partial_physical_room_universe(
    tmp_path,
) -> None:
    path = tmp_path / "partial-room-topology-metric-closure.pdf"
    _write_plan(path)
    published, room_faces, selector = _authority(path)
    bridge = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=_document(published),
        viewport=_viewport(published),
        page_no=1,
        scale_calibration=_firm_scale(published),
    )
    original = _floor_composition_from_bridge(published, bridge)
    upstream_partial = replace(
        original,
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(
            LIVE_CANONICAL_FLOOR_SURFACE_PARTIAL,
            "source_room_universe_incomplete",
        ),
    )
    enriched = enrich_live_canonical_floor_metric_areas(
        upstream_partial, bridge
    )
    assert all(floor.metric_area_quantity_id for floor in enriched.floors)
    assert enriched.status is EvidenceResolutionStatus.CANDIDATE
    assert enriched.reason_codes == (
        LIVE_CANONICAL_FLOOR_SURFACE_PARTIAL,
        "source_room_universe_incomplete",
        LIVE_CANONICAL_FLOOR_METRIC_AREA_RESOLVED,
    )


def test_candidate_source_room_entity_does_not_enrich_metric_floor(tmp_path) -> None:
    path = tmp_path / "metric-floor-candidate-entity.pdf"
    _write_plan(path)
    published, room_faces, selector = _authority(path)
    bridge = build_source_room_area_bridge(
        room_face_authority=room_faces,
        selector=selector,
        context=_context(published),
        document=_document(published),
        viewport=_viewport(published),
        page_no=1,
        scale_calibration=_firm_scale(published),
    )
    floors = _floor_composition_from_bridge(published, bridge)
    candidate_entities = tuple(
        replace(entity, status=EvidenceResolutionStatus.CANDIDATE)
        for entity in bridge.entities
    )
    weakened_bridge = replace(bridge, entities=candidate_entities)
    result = enrich_live_canonical_floor_metric_areas(floors, weakened_bridge)
    assert len(result.floors) == len(floors.floors)
    assert all(floor.metric_area_m2 is None for floor in result.floors)
    assert all(floor.metric_area_quantity_id is None for floor in result.floors)
