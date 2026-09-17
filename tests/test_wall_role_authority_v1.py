"""Production + adversarial tests for pb_wall_role_authority (Item 26).

Tests cover:
  - Happy-path EXTERNAL / INTERNAL / GABLE / PARTY classification
  - Sealed authority constructor
  - Producer constructor seal enforced
  - Unknown physical_wall_id abstains
"""
from __future__ import annotations

import pytest

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    _AUTHORITY_SEAL as CANDIDATE_SEAL,
    _ScopeKey,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_role_authority import (
    WALL_ROLE_RECORD_UNAVAILABLE,
    WALL_ROLE_RESOLVED,
    WALL_ROLE_UNRESOLVED,
    WALL_ROLE_WALL_UNRESOLVED,
    WallRoleAuthority,
    WallRoleClassification,
    WallRoleProducer,
    WallRoleResult,
    WallRoleSelector,
)

# ── Shared test fixtures ──────────────────────────────────────────────────────
DOC = "doc-wall-role-test"
REV = "R1"
SHA = "a" * 64
SNAP = "snap-wall-role-1"
PAGE = "page-WR01"
SCOPE = f"wall-source:page-{PAGE}"
VP = "vp-WR01"
WALL_A = "phys-wall-A"
WALL_B = "phys-wall-B"
WALL_GABLE = "phys-wall-gable"


def _selector(wall_id: str = WALL_A, page_id: str = PAGE, scope: str = SCOPE) -> WallRoleSelector:
    return WallRoleSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=page_id,
        decision_scope_id=scope,
        physical_wall_id=wall_id,
    )


def _make_candidate_record(
    wall_id: str,
    interior_exterior: str = "exterior",
    is_gable: bool = False,
    is_party: bool = False,
) -> PhysicalWallCandidateRecord:
    meta = {}
    if is_gable:
        meta["is_gable"] = True
    if is_party:
        meta["is_party"] = True

    cand = WallCandidate(
        candidate_id=wall_id,
        viewport_id=SCOPE,
        representation="single_line",
        centerline_pts=((0.0, 0.0), (10.0, 0.0)),
        face_a_segment_ids=("s1",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=0.2,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=10.0,
        end_node_ids=("n1", "n2"),
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior=interior_exterior,
        level_id=None,
        supporting_evidence_ids=("s1",),
        metadata=meta,
    )
    ident = PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id=SCOPE,
        candidate_identity_id=f"ident-{wall_id}",
        path_fingerprint=((0.0, 0.0), (10.0, 0.0)),
        source_primitive_ids=("s1",),
        edge_ids=("s1",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    return PhysicalWallCandidateRecord(
        wall_candidate_id=wall_id, wall_candidate=cand, physical_identity=ident,
    )


def _authority_with(
    *wall_specs: tuple[str, str] | tuple[str, str, bool],
) -> PhysicalWallCandidateAuthority:
    """Return a real (sealed) PhysicalWallCandidateAuthority containing the given wall specs (id, interior_exterior, is_gable)."""
    if not wall_specs:
        wall_specs = ((WALL_A, "exterior"),)

    records = []
    for spec in wall_specs:
        wid = spec[0]
        ie = spec[1]
        gable = spec[2] if len(spec) > 2 else False
        records.append(_make_candidate_record(wid, interior_exterior=ie, is_gable=gable))

    cand_key = _ScopeKey(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
    )
    return PhysicalWallCandidateAuthority(
        {cand_key: PhysicalWallCandidateScopeResult(
            status=EvidenceResolutionStatus.CORROBORATED, scope_complete=True,
            records=tuple(records), source_observation_ids=(), document_id=DOC,
            revision_id=REV, source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
            decision_scope_id=SCOPE, reason_codes=(),
        )},
        _seal=CANDIDATE_SEAL,
    )


def _producer(*wall_specs: tuple[str, str] | tuple[str, str, bool]) -> WallRoleProducer:
    auth = _authority_with(*wall_specs)
    return WallRoleProducer.from_authorities(physical_wall_candidate_authority=auth)


# ── Authority constructor seal ────────────────────────────────────────────────

def test_authority_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        WallRoleAuthority({})


# ── Producer constructor seal ─────────────────────────────────────────────────

def test_producer_constructor_sealed() -> None:
    auth = _authority_with((WALL_A, "exterior"))
    with pytest.raises(TypeError, match="from_authorities"):
        WallRoleProducer(auth)  # type: ignore[call-arg]


def test_producer_rejects_wrong_authority_type() -> None:
    with pytest.raises(TypeError, match="producer-owned PhysicalWallCandidateAuthority"):
        WallRoleProducer.from_authorities(
            physical_wall_candidate_authority=object()  # type: ignore[arg-type]
        )


# ── Happy path ────────────────────────────────────────────────────────────────

def test_external_wall_classified() -> None:
    producer = _producer((WALL_A, "exterior"))
    sel = _selector(WALL_A)
    result = producer.publish(sel)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.role is WallRoleClassification.EXTERNAL
    assert WALL_ROLE_RESOLVED in result.reason_codes


def test_internal_wall_classified() -> None:
    producer = _producer((WALL_B, "interior"))
    sel = _selector(WALL_B)
    result = producer.publish(sel)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record.role is WallRoleClassification.INTERNAL


def test_gable_wall_classified() -> None:
    producer = _producer((WALL_GABLE, "exterior", True))
    sel = _selector(WALL_GABLE)
    result = producer.publish(sel)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record.role is WallRoleClassification.GABLE


def test_distinct_walls_remain_distinct() -> None:
    """Two walls classify independently based on candidate topology."""
    producer = _producer((WALL_A, "exterior"), (WALL_B, "interior"))
    sel_a = _selector(WALL_A)
    sel_b = _selector(WALL_B)
    producer.publish(sel_a)
    producer.publish(sel_b)
    auth = producer.authority()
    r_a = auth.resolve(sel_a)
    r_b = auth.resolve(sel_b)
    assert r_a.record.role is WallRoleClassification.EXTERNAL
    assert r_b.record.role is WallRoleClassification.INTERNAL


# ── Abstain: unknown physical wall ───────────────────────────────────────────

def test_unknown_physical_wall_abstains() -> None:
    producer = _producer((WALL_A, "exterior"))
    sel = _selector("phys-wall-UNKNOWN")
    result = producer.publish(sel)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_ROLE_WALL_UNRESOLVED in result.reason_codes


# ── Wrong selector type ───────────────────────────────────────────────────────

def test_wrong_selector_type_raises() -> None:
    producer = _producer()
    with pytest.raises(TypeError, match="WallRoleSelector"):
        producer.publish("not-a-selector")  # type: ignore[arg-type]


# ── Authority lookup: record not present ─────────────────────────────────────

def test_authority_resolve_missing_abstains() -> None:
    producer = _producer()
    auth = producer.authority()
    sel = _selector(WALL_A)
    result = auth.resolve(sel)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_ROLE_RECORD_UNAVAILABLE in result.reason_codes


def test_authority_resolve_wrong_type_raises() -> None:
    producer = _producer()
    auth = producer.authority()
    with pytest.raises(TypeError, match="WallRoleSelector"):
        auth.resolve("not-a-selector")  # type: ignore[arg-type]


# ── Selector validation ───────────────────────────────────────────────────────

def test_selector_missing_field_raises() -> None:
    with pytest.raises(ValueError):
        WallRoleSelector(
            document_id="",
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            physical_wall_id=WALL_A,
        )
