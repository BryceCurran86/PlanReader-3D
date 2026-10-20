import math
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_balcony_drainage_fall_shadow import (
    SourceBalconyDrainageFallShadowAuthority,
    BalconyDrainageFallReceipt,
    SCHEMA_VERSION,
)


def test_standard_balcony_drainage_1_in_100():
    authority = SourceBalconyDrainageFallShadowAuthority()

    rec = authority.compute_balcony_drainage(
        room_id="BALCONY_01",
        area_pt2=10000.0,
        fall_distance_pt=100.0,
        fall_ratio_1_in_n=100.0,
        threshold_stepdown_pt=2.0,
        screed_min_thickness_pt=1.0,
        strip_drain_length_pt=100.0,
    )

    assert rec.room_id == "BALCONY_01"
    assert rec.area_pt2 == 10000.0
    assert rec.fall_distance_pt == 100.0
    assert rec.vertical_fall_pt == 1.0
    assert rec.screed_min_thickness_pt == 1.0
    assert rec.screed_max_thickness_pt == 2.0
    assert rec.screed_volume_pt3 == 15000.0  # 10000 * 1.5
    assert rec.strip_drain_length_pt == 100.0
    assert rec.threshold_stepdown_pt == 2.0


def test_balcony_drainage_1_in_80():
    authority = SourceBalconyDrainageFallShadowAuthority()

    rec = authority.compute_balcony_drainage(
        room_id="TERRACE_01",
        area_pt2=8000.0,
        fall_distance_pt=80.0,
        fall_ratio_1_in_n=80.0,
        screed_min_thickness_pt=0.5,
    )

    assert rec.vertical_fall_pt == 1.0
    assert rec.screed_max_thickness_pt == 1.5
    assert rec.screed_volume_pt3 == 8000.0 * 1.0  # 8000.0


def test_compile_balcony_receipt():
    authority = SourceBalconyDrainageFallShadowAuthority()

    b1 = authority.compute_balcony_drainage(
        room_id="B1",
        area_pt2=5000.0,
        fall_distance_pt=50.0,
        screed_min_thickness_pt=1.0,
        strip_drain_length_pt=50.0,
    )

    receipt = authority.compile_balcony_receipt(
        document_id="DOC_BALCONY",
        revision_id="REV_1",
        source_sha256="aabbcc99" * 8,
        balconies=[b1],
    )

    assert isinstance(receipt, BalconyDrainageFallReceipt)
    assert receipt.total_balconies_count == 1
    assert receipt.total_balcony_area_pt2 == 5000.0
    assert receipt.total_strip_drain_length_pt == 50.0
    assert receipt.status == EvidenceResolutionStatus.CORROBORATED
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_BALCONY"
    assert len(d["balconies"]) == 1


def test_empty_receipt_abstained():
    authority = SourceBalconyDrainageFallShadowAuthority()

    receipt = authority.compile_balcony_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        balconies=[],
    )

    assert receipt.total_balconies_count == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        BalconyDrainageFallReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_balconies_count=0,
            total_balcony_area_pt2=0.0,
            total_screed_volume_pt3=0.0,
            total_strip_drain_length_pt=0.0,
            balconies=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
