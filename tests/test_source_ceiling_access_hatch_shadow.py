import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_ceiling_access_hatch_shadow import (
    SourceCeilingAccessHatchShadowAuthority,
    CeilingAccessHatchReceipt,
    AccessHatchFireRating,
    SCHEMA_VERSION,
)


def test_standard_compliant_access_hatch():
    authority = SourceCeilingAccessHatchShadowAuthority()

    h = authority.compute_access_hatch(
        room_id="ROOM_HALLWAY",
        center_pt=(150.0, 200.0),
        width_pt=20.0,
        length_pt=20.0,
        fire_rating=AccessHatchFireRating.FIRE_RATED_60_MIN,
        panel_type="PLASTERBOARD_INFILL_FLUSH",
    )

    assert h.room_id == "ROOM_HALLWAY"
    assert h.area_pt2 == 400.0
    assert h.trim_perimeter_pt == 80.0
    assert h.fire_rating == AccessHatchFireRating.FIRE_RATED_60_MIN
    assert h.is_code_compliant is True
    assert h.panel_type == "PLASTERBOARD_INFILL_FLUSH"


def test_undersized_non_compliant_hatch():
    authority = SourceCeilingAccessHatchShadowAuthority()

    h = authority.compute_access_hatch(
        room_id="ROOM_CUPBOARD",
        center_pt=(50.0, 50.0),
        width_pt=10.0,
        length_pt=10.0,
        min_code_dimension_pt=12.75,
    )

    assert h.is_code_compliant is False


def test_compile_hatch_receipt():
    authority = SourceCeilingAccessHatchShadowAuthority()

    h1 = authority.compute_access_hatch(
        room_id="R1",
        center_pt=(100.0, 100.0),
        width_pt=20.0,
        length_pt=20.0,
        fire_rating=AccessHatchFireRating.NON_RATED,
    )
    h2 = authority.compute_access_hatch(
        room_id="R2",
        center_pt=(200.0, 200.0),
        width_pt=25.0,
        length_pt=25.0,
        fire_rating=AccessHatchFireRating.FIRE_RATED_120_MIN,
    )

    receipt = authority.compile_hatch_receipt(
        document_id="DOC_CEIL_HATCH",
        revision_id="REV_1",
        source_sha256="12123434" * 8,
        hatches=[h1, h2],
    )

    assert isinstance(receipt, CeilingAccessHatchReceipt)
    assert receipt.total_hatches_count == 2
    assert receipt.fire_rated_count == 1
    assert receipt.total_trim_perimeter_pt == 80.0 + 100.0 # 180.0
    assert receipt.total_hatch_area_pt2 == 400.0 + 625.0    # 1025.0
    assert receipt.status == EvidenceResolutionStatus.CORROBORATED
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_CEIL_HATCH"
    assert len(d["hatches"]) == 2


def test_empty_receipt_abstained():
    authority = SourceCeilingAccessHatchShadowAuthority()

    receipt = authority.compile_hatch_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        hatches=[],
    )

    assert receipt.total_hatches_count == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        CeilingAccessHatchReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_hatches_count=0,
            fire_rated_count=0,
            total_trim_perimeter_pt=0.0,
            total_hatch_area_pt2=0.0,
            hatches=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
