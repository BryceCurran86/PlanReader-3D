"""Production + adversarial tests for pb_wall_thickness_face_authority (Item 27).

Tests cover:
  - Happy-path authenticated thickness and face geometry resolution
  - Default / assumed thicknesses (is_default=True, kind/method='model_default') fail closed
  - No 90mm / 110mm / 230mm assumption without explicit evidence
  - Unresolved thickness means face geometry is unavailable (ABSTAINED)
  - Mismatched physical wall candidate ID abstains
  - Stale source/revision/snapshot lineage fails closed
  - Conflicting thickness observations fail closed
  - Sealed authority constructor
  - Sealed producer constructor
  - Selector validation
"""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_scale_authority import (
    PhysicalScaleAuthority,
    PhysicalScaleEvidence,
    PhysicalScaleResult,
    PhysicalScaleSelector,
    _AUTHORITY_SEAL as SCALE_SEAL,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    PhysicalWallCandidateSelector,
    _AUTHORITY_SEAL as CANDIDATE_SEAL,
    _ScopeKey,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_wall_thickness_face_authority import (
    WALL_THICKNESS_DEFAULT_FORBIDDEN,
    WALL_THICKNESS_FACE_RESOLVED,
    WALL_THICKNESS_LINEAGE_MISMATCH,
    WALL_THICKNESS_RECORD_UNAVAILABLE,
    WALL_THICKNESS_SCALE_UNRESOLVED,
    WALL_THICKNESS_UNRESOLVED,
    WALL_THICKNESS_WALL_UNRESOLVED,
    WallFaceGeometryRecord,
    WallThicknessFaceAuthority,
    WallThicknessFaceProducer,
    WallThicknessFaceResult,
    WallThicknessFaceSelector,
    WallThicknessObservation,
)

DOC = "doc-thick-test"
REV = "R1"
SHA = "b" * 64
SNAP = "snap-thick-1"
PAGE = "page-T01"
SCOPE = f"wall-source:page-{PAGE}"
VP = "vp-T01"
WALL_A = "phys-wall-thick-A"
WALL_B = "phys-wall-thick-B"


def _selector(wall_id: str = WALL_A) -> WallThicknessFaceSelector:
    return WallThicknessFaceSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
        physical_wall_id=wall_id,
    )


def _obs(
    wall_id: str = WALL_A,
    thick_mm: float = 110.0,
    kind: str = "wall_callout_dimension",
    method: str = "direct_dimension",
    sha: str = SHA,
    rev: str = REV,
    snap: str = SNAP,
    is_default: bool = False,
    eid: str | None = None,
) -> WallThicknessObservation:
    if eid is None:
        eid = stable_contract_id("thick_obs", {"wall": wall_id, "thick": thick_mm})
    return WallThicknessObservation(
        evidence_id=eid,
        source_sha256=sha,
        revision_id=rev,
        snapshot_id=snap,
        page_id=PAGE,
        viewport_id=VP,
        thickness_mm=thick_mm,
        kind=kind,
        method=method,
        confidence=0.95,
        is_default=is_default,
    )


def _setup_authorities(*wall_ids: str):
    records = []
    for wid in wall_ids:
        ident = PhysicalWallIdentity(
            wall_candidate_id=wid, viewport_id=VP, candidate_identity_id=None,
            path_fingerprint=None, source_primitive_ids=(), edge_ids=(),
            status=EvidenceResolutionStatus.CORROBORATED,
        )
        rec = PhysicalWallCandidateRecord(
            wall_candidate_id=wid, wall_candidate=None, physical_identity=ident,
        )
        records.append(rec)

    cand_key = _ScopeKey(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
    )
    cand_auth = PhysicalWallCandidateAuthority(
        {cand_key: PhysicalWallCandidateScopeResult(
            status=EvidenceResolutionStatus.CORROBORATED, scope_complete=True,
            records=tuple(records), source_observation_ids=(), document_id=DOC,
            revision_id=REV, source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
            decision_scope_id=SCOPE, reason_codes=(),
        )}, _seal=CANDIDATE_SEAL,
    )

    scale_sel = PhysicalScaleSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=PAGE,
    )
    scale_ev = PhysicalScaleEvidence(
        selector=scale_sel, record_id="rec-scale", source_kind="graphic_scale",
        source_span_pt=100.0, physical_span_mm=1000.0, points_per_mm=0.1,
        mm_per_point=10.0, source_segment_observation_ids=(),
        source_text_observation_ids=(), viewport_id=None,
    )
    scale_auth = PhysicalScaleAuthority(
        {scale_sel.key: PhysicalScaleResult(
            status=EvidenceResolutionStatus.CORROBORATED, reason_codes=(), evidence=scale_ev,
        )}, _seal=SCALE_SEAL,
    )

    return cand_auth, scale_auth


def _producer(*wall_ids: str) -> WallThicknessFaceProducer:
    if not wall_ids:
        wall_ids = (WALL_A,)
    cand_auth, scale_auth = _setup_authorities(*wall_ids)
    return WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
    )


# ── Constructor Seals ─────────────────────────────────────────────────────────

def test_authority_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        WallThicknessFaceAuthority({})


def test_producer_constructor_sealed() -> None:
    cand_auth, scale_auth = _setup_authorities(WALL_A)
    with pytest.raises(TypeError, match="from_authorities"):
        WallThicknessFaceProducer(cand_auth, scale_auth)  # type: ignore[call-arg]


def test_producer_rejects_wrong_authority_types() -> None:
    cand_auth, scale_auth = _setup_authorities(WALL_A)
    with pytest.raises(TypeError, match="PhysicalWallCandidateAuthority"):
        WallThicknessFaceProducer.from_authorities(
            physical_wall_candidate_authority=object(),  # type: ignore[arg-type]
            physical_scale_authority=scale_auth,
        )
    with pytest.raises(TypeError, match="PhysicalScaleAuthority"):
        WallThicknessFaceProducer.from_authorities(
            physical_wall_candidate_authority=cand_auth,
            physical_scale_authority=object(),  # type: ignore[arg-type]
        )


# ── Happy Path ────────────────────────────────────────────────────────────────

def test_authenticated_110mm_thickness_resolved() -> None:
    prod = _producer(WALL_A)
    sel = _selector(WALL_A)
    obs = [_obs(WALL_A, thick_mm=110.0)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.thickness_mm == 110.0
    assert res.record.thickness_m == 0.11
    assert WALL_THICKNESS_FACE_RESOLVED in res.reason_codes


def test_authenticated_230mm_thickness_resolved() -> None:
    prod = _producer(WALL_A)
    sel = _selector(WALL_A)
    obs = [_obs(WALL_A, thick_mm=230.0)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.thickness_mm == 230.0
    assert res.record.thickness_m == 0.23


# ── Adversarial: No default / assumed thickness ───────────────────────────────

def test_is_default_flag_rejected() -> None:
    prod = _producer(WALL_A)
    sel = _selector(WALL_A)
    obs = [_obs(WALL_A, thick_mm=110.0, is_default=True)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_DEFAULT_FORBIDDEN in res.reason_codes


def test_model_default_kind_rejected() -> None:
    prod = _producer(WALL_A)
    sel = _selector(WALL_A)
    obs = [_obs(WALL_A, thick_mm=90.0, kind="model_default")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_DEFAULT_FORBIDDEN in res.reason_codes


def test_assumed_method_rejected() -> None:
    prod = _producer(WALL_A)
    sel = _selector(WALL_A)
    obs = [_obs(WALL_A, thick_mm=230.0, method="assumed_thickness")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_DEFAULT_FORBIDDEN in res.reason_codes


# ── Adversarial: Unresolved / Stale / Conflict ───────────────────────────────

def test_empty_observations_abstains() -> None:
    prod = _producer(WALL_A)
    sel = _selector(WALL_A)
    res = prod.publish(sel, [])
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_UNRESOLVED in res.reason_codes
    assert res.record is None


def test_stale_lineage_fails_closed() -> None:
    prod = _producer(WALL_A)
    sel = _selector(WALL_A)
    obs = [_obs(WALL_A, thick_mm=110.0, sha="c" * 64)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert WALL_THICKNESS_LINEAGE_MISMATCH in res.reason_codes


def test_conflicting_thicknesses_fails_closed() -> None:
    prod = _producer(WALL_A)
    sel = _selector(WALL_A)
    obs = [
        _obs(WALL_A, thick_mm=110.0, eid="ev-110"),
        _obs(WALL_A, thick_mm=230.0, eid="ev-230"),
    ]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert WALL_THICKNESS_UNRESOLVED in res.reason_codes


def test_unknown_physical_wall_abstains() -> None:
    prod = _producer(WALL_A)
    sel = _selector("phys-wall-UNKNOWN")
    obs = [_obs("phys-wall-UNKNOWN", thick_mm=110.0)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_WALL_UNRESOLVED in res.reason_codes


# ── Authority Lookup ──────────────────────────────────────────────────────────

def test_authority_lookup_published_record() -> None:
    prod = _producer(WALL_A)
    sel = _selector(WALL_A)
    prod.publish(sel, [_obs(WALL_A, thick_mm=110.0)])
    auth = prod.authority()
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.thickness_mm == 110.0


def test_authority_lookup_missing_abstains() -> None:
    prod = _producer(WALL_A)
    auth = prod.authority()
    sel = _selector(WALL_A)
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_RECORD_UNAVAILABLE in res.reason_codes


def test_authority_lookup_wrong_selector_type_raises() -> None:
    prod = _producer(WALL_A)
    auth = prod.authority()
    with pytest.raises(TypeError, match="WallThicknessFaceSelector"):
        auth.resolve("not-a-selector")  # type: ignore[arg-type]


# ── Validation ────────────────────────────────────────────────────────────────

def test_observation_invalid_thickness_raises() -> None:
    with pytest.raises(ValueError, match="thickness_mm"):
        WallThicknessObservation(
            evidence_id="ev-bad", source_sha256=SHA, revision_id=REV,
            snapshot_id=SNAP, page_id=PAGE, viewport_id=VP,
            thickness_mm=-10.0, kind="wall_callout", method="direct", confidence=0.9,
        )


def test_selector_empty_field_raises() -> None:
    with pytest.raises(ValueError):
        WallThicknessFaceSelector(
            document_id="", revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
            physical_wall_id=WALL_A,
        )
