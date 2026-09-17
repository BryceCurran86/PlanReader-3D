"""Production + adversarial tests for pb_ghazi_wall_finish_recovery_authority (Item 28).

Tests cover:
  - Happy-path generic recovery (root_cause=RESOLVED)
  - Root cause classification when recovery fails (WALL_ROLE_UNRESOLVED, OPENING_DEDUCTION_UNRESOLVED, etc.)
  - Rejection of hardcoded benchmark values / project-specific constants (ABSTAINED)
  - Stale lineage fails closed (CONFLICT)
  - Conflicting area quantities fail closed (CONFLICT)
  - Sealed authority constructor
  - Selector validation
"""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_ghazi_wall_finish_recovery_authority import (
    GHAZI_RECOVERY_HARDCODED_VALUES_REJECTED,
    GHAZI_RECOVERY_LINEAGE_MISMATCH,
    GHAZI_RECOVERY_RECORD_UNAVAILABLE,
    GHAZI_RECOVERY_RESOLVED,
    GHAZI_RECOVERY_UNRESOLVED,
    GhaziRecoveryRootCause,
    GhaziWallFinishRecoveryAuthority,
    GhaziWallFinishRecoveryEvidence,
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
SCOPE = f"recovery-source:page-{PAGE}"
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


def _obs(
    wall_id: str = WALL,
    trade_id: str = TRADE,
    gross: float = 30.0,
    net: float = 26.0,
    root_cause: GhaziRecoveryRootCause = GhaziRecoveryRootCause.RESOLVED,
    kind: str = "authenticated_finish_propagation",
    sha: str = SHA,
    rev: str = REV,
    snap: str = SNAP,
    is_hardcoded: bool = False,
    eid: str | None = None,
) -> GhaziWallFinishRecoveryEvidence:
    if eid is None:
        eid = stable_contract_id("obs", {"wall": wall_id, "cause": root_cause.value})
    return GhaziWallFinishRecoveryEvidence(
        evidence_id=eid,
        source_sha256=sha,
        revision_id=rev,
        snapshot_id=snap,
        page_id=PAGE,
        viewport_id=VP,
        gross_area_m2=gross,
        net_area_m2=net,
        root_cause=root_cause,
        kind=kind,
        confidence=0.95,
        is_hardcoded=is_hardcoded,
    )


# ── Constructor Seals ─────────────────────────────────────────────────────────

def test_authority_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        GhaziWallFinishRecoveryAuthority({})


def test_producer_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="create()"):
        GhaziWallFinishRecoveryProducer()  # type: ignore[call-arg]


# ── Happy Path ────────────────────────────────────────────────────────────────

def test_generic_recovery_resolved() -> None:
    prod = GhaziWallFinishRecoveryProducer.create()
    sel = _selector()
    obs = [_obs(gross=30.0, net=26.0, root_cause=GhaziRecoveryRootCause.RESOLVED)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.gross_area_m2 == 30.0
    assert res.record.net_area_m2 == 26.0
    assert res.record.root_cause is GhaziRecoveryRootCause.RESOLVED
    assert GHAZI_RECOVERY_RESOLVED in res.reason_codes


# ── Root Cause Classifications ─────────────────────────────────────────────

def test_wall_role_unresolved_classified() -> None:
    prod = GhaziWallFinishRecoveryProducer.create()
    sel = _selector()
    obs = [_obs(root_cause=GhaziRecoveryRootCause.WALL_ROLE_UNRESOLVED)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GhaziRecoveryRootCause.WALL_ROLE_UNRESOLVED.value in res.reason_codes
    assert res.record is None


def test_opening_deduction_unresolved_classified() -> None:
    prod = GhaziWallFinishRecoveryProducer.create()
    sel = _selector()
    obs = [_obs(root_cause=GhaziRecoveryRootCause.OPENING_DEDUCTION_UNRESOLVED)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GhaziRecoveryRootCause.OPENING_DEDUCTION_UNRESOLVED.value in res.reason_codes


def test_cross_sheet_evidence_missing_classified() -> None:
    prod = GhaziWallFinishRecoveryProducer.create()
    sel = _selector()
    obs = [_obs(root_cause=GhaziRecoveryRootCause.CROSS_SHEET_EVIDENCE_MISSING)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GhaziRecoveryRootCause.CROSS_SHEET_EVIDENCE_MISSING.value in res.reason_codes


# ── Adversarial: Hardcoded Benchmark Values ──────────────────────────────────

def test_hardcoded_benchmark_values_rejected() -> None:
    prod = GhaziWallFinishRecoveryProducer.create()
    sel = _selector()
    obs = [_obs(is_hardcoded=True)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GHAZI_RECOVERY_HARDCODED_VALUES_REJECTED in res.reason_codes


def test_hardcoded_kind_string_rejected() -> None:
    prod = GhaziWallFinishRecoveryProducer.create()
    sel = _selector()
    obs = [_obs(kind="hardcoded_benchmark_constant")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GHAZI_RECOVERY_HARDCODED_VALUES_REJECTED in res.reason_codes


# ── Adversarial: Stale & Conflict ─────────────────────────────────────────────

def test_stale_lineage_fails_closed() -> None:
    prod = GhaziWallFinishRecoveryProducer.create()
    sel = _selector()
    obs = [_obs(sha="2" * 64)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert GHAZI_RECOVERY_LINEAGE_MISMATCH in res.reason_codes


def test_conflicting_area_quantities_conflicts() -> None:
    prod = GhaziWallFinishRecoveryProducer.create()
    sel = _selector()
    obs = [
        _obs(gross=30.0, net=26.0, eid="obs-1"),
        _obs(gross=30.0, net=20.0, eid="obs-2"),
    ]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert GHAZI_RECOVERY_UNRESOLVED in res.reason_codes


def test_empty_observations_abstains() -> None:
    prod = GhaziWallFinishRecoveryProducer.create()
    sel = _selector()
    res = prod.publish(sel, [])
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GHAZI_RECOVERY_UNRESOLVED in res.reason_codes


# ── Authority Lookup ──────────────────────────────────────────────────────────

def test_authority_lookup_published_record() -> None:
    prod = GhaziWallFinishRecoveryProducer.create()
    sel = _selector()
    prod.publish(sel, [_obs()])
    auth = prod.authority()
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.net_area_m2 == 26.0


def test_authority_lookup_missing_abstains() -> None:
    prod = GhaziWallFinishRecoveryProducer.create()
    auth = prod.authority()
    sel = _selector()
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GHAZI_RECOVERY_RECORD_UNAVAILABLE in res.reason_codes


def test_authority_lookup_wrong_selector_type_raises() -> None:
    prod = GhaziWallFinishRecoveryProducer.create()
    auth = prod.authority()
    with pytest.raises(TypeError, match="GhaziWallFinishRecoverySelector"):
        auth.resolve("not-a-selector")  # type: ignore[arg-type]


# ── Validation ────────────────────────────────────────────────────────────────

def test_evidence_invalid_confidence_raises() -> None:
    with pytest.raises(ValueError, match="confidence"):
        GhaziWallFinishRecoveryEvidence(
            evidence_id="ev-bad", source_sha256=SHA, revision_id=REV,
            snapshot_id=SNAP, page_id=PAGE, viewport_id=VP,
            gross_area_m2=30.0, net_area_m2=26.0,
            root_cause=GhaziRecoveryRootCause.RESOLVED,
            kind="propagation", confidence=1.5,
        )


def test_selector_empty_field_raises() -> None:
    with pytest.raises(ValueError):
        GhaziWallFinishRecoverySelector(
            document_id="", revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
            physical_wall_id=WALL, trade_scope_id=TRADE,
        )
