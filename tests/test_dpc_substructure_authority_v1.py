"""Production + adversarial tests for pb_dpc_substructure_authority (Item 30).

Tests cover:
  - Happy-path DPC length, foundation wall length, strip footing length, substructure area
  - Rejection of perimeter = DPC shortcut (ABSTAINED)
  - Rejection of copied superstructure shortcut (ABSTAINED)
  - Rejection when section detail is missing (ABSTAINED)
  - Stale lineage fails closed (CONFLICT)
  - Conflicting measured values fail closed (CONFLICT)
  - Sealed authority constructor
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
from pb_dpc_substructure_authority import (
    DPC_SUBSTRUCTURE_LINEAGE_MISMATCH,
    DPC_SUBSTRUCTURE_MISSING_SECTION_DETAIL,
    DPC_SUBSTRUCTURE_PERIMETER_SHORTCUT_REJECTED,
    DPC_SUBSTRUCTURE_RECORD_UNAVAILABLE,
    DPC_SUBSTRUCTURE_RESOLVED,
    DPC_SUBSTRUCTURE_SUPERSTRUCTURE_COPY_REJECTED,
    DPC_SUBSTRUCTURE_UNRESOLVED,
    DPC_SUBSTRUCTURE_WALL_UNRESOLVED,
    DPCSubstructureAuthority,
    DPCSubstructureEvidence,
    DPCSubstructureProducer,
    DPCSubstructureRecord,
    DPCSubstructureResult,
    DPCSubstructureSelector,
    SubstructureFamily,
)

DOC = "doc-dpc-test"
REV = "R1"
SHA = "e" * 64
SNAP = "snap-dpc-1"
PAGE = "page-DPC01"
SCOPE = f"wall-source:page-{PAGE}"
VP = "vp-DPC01"
WALL_FOUNDATION = "phys-foundation-wall-1"


def _selector(
    family: SubstructureFamily = SubstructureFamily.DPC_LENGTH,
    wall_id: str = WALL_FOUNDATION,
) -> DPCSubstructureSelector:
    return DPCSubstructureSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
        physical_foundation_id=wall_id,
        family=family,
    )


def _obs(
    family: SubstructureFamily = SubstructureFamily.DPC_LENGTH,
    wall_id: str = WALL_FOUNDATION,
    value: float = 12.5,
    unit: str = "m",
    kind: str = "dpc_schedule_row",
    method: str = "direct_dimension",
    sha: str = SHA,
    rev: str = REV,
    snap: str = SNAP,
    eid: str | None = None,
) -> DPCSubstructureEvidence:
    if eid is None:
        eid = stable_contract_id("obs", {"wall": wall_id, "fam": family.value})
    return DPCSubstructureEvidence(
        evidence_id=eid,
        source_sha256=sha,
        revision_id=rev,
        snapshot_id=snap,
        page_id=PAGE,
        viewport_id=VP,
        family=family,
        measured_value=value,
        unit=unit,
        kind=kind,
        method=method,
        confidence=0.95,
    )


def _setup_authorities(*wall_ids: str):
    if not wall_ids:
        wall_ids = (WALL_FOUNDATION,)
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


def _producer(*wall_ids: str) -> DPCSubstructureProducer:
    cand_auth, scale_auth = _setup_authorities(*wall_ids)
    return DPCSubstructureProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
    )


# ── Constructor Seals ─────────────────────────────────────────────────────────

def test_authority_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        DPCSubstructureAuthority({})


def test_producer_constructor_sealed() -> None:
    cand_auth, scale_auth = _setup_authorities()
    with pytest.raises(TypeError, match="from_authorities"):
        DPCSubstructureProducer(cand_auth, scale_auth)  # type: ignore[call-arg]


# ── Happy Path ────────────────────────────────────────────────────────────────

def test_dpc_length_resolved() -> None:
    prod = _producer()
    sel = _selector(SubstructureFamily.DPC_LENGTH)
    obs = [_obs(SubstructureFamily.DPC_LENGTH, value=12.5)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.value == 12.5
    assert res.record.family is SubstructureFamily.DPC_LENGTH
    assert DPC_SUBSTRUCTURE_RESOLVED in res.reason_codes


def test_foundation_wall_length_resolved() -> None:
    prod = _producer()
    sel = _selector(SubstructureFamily.FOUNDATION_WALL_LENGTH)
    obs = [_obs(SubstructureFamily.FOUNDATION_WALL_LENGTH, value=15.0)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.value == 15.0


def test_strip_footing_length_resolved() -> None:
    prod = _producer()
    sel = _selector(SubstructureFamily.STRIP_FOOTING_LENGTH)
    obs = [_obs(SubstructureFamily.STRIP_FOOTING_LENGTH, value=18.0)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.value == 18.0


def test_substructure_wall_area_resolved() -> None:
    prod = _producer()
    sel = _selector(SubstructureFamily.SUBSTRUCTURE_WALL_AREA)
    obs = [_obs(SubstructureFamily.SUBSTRUCTURE_WALL_AREA, value=25.0, unit="m2")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.value == 25.0
    assert res.record.unit == "m2"


# ── Adversarial: Rejected Shortcuts ─────────────────────────────────────────

def test_perimeter_dpc_shortcut_rejected() -> None:
    prod = _producer()
    sel = _selector(SubstructureFamily.DPC_LENGTH)
    obs = [_obs(SubstructureFamily.DPC_LENGTH, kind="perimeter_dpc_shortcut")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert DPC_SUBSTRUCTURE_PERIMETER_SHORTCUT_REJECTED in res.reason_codes
    assert res.record is None


def test_copied_superstructure_shortcut_rejected() -> None:
    prod = _producer()
    sel = _selector(SubstructureFamily.FOUNDATION_WALL_LENGTH)
    obs = [_obs(SubstructureFamily.FOUNDATION_WALL_LENGTH, kind="copied_superstructure_shortcut")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert DPC_SUBSTRUCTURE_SUPERSTRUCTURE_COPY_REJECTED in res.reason_codes


def test_missing_section_detail_rejected() -> None:
    prod = _producer()
    sel = _selector(SubstructureFamily.STRIP_FOOTING_LENGTH)
    obs = [_obs(SubstructureFamily.STRIP_FOOTING_LENGTH, method="missing_section_detail")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert DPC_SUBSTRUCTURE_MISSING_SECTION_DETAIL in res.reason_codes


# ── Adversarial: Stale & Conflict ─────────────────────────────────────────────

def test_stale_lineage_fails_closed() -> None:
    prod = _producer()
    sel = _selector(SubstructureFamily.DPC_LENGTH)
    obs = [_obs(SubstructureFamily.DPC_LENGTH, sha="f" * 64)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert DPC_SUBSTRUCTURE_LINEAGE_MISMATCH in res.reason_codes


def test_conflicting_measured_values_conflicts() -> None:
    prod = _producer()
    sel = _selector(SubstructureFamily.DPC_LENGTH)
    obs = [
        _obs(SubstructureFamily.DPC_LENGTH, value=12.5, eid="obs-1"),
        _obs(SubstructureFamily.DPC_LENGTH, value=15.0, eid="obs-2"),
    ]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert DPC_SUBSTRUCTURE_UNRESOLVED in res.reason_codes


def test_unknown_foundation_wall_abstains() -> None:
    prod = _producer()
    sel = _selector(SubstructureFamily.DPC_LENGTH, wall_id="phys-UNKNOWN")
    obs = [_obs(SubstructureFamily.DPC_LENGTH, wall_id="phys-UNKNOWN")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert DPC_SUBSTRUCTURE_WALL_UNRESOLVED in res.reason_codes


# ── Authority Lookup ──────────────────────────────────────────────────────────

def test_authority_lookup_published_record() -> None:
    prod = _producer()
    sel = _selector()
    prod.publish(sel, [_obs()])
    auth = prod.authority()
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.value == 12.5


def test_authority_lookup_missing_abstains() -> None:
    prod = _producer()
    auth = prod.authority()
    sel = _selector()
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert DPC_SUBSTRUCTURE_RECORD_UNAVAILABLE in res.reason_codes


def test_authority_lookup_wrong_selector_type_raises() -> None:
    prod = _producer()
    auth = prod.authority()
    with pytest.raises(TypeError, match="DPCSubstructureSelector"):
        auth.resolve("not-a-selector")  # type: ignore[arg-type]


# ── Validation ────────────────────────────────────────────────────────────────

def test_evidence_invalid_value_raises() -> None:
    with pytest.raises(ValueError, match="measured_value"):
        DPCSubstructureEvidence(
            evidence_id="ev-bad", source_sha256=SHA, revision_id=REV,
            snapshot_id=SNAP, page_id=PAGE, viewport_id=VP,
            family=SubstructureFamily.DPC_LENGTH, measured_value=-5.0,
            unit="m", kind="dpc_callout", method="direct", confidence=0.9,
        )


def test_selector_empty_field_raises() -> None:
    with pytest.raises(ValueError):
        DPCSubstructureSelector(
            document_id="", revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
            physical_foundation_id=WALL_FOUNDATION,
            family=SubstructureFamily.DPC_LENGTH,
        )
