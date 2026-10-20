import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_fire_compartment_separation_shadow import (
    SourceFireCompartmentSeparationShadowAuthority,
    FireCompartmentSeparationReceipt,
    SCHEMA_VERSION,
)


def test_fire_compartment_wall_with_penetrations():
    authority = SourceFireCompartmentSeparationShadowAuthority()

    p1 = authority.create_penetration(
        wall_id="FW_01",
        penetration_type="FIRE_DAMPER",
        service_dimension_pt=15.0,
        damper_rating_min=90,
    )
    p2 = authority.create_penetration(
        wall_id="FW_01",
        penetration_type="INTUMESCENT_COLLAR",
        service_dimension_pt=5.0,
        damper_rating_min=90,
    )

    wall = authority.create_fire_wall(
        wall_id="FW_01",
        frl_rating="90/90/90",
        boundary_type="INTER_TENANCY_PARTY_WALL",
        wall_length_pt=120.0,
        wall_height_pt=80.0,
        penetrations=[p1, p2],
    )

    assert wall.wall_id == "FW_01"
    assert wall.frl_rating == "90/90/90"
    assert wall.compartment_boundary_type == "INTER_TENANCY_PARTY_WALL"
    assert wall.wall_area_pt2 == 9600.0
    assert len(wall.penetrations) == 2


def test_omitted_ratings_do_not_invent_ninety_minute_frl():
    authority = SourceFireCompartmentSeparationShadowAuthority()

    p = authority.create_penetration(wall_id="FW_UNKNOWN")
    wall = authority.create_fire_wall(
        wall_id="FW_UNKNOWN",
        wall_length_pt=10.0,
        wall_height_pt=10.0,
        penetrations=[p],
    )

    assert p.penetration_type == ""
    assert p.service_dimension_pt == 0.0
    assert p.damper_rating_min == 0
    assert wall.frl_rating == ""
    assert wall.compartment_boundary_type == ""


def test_compile_fire_compartment_receipt():
    authority = SourceFireCompartmentSeparationShadowAuthority()

    p1 = authority.create_penetration(wall_id="W1", penetration_type="FIRE_DAMPER")
    w1 = authority.create_fire_wall(
        wall_id="W1",
        frl_rating="60/60/60",
        wall_length_pt=50.0,
        wall_height_pt=50.0,
        penetrations=[p1],
    )

    receipt = authority.compile_fire_compartment_receipt(
        document_id="DOC_FIRE",
        revision_id="REV_1",
        source_sha256="44335566" * 8,
        walls=[w1],
    )

    assert isinstance(receipt, FireCompartmentSeparationReceipt)
    assert receipt.total_fire_walls_count == 1
    assert receipt.total_fire_wall_area_pt2 == 2500.0
    assert receipt.total_fire_dampers_count == 1
    assert receipt.total_collars_count == 0
    assert receipt.status == EvidenceResolutionStatus.CANDIDATE
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_FIRE"
    assert len(d["walls"]) == 1


def test_empty_receipt_abstained():
    authority = SourceFireCompartmentSeparationShadowAuthority()

    receipt = authority.compile_fire_compartment_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        walls=[],
    )

    assert receipt.total_fire_walls_count == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        FireCompartmentSeparationReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_fire_walls_count=0,
            total_fire_wall_area_pt2=0.0,
            total_fire_dampers_count=0,
            total_collars_count=0,
            walls=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
