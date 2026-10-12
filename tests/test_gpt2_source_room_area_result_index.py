"""Source-area producer accessors must not pick first/last original owner."""
from dataclasses import replace
from types import SimpleNamespace
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as S
from pb_cross_view_room_area_authority import (
    CrossViewRoomAreaRecord, CrossViewRoomAreaResult,
    _RECORD_SEAL as CROSS_SEAL,
)
from pb_same_view_room_area_authority import (
    SameViewRoomAreaRecord, SameViewRoomAreaResult,
    _RECORD_SEAL as SAME_SEAL,
)
from pb_source_room_area_receipt_index import unique_source_room_area_evidence_by


def record(class_, seal, *, face, physical, evidence):
    return class_(
        physical_room_id=physical,
        source_room_face_record_id=face,
        room_label="AUTHENTIC SOURCE ROOM",
        source_dimension_page_id="11",
        source_label_observation_ids=("source-native-word-"+face,),
        source_label_receipt_ids=("source-label-receipt-"+face,),
        horizontal_dimension_id="figured-horizontal-"+face,
        vertical_dimension_id="figured-vertical-"+face,
        area_evidence=SimpleNamespace(evidence_id=evidence),
        _seal=seal,
    )


def cross(records):
    return CrossViewRoomAreaResult(
        status=S.CORROBORATED,reason_codes=(),records=tuple(records),
        unresolved_physical_room_ids=(),
    )


def same(records):
    return SameViewRoomAreaResult(
        status=S.CORROBORATED,reason_codes=(),records=tuple(records),
        unresolved_physical_room_ids=(),
    )


@pytest.mark.parametrize("type_,seal,kind",[
    (CrossViewRoomAreaRecord,CROSS_SEAL,"cross"),
    (SameViewRoomAreaRecord,SAME_SEAL,"same"),
])
def test_valid_original_source_room_area_reaches_only_exact_immutable_owner(type_,seal,kind):
    a=record(type_,seal,face="face-a",physical="physical-a",evidence="area-a")
    b=record(type_,seal,face="face-b",physical="physical-b",evidence="area-b")
    result=cross((a,b)) if kind=="cross" else same((a,b))
    owner=result.evidence_by_source_room_face_record_id
    assert dict(owner)=={"face-a":a.area_evidence,"face-b":b.area_evidence}
    if kind=="cross":
        assert dict(result.evidence_by_physical_room_id)=={
            "physical-a":a.area_evidence,"physical-b":b.area_evidence}
    with pytest.raises(TypeError):
        owner["forged-source-room"]=a.area_evidence


@pytest.mark.parametrize("conflict",[
    "same_source_face", "same_physical_room", "same_figured_area_receipt",
    "source_face_replay", "malformed_competing_area", "malformed_competing_physical",
])
@pytest.mark.parametrize("type_,seal,kind",[
    (CrossViewRoomAreaRecord,CROSS_SEAL,"cross"),
    (SameViewRoomAreaRecord,SAME_SEAL,"same"),
])
def test_ambiguous_producer_original_room_cannot_overwrite_firm_area(
    type_,seal,kind,conflict,
):
    a=record(type_,seal,face="face-a",physical="physical-a",evidence="area-a")
    b=record(type_,seal,face="face-b",physical="physical-b",evidence="area-b")
    independent=record(type_,seal,face="face-independent",
                       physical="physical-independent",evidence="area-independent")
    if conflict=="same_source_face":
        b=replace(b,source_room_face_record_id="face-a")
    elif conflict=="same_physical_room":
        b=replace(b,physical_room_id="physical-a")
    elif conflict=="same_figured_area_receipt":
        b=replace(b,area_evidence=SimpleNamespace(evidence_id="area-a"))
    elif conflict=="source_face_replay":
        b=a
    elif conflict=="malformed_competing_area":
        b=replace(b,source_room_face_record_id="face-a",
                  area_evidence=SimpleNamespace(evidence_id=None))
    elif conflict=="malformed_competing_physical":
        b=replace(b,source_room_face_record_id="face-a",
                  physical_room_id=" ")
    for rows in ((a,b,independent),(independent,b,a)):
        result=cross(rows) if kind=="cross" else same(rows)
        by_source=dict(result.evidence_by_source_room_face_record_id)
        assert by_source=={"face-independent":independent.area_evidence}
        if kind=="cross":
            assert dict(result.evidence_by_physical_room_id)=={
                "physical-independent":independent.area_evidence}


def test_result_cannot_promote_forged_room_record_or_bad_address_type():
    real=record(CrossViewRoomAreaRecord,CROSS_SEAL,face="face-a",
                physical="physical-a",evidence="area-a")
    with pytest.raises(TypeError):
        cross((real,SimpleNamespace(source_room_face_record_id="face-b",
             physical_room_id="physical-b",area_evidence=SimpleNamespace(
                 evidence_id="area-b")))).evidence_by_source_room_face_record_id
    for key in (None,"physical_room","source_sha256",""):
        with pytest.raises(ValueError):
            unique_source_room_area_evidence_by((real,),key=key,
                                               record_type=CrossViewRoomAreaRecord)
    with pytest.raises(TypeError):
        unique_source_room_area_evidence_by([real],key="physical_room_id",
                                           record_type=CrossViewRoomAreaRecord)


def test_source_area_receipts_from_two_producers_have_independent_priority():
    # This function indexes one producer. It must not blend same-view and
    # cross-view claims; live integration gives authenticated cross-view
    # evidence priority, and the independent producer indexes stay separate.
    cross_record=record(CrossViewRoomAreaRecord,CROSS_SEAL,face="face-a",
                        physical="physical-a",evidence="cross-area")
    same_record=record(SameViewRoomAreaRecord,SAME_SEAL,face="face-a",
                       physical="physical-a",evidence="same-area")
    assert cross((cross_record,)).evidence_by_source_room_face_record_id["face-a"] is cross_record.area_evidence
    assert same((same_record,)).evidence_by_source_room_face_record_id["face-a"] is same_record.area_evidence
