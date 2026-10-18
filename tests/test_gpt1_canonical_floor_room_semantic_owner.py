"""Floor metric enrichment may use only its own source room semantics."""
from dataclasses import replace
from types import SimpleNamespace as Record
from pb_live_canonical_floor_surface import _valid_metric_area_quantity
from pb_geometry_takeoff_model import MeasurementAuthorityType


def _records():
    floor=Record(
        source_room_face_record_id="source-room-face-1",
        source_sha256="a"*64, revision_id="rev-1",page_id="1",
        snapshot_id="source-room-snapshot-1",viewport_id="floor-viewport",
    )
    entity=Record(
        status=__import__("pb_migration_contracts").EvidenceResolutionStatus.CORROBORATED,
        candidate_entity_id="source-room-1",
        evidence_ids=("source-room-face-1","original-figured-area-1"),
        metadata={"source_sha256":"a"*64,"revision_id":"rev-1","page_id":"1"},
    )
    quantity=Record(
        abstained=False,family="room_area",semantic_key="room_area:source-room-1",
        status="firm",unit="m2",blocking_reasons=(),
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        input_entity_ids=("source-room-1",),
        value=13.25,confidence=1.0,quantity_id="source-room-area-1",
        evidence_ids=("original-figured-area-1",),
        metadata={"source_sha256":"a"*64,"revision_id":"rev-1","page_no":1},
    )
    return floor,entity,quantity


def test_exact_original_room_area_remains_eligible_to_enrich_source_floor():
    floor,entity,quantity=_records()
    assert _valid_metric_area_quantity(floor,quantity,source_room_entity=entity)


def test_rekeying_same_original_source_to_other_room_semantic_abstains():
    floor,entity,quantity=_records()
    for candidate in (
        "room_area:source-room-2",
        "room_area:source-room-1 ",
        "floor_finish_area:source-room-1",
        "ceiling_lining:source-room-1",
    ):
        quantity.semantic_key=candidate
        assert not _valid_metric_area_quantity(floor,quantity,source_room_entity=entity)


def test_mismatched_input_owner_and_source_face_still_abstain():
    floor,entity,quantity=_records()
    quantity.input_entity_ids=("source-room-2",)
    assert not _valid_metric_area_quantity(floor,quantity,source_room_entity=entity)
    floor,entity,quantity=_records()
    floor.source_room_face_record_id="other-face"
    assert not _valid_metric_area_quantity(floor,quantity,source_room_entity=entity)
