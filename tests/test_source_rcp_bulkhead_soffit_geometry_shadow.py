import math
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_rcp_bulkhead_soffit_geometry_shadow import (
    SourceRcpBulkheadSoffitGeometryShadowAuthority,
    CeilingBulkheadSoffitReceipt,
    SCHEMA_VERSION,
)


def test_kitchen_bulkhead_step():
    authority = SourceRcpBulkheadSoffitGeometryShadowAuthority()

    soffit_box = ((10.0, 10.0), (60.0, 10.0), (60.0, 30.0), (10.0, 30.0))
    rec = authority.compute_bulkhead_step(
        bulkhead_id="BH_KITCHEN_01",
        room_id="ROOM_KITCHEN",
        high_level_pt=76.5,
        low_level_pt=68.0,
        step_length_pt=50.0,
        soffit_polygon=soffit_box,
    )

    assert rec.bulkhead_id == "BH_KITCHEN_01"
    assert rec.room_id == "ROOM_KITCHEN"
    assert rec.step_height_pt == 8.5
    assert rec.step_length_pt == 50.0
    assert rec.fascia_area_pt2 == 425.0  # 50 * 8.5
    assert rec.soffit_area_pt2 == 1000.0 # 50 * 20


def test_zero_or_negative_step_clamp():
    authority = SourceRcpBulkheadSoffitGeometryShadowAuthority()

    rec = authority.compute_bulkhead_step(
        bulkhead_id="BH_FLAT",
        room_id="ROOM_01",
        high_level_pt=70.0,
        low_level_pt=75.0,  # inverted
        step_length_pt=20.0,
        soffit_polygon=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
    )

    assert rec.step_height_pt == 0.0
    assert rec.fascia_area_pt2 == 0.0


def test_compile_bulkhead_receipt():
    authority = SourceRcpBulkheadSoffitGeometryShadowAuthority()

    b1 = authority.compute_bulkhead_step(
        bulkhead_id="B1",
        room_id="R1",
        high_level_pt=100.0,
        low_level_pt=80.0,
        step_length_pt=40.0,
        soffit_polygon=((0.0, 0.0), (40.0, 0.0), (40.0, 10.0), (0.0, 10.0)),
    )

    receipt = authority.compile_bulkhead_receipt(
        document_id="DOC_RCP",
        revision_id="REV_1",
        source_sha256="99001122" * 8,
        bulkheads=[b1],
    )

    assert isinstance(receipt, CeilingBulkheadSoffitReceipt)
    assert receipt.total_bulkheads_count == 1
    assert receipt.total_fascia_area_pt2 == 800.0  # 40 * 20
    assert receipt.total_soffit_area_pt2 == 400.0  # 40 * 10
    assert receipt.status == EvidenceResolutionStatus.CORROBORATED
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_RCP"
    assert len(d["bulkheads"]) == 1


def test_empty_receipt_abstained():
    authority = SourceRcpBulkheadSoffitGeometryShadowAuthority()

    receipt = authority.compile_bulkhead_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        bulkheads=[],
    )

    assert receipt.total_bulkheads_count == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        CeilingBulkheadSoffitReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_bulkheads_count=0,
            total_fascia_area_pt2=0.0,
            total_soffit_area_pt2=0.0,
            bulkheads=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
