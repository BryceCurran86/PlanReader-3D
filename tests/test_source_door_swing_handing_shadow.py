import math
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_door_swing_handing_shadow import (
    SourceDoorSwingHandingShadowAuthority,
    DoorSwingHandingReceipt,
    DoorHanding,
    SCHEMA_VERSION,
)


def test_resolve_left_hand_inward_door():
    authority = SourceDoorSwingHandingShadowAuthority()

    record = authority.resolve_swing_door(
        door_id="D01",
        hinge_pt=(100.0, 100.0),
        latch_pt=(130.0, 100.0),
        is_left_hand=True,
        swings_inward=True,
        swing_angle_deg=90.0,
    )

    assert record.door_id == "D01"
    assert record.handing == DoorHanding.LEFT_HAND_INWARD
    assert record.leaf_length_pt == 30.0
    expected_swept = (math.pi * (30.0 ** 2)) / 4.0
    assert math.isclose(record.swept_area_pt2, expected_swept, rel_tol=1e-3)
    assert record.is_swing_obstructed is False


def test_resolve_right_hand_outward_door():
    authority = SourceDoorSwingHandingShadowAuthority()

    record = authority.resolve_swing_door(
        door_id="D02",
        hinge_pt=(200.0, 200.0),
        latch_pt=(200.0, 240.0),
        is_left_hand=False,
        swings_inward=False,
        swing_angle_deg=90.0,
        is_obstructed=True,
    )

    assert record.handing == DoorHanding.RIGHT_HAND_OUTWARD
    assert record.leaf_length_pt == 40.0
    assert record.is_swing_obstructed is True


def test_resolve_sliding_door():
    authority = SourceDoorSwingHandingShadowAuthority()

    record = authority.resolve_sliding_door(
        door_id="D03_SLIDING",
        start_pt=(300.0, 100.0),
        end_pt=(350.0, 100.0),
    )

    assert record.handing == DoorHanding.SLIDING_OR_CAVITY
    assert record.leaf_length_pt == 50.0
    assert record.swept_area_pt2 == 0.0
    assert record.swing_angle_deg == 0.0


def test_omitted_swing_angle_does_not_invent_ninety_degrees():
    authority = SourceDoorSwingHandingShadowAuthority()

    record = authority.resolve_swing_door(
        door_id="D_UNKNOWN_ANGLE",
        hinge_pt=(0.0, 0.0),
        latch_pt=(20.0, 0.0),
        is_left_hand=True,
        swings_inward=True,
    )

    assert record.swing_angle_deg == 0.0
    assert record.swept_area_pt2 == 0.0


def test_compile_swing_handing_receipt():
    authority = SourceDoorSwingHandingShadowAuthority()

    d1 = authority.resolve_swing_door(
        door_id="D1",
        hinge_pt=(0.0, 0.0),
        latch_pt=(20.0, 0.0),
        is_left_hand=True,
        swings_inward=True,
        swing_angle_deg=90.0,
    )
    d2 = authority.resolve_sliding_door(
        door_id="D2",
        start_pt=(50.0, 50.0),
        end_pt=(80.0, 50.0),
    )

    receipt = authority.compile_swing_handing_receipt(
        document_id="DOC_DOORS",
        revision_id="REV_1",
        source_sha256="99887766" * 8,
        doors=[d1, d2],
    )

    assert isinstance(receipt, DoorSwingHandingReceipt)
    assert receipt.total_doors_evaluated == 2
    assert receipt.swinging_doors_count == 1
    assert receipt.sliding_doors_count == 1
    assert receipt.status == EvidenceResolutionStatus.CANDIDATE
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_DOORS"
    assert len(d["doors"]) == 2


def test_empty_receipt_abstained():
    authority = SourceDoorSwingHandingShadowAuthority()

    receipt = authority.compile_swing_handing_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        doors=[],
    )

    assert receipt.total_doors_evaluated == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        DoorSwingHandingReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_doors_evaluated=0,
            swinging_doors_count=0,
            sliding_doors_count=0,
            doors=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
