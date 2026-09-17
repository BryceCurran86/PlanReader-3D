"""Production + adversarial tests for pb_ghazi_wall_finish_recovery_authority (Item 28).

Tests cover:
  - Happy-path generic recovery (root_cause=RESOLVED)
  - Missing physical wall candidate abstains (WALL_INSTANCE_MISSING)
  - Sealed authority and producer constructors
  - Selector validation
"""
from __future__ import annotations

import pytest

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    _ScopeKey,
    _AUTHORITY_SEAL as CAND_AUTHORITY_SEAL,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_wall_room_topology_contracts import JunctionType, WallCandidate

from pb_ghazi_wall_finish_recovery_authority import (
    GHAZI_RECOVERY_RECORD_UNAVAILABLE,
    GHAZI_RECOVERY_RESOLVED,
    GHAZI_RECOVERY_UNRESOLVED,
    GhaziRecoveryRootCause,
    GhaziWallFinishRecoveryAuthority,
    GhaziWallFinishRecoveryProducer,
    GhaziWallFinishRecoveryRecord,
    GhaziWallFinishRecoveryResult,
    GhaziWallFinishRecoverySelector,
)

DOC = "doc-rec-test"
REV = "R1"
SHA = "1" * 64
SNAP = "snap-rec-1"
PAGE = "page-REC01"
SCOPE = f"wall-source:page-{PAGE}"
VP = "vp-REC01"
WALL = "phys-wall-rec-1"
TRADE = "plastering_internal_walls"


def _selector(
    wall_id: str = WALL,
    trade_id: str = TRADE,
) -> GhaziWallFinishRecoverySelector:
    return GhaziWallFinishRecoverySelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
        physical_wall_id=wall_id,
        trade_scope_id=trade_id,
    )


def _setup_candidate_authority(
    wall_id: str = WALL,
    length_m: float = 10.0,
    height_m: float = 3.0,
) -> PhysicalWallCandidateAuthority:
    cand = WallCandidate(
        candidate_id=wall_id,
        viewport_id=SCOPE,
        representation="single_line",
        centerline_pts=((0.0, 0.0), (length_m, 0.0)),
        face_a_segment_ids=("s1",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=0.2,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=length_m,
        end_node_ids=("n1", "n2"),
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior="interior",
        level_id=None,
        supporting_evidence_ids=("s1",),
    )
    ident = PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id=SCOPE,
        candidate_identity_id=f"ident-{wall_id}",
        path_fingerprint=((0.0, 0.0), (length_m, 0.0)),
        source_primitive_ids=("s1",),
        edge_ids=("s1",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    rec = PhysicalWallCandidateRecord(
        wall_candidate_id=wall_id,
        wall_candidate=cand,
        physical_identity=ident,
    )
    scope_key = _ScopeKey(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
    )
    scope_res = PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=(rec,),
        source_observation_ids=(),
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
        reason_codes=(),
    )
    return PhysicalWallCandidateAuthority({scope_key: scope_res}, _seal=CAND_AUTHORITY_SEAL)


def _producer(
    wall_id: str = WALL,
    length_m: float = 10.0,
    height_m: float = 3.0,
) -> GhaziWallFinishRecoveryProducer:
    cand_auth = _setup_candidate_authority(wall_id, length_m, height_m)
    return GhaziWallFinishRecoveryProducer.from_authorities(physical_wall_candidate_authority=cand_auth)


# ── Constructor Seals ─────────────────────────────────────────────────────────

def test_authority_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        GhaziWallFinishRecoveryAuthority({})


def test_producer_constructor_sealed() -> None:
    cand_auth = _setup_candidate_authority()
    with pytest.raises(TypeError, match="from_authorities"):
        GhaziWallFinishRecoveryProducer(cand_auth)  # type: ignore[call-arg]


# ── Happy Path ────────────────────────────────────────────────────────────────

def test_generic_recovery_resolved() -> None:
    prod = _producer(length_m=10.0, height_m=3.0)
    sel = _selector()
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.gross_area_m2 == 30.0
    assert res.record.net_area_m2 == 30.0
    assert res.record.root_cause is GhaziRecoveryRootCause.RESOLVED
    assert GHAZI_RECOVERY_RESOLVED in res.reason_codes


# ── Root Cause Classifications ─────────────────────────────────────────────

def test_missing_wall_candidate_classified() -> None:
    prod = _producer()
    sel = _selector(wall_id="non-existent-wall")
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GhaziRecoveryRootCause.WALL_INSTANCE_MISSING.value in res.reason_codes
    assert res.record is None


# ── Authority Lookup ──────────────────────────────────────────────────────────

def test_authority_lookup_published_record() -> None:
    prod = _producer()
    sel = _selector()
    prod.publish(sel)
    auth = prod.authority()
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.gross_area_m2 == 30.0


def test_authority_lookup_missing_abstains() -> None:
    prod = _producer()
    auth = prod.authority()
    sel = _selector(wall_id="other-wall")
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GHAZI_RECOVERY_RECORD_UNAVAILABLE in res.reason_codes


def test_authority_lookup_wrong_selector_type_raises() -> None:
    prod = _producer()
    auth = prod.authority()
    with pytest.raises(TypeError, match="GhaziWallFinishRecoverySelector"):
        auth.resolve("not-a-selector")  # type: ignore[arg-type]


# ── Validation ────────────────────────────────────────────────────────────────

def test_selector_empty_field_raises() -> None:
    with pytest.raises(ValueError):
        GhaziWallFinishRecoverySelector(
            document_id="", revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
            physical_wall_id=WALL, trade_scope_id=TRADE,
        )
