"""Independent expected-red validator for Item 19 caller-mintable finish authority.

This file is test-only.  It proves that caller-created WallFinishAssignment values
must never be sufficient to mint CORROBORATED/FIRM wall-finish quantity, even when
all upstream wall/net-wall geometry is genuinely producer-owned.
"""
from __future__ import annotations

from pb_migration_contracts import EvidenceResolutionStatus
from pb_net_wall_boolean_union_authority import (
    NET_WALL_BOOLEAN_UNION_RESOLVED,
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionRecord,
    NetWallBooleanUnionResult,
    NetWallBooleanUnionSelector,
    _AUTHORITY_SEAL as _NET_AUTH_SEAL,
)
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    _AUTHORITY_SEAL as _WALL_AUTH_SEAL,
    _ScopeKey,
    _decision_scope_id,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_wall_finish_propagation_authority import (
    WallFinishAssignment,
    WallFinishPropagationProducer,
    WallFinishPropagationSelector,
)

DECISION_SCOPE = _decision_scope_id("page_1")


def _wall_auth(wall_id: str) -> PhysicalWallCandidateAuthority:
    identity = PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id="view-1",
        candidate_identity_id=wall_id,
        path_fingerprint=((0.0, 0.0), (100.0, 0.0)),
        source_primitive_ids=("prim-1",),
        edge_ids=("edge-1",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    record = PhysicalWallCandidateRecord(
        wall_candidate_id=wall_id,
        wall_candidate=None,
        physical_identity=identity,
    )
    scope = PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=(record,),
        source_observation_ids=("obs-1",),
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="a" * 64,
        snapshot_id="snap-1",
        page_id="page_1",
        decision_scope_id=DECISION_SCOPE,
        reason_codes=(PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,),
    )
    key = _ScopeKey(
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="a" * 64,
        snapshot_id="snap-1",
        page_id="page_1",
        decision_scope_id=DECISION_SCOPE,
    )
    return PhysicalWallCandidateAuthority({key: scope}, _seal=_WALL_AUTH_SEAL)


def _net_auth(wall_id: str, trade_scope_id: str, net_area_m2: float = 10.0) -> NetWallBooleanUnionAuthority:
    selector = NetWallBooleanUnionSelector(
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="a" * 64,
        snapshot_id="snap-1",
        page_id="page_1",
        decision_scope_id=DECISION_SCOPE,
        physical_wall_id=wall_id,
        trade_scope_id=trade_scope_id,
    )
    record = NetWallBooleanUnionRecord(
        record_id=f"net-{wall_id}-{trade_scope_id}",
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        page_id=selector.page_id,
        decision_scope_id=selector.decision_scope_id,
        physical_wall_id=wall_id,
        gross_geometry_record_id=f"gross-{wall_id}",
        opening_universe_record_id=f"universe-{wall_id}",
        deduction_record_ids=(),
        union_geometry_id=f"geom-{wall_id}",
        net_area_m2=net_area_m2,
        gross_area_m2=net_area_m2,
        void_union_area_m2=0.0,
        trade_scope_id=trade_scope_id,
        gross_wall_record_id=f"gross-{wall_id}",
        opening_deduction_record_ids=(),
    )
    result = NetWallBooleanUnionResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(NET_WALL_BOOLEAN_UNION_RESOLVED,),
        record=record,
    )
    return NetWallBooleanUnionAuthority({selector.key: result}, _seal=_NET_AUTH_SEAL)


def _selector(wall_id: str, trade_scope_id: str) -> WallFinishPropagationSelector:
    return WallFinishPropagationSelector(
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="a" * 64,
        snapshot_id="snap-1",
        page_id="page_1",
        decision_scope_id=DECISION_SCOPE,
        physical_wall_id=wall_id,
        trade_scope_id=trade_scope_id,
    )


def _assert_caller_assignment_does_not_mint_authority(*, wall_id: str, trade_scope_id: str, face: str) -> None:
    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=_wall_auth(wall_id),
        net_wall_authority=_net_auth(wall_id, trade_scope_id),
        assignments=[
            WallFinishAssignment(
                assignment_id="caller-assignment",
                physical_wall_id=wall_id,
                trade_scope_id=trade_scope_id,
                wall_face_target=face,
                finish_material="caller-selected-material",
            )
        ],
    )
    result = producer.publish(_selector(wall_id, trade_scope_id))
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.record is None


def test_A_exact_class_caller_assignment_cannot_mint_single_face_authority() -> None:
    _assert_caller_assignment_does_not_mint_authority(
        wall_id="wall-1",
        trade_scope_id="internal_plaster",
        face="left_face",
    )


def test_B_exact_class_caller_assignment_cannot_mint_both_faces_authority() -> None:
    _assert_caller_assignment_does_not_mint_authority(
        wall_id="wall-1",
        trade_scope_id="internal_plaster",
        face="both_faces",
    )


def test_C_caller_can_not_invent_arbitrary_trade_scope_and_get_authority() -> None:
    _assert_caller_assignment_does_not_mint_authority(
        wall_id="wall-1",
        trade_scope_id="caller_invented_finish_trade",
        face="right_face",
    )


def test_D_scope_summary_from_caller_assignments_must_not_publish_numeric_authority() -> None:
    wall_id = "wall-1"
    trade = "internal_plaster"
    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=_wall_auth(wall_id),
        net_wall_authority=_net_auth(wall_id, trade, 12.0),
        assignments=[WallFinishAssignment("caller", wall_id, trade, "both_faces")],
    )
    summary = producer.publish_scope_summary(
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="a" * 64,
        snapshot_id="snap-1",
        page_id="page_1",
        decision_scope_id=DECISION_SCOPE,
        trade_scope_id=trade,
    )
    assert summary.is_scope_complete is False
    assert summary.total_trade_area_m2 is None
    assert summary.contributing_wall_records == ()


def test_E_authority_snapshot_cannot_expose_caller_minted_corroborated_record() -> None:
    wall_id = "wall-1"
    trade = "internal_plaster"
    selector = _selector(wall_id, trade)
    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=_wall_auth(wall_id),
        net_wall_authority=_net_auth(wall_id, trade),
        assignments=[WallFinishAssignment("caller", wall_id, trade, "both_faces")],
    )
    producer.publish(selector)
    replay = producer.authority().resolve(selector)
    assert replay.status is not EvidenceResolutionStatus.CORROBORATED
    assert replay.record is None
