"""Non-square forged cross-view axis/ceiling metadata regressions.

Synthetic seam proof only: the PDF is generated in-test, not an original
Maryborough source, so this is NOT original-source acceptance. Axis IDs and
millimetres must come from the producer-issued room-area record; caller
metadata can only agree with it, never supply or swap it.
"""
from __future__ import annotations

from dataclasses import replace

import fitz
import pytest

import pb_cross_view_room_area_authority as room_area
import pb_source_cross_view_floor_correspondence_shadow as correspondence
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from tests import test_cross_view_room_area_authority_v1 as source_fixture


def _nonsquare_source_bytes(**_kwargs):
    with fitz.open() as doc:
        plan = doc.new_page(width=400, height=300)
        plan.insert_text((80, 60), "GROUND FLOOR PLAN", fontsize=10)
        detail = doc.new_page(width=400, height=300)
        for start, end in [
            ((100, 80), (225, 80)), ((100, 68), (100, 92)),
            ((225, 68), (225, 92)), ((255, 80), (255, 155)),
            ((225, 80), (267, 80)), ((243, 155), (267, 155)),
        ]:
            detail.draw_line(start, end, color=(0, 0, 0), width=1)
        detail.insert_text((150, 77), "3000", fontsize=9)
        detail.insert_text((252, 127.5), "1800", fontsize=9, rotate=90)
        detail.insert_text((140, 122), "TEST ROOM", fontsize=10)
        return doc.tobytes()


@pytest.fixture
def case(monkeypatch):
    monkeypatch.setattr(source_fixture, "_payload", _nonsquare_source_bytes)
    source, rooms = source_fixture._source_and_room()
    result = room_area.CrossViewRoomAreaProducer.from_source(
        source=source, rooms=rooms).publish()
    assert len(result.records) == 1
    record = result.records[0]
    assert record.area_evidence.normalized_value == 5.4
    assert record.horizontal_dimension_id != record.vertical_dimension_id
    room = rooms.rooms[0]
    corr = correspondence.SourceCrossViewCeilingCorrespondenceRecord(
        record_id="nonsquare-ceiling-axis-record",
        canonical_ceiling_id="nonsquare-ceiling",
        physical_room_id=room.physical_room_id,
        canonical_room_id=room.canonical_room_id,
        source_room_face_record_id=room.source_room_face_record_id,
        support_page_id="9", support_viewport_id="synthetic-RCP",
        target_page_id=room.page_id, target_viewport_id=room.viewport_id,
        support_dimension_box_pdf_pts=(100, 80, 225, 205),
        target_box_pdf_pts=(100, 100, 250, 200),
        registration_translation_pdf_pts=(0, 0),
        finish_code="GRID", semantic_finish="GRID", ceiling_height_mm=2400,
        area_m2=5.4,
        figured_dimension_ids=(record.horizontal_dimension_id,
                               record.vertical_dimension_id),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("synthetic",), authority_blockers=(),
        commercial_projection_allowed=True, takeoff_eligible=True,
        definition_record_id="nonsquare-definition",
        occurrence_record_id="nonsquare-occurrence",
        occurrence_evidence_id="nonsquare-occurrence-evidence",
        document_id=room.document_id, revision_id=room.revision_id,
        source_sha256=room.source_sha256, snapshot_id=room.snapshot_id,
    )
    return room, corr, record, monkeypatch


def _compose(case, *, refs=None, metadata=None):
    room, corr, record, mp = case
    if refs is not None:
        corr = replace(corr, figured_dimension_ids=tuple(refs))
    mp.setitem(correspondence._REGISTERED_CEILING_CORRESPONDENCES_BY_SNAPSHOT,
               (corr.snapshot_id, corr.record_id), corr)
    atom = record.area_evidence
    evidence = atom
    if metadata is not None:
        evidence = QuantityEvidence(
            quantity_id=atom.evidence_id, family="floor_area", unit="m2",
            value=5.4, semantic_key=f"floor_area:{room.physical_room_id}",
            status="firm", authority="documented_dimension",
            evidence_ids=(atom.evidence_id,),
            metadata={**atom.metadata, **metadata},
        )
    return correspondence.compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
        correspondence=corr, room=room, room_area_qty_id=atom.evidence_id,
        area_evidence=evidence)


def test_nonsquare_authentic_record_is_accepted(case):
    _surface, quantity = _compose(case)
    assert quantity.family == "ceiling_lining" and quantity.value == 5.4


def test_nonsquare_quantity_evidence_wrapper_positive_is_accepted(case):
    _surface, quantity = _compose(case, metadata={})
    assert quantity.family == "ceiling_lining" and quantity.value == 5.4
    assert case[2].area_evidence.evidence_id in quantity.evidence_ids


def test_swapped_axis_ids_and_values_with_identical_product_reject(case):
    record = case[2]
    swapped = {
        "horizontal_dimension_id": record.vertical_dimension_id,
        "vertical_dimension_id": record.horizontal_dimension_id,
        "horizontal_value_mm": 1800.0,
        "vertical_value_mm": 3000.0,
    }
    with pytest.raises(ValueError, match="conflicts with authenticated producer"):
        _compose(case, metadata=swapped)


@pytest.mark.parametrize("h,v", [(1800.0, 3000.0), (1500.0, 3600.0),
                                 (5400.0, 1000.0), (2700.0, 2000.0)])
def test_forged_same_product_axis_millimetres_reject(case, h, v):
    with pytest.raises(ValueError, match="conflicts with authenticated producer"):
        _compose(case, metadata={"horizontal_value_mm": h,
                                 "vertical_value_mm": v})


@pytest.mark.parametrize("key,value", [
    ("snapshot_id", "foreign-snapshot"),
    ("document_id", "foreign-document"),
    ("entity_id", "FOREIGN_ROOM"),
    ("source_sha256", "0" * 64),
])
def test_foreign_snapshot_document_room_or_hash_metadata_reject(case, key, value):
    with pytest.raises(ValueError):
        _compose(case, metadata={key: value})


@pytest.mark.parametrize("refs", [
    ("dim_3000", "dim_9999"),       # second axis foreign
    ("foreign_h", "foreign_v"),     # both foreign
    ("dim_1800",),                   # one axis only
    (),                              # none
])
def test_correspondence_foreign_or_missing_figured_axis_rejects(case, refs):
    with pytest.raises(ValueError):
        _compose(case, refs=refs)


def test_correspondence_area_product_not_from_producer_rejects(case):
    room, corr, record, mp = case
    forged = replace(corr, area_m2=5.9)
    mp.setitem(correspondence._REGISTERED_CEILING_CORRESPONDENCES_BY_SNAPSHOT,
               (forged.snapshot_id, forged.record_id), forged)
    with pytest.raises(ValueError):
        correspondence.compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
            correspondence=forged, room=room,
            room_area_qty_id=record.area_evidence.evidence_id,
            area_evidence=record.area_evidence)
