import math
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_stair_flight_void_geometry_shadow import (
    SourceStairFlightVoidGeometryShadowAuthority,
    StairFlightVoidReceipt,
    StairLayoutType,
    SCHEMA_VERSION,
)


def test_straight_horizontal_stair_flight():
    authority = SourceStairFlightVoidGeometryShadowAuthority()

    flight = authority.compute_straight_flight(
        flight_id="STAIR_FLIGHT_01",
        origin_pt=(100.0, 200.0),
        direction="UP",
        riser_count=16,
        riser_height_pt=5.0,
        tread_going_pt=7.0,
        flight_width_pt=30.0,
        is_horizontal_run=True,
    )

    assert flight.flight_id == "STAIR_FLIGHT_01"
    assert flight.layout_type == StairLayoutType.STRAIGHT_FLIGHT
    assert flight.direction == "UP"
    assert flight.riser_count == 16
    assert flight.tread_count == 15
    assert flight.flight_length_pt == 105.0  # 15 * 7.0
    assert flight.total_rise_pt == 80.0      # 16 * 5.0

    expected_pitch = math.degrees(math.atan2(5.0, 7.0))
    assert math.isclose(flight.pitch_deg, expected_pitch, abs_tol=1e-2)

    expected_walkline = math.hypot(105.0, 80.0)
    assert math.isclose(flight.walkline_length_pt, expected_walkline, abs_tol=1e-2)

    assert len(flight.void_polygon) == 4
    # Bounding box is (100, 200) to (205, 230)
    assert flight.void_polygon[0] == (100.0, 200.0)
    assert flight.void_polygon[2] == (205.0, 230.0)


def test_straight_vertical_stair_flight():
    authority = SourceStairFlightVoidGeometryShadowAuthority()

    flight = authority.compute_straight_flight(
        flight_id="STAIR_VERT_01",
        origin_pt=(50.0, 50.0),
        direction="DN",
        riser_count=10,
        riser_height_pt=6.0,
        tread_going_pt=8.0,
        flight_width_pt=25.0,
        is_horizontal_run=False,
    )

    assert flight.direction == "DN"
    assert flight.tread_count == 9
    assert flight.flight_length_pt == 72.0  # 9 * 8.0
    assert flight.void_polygon[0] == (50.0, 50.0)
    assert flight.void_polygon[2] == (75.0, 122.0)


def test_omitted_stair_geometry_does_not_invent_typical_flight():
    authority = SourceStairFlightVoidGeometryShadowAuthority()

    flight = authority.compute_straight_flight(
        flight_id="STAIR_UNKNOWN",
        origin_pt=(0.0, 0.0),
    )

    assert flight.riser_count == 0
    assert flight.tread_count == 0
    assert flight.riser_height_pt == 0.0
    assert flight.tread_going_pt == 0.0
    assert flight.flight_width_pt == 0.0
    assert flight.flight_length_pt == 0.0
    assert flight.total_rise_pt == 0.0
    assert flight.direction == ""


def test_compile_stair_void_receipt():
    authority = SourceStairFlightVoidGeometryShadowAuthority()

    f1 = authority.compute_straight_flight(
        flight_id="F1",
        origin_pt=(0.0, 0.0),
        riser_count=10,
        riser_height_pt=5.0,
        tread_going_pt=10.0,
        flight_width_pt=20.0,
    )

    receipt = authority.compile_stair_void_receipt(
        document_id="DOC_STAIRS",
        revision_id="REV_1",
        source_sha256="aabb1122" * 8,
        flights=[f1],
    )

    assert isinstance(receipt, StairFlightVoidReceipt)
    assert receipt.total_flights_count == 1
    assert receipt.total_risers_count == 10
    # Length = 9 * 10 = 90, width = 20 -> area = 1800
    assert receipt.total_void_area_pt2 == 1800.0
    assert receipt.status == EvidenceResolutionStatus.CANDIDATE
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_STAIRS"
    assert len(d["flights"]) == 1


def test_empty_receipt_abstained():
    authority = SourceStairFlightVoidGeometryShadowAuthority()

    receipt = authority.compile_stair_void_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        flights=[],
    )

    assert receipt.total_flights_count == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        StairFlightVoidReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_flights_count=0,
            total_risers_count=0,
            total_void_area_pt2=0.0,
            flights=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
