from __future__ import annotations

import inspect
from types import SimpleNamespace

import fitz
import pytest

import pb_live_physical_net_wall_integration as live_integration
from pb_live_physical_net_wall_integration import (
    _uniquely_owned_explicit_area_by_source_face,
    collect_live_physical_net_wall_claim,
)
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_live_physical_opening_void_composition import _complete_void_pdf


def _source_face(record_id: str, face_id: str):
    return SimpleNamespace(record_id=record_id, face_id=face_id)


def _canonical_room_owner(record_id: str, physical_id: str):
    return SimpleNamespace(
        source_room_face_record_id=record_id,
        physical_room_id=physical_id,
    )


def test_unique_documented_area_claim_maps_to_one_source_owned_face() -> None:
    evidence = object()
    assert _uniquely_owned_explicit_area_by_source_face(
        source_face_records=(_source_face("rec-a", "face-1"),),
        canonical_rooms=(_canonical_room_owner("rec-a", "physical-a"),),
        evidence_by_source_record={"rec-a": evidence},
    ) == {"face-1": evidence}


def test_competing_documented_records_for_same_face_fail_closed() -> None:
    retained = object()
    assert _uniquely_owned_explicit_area_by_source_face(
        source_face_records=(
            _source_face("rec-a", "face-1"),
            _source_face("rec-b", "face-1"),
            _source_face("rec-c", "face-2"),
        ),
        canonical_rooms=(
            _canonical_room_owner("rec-a", "physical-a"),
            _canonical_room_owner("rec-b", "physical-b"),
            _canonical_room_owner("rec-c", "physical-c"),
        ),
        evidence_by_source_record={
            "rec-a": object(),
            "rec-b": object(),
            "rec-c": retained,
        },
    ) == {"face-2": retained}


def test_source_record_with_competing_faces_cannot_mint_area() -> None:
    assert _uniquely_owned_explicit_area_by_source_face(
        source_face_records=(
            _source_face("rec-a", "face-1"),
            _source_face("rec-a", "face-2"),
        ),
        canonical_rooms=(_canonical_room_owner("rec-a", "physical-a"),),
        evidence_by_source_record={"rec-a": object()},
    ) == {}


def test_one_source_record_cannot_have_two_canonical_room_owners() -> None:
    assert _uniquely_owned_explicit_area_by_source_face(
        source_face_records=(_source_face("rec-a", "face-1"),),
        canonical_rooms=(
            _canonical_room_owner("rec-a", "physical-a"),
            _canonical_room_owner("rec-a", "physical-b"),
        ),
        evidence_by_source_record={"rec-a": object()},
    ) == {}


def test_exact_source_face_record_replay_is_idempotent() -> None:
    evidence = object()
    assert _uniquely_owned_explicit_area_by_source_face(
        source_face_records=(
            _source_face("rec-a", "face-1"),
            _source_face("rec-a", "face-1"),
        ),
        canonical_rooms=(_canonical_room_owner("rec-a", "physical-a"),),
        evidence_by_source_record={"rec-a": evidence},
    ) == {"face-1": evidence}


def test_live_physical_net_wall_runs_real_source_chain_and_fails_closed_without_height(
    tmp_path,
) -> None:
    path = tmp_path / "physical-net-wall.pdf"
    path.write_bytes(_complete_void_pdf())

    result = collect_live_physical_net_wall_claim(path, pages=(0,))

    # This fixture deliberately has no independent wall-height authority.
    # The live seam must execute the source-owned chain without manufacturing
    # a default-height gross/net wall quantity.
    assert result.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert result.quantity_m2 is None
    assert result.quantity_id is None

    # Semantic wall identity/geometry must survive independently from later
    # height/gross/net-wall quantity authority.
    assert result.canonical_wall_status is EvidenceResolutionStatus.CORROBORATED
    assert result.canonical_walls
    assert all(wall.geometry_complete for wall in result.canonical_walls)
    assert any(
        wall.physical_identity_resolved
        and wall.identity_status == "physical_resolved_by_opening_host_frame"
        for wall in result.canonical_walls
    )
    assert all(
        wall.metric_geometry_complete is False
        for wall in result.canonical_walls
    )

    assert result.canonical_openings
    assert all(
        opening.canonical_opening_id == opening.physical_opening_id
        for opening in result.canonical_openings
    )
    assert result.external_wall_ids == ()


def test_live_physical_net_wall_rejects_empty_or_out_of_range_page_scope(
    tmp_path,
) -> None:
    path = tmp_path / "physical-net-wall.pdf"
    path.write_bytes(_complete_void_pdf())

    with pytest.raises(ValueError):
        collect_live_physical_net_wall_claim(path, pages=())

    with pytest.raises(ValueError):
        collect_live_physical_net_wall_claim(path, pages=(999,))


def test_live_physical_net_wall_accepts_no_quantity_truth_inputs() -> None:
    parameters = set(
        inspect.signature(collect_live_physical_net_wall_claim).parameters
    )
    forbidden = {
        "wall_id",
        "wall_ids",
        "external_wall_ids",
        "gross_area_m2",
        "net_area_m2",
        "opening_area_m2",
        "opening_count",
        "quantity",
        "trade_scope_id",
        "deduction_rule",
        "expected",
        "benchmark",
    }
    assert not (parameters & forbidden)



def test_live_chain_reuses_one_source_owned_physical_scale_producer(
    tmp_path,
    monkeypatch,
) -> None:
    from pb_physical_scale_authority import PhysicalScaleProducer

    path = tmp_path / "physical-net-wall-scale-reuse.pdf"
    path.write_bytes(_complete_void_pdf())

    original_init = PhysicalScaleProducer.__init__
    construction_count = 0

    def counted_init(self, *args, **kwargs):
        nonlocal construction_count
        construction_count += 1
        return original_init(self, *args, **kwargs)

    monkeypatch.setattr(PhysicalScaleProducer, "__init__", counted_init)

    result = collect_live_physical_net_wall_claim(path, pages=(0,))

    assert construction_count == 1
    assert result.canonical_walls
    assert result.canonical_openings


def _two_room_cross_view_area_pdf() -> bytes:
    doc = fitz.open()
    try:
        plan = doc.new_page(width=300.0, height=200.0)
        for first, second in (
            ((50.0, 50.0), (250.0, 50.0)),
            ((250.0, 50.0), (250.0, 150.0)),
            ((250.0, 150.0), (50.0, 150.0)),
            ((50.0, 150.0), (50.0, 50.0)),
            ((150.0, 50.0), (150.0, 150.0)),
        ):
            plan.draw_line(
                fitz.Point(*first),
                fitz.Point(*second),
                color=(0, 0, 0),
                width=1.0,
            )
        plan.insert_text((78.0, 100.0), "OFFICE", fontsize=9.0)
        plan.insert_text((178.0, 100.0), "STUDY", fontsize=9.0)

        detail = doc.new_page(width=400.0, height=300.0)
        detail.insert_text((150.0, 150.0), "OFFICE", fontsize=10.0)
        detail.draw_line((100.0, 80.0), (250.0, 80.0), color=(0, 0, 0), width=1.0)
        detail.draw_line((100.0, 68.0), (100.0, 92.0), color=(0, 0, 0), width=1.0)
        detail.draw_line((250.0, 68.0), (250.0, 92.0), color=(0, 0, 0), width=1.0)
        detail.insert_text((164.0, 77.0), "3600", fontsize=9.0)

        # The vertical dimension shares a real source witness junction with
        # the horizontal dimension at (250, 80). Hardened cross-view area
        # authority requires this positive topology; a merely nearby pair
        # must remain fail-closed.
        detail.draw_line((280.0, 80.0), (280.0, 180.0), color=(0, 0, 0), width=1.0)
        detail.draw_line((250.0, 80.0), (292.0, 80.0), color=(0, 0, 0), width=1.0)
        detail.draw_line((268.0, 180.0), (292.0, 180.0), color=(0, 0, 0), width=1.0)
        detail.insert_text((277.0, 147.0), "2400", fontsize=9.0, rotate=90)
        return doc.tobytes()
    finally:
        doc.close()


def _room_area_with_semantic_only_page_pdf() -> bytes:
    doc = fitz.open(
        stream=_two_room_cross_view_area_pdf(),
        filetype="pdf",
    )
    try:
        semantic = doc.new_page(width=300.0, height=220.0)
        semantic.insert_text((70.0, 80.0), "REFLECTED CEILING PLAN", fontsize=10.0)
        semantic.insert_text((70.0, 110.0), "OFFICE GRID", fontsize=9.0)
        return doc.tobytes()
    finally:
        doc.close()


def test_surface_semantic_pages_use_isolated_source_without_expanding_topology(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "cross-view-room-area-with-semantic.pdf"
    path.write_bytes(_room_area_with_semantic_only_page_pdf())
    seen = {}

    class _FloorProducer:
        @classmethod
        def from_source(
            cls,
            *,
            source,
            room_areas,
            floors,
            same_view_room_areas=None,
        ):
            revision_id = (
                room_areas.records[0].area_evidence.metadata["room_revision_id"]
                if room_areas is not None and room_areas.records
                else same_view_room_areas.records[0].area_evidence.metadata[
                    "room_revision_id"
                ]
            )
            published = source.published_snapshot_for_revision(revision_id)
            assert published is not None
            seen["floor_decoded_pages"] = tuple(published.coverage.decoded_pages)
            seen["floor_semantic_snapshot_id"] = published.snapshot.snapshot_id
            return cls()

        def publish(self):
            return SimpleNamespace(quantities=())

    class _CeilingProducer:
        @classmethod
        def from_source(cls, *, source, rooms):
            revision_id = rooms.rooms[0].revision_id
            published = source.published_snapshot_for_revision(revision_id)
            assert published is not None
            seen["decoded_pages"] = tuple(published.coverage.decoded_pages)
            seen["semantic_snapshot_id"] = published.snapshot.snapshot_id
            seen["room_snapshot_id"] = rooms.rooms[0].snapshot_id
            return cls()

        def publish(self):
            return SimpleNamespace(records=())

    monkeypatch.setattr(
        live_integration,
        "CrossViewFloorFinishProducer",
        _FloorProducer,
    )
    monkeypatch.setattr(
        live_integration,
        "enrich_live_canonical_floor_finishes",
        lambda floors, _finishes: floors,
    )
    monkeypatch.setattr(
        live_integration,
        "CrossViewCeilingFinishProducer",
        _CeilingProducer,
    )

    result = live_integration.collect_live_physical_net_wall_claim(
        path,
        pages=(0,),
        topology_pages=(0,),
        room_area_support_pages=(1,),
        surface_semantic_pages=(2,),
    )

    assert seen["decoded_pages"] == (1, 2, 3)
    assert seen["floor_decoded_pages"] == (1, 2, 3)
    # Both semantic consumers retain source-plan and dimension support evidence.
    # Topology remains scoped to page 1, as asserted below.
    assert (
        seen["floor_semantic_snapshot_id"]
        == seen["semantic_snapshot_id"]
    )
    assert seen["semantic_snapshot_id"] != seen["room_snapshot_id"]
    assert result.canonical_room_source_pages == (1,)
    assert all(room.page_id == "1" for room in result.canonical_rooms)
    assert all(floor.page_id == "1" for floor in result.canonical_floors)
    assert any(
        quantity.value == 8.64
        for quantity in result.room_area_quantity_evidence
        if not quantity.abstained
    )


def test_cross_view_room_area_reaches_same_canonical_floor_without_scale(
    tmp_path,
) -> None:
    path = tmp_path / "cross-view-room-area.pdf"
    path.write_bytes(_two_room_cross_view_area_pdf())
    result = collect_live_physical_net_wall_claim(
        path,
        pages=(0,),
        room_area_support_pages=(1,),
    )

    assert len(result.canonical_rooms) == 2
    assert {room.room_label for room in result.canonical_rooms} == {
        "OFFICE",
        "STUDY",
    }
    assert len(result.canonical_floors) == 2

    # An authenticated cross-view OFFICE measurement must not erase the
    # independent same-view authority's first-failure provenance.
    first_failures = dict(result.same_view_room_area_first_failure_codes)
    assert set(first_failures) == {
        room.physical_room_id for room in result.canonical_rooms
    }
    assert set(first_failures.values()) == {
        "same_view_dimension_orientation_pair_unavailable"
    }
    assert result.same_view_room_area_first_failure_codes == tuple(
        sorted(result.same_view_room_area_first_failure_codes)
    )

    scale_gates = dict(result.physical_scale_first_failure_codes)
    assert set(scale_gates) == {
        room.physical_room_id for room in result.canonical_rooms
    }
    assert all(reason_codes for reason_codes in scale_gates.values())
    assert result.physical_scale_first_failure_codes == tuple(
        sorted(result.physical_scale_first_failure_codes)
    )
    # The independent cross-view documented dimension for OFFICE still
    # publishes FIRM, even though the physical-scale producer abstains.
    assert any(
        quantity.value == 8.64 and not quantity.abstained
        for quantity in result.room_area_quantity_evidence
    )

    resolved_floors = [
        floor for floor in result.canonical_floors
        if floor.metric_area_m2 is not None
    ]
    assert len(resolved_floors) == 1
    resolved_floor = resolved_floors[0]
    office_room = next(
        room for room in result.canonical_rooms
        if room.room_label == "OFFICE"
    )
    assert resolved_floor.room_entity_id == office_room.physical_room_id
    # A resolved documented OFFICE quantity remains independent of STUDY's
    # missing cross-view support label, with both results owned by source rooms.
    study_room = next(
        room for room in result.canonical_rooms if room.room_label == "STUDY"
    )
    cross_failures = dict(result.cross_view_room_area_first_failure_codes)
    assert cross_failures == {
        study_room.physical_room_id: "cross_view_trusted_support_label_unavailable"
    }
    assert office_room.physical_room_id not in cross_failures
    assert result.cross_view_room_area_first_failure_codes == tuple(
        sorted(result.cross_view_room_area_first_failure_codes)
    )
    assert resolved_floor.metric_area_m2 == 8.64
    assert resolved_floor.metric_area_quantity_id
    assert resolved_floor.metric_area_authority
    assert resolved_floor.commercial_quantity_authority is False
    assert resolved_floor.finish_descriptor is None

    firm_room_areas = [
        quantity for quantity in result.room_area_quantity_evidence
        if not quantity.abstained
    ]
    assert len(firm_room_areas) == 1
    assert firm_room_areas[0].value == 8.64
    assert firm_room_areas[0].formula == "authoritative_explicit_area"


def test_room_area_support_pages_do_not_expand_topology_scope(
    tmp_path,
) -> None:
    path = tmp_path / "cross-view-room-area-scope.pdf"
    path.write_bytes(_two_room_cross_view_area_pdf())
    result = collect_live_physical_net_wall_claim(
        path,
        pages=(0,),
        topology_pages=(0,),
        room_area_support_pages=(1,),
    )

    assert result.canonical_room_source_pages == (1,)
    assert all(room.page_id == "1" for room in result.canonical_rooms)
    assert all(floor.page_id == "1" for floor in result.canonical_floors)
