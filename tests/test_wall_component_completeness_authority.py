from __future__ import annotations

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateRecord
from pb_physical_wall_identity import (
    PhysicalEquivalenceClass,
    PhysicalWallEquivalenceResolution,
    PhysicalWallIdentity,
)
from pb_wall_component_completeness_authority import (
    WALL_COMPONENT_WITHHELD_PLAUSIBLE_SAME_FACE,
    WALL_COMPONENT_WITHHELD_SOURCE_CONTACT,
    WALL_COMPONENT_WITHHELD_SOURCE_PATH_RELATED,
    _component_sets,
    _positive_same_separations,
    _withheld_affects_component,
)
from pb_wall_room_topology_contracts import JunctionType, WallCandidate


def _record(
    wall_id: str,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    raw_id: str,
):
    wall=WallCandidate(
        candidate_id=wall_id,
        viewport_id="wall-source:viewport:1:view",
        representation="single_line",
        centerline_pts=(start,end),
        face_a_segment_ids=(raw_id,),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=None,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=None,
        end_node_ids=(f"{wall_id}:a",f"{wall_id}:b"),
        junction_types=(JunctionType.ENDPOINT,JunctionType.ENDPOINT),
        interior_exterior="unresolved",
        level_id=None,
        confidence=0.5,
    )
    identity=PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id=wall.viewport_id,
        candidate_identity_id=f"identity:{wall_id}",
        path_fingerprint=(start,end),
        source_primitive_ids=(raw_id,),
        edge_ids=(raw_id,),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    return PhysicalWallCandidateRecord(
        wall_candidate_id=wall_id,
        wall_candidate=wall,
        physical_identity=identity,
    )


def _equivalence(records, *, same=()):
    ids=tuple(r.wall_candidate_id for r in records)
    groups=tuple(tuple(sorted(group)) for group in same)
    pairs=[]
    for group in groups:
        for i,left in enumerate(group):
            for right in group[i+1:]:
                pairs.append((
                    min(left,right),
                    max(left,right),
                    PhysicalEquivalenceClass.SAME_PHYSICAL_WALL.value,
                ))
    return PhysicalWallEquivalenceResolution(
        scope_viewport_id="scope",
        representative_wall_ids=ids,
        abstained_wall_ids=(),
        equivalence_groups=groups,
        ambiguous_wall_ids=(),
        same_wall_ids=tuple(sorted({x for g in groups for x in g})),
        pair_classifications=tuple(sorted(pairs)),
        blocking_reasons_by_wall_id={},
    )


def test_endpoint_connected_walls_form_one_component() -> None:
    records=(
        _record("a",(0,0),(10,0),raw_id="d1i0"),
        _record("b",(10,0),(10,10),raw_id="d2i0"),
        _record("remote",(100,0),(110,0),raw_id="d3i0"),
    )
    groups=_component_sets(records,_equivalence(records))
    assert ("a","b") in groups
    assert ("remote",) in groups


def test_positive_same_group_unions_offset_face_representations() -> None:
    records=(
        _record("face-a",(0,0),(20,0),raw_id="d10i0"),
        _record("face-b",(0,5),(20,5),raw_id="d10i1"),
    )
    groups=_component_sets(
        records,
        _equivalence(records,same=(("face-a","face-b"),)),
    )
    assert groups == (("face-a","face-b"),)


def test_intersecting_withheld_primitive_blocks_component() -> None:
    record=_record("wall",(0,0),(20,0),raw_id="d10i0")
    reason=_withheld_affects_component(
        withheld_line=(10,-10,10,10),
        withheld_raw_id="d20i0",
        component_records=(record,),
        known_same_separations=(),
    )
    assert reason == WALL_COMPONENT_WITHHELD_SOURCE_CONTACT


def test_collinear_gap_within_existing_snap_tolerance_blocks_component() -> None:
    record=_record("wall",(0,0),(20,0),raw_id="d10i0")
    reason=_withheld_affects_component(
        withheld_line=(22,0,40,0),
        withheld_raw_id="d20i0",
        component_records=(record,),
        known_same_separations=(),
    )
    assert reason == WALL_COMPONENT_WITHHELD_SOURCE_CONTACT


def test_same_native_drawing_path_blocks_even_without_contact() -> None:
    record=_record("wall",(0,0),(20,0),raw_id="d10i0")
    reason=_withheld_affects_component(
        withheld_line=(100,100,120,100),
        withheld_raw_id="d10i7",
        component_records=(record,),
        known_same_separations=(),
    )
    assert reason == WALL_COMPONENT_WITHHELD_SOURCE_PATH_RELATED


def test_parallel_overlapping_within_upstream_proven_same_separation_blocks() -> None:
    record=_record("wall",(0,0),(20,0),raw_id="d10i0")
    reason=_withheld_affects_component(
        withheld_line=(0,4,20,4),
        withheld_raw_id="d20i0",
        component_records=(record,),
        known_same_separations=(5.0,),
    )
    assert reason == WALL_COMPONENT_WITHHELD_PLAUSIBLE_SAME_FACE


def test_parallel_overlapping_farther_than_any_proven_same_separation_is_remote() -> None:
    record=_record("wall",(0,0),(20,0),raw_id="d10i0")
    reason=_withheld_affects_component(
        withheld_line=(0,50,20,50),
        withheld_raw_id="d20i0",
        component_records=(record,),
        known_same_separations=(5.0,),
    )
    assert reason is None


def test_remote_nonparallel_geometry_does_not_poison_component() -> None:
    record=_record("wall",(0,0),(20,0),raw_id="d10i0")
    reason=_withheld_affects_component(
        withheld_line=(100,100,100,120),
        withheld_raw_id="d20i0",
        component_records=(record,),
        known_same_separations=(5.0,),
    )
    assert reason is None


def test_positive_same_separation_is_derived_from_upstream_equivalence_only() -> None:
    records=(
        _record("a",(0,0),(20,0),raw_id="d10i0"),
        _record("b",(0,5),(20,5),raw_id="d10i1"),
        _record("unrelated",(0,40),(20,40),raw_id="d30i0"),
    )
    by_id={r.wall_candidate_id:r for r in records}
    eq=_equivalence(records,same=(("a","b"),))
    values=_positive_same_separations(by_id,eq)
    assert values == (5.0,)
    assert 40.0 not in values
