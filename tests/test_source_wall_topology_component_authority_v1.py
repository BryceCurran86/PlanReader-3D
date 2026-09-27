from __future__ import annotations

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    _AUTHORITY_SEAL as CANDIDATE_AUTHORITY_SEAL,
    _ScopeKey,
)
from pb_physical_wall_identity import PhysicalWallEquivalenceResolution, PhysicalWallIdentity
from pb_wall_component_completeness_authority import (
    WALL_COMPONENT_COMPLETE,
    WallComponentCompletenessAuthority,
    WallComponentCompletenessRecord,
    WallComponentCompletenessResult,
    _AUTHORITY_SEAL as COMPONENT_AUTHORITY_SEAL,
    _RECORD_SEAL as COMPONENT_RECORD_SEAL,
)
from pb_wall_role_authority import (
    WallRoleClassification,
    WallRoleProducer,
    WallRoleSelector,
)
from pb_wall_room_topology_contracts import JunctionType, WallCandidate


DOC="doc-component-topology"
REV="r1"
SHA="a"*64
SNAP="snap1"
PAGE="1"
SCOPE="wall-source:viewport:1:test"


def _record(wall_id: str, first, second, raw_id: str) -> PhysicalWallCandidateRecord:
    wall=WallCandidate(
        candidate_id=wall_id,
        viewport_id=SCOPE,
        representation="single_line",
        centerline_pts=(first,second),
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
        viewport_id=SCOPE,
        candidate_identity_id=f"identity:{wall_id}",
        path_fingerprint=(first,second),
        source_primitive_ids=(raw_id,),
        edge_ids=(raw_id,),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    return PhysicalWallCandidateRecord(
        wall_candidate_id=wall_id,
        wall_candidate=wall,
        physical_identity=identity,
    )


def _records():
    return (
        _record("top-left",(50.0,50.0),(150.0,50.0),"d1i0"),
        _record("top-right",(150.0,50.0),(250.0,50.0),"d2i0"),
        _record("right",(250.0,50.0),(250.0,250.0),"d3i0"),
        _record("bottom-right",(250.0,250.0),(150.0,250.0),"d4i0"),
        _record("bottom-left",(150.0,250.0),(50.0,250.0),"d5i0"),
        _record("left",(50.0,250.0),(50.0,50.0),"d6i0"),
        _record("divider",(150.0,50.0),(150.0,250.0),"d7i0"),
    )


def _wall_authority(records) -> PhysicalWallCandidateAuthority:
    ids=tuple(record.wall_candidate_id for record in records)
    equivalence=PhysicalWallEquivalenceResolution(
        scope_viewport_id=SCOPE,
        representative_wall_ids=ids,
        abstained_wall_ids=(),
        equivalence_groups=(),
        ambiguous_wall_ids=(),
        same_wall_ids=(),
        pair_classifications=(),
        blocking_reasons_by_wall_id={},
    )
    scope=PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=False,
        records=tuple(records),
        source_observation_ids=(),
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
        reason_codes=(
            "physical_wall_candidate_scope_resolved",
            "physical_wall_candidate_scope_cropped_at_viewport_boundary",
        ),
        equivalence=equivalence,
        proposition="physical_wall_candidate_scope_resolved",
        scope_kind="viewport",
        viewport_id="view-1",
        viewport_bbox=(0.0,0.0,500.0,500.0),
        viewport_view_type="floor_plan",
        viewport_status="derived",
        viewport_boundary_source="title_partition",
    )
    key=_ScopeKey(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
    )
    return PhysicalWallCandidateAuthority({key:scope},_seal=CANDIDATE_AUTHORITY_SEAL)


def _component_authority(records) -> WallComponentCompletenessAuthority:
    member_ids=tuple(record.wall_candidate_id for record in records)
    member_sources=tuple(
        raw
        for record in records
        for raw in record.physical_identity.source_primitive_ids
    )
    record=WallComponentCompletenessRecord(
        record_id="component-completeness-1",
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        viewport_id="view-1",
        decision_scope_id=SCOPE,
        component_id="component-1",
        member_wall_ids=member_ids,
        member_source_primitive_ids=member_sources,
        positive_equivalence_groups=(),
        checked_withheld_observation_ids=("withheld-far",),
        source_scope_complete=False,
        source_scope_reason_codes=(
            "physical_wall_candidate_scope_resolved",
            "physical_wall_candidate_scope_cropped_at_viewport_boundary",
        ),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(WALL_COMPONENT_COMPLETE,),
        _seal=COMPONENT_RECORD_SEAL,
    )
    result=WallComponentCompletenessResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(WALL_COMPONENT_COMPLETE,),
        record=record,
    )
    mapping={
        (DOC,REV,SHA,SNAP,PAGE,SCOPE,wall_id): result
        for wall_id in member_ids
    }
    return WallComponentCompletenessAuthority(
        mapping,
        _seal=COMPONENT_AUTHORITY_SEAL,
    )


def _selector(wall_id: str) -> WallRoleSelector:
    return WallRoleSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
        physical_wall_id=wall_id,
    )


def test_incomplete_viewport_without_component_authority_cannot_mint_roles() -> None:
    records=_records()
    walls=_wall_authority(records)
    producer=WallRoleProducer.from_source_topology(
        physical_wall_candidate_authority=walls,
    )
    results=[producer.publish(_selector(r.wall_candidate_id)) for r in records]
    assert all(result.status is EvidenceResolutionStatus.ABSTAINED for result in results)


def test_proven_complete_component_mints_exact_external_and_internal_roles() -> None:
    records=_records()
    walls=_wall_authority(records)
    components=_component_authority(records)
    producer=WallRoleProducer.from_source_topology(
        physical_wall_candidate_authority=walls,
        wall_component_completeness_authority=components,
    )

    results={
        r.wall_candidate_id: producer.publish(_selector(r.wall_candidate_id))
        for r in records
    }
    resolved={
        wall_id: result.record.role
        for wall_id,result in results.items()
        if result.status is EvidenceResolutionStatus.CORROBORATED
        and result.record is not None
    }

    assert resolved["divider"] is WallRoleClassification.INTERNAL
    assert resolved["left"] is WallRoleClassification.EXTERNAL
    assert resolved["right"] is WallRoleClassification.EXTERNAL
    assert resolved["top-left"] is WallRoleClassification.EXTERNAL
    assert resolved["top-right"] is WallRoleClassification.EXTERNAL
    assert resolved["bottom-left"] is WallRoleClassification.EXTERNAL
    assert resolved["bottom-right"] is WallRoleClassification.EXTERNAL


def test_component_authority_for_other_lineage_does_not_mint_role() -> None:
    records=_records()
    walls=_wall_authority(records)
    components=_component_authority(records)
    # Querying an unknown wall remains fail-closed even though another complete
    # component exists in the same producer.
    producer=WallRoleProducer.from_source_topology(
        physical_wall_candidate_authority=walls,
        wall_component_completeness_authority=components,
    )
    result=producer.publish(_selector("not-a-wall"))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
