"""Tests for firm cross-view ceiling quantity publication."""
from __future__ import annotations

import pb_cross_view_ceiling_finish_authority as finish_authority
import pb_cross_view_ceiling_quantity_authority as ceiling_quantity
import pb_cross_view_room_area_authority as room_area_authority
from pb_live_canonical_room_composition import (
    LiveCanonicalRoomComposition,
    LiveCanonicalRoomObject,
)
from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus


def _room() -> LiveCanonicalRoomObject:
    return LiveCanonicalRoomObject(
        canonical_room_id="canonical-room-1",
        physical_room_id="physical-room-1",
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="a" * 64,
        snapshot_id="snap-1",
        page_id="7",
        viewport_id="floor-vp",
        decision_scope_id="scope-1",
        polygon_pdf_pts=(
            (0.0, 0.0),
            (100.0, 0.0),
            (100.0, 80.0),
            (0.0, 80.0),
        ),
        bounding_wall_ids=("w1", "w2", "w3", "w4"),
        canonical_bounding_wall_ids=("cw1", "cw2", "cw3", "cw4"),
        wall_relationships_complete=True,
        area_page_pts2=8000.0,
        source_room_face_record_id="face-1",
        evidence_ids=("room-evidence",),
        geometry_complete=True,
        metric_geometry_complete=False,
        room_label="OFFICE",
        room_label_binding_record_id="label-binding-1",
        room_label_evidence_ids=("room-label-evidence",),
    )


def _rooms() -> LiveCanonicalRoomComposition:
    return LiveCanonicalRoomComposition(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("resolved",),
        rooms=(_room(),),
        source_pages=(7,),
    )


def _area(*, face_id: str = "face-1"):
    evidence = EvidenceAtom(
        evidence_id="area-evidence",
        document_id="doc-1",
        page_id="7",
        viewport_id="floor-vp",
        kind="explicit_room_area",
        method="authenticated_cross_view_figured_dimensions",
        normalized_value=9.05352,
        unit="m2",
        confidence=1.0,
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("resolved",),
        metadata={
            "physical_room_id": "physical-room-1",
            "source_room_face_record_id": face_id,
            "figured_dimension_ids": ["dim-h", "dim-v"],
            "room_revision_id": "rev-1",
            "room_snapshot_id": "snap-1",
            "source_sha256": "a" * 64,
        },
    )
    record = room_area_authority.CrossViewRoomAreaRecord(
        physical_room_id="physical-room-1",
        source_room_face_record_id=face_id,
        room_label="OFFICE",
        source_dimension_page_id="11",
        source_label_observation_ids=("area-label-obs",),
        source_label_receipt_ids=("area-label-receipt",),
        horizontal_dimension_id="dim-h",
        vertical_dimension_id="dim-v",
        area_evidence=evidence,
        _seal=room_area_authority._RECORD_SEAL,
    )
    return room_area_authority.CrossViewRoomAreaResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("resolved",),
        records=(record,),
        unresolved_physical_room_ids=(),
    )


def _finish(*, face_id: str = "face-1"):
    record = finish_authority.CrossViewCeilingFinishRecord(
        record_id="ceiling-finish-record",
        physical_room_id="physical-room-1",
        canonical_room_id="canonical-room-1",
        source_room_face_record_id=face_id,
        room_label="OFFICE",
        support_page_id="9",
        support_viewport_id="rcp-vp",
        support_source_partition_id="partition-9",
        support_block_no=12,
        room_label_observation_ids=("rcp-label-obs",),
        room_label_receipt_ids=("rcp-label-receipt",),
        finish_code="GRID",
        semantic_finish="ceiling_grid",
        definition_record_id="def-grid",
        definition_evidence_ids=("def-evidence",),
        occurrence_record_id="occ-grid",
        occurrence_evidence_id="occ-evidence",
        occurrence_bbox_pdf_pts=(100.0, 70.0, 125.0, 82.0),
        _seal=finish_authority._RECORD_SEAL,
    )
    return finish_authority.CrossViewCeilingFinishResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("resolved",),
        records=(record,),
        unresolved_physical_room_ids=(),
    )


def test_documented_room_area_and_rcp_finish_publish_firm_ceiling_quantity() -> None:
    result = ceiling_quantity.publish_cross_view_ceiling_quantities(
        rooms=_rooms(),
        room_areas=_area(),
        finishes=_finish(),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.unresolved_physical_room_ids == ()
    assert len(result.records) == 1
    record = result.records[0]
    quantity = record.quantity
    assert record.canonical_ceiling_id == record.physical_ceiling_surface_id
    assert record.physical_room_id == "physical-room-1"
    assert record.room_label == "OFFICE"
    assert record.finish_code == "GRID"
    assert record.semantic_finish == "ceiling_grid"
    assert quantity.family == "ceiling_lining"
    assert quantity.value == 9.05352
    assert quantity.unit == "m2"
    assert quantity.authority == "documented_dimension"
    assert quantity.status == "firm"
    assert quantity.abstained is False
    assert quantity.input_entity_ids == (record.canonical_ceiling_id,)
    assert quantity.metadata["figured_dimension_ids"] == ["dim-h", "dim-v"]
    assert quantity.metadata["support_page_id"] == "9"
    assert quantity.metadata["support_viewport_id"] == "rcp-vp"
    assert quantity.metadata["row_role"] == "ceiling_area"


def test_source_room_face_mismatch_remains_unresolved() -> None:
    result = ceiling_quantity.publish_cross_view_ceiling_quantities(
        rooms=_rooms(),
        room_areas=_area(face_id="face-other"),
        finishes=_finish(),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert result.unresolved_physical_room_ids == ("physical-room-1",)


def test_ceiling_identity_and_quantity_id_are_deterministic() -> None:
    first = ceiling_quantity.publish_cross_view_ceiling_quantities(
        rooms=_rooms(),
        room_areas=_area(),
        finishes=_finish(),
    )
    second = ceiling_quantity.publish_cross_view_ceiling_quantities(
        rooms=_rooms(),
        room_areas=_area(),
        finishes=_finish(),
    )

    assert len(first.records) == 1
    assert len(second.records) == 1
    assert (
        first.records[0].canonical_ceiling_id
        == second.records[0].canonical_ceiling_id
    )
    assert (
        first.records[0].quantity.quantity_id
        == second.records[0].quantity.quantity_id
    )
