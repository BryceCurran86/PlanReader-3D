import math
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_level_datum_height_extrusion_shadow import (
    SourceLevelDatumHeightExtrusionShadowAuthority,
    BuildingLevelDatumReceipt,
    SCHEMA_VERSION,
)


def test_multilevel_building_stack():
    authority = SourceLevelDatumHeightExtrusionShadowAuthority()

    raw = [
        {"level_name": "Level 1", "elevation_reduced_level_m": 14.0, "associated_sheet_ids": ["A102"]},
        {"level_name": "Ground Floor", "elevation_reduced_level_m": 10.0, "associated_sheet_ids": ["A101"]},
        {"level_name": "Roof", "elevation_reduced_level_m": 21.0, "associated_sheet_ids": ["A104"]},
        {"level_name": "Level 2", "elevation_reduced_level_m": 17.5, "associated_sheet_ids": ["A103"]},
    ]

    receipt = authority.compile_level_stack(
        document_id="DOC_TOWER",
        revision_id="REV_A",
        source_sha256="12344321" * 8,
        raw_levels=raw,
        default_floor_finish_thickness_m=0.05,
        default_ceiling_offset_m=0.60,
    )

    assert isinstance(receipt, BuildingLevelDatumReceipt)
    assert receipt.total_levels_count == 4
    assert receipt.base_level_elevation_m == 10.0
    assert receipt.top_level_elevation_m == 21.0
    assert receipt.total_building_height_m == 11.0
    assert receipt.status == EvidenceResolutionStatus.CORROBORATED
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    # Levels should be sorted: Ground (0), L1 (1), L2 (2), Roof (3)
    l0, l1, l2, l3 = receipt.levels
    assert l0.level_name == "Ground Floor"
    assert l0.story_index == 0
    assert l0.floor_to_floor_height_m == 4.0  # 14.0 - 10.0
    assert l0.structural_slab_level_m == 9.95
    assert l0.floor_to_ceiling_clear_height_m == 3.4  # 4.0 - 0.60

    assert l1.level_name == "Level 1"
    assert l1.story_index == 1
    assert l1.floor_to_floor_height_m == 3.5  # 17.5 - 14.0

    assert l2.level_name == "Level 2"
    assert l2.story_index == 2
    assert l2.floor_to_floor_height_m == 3.5  # 21.0 - 17.5

    assert l3.level_name == "Roof"
    assert l3.story_index == 3

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_TOWER"
    assert len(d["levels"]) == 4


def test_empty_levels_abstained():
    authority = SourceLevelDatumHeightExtrusionShadowAuthority()

    receipt = authority.compile_level_stack(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        raw_levels=[],
    )

    assert receipt.total_levels_count == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        BuildingLevelDatumReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_levels_count=0,
            base_level_elevation_m=0.0,
            top_level_elevation_m=0.0,
            total_building_height_m=0.0,
            levels=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
