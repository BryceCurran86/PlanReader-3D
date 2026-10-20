import math
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_wet_area_waterproofing_shadow import (
    SourceWetAreaWaterproofingShadowAuthority,
    WetAreaWaterproofingReceipt,
    WetAreaKind,
    SCHEMA_VERSION,
)


def test_bathroom_with_shower_recess():
    authority = SourceWetAreaWaterproofingShadowAuthority()

    rec = authority.compute_wet_area_waterproofing(
        room_id="ROOM_BATH_01",
        kind=WetAreaKind.BATHROOM,
        floor_area_pt2=5000.0,
        general_perimeter_pt=200.0,
        shower_perimeter_pt=50.0,
        general_upstand_height_pt=4.25,
        shower_tanking_height_pt=56.69,
    )

    assert rec.room_id == "ROOM_BATH_01"
    assert rec.kind == WetAreaKind.BATHROOM
    assert rec.floor_area_pt2 == 5000.0
    expected_gen_upstand = 200.0 * 4.25   # 850.0
    expected_shower_tank = 50.0 * 56.69   # 2834.5
    expected_vert = expected_gen_upstand + expected_shower_tank
    expected_total = 5000.0 + expected_vert

    assert math.isclose(rec.vertical_upstand_area_pt2, expected_vert, rel_tol=1e-3)
    assert math.isclose(rec.total_membrane_area_pt2, expected_total, rel_tol=1e-3)
    assert rec.membrane_system_spec == "CLASS_III_POLYURETHANE_MEMBRANE"


def test_powder_room_no_shower():
    authority = SourceWetAreaWaterproofingShadowAuthority()

    rec = authority.compute_wet_area_waterproofing(
        room_id="ROOM_POWDER_01",
        kind=WetAreaKind.POWDER_ROOM,
        floor_area_pt2=2000.0,
        general_perimeter_pt=180.0,
        shower_perimeter_pt=0.0,
        general_upstand_height_pt=5.0,
    )

    assert rec.kind == WetAreaKind.POWDER_ROOM
    assert rec.shower_perimeter_pt == 0.0
    assert rec.vertical_upstand_area_pt2 == 180.0 * 5.0 # 900.0
    assert rec.total_membrane_area_pt2 == 2900.0


def test_compile_waterproofing_receipt():
    authority = SourceWetAreaWaterproofingShadowAuthority()

    w1 = authority.compute_wet_area_waterproofing(
        room_id="R1",
        kind=WetAreaKind.ENSUITE,
        floor_area_pt2=3000.0,
        general_perimeter_pt=150.0,
        general_upstand_height_pt=4.0,
    )

    receipt = authority.compile_waterproofing_receipt(
        document_id="DOC_WATERPROOF",
        revision_id="REV_1",
        source_sha256="44556677" * 8,
        wet_areas=[w1],
    )

    assert isinstance(receipt, WetAreaWaterproofingReceipt)
    assert receipt.total_wet_areas_count == 1
    assert receipt.total_floor_membrane_pt2 == 3000.0
    assert receipt.total_vertical_upstand_pt2 == 600.0
    assert receipt.total_membrane_takeoff_pt2 == 3600.0
    assert receipt.status == EvidenceResolutionStatus.CORROBORATED
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_WATERPROOF"
    assert len(d["wet_areas"]) == 1


def test_empty_receipt_abstained():
    authority = SourceWetAreaWaterproofingShadowAuthority()

    receipt = authority.compile_waterproofing_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        wet_areas=[],
    )

    assert receipt.total_wet_areas_count == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        WetAreaWaterproofingReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_wet_areas_count=0,
            total_floor_membrane_pt2=0.0,
            total_vertical_upstand_pt2=0.0,
            total_membrane_takeoff_pt2=0.0,
            wet_areas=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
