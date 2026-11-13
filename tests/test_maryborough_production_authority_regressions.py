"""Synthetic authority regressions; original-PDF acceptance runs separately."""
from __future__ import annotations

from dataclasses import dataclass, replace
import gc
import traceback

import fitz
import pytest

import pb_cross_view_room_area_authority as room_area
import pb_source_cross_view_floor_correspondence_shadow as correspondence
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from tests import test_cross_view_room_area_authority_v1 as source_fixture


@dataclass(frozen=True)
class _RegistryValue:
    value: int


@pytest.fixture(params=[room_area, correspondence], ids=["room-area", "correspondence"])
def registry(request):
    return request.param._UniqueWeakValueDictionary()


def test_registry_rejects_equal_but_distinct_record(registry):
    original = _RegistryValue(1)
    copy = replace(original)
    assert copy == original and copy is not original
    registry[("snapshot", "evidence")] = original
    with pytest.raises(ValueError, match="^duplicate_authority_conflict$"):
        registry[("snapshot", "evidence")] = copy
    assert registry[("snapshot", "evidence")] is original


def test_registry_same_object_registration_is_idempotent(registry):
    original = _RegistryValue(1)
    registry[("snapshot", "evidence")] = original
    registry[("snapshot", "evidence")] = original
    assert registry[("snapshot", "evidence")] is original


def test_registry_rejects_conflicting_record_without_private_data(registry):
    original, conflict = _RegistryValue(1), _RegistryValue(2)
    key = ("PRIVATE_SNAPSHOT_SENTINEL", "PRIVATE_EVIDENCE_SENTINEL")
    registry[key] = original
    with pytest.raises(ValueError) as exc:
        registry[key] = conflict
    assert str(exc.value) == "duplicate_authority_conflict"
    assert registry[key] is original


def test_registry_releases_unreferenced_records(registry):
    original = _RegistryValue(1)
    registry[("snapshot", "evidence")] = original
    del original
    gc.collect()
    assert len(registry) == 0


def test_producer_replay_reuses_first_record_for_all_aliases(registry):
    first = _RegistryValue(1)
    keys = (("snapshot", "evidence"), ("revision", "evidence"))
    assert registry.register_issued(keys, first) is first
    assert registry.register_issued(keys, replace(first)) is first
    assert all(registry[key] is first for key in keys)


def test_conflicting_producer_replay_writes_no_partial_aliases(registry):
    first, conflict = _RegistryValue(1), _RegistryValue(2)
    registry[("snapshot", "existing")] = first
    keys = (("snapshot", "new-alias"), ("snapshot", "existing"))
    with pytest.raises(ValueError, match="^duplicate_authority_conflict$"):
        registry.register_issued(keys, conflict)
    assert ("snapshot", "new-alias") not in registry
    assert registry[("snapshot", "existing")] is first


def test_genuine_room_area_producer_replay_preserves_first_issued_identity():
    source, rooms = source_fixture._source_and_room()
    producer = room_area.CrossViewRoomAreaProducer.from_source(source=source, rooms=rooms)
    first = producer.publish()
    second = producer.publish()
    assert len(first.records) == len(second.records) == 1
    assert first.records[0] is second.records[0]
    record = first.records[0]
    assert room_area.get_authenticated_room_area_record(
        rooms.rooms[0].snapshot_id, record.area_evidence.evidence_id,
    ) is record


def _square_source_bytes(**_kwargs):
    with fitz.open() as doc:
        plan = doc.new_page(width=400, height=300)
        plan.insert_text((80, 60), "GROUND FLOOR PLAN", fontsize=10)
        detail = doc.new_page(width=400, height=300)
        for start, end in [
            ((100, 80), (225, 80)), ((100, 68), (100, 92)),
            ((225, 68), (225, 92)), ((255, 80), (255, 205)),
            ((225, 80), (267, 80)), ((243, 205), (267, 205)),
        ]:
            detail.draw_line(start, end, color=(0, 0, 0), width=1)
        detail.insert_text((150, 77), "3000", fontsize=9)
        detail.insert_text((252, 170), "3000", fontsize=9, rotate=90)
        detail.insert_text((140, 150), "TEST ROOM", fontsize=10)
        return doc.tobytes()


@pytest.fixture
def ceiling_case(monkeypatch):
    # The area/axis record is produced from actual native PDF words and
    # dimension/witness lines, rather than fabricated axis metadata.
    monkeypatch.setattr(source_fixture, "_payload", _square_source_bytes)
    source, rooms = source_fixture._source_and_room()
    result = room_area.CrossViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish()
    assert len(result.records) == 1
    record = result.records[0]
    assert record.area_evidence.normalized_value == 9.0
    assert record.horizontal_dimension_id != record.vertical_dimension_id
    room = rooms.rooms[0]
    corr = correspondence.SourceCrossViewCeilingCorrespondenceRecord(
        record_id="synthetic-ceiling-axis-record",
        canonical_ceiling_id="synthetic-ceiling",
        physical_room_id=room.physical_room_id,
        canonical_room_id=room.canonical_room_id,
        source_room_face_record_id=room.source_room_face_record_id,
        support_page_id="9", support_viewport_id="synthetic-RCP",
        target_page_id=room.page_id, target_viewport_id=room.viewport_id,
        support_dimension_box_pdf_pts=(100, 80, 225, 205),
        target_box_pdf_pts=(100, 100, 250, 200),
        registration_translation_pdf_pts=(0, 0),
        finish_code="GRID", semantic_finish="GRID", ceiling_height_mm=2400,
        area_m2=9.0,
        figured_dimension_ids=(record.horizontal_dimension_id, record.vertical_dimension_id),
        status=EvidenceResolutionStatus.CORROBORATED, reason_codes=("synthetic",),
        authority_blockers=(), commercial_projection_allowed=True, takeoff_eligible=True,
        definition_record_id="synthetic-definition", occurrence_record_id="synthetic-occurrence",
        occurrence_evidence_id="synthetic-occurrence-evidence",
        document_id=room.document_id, revision_id=room.revision_id,
        source_sha256=room.source_sha256, snapshot_id=room.snapshot_id,
    )
    return source, result, room, corr, record


def _compose(case, *, refs=None, metadata=None):
    _source, _result, room, corr, record = case
    if refs is not None:
        corr = replace(corr, figured_dimension_ids=tuple(refs))
    # Synthetic RCP registration exercises only this consumer seam. It is
    # deliberately not original-source/customer acceptance.
    correspondence._REGISTERED_CEILING_CORRESPONDENCES_BY_SNAPSHOT[
        (corr.snapshot_id, corr.record_id)
    ] = corr
    atom = record.area_evidence
    evidence = atom
    if metadata is not None:
        evidence = QuantityEvidence(
            quantity_id=atom.evidence_id, family="floor_area", unit="m2", value=9.0,
            semantic_key=f"floor_area:{room.physical_room_id}",
            status="firm", authority="documented_dimension", evidence_ids=(atom.evidence_id,),
            metadata={**atom.metadata, **metadata},
        )
    return correspondence.compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
        correspondence=corr, room=room, room_area_qty_id=atom.evidence_id, area_evidence=evidence,
    )


@pytest.mark.parametrize("refs", [(), ("dim_3000",), ("3000",),
                                      ("dim_3000", "dim_3000"), ("dim_3000", "3000")])
def test_square_ceiling_rejects_shared_numeric_alias_as_two_axis_witnesses(ceiling_case, refs):
    with pytest.raises(ValueError, match="missing figured dimension|distinct axis witnesses required"):
        _compose(ceiling_case, refs=refs)


def test_square_ceiling_requires_both_distinct_producer_axis_witnesses(ceiling_case):
    record = ceiling_case[-1]
    surface, quantity = _compose(ceiling_case)
    assert quantity.family == "ceiling_lining" and quantity.value == 9.0
    assert surface.figured_dimension_ids == (
        record.horizontal_dimension_id, record.vertical_dimension_id,
    )


def test_square_ceiling_one_axis_and_ambiguous_alias_is_insufficient(ceiling_case):
    with pytest.raises(ValueError, match="distinct axis witnesses required"):
        _compose(ceiling_case, refs=(ceiling_case[-1].horizontal_dimension_id, "dim_3000"))


def test_valid_quantity_keeps_authentic_atom_id_in_ceiling_lineage(ceiling_case):
    _surface, quantity = _compose(ceiling_case, metadata={})
    atom = ceiling_case[-1].area_evidence
    assert atom.evidence_id in quantity.evidence_ids
    assert not any("QuantityEvidence(" in ref for ref in quantity.evidence_ids)


@pytest.mark.parametrize("metadata", [
    {"horizontal_dimension_id": "PRIVATE_DIMENSION_SENTINEL"},
    {"vertical_dimension_id": "PRIVATE_DIMENSION_SENTINEL"},
    {"horizontal_value_mm": "PRIVATE_VALUE_SENTINEL"},
    {"vertical_value_mm": "PRIVATE_VALUE_SENTINEL"},
    {"horizontal_value_mm": 987654321},
    {"vertical_value_mm": 987654321},
])
def test_axis_conflict_error_does_not_disclose_source_ids_or_values(ceiling_case, metadata):
    with pytest.raises(ValueError) as exc:
        _compose(ceiling_case, metadata=metadata)
    message = "".join(traceback.format_exception(exc.type, exc.value, exc.tb))
    assert "PRIVATE_DIMENSION_SENTINEL" not in message
    assert "PRIVATE_VALUE_SENTINEL" not in message
    assert "987654321" not in message
    assert ceiling_case[-1].horizontal_dimension_id not in str(exc.value)
    assert ceiling_case[-1].vertical_dimension_id not in str(exc.value)


@pytest.mark.parametrize("axis", ["horizontal", "vertical"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_caller_axis_values_cannot_evade_conflict_check(ceiling_case, axis, value):
    with pytest.raises(ValueError):
        _compose(ceiling_case, metadata={f"{axis}_value_mm": value})
