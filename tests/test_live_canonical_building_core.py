from __future__ import annotations

from pb_live_canonical_building_core import (
    LIVE_CANONICAL_BUILDING_CORE_ASSEMBLED,
    LIVE_CANONICAL_BUILDING_CORE_LEVEL_PARTIAL,
    LIVE_CANONICAL_BUILDING_CORE_LEVEL_UNAVAILABLE,
    LIVE_CANONICAL_BUILDING_CORE_UNAVAILABLE,
    assemble_live_canonical_building_core,
)
from pb_migration_contracts import EvidenceResolutionStatus


SHA = "a" * 64


def _wall(*, level_ids=()):
    return {
        "canonical_wall_id": "wall-1",
        "physical_wall_id": "wall-1",
        "level_ids": list(level_ids),
        "member_wall_candidate_ids": ["wall-candidate-1"],
    }


def _opening(*, kind="door"):
    return {
        "canonical_opening_id": "opening-1",
        "physical_opening_id": "opening-1",
        "host_wall_id": "wall-1",
        "opening_kind": kind,
        "type_mark": "D1" if kind == "door" else "W1",
    }


def _room():
    return {
        "canonical_room_id": "room-1",
        "bounding_wall_ids": ["wall-candidate-1"],
        "polygon_pdf_pts": [[0, 0], [10, 0], [10, 8], [0, 8]],
    }


def _ceiling():
    return {
        "canonical_ceiling_id": "ceiling-1",
        "room_entity_id": "room-1",
        "polygon_pdf_pts": [[0, 0], [10, 0], [10, 8], [0, 8]],
    }


def test_no_level_evidence_never_invents_a_storey() -> None:
    result = assemble_live_canonical_building_core(
        source_sha256=SHA,
        walls=(_wall(),),
        openings=(_opening(),),
        rooms=(_room(),),
        ceilings=(_ceiling(),),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (
        LIVE_CANONICAL_BUILDING_CORE_ASSEMBLED,
        LIVE_CANONICAL_BUILDING_CORE_LEVEL_UNAVAILABLE,
    )
    assert result.building_id
    assert result.cross_revision_identity_resolved is False
    assert result.levels == ()
    assert result.level_assignment_complete is False
    assert len(result.unassigned["walls"]) == 1
    assert len(result.unassigned["openings"]) == 1
    assert len(result.unassigned["rooms"]) == 1
    assert len(result.unassigned["ceilings"]) == 1


def test_proven_wall_level_propagates_through_physical_relationships_only() -> None:
    slab = {"canonical_slab_id": "slab-1", "source_page": 1}
    roof = {"canonical_roof_id": "roof-1", "source_page": 3}
    structure = {
        "canonical_structural_member_id": "column-1",
        "member_kind": "column",
    }

    result = assemble_live_canonical_building_core(
        source_sha256=SHA,
        walls=(_wall(level_ids=("L1",)),),
        openings=(_opening(kind="door"),),
        rooms=(_room(),),
        ceilings=(_ceiling(),),
        slabs=(slab,),
        roofs=(roof,),
        structural_members=(structure,),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (
        LIVE_CANONICAL_BUILDING_CORE_ASSEMBLED,
        LIVE_CANONICAL_BUILDING_CORE_LEVEL_PARTIAL,
    )
    assert len(result.levels) == 1
    level = result.levels[0]
    assert level.level_id == "L1"
    assert [item["canonical_wall_id"] for item in level.walls] == ["wall-1"]
    assert [item["canonical_opening_id"] for item in level.openings] == [
        "opening-1"
    ]
    assert [item["canonical_room_id"] for item in level.rooms] == ["room-1"]
    assert [item["canonical_ceiling_id"] for item in level.ceilings] == [
        "ceiling-1"
    ]

    payload = level.to_dict()
    assert [item["canonical_opening_id"] for item in payload["doors"]] == [
        "opening-1"
    ]
    assert payload["windows"] == []

    # No level is invented for unrelated objects that carry no proven level.
    assert result.unassigned["slabs"] == (slab,)
    assert result.unassigned["roofs"] == (roof,)
    assert result.unassigned["structural_members"] == (structure,)
    assert result.level_assignment_complete is False


def test_explicit_object_level_is_accepted_without_guessing() -> None:
    slab = {
        "canonical_slab_id": "slab-1",
        "level_id": "L2",
        "source_page": 2,
    }
    result = assemble_live_canonical_building_core(
        source_sha256=SHA,
        slabs=(slab,),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.levels) == 1
    assert result.levels[0].level_id == "L2"
    assert result.levels[0].slabs == (slab,)
    assert result.level_assignment_complete is True


def test_source_owned_level_metadata_survives_into_building_bucket() -> None:
    level_id = "level-source-view-1"
    source_level = {
        "canonical_level_id": level_id,
        "level_label": "GROUND FLOOR PLAN",
        "normalized_level_label": "ground_floor",
        "level_index": 0,
        "source_page": 4,
        "source_viewport_id": "view_p4_1",
        "cross_view_identity_resolved": False,
    }
    result = assemble_live_canonical_building_core(
        source_sha256=SHA,
        levels=(source_level,),
        walls=(_wall(level_ids=(level_id,)),),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.levels) == 1
    level = result.levels[0]
    assert level.level_id == level_id
    assert level.level_label == "GROUND FLOOR PLAN"
    assert level.normalized_level_label == "ground_floor"
    assert level.level_index == 0
    assert level.source_page == 4
    assert level.source_viewport_id == "view_p4_1"
    assert level.cross_view_identity_resolved is False
    payload = result.to_dict()
    assert payload["levels"][0]["level_label"] == "GROUND FLOOR PLAN"
    assert payload["object_counts"]["levels"] == 1


def test_duplicate_canonical_identity_fails_closed() -> None:
    result = assemble_live_canonical_building_core(
        source_sha256=SHA,
        walls=(_wall(), _wall()),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (LIVE_CANONICAL_BUILDING_CORE_UNAVAILABLE,)
    assert result.building_id is None


def test_invalid_source_identity_fails_closed() -> None:
    result = assemble_live_canonical_building_core(
        source_sha256="not-a-sha",
        walls=(_wall(),),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (LIVE_CANONICAL_BUILDING_CORE_UNAVAILABLE,)
