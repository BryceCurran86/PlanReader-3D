"""Adversarial tests for fail-closed Item 28 wall/finish recovery."""

from __future__ import annotations

import pytest

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_ghazi_wall_finish_recovery_authority import (
    GHAZI_RECOVERY_GROSS_NET_MISMATCH,
    GHAZI_RECOVERY_LINEAGE_MISMATCH,
    GHAZI_RECOVERY_NET_AREA_UNAVAILABLE,
    GHAZI_RECOVERY_RECORD_UNAVAILABLE,
    GHAZI_RECOVERY_UNRESOLVED,
    GhaziRecoveryRootCause,
    GhaziWallFinishRecoveryAuthority,
    GhaziWallFinishRecoveryProducer,
    GhaziWallFinishRecoverySelector,
)
from pb_gross_wall_geometry_authority import (
    GrossWallGeometryAuthority,
    GrossWallGeometryRecord,
    GrossWallGeometryResult,
    _AUTHORITY_SEAL as GROSS_SEAL,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_net_wall_boolean_union_authority import (
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionRecord,
    NetWallBooleanUnionResult,
    _AUTHORITY_SEAL as NET_SEAL,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    _AUTHORITY_SEAL as CANDIDATE_SEAL,
    _ScopeKey,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_wall_finish_propagation_authority import (
    WallFinishPropagationAuthority,
    _AUTHORITY_SEAL as FINISH_SEAL,
)
from pb_wall_role_authority import (
    WallRoleAuthority,
    WallRoleClassification,
    WallRoleRecord,
    WallRoleResult,
    _AUTHORITY_SEAL as ROLE_SEAL,
    _RECORD_SEAL as ROLE_RECORD_SEAL,
)
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_thickness_face_authority import (
    WallFaceGeometryRecord,
    WallThicknessFaceAuthority,
    WallThicknessFaceResult,
    _AUTHORITY_SEAL as THICKNESS_SEAL,
    _RECORD_SEAL as THICKNESS_RECORD_SEAL,
)

DOC = "doc-item28"
REV = "R1"
SHA = "f" * 64
SNAP = "snap-1"
PAGE = "p1"
SCOPE = f"wall-source:page-{PAGE}"
WALL = "wall-1"
TRADE = "trade-masonry"


def _selector(
    *,
    scope: str = SCOPE,
    wall: str = WALL,
    trade: str = TRADE,
) -> GhaziWallFinishRecoverySelector:
    return GhaziWallFinishRecoverySelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=scope,
        physical_wall_id=wall,
        trade_scope_id=trade,
    )


def _candidate_record(*, length_m: float = 999.0) -> PhysicalWallCandidateRecord:
    candidate = WallCandidate(
        candidate_id=WALL,
        viewport_id=SCOPE,
        representation="single_line",
        centerline_pts=((0.0, 0.0), (length_m, 0.0)),
        face_a_segment_ids=("s1",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=9.99,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=length_m,
        end_node_ids=("n1", "n2"),
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior="external",
        level_id=None,
        supporting_evidence_ids=("candidate-diagnostic",),
        metadata={},
    )
    identity = PhysicalWallIdentity(
        wall_candidate_id=WALL,
        viewport_id=SCOPE,
        candidate_identity_id="ident-wall-1",
        path_fingerprint=((0.0, 0.0), (length_m, 0.0)),
        source_primitive_ids=("s1",),
        edge_ids=("s1",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    return PhysicalWallCandidateRecord(
        wall_candidate_id=WALL,
        wall_candidate=candidate,
        physical_identity=identity,
    )


def _candidate_authority(
    *,
    records: tuple[PhysicalWallCandidateRecord, ...] | None = None,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
    result_scope: str = SCOPE,
    result_revision: str = REV,
) -> PhysicalWallCandidateAuthority:
    key = _ScopeKey(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
    )
    return PhysicalWallCandidateAuthority(
        {
            key: PhysicalWallCandidateScopeResult(
                status=status,
                scope_complete=True,
                records=tuple(records if records is not None else (_candidate_record(),)),
                source_observation_ids=(),
                document_id=DOC,
                revision_id=result_revision,
                source_sha256=SHA,
                snapshot_id=SNAP,
                page_id=PAGE,
                decision_scope_id=result_scope,
                reason_codes=(),
            )
        },
        _seal=CANDIDATE_SEAL,
    )


def _role_authority(
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
) -> WallRoleAuthority:
    key = (DOC, REV, SHA, SNAP, PAGE, SCOPE, WALL)
    record = None
    if status is EvidenceResolutionStatus.CORROBORATED:
        record = WallRoleRecord(
            record_id="role-record",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            physical_wall_id=WALL,
            role=WallRoleClassification.EXTERNAL,
            corroborating_evidence_ids=("role-evidence",),
            _seal=ROLE_RECORD_SEAL,
        )
    return WallRoleAuthority(
        {key: WallRoleResult(status=status, reason_codes=("role-state",), record=record)},
        _seal=ROLE_SEAL,
    )


def _thickness_authority(
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
) -> WallThicknessFaceAuthority:
    key = (DOC, REV, SHA, SNAP, PAGE, SCOPE, WALL)
    record = None
    if status is EvidenceResolutionStatus.CORROBORATED:
        record = WallFaceGeometryRecord(
            record_id="thickness-record",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            physical_wall_id=WALL,
            thickness_m=0.23,
            thickness_mm=230.0,
            length_m=8.0,
            centerline_wkb_hex="",
            face_left_wkb_hex="",
            face_right_wkb_hex="",
            polygon_wkb_hex="",
            corroborating_evidence_ids=("thickness-evidence",),
            _seal=THICKNESS_RECORD_SEAL,
        )
    return WallThicknessFaceAuthority(
        {
            key: WallThicknessFaceResult(
                status=status,
                reason_codes=("thickness-state",),
                record=record,
            )
        },
        _seal=THICKNESS_SEAL,
    )


def _gross_authority(
    *,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
    record_id: str = "gross-record",
    length_m: float = 8.0,
    height_m: float = 3.0,
    gross_area_m2: float = 24.0,
) -> GrossWallGeometryAuthority:
    key = (DOC, REV, SHA, SNAP, PAGE, SCOPE, WALL)
    record = None
    if status is EvidenceResolutionStatus.CORROBORATED:
        record = GrossWallGeometryRecord(
            record_id=record_id,
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            physical_wall_id=WALL,
            wall_local_frame_id="frame-1",
            length_m=length_m,
            height_m=height_m,
            gross_area_m2=gross_area_m2,
            polygon_wkb_hex="",
        )
    return GrossWallGeometryAuthority(
        {key: GrossWallGeometryResult(status=status, reason_codes=("gross-state",), record=record)},
        _seal=GROSS_SEAL,
    )


def _net_authority(
    *,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
    gross_record_id: str = "gross-record",
    gross_area_m2: float = 24.0,
    net_area_m2: float | None = 20.0,
) -> NetWallBooleanUnionAuthority:
    key = (DOC, REV, SHA, SNAP, PAGE, SCOPE, WALL, TRADE)
    record = None
    if status is EvidenceResolutionStatus.CORROBORATED:
        record = NetWallBooleanUnionRecord(
            record_id="net-record",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            physical_wall_id=WALL,
            gross_geometry_record_id=gross_record_id,
            opening_universe_record_id="opening-universe",
            deduction_record_ids=("deduction-1",),
            union_geometry_id="union-1",
            net_area_m2=net_area_m2,
            gross_area_m2=gross_area_m2,
            trade_scope_id=TRADE,
        )
    return NetWallBooleanUnionAuthority(
        {key: NetWallBooleanUnionResult(status=status, reason_codes=("net-state",), record=record)},
        _seal=NET_SEAL,
    )


def _finish_authority_empty() -> WallFinishPropagationAuthority:
    return WallFinishPropagationAuthority({}, _seal=FINISH_SEAL)


def _producer(
    *,
    candidate: PhysicalWallCandidateAuthority | None = None,
    role: WallRoleAuthority | None = None,
    thickness: WallThicknessFaceAuthority | None = None,
    gross: GrossWallGeometryAuthority | None = None,
    net: NetWallBooleanUnionAuthority | None = None,
    finish: WallFinishPropagationAuthority | None = None,
) -> GhaziWallFinishRecoveryProducer:
    return GhaziWallFinishRecoveryProducer.from_authorities(
        physical_wall_candidate_authority=candidate or _candidate_authority(),
        wall_role_authority=role,
        wall_thickness_face_authority=thickness,
        gross_wall_geometry_authority=gross,
        net_wall_boolean_union_authority=net,
        wall_finish_propagation_authority=finish,
    )


def test_authority_constructor_is_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        GhaziWallFinishRecoveryAuthority({})


def test_direct_producer_constructor_is_sealed() -> None:
    with pytest.raises(TypeError, match="from_authorities"):
        GhaziWallFinishRecoveryProducer(_candidate_authority())


def test_caller_cannot_switch_required_evidence_off() -> None:
    producer = _producer()
    with pytest.raises(TypeError):
        producer.publish(_selector(), require_wall_role=False)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        producer.publish(_selector(), require_wall_thickness=False)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        producer.publish(_selector(), require_finish_binding=False)  # type: ignore[call-arg]


def test_missing_wall_candidate_abstains() -> None:
    producer = _producer(candidate=_candidate_authority(records=()))
    result = producer.publish(_selector())
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert GhaziRecoveryRootCause.WALL_INSTANCE_MISSING.value in result.reason_codes
    assert result.record is None


def test_candidate_scope_or_lineage_mismatch_conflicts() -> None:
    producer = _producer(
        candidate=_candidate_authority(result_scope="other-scope")
    )
    result = producer.publish(_selector())
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert GHAZI_RECOVERY_LINEAGE_MISMATCH in result.reason_codes


def test_wall_role_is_always_required() -> None:
    result = _producer().publish(_selector())
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert GhaziRecoveryRootCause.WALL_ROLE_UNRESOLVED.value in result.reason_codes


def test_wall_role_conflict_stays_conflict() -> None:
    result = _producer(
        role=_role_authority(EvidenceResolutionStatus.CONFLICT)
    ).publish(_selector())
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert GhaziRecoveryRootCause.WALL_ROLE_UNRESOLVED.value in result.reason_codes


def test_wall_thickness_is_always_required() -> None:
    result = _producer(role=_role_authority()).publish(_selector())
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert GhaziRecoveryRootCause.WALL_THICKNESS_UNRESOLVED.value in result.reason_codes


def test_gross_geometry_is_required_for_length_height_and_area() -> None:
    result = _producer(
        role=_role_authority(),
        thickness=_thickness_authority(),
    ).publish(_selector())
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert GhaziRecoveryRootCause.WALL_HEIGHT_UNRESOLVED.value in result.reason_codes


def test_net_none_never_becomes_zero() -> None:
    result = _producer(
        role=_role_authority(),
        thickness=_thickness_authority(),
        gross=_gross_authority(),
        net=_net_authority(net_area_m2=None),
    ).publish(_selector())
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert GHAZI_RECOVERY_NET_AREA_UNAVAILABLE in result.reason_codes
    assert GhaziRecoveryRootCause.OPENING_DEDUCTION_UNRESOLVED.value in result.reason_codes
    assert result.record is None


def test_net_wall_must_bind_to_exact_gross_record() -> None:
    result = _producer(
        role=_role_authority(),
        thickness=_thickness_authority(),
        gross=_gross_authority(record_id="gross-A"),
        net=_net_authority(gross_record_id="gross-B"),
    ).publish(_selector())
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert GHAZI_RECOVERY_GROSS_NET_MISMATCH in result.reason_codes


def test_net_gross_area_must_match_gross_geometry() -> None:
    result = _producer(
        role=_role_authority(),
        thickness=_thickness_authority(),
        gross=_gross_authority(gross_area_m2=24.0),
        net=_net_authority(gross_area_m2=25.0),
    ).publish(_selector())
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert GHAZI_RECOVERY_GROSS_NET_MISMATCH in result.reason_codes


def test_current_item19a_finish_boundary_prevents_false_positive() -> None:
    result = _producer(
        role=_role_authority(),
        thickness=_thickness_authority(),
        gross=_gross_authority(),
        net=_net_authority(),
        finish=_finish_authority_empty(),
    ).publish(_selector())
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert GhaziRecoveryRootCause.FINISH_ASSIGNMENT_UNRESOLVED.value in result.reason_codes
    assert result.record is None


def test_provisional_candidate_length_does_not_create_height() -> None:
    # Candidate says 999m. Authoritative gross geometry says 8m x 3m.
    # Item 28 must never reconstruct height from candidate.length_m.
    result = _producer(
        candidate=_candidate_authority(records=(_candidate_record(length_m=999.0),)),
        role=_role_authority(),
        thickness=_thickness_authority(),
        gross=_gross_authority(length_m=8.0, height_m=3.0, gross_area_m2=24.0),
        net=_net_authority(),
        finish=_finish_authority_empty(),
    ).publish(_selector())
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert GhaziRecoveryRootCause.FINISH_ASSIGNMENT_UNRESOLVED.value in result.reason_codes


def test_unpublished_selector_returns_abstained() -> None:
    producer = _producer()
    auth = producer.authority()
    result = auth.resolve(_selector(wall="unknown-wall"))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert GHAZI_RECOVERY_RECORD_UNAVAILABLE in result.reason_codes
