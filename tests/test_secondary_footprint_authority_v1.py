"""Production + adversarial tests for pb_secondary_footprint_authority (Item 29).

Tests cover:
  - Happy-path verandah, porch, canopy resolution (is_enclosed=False)
  - Primary enclosed footprint resolution (is_enclosed=True)
  - Rejection of largest_polygon_rule heuristic (ABSTAINED)
  - Rejection of proximity_absorption heuristic (ABSTAINED)
  - Stale lineage fails closed (CONFLICT)
  - Conflicting footprint categories fail closed (CONFLICT)
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
from pb_secondary_footprint_authority import (
    FootprintCategory,
    SECONDARY_FOOTPRINT_LARGEST_POLYGON_REJECTED,
    SECONDARY_FOOTPRINT_LINEAGE_MISMATCH,
    SECONDARY_FOOTPRINT_PROXIMITY_ABSORPTION_REJECTED,
    SECONDARY_FOOTPRINT_RECORD_UNAVAILABLE,
    SECONDARY_FOOTPRINT_RESOLVED,
    SECONDARY_FOOTPRINT_UNRESOLVED,
    SecondaryFootprintAuthority,
    SecondaryFootprintEvidence,
    SecondaryFootprintProducer,
    SecondaryFootprintRecord,
    SecondaryFootprintResult,
    SecondaryFootprintSelector,
)

DOC = "doc-fp-test"
REV = "R1"
SHA = "d" * 64
SNAP = "snap-fp-1"
PAGE = "page-FP01"
SCOPE = f"footprint-source:page-{PAGE}"
VP = "vp-FP01"
FOOTPRINT_A = "fp-verandah-1"
FOOTPRINT_B = "fp-main-1"

# 10m x 5m rectangle in points (100 pt x 50 pt at scale)
PTS = ((0.0, 0.0), (100.0, 0.0), (100.0, 50.0), (0.0, 50.0), (0.0, 0.0))


def _selector(fp_id: str = FOOTPRINT_A) -> SecondaryFootprintSelector:
    return SecondaryFootprintSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
        footprint_id=fp_id,
    )


def _obs(
    fp_id: str = FOOTPRINT_A,
    category: FootprintCategory = FootprintCategory.VERANDAH,
    kind: str = "plan_verandah_outline",
    sha: str = SHA,
    rev: str = REV,
    snap: str = SNAP,
    pid: str | None = None,
) -> SecondaryFootprintEvidence:
    if pid is None:
        pid = stable_contract_id("obs", {"fp": fp_id, "cat": category.value})
    return SecondaryFootprintEvidence(
        evidence_id=pid,
        source_sha256=sha,
        revision_id=rev,
        snapshot_id=snap,
        page_id=PAGE,
        viewport_id=VP,
        category=category,
        polygon_points_pt=PTS,
        kind=kind,
        confidence=0.9,
    )


def _setup_scale_authority():
    scale_sel = PhysicalScaleSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=PAGE,
    )
    scale_ev = PhysicalScaleEvidence(
        selector=scale_sel, record_id="rec-scale", source_kind="graphic_scale",
        source_span_pt=100.0, physical_span_mm=10000.0, points_per_mm=0.01,
        mm_per_point=100.0, source_segment_observation_ids=(),
        source_text_observation_ids=(), viewport_id=None,
    )
    return PhysicalScaleAuthority(
        {scale_sel.key: PhysicalScaleResult(
            status=EvidenceResolutionStatus.CORROBORATED, reason_codes=(), evidence=scale_ev,
        )}, _seal=SCALE_SEAL,
    )


def _producer() -> SecondaryFootprintProducer:
    scale_auth = _setup_scale_authority()
    return SecondaryFootprintProducer.from_authorities(physical_scale_authority=scale_auth)


# ── Constructor Seals ─────────────────────────────────────────────────────────

def test_authority_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        SecondaryFootprintAuthority({})


def test_producer_constructor_sealed() -> None:
    scale_auth = _setup_scale_authority()
    with pytest.raises(TypeError, match="from_authorities"):
        SecondaryFootprintProducer(scale_auth)  # type: ignore[call-arg]


# ── Happy Path ────────────────────────────────────────────────────────────────

def test_verandah_footprint_resolved() -> None:
    prod = _producer()
    sel = _selector(FOOTPRINT_A)
    obs = [_obs(FOOTPRINT_A, category=FootprintCategory.VERANDAH)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.category is FootprintCategory.VERANDAH
    assert res.record.is_enclosed is False
    assert SECONDARY_FOOTPRINT_RESOLVED in res.reason_codes


def test_primary_enclosed_footprint_resolved() -> None:
    prod = _producer()
    sel = _selector(FOOTPRINT_B)
    obs = [_obs(FOOTPRINT_B, category=FootprintCategory.PRIMARY_ENCLOSED)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.category is FootprintCategory.PRIMARY_ENCLOSED
    assert res.record.is_enclosed is True


def test_porch_and_canopy_resolved_not_enclosed() -> None:
    prod = _producer()
    sel = _selector(FOOTPRINT_A)

    res_porch = prod.publish(sel, [_obs(FOOTPRINT_A, category=FootprintCategory.PORCH)])
    assert res_porch.record.is_enclosed is False

    res_canopy = prod.publish(sel, [_obs(FOOTPRINT_A, category=FootprintCategory.CANOPY)])
    assert res_canopy.record.is_enclosed is False


# ── Adversarial: Rejected Heuristics ─────────────────────────────────────────

def test_largest_polygon_rule_rejected() -> None:
    prod = _producer()
    sel = _selector()
    obs = [_obs(kind="largest_polygon_rule")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert SECONDARY_FOOTPRINT_LARGEST_POLYGON_REJECTED in res.reason_codes
    assert res.record is None


def test_proximity_absorption_rejected() -> None:
    prod = _producer()
    sel = _selector()
    obs = [_obs(kind="proximity_absorption")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert SECONDARY_FOOTPRINT_PROXIMITY_ABSORPTION_REJECTED in res.reason_codes


# ── Adversarial: Stale & Conflict ─────────────────────────────────────────────

def test_stale_lineage_fails_closed() -> None:
    prod = _producer()
    sel = _selector()
    obs = [_obs(sha="e" * 64)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert SECONDARY_FOOTPRINT_LINEAGE_MISMATCH in res.reason_codes


def test_conflicting_categories_conflicts() -> None:
    prod = _producer()
    sel = _selector()
    obs = [
        _obs(category=FootprintCategory.VERANDAH, pid="obs-v"),
        _obs(category=FootprintCategory.PORCH, pid="obs-p"),
    ]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert SECONDARY_FOOTPRINT_UNRESOLVED in res.reason_codes


def test_empty_observations_abstains() -> None:
    prod = _producer()
    sel = _selector()
    res = prod.publish(sel, [])
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert SECONDARY_FOOTPRINT_UNRESOLVED in res.reason_codes


# ── Authority Lookup ──────────────────────────────────────────────────────────

def test_authority_lookup_published_record() -> None:
    prod = _producer()
    sel = _selector()
    prod.publish(sel, [_obs()])
    auth = prod.authority()
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.footprint_id == FOOTPRINT_A


def test_authority_lookup_missing_abstains() -> None:
    prod = _producer()
    auth = prod.authority()
    sel = _selector()
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert SECONDARY_FOOTPRINT_RECORD_UNAVAILABLE in res.reason_codes


def test_authority_lookup_wrong_selector_type_raises() -> None:
    prod = _producer()
    auth = prod.authority()
    with pytest.raises(TypeError, match="SecondaryFootprintSelector"):
        auth.resolve("not-a-selector")  # type: ignore[arg-type]


# ── Validation ────────────────────────────────────────────────────────────────

def test_evidence_too_few_points_raises() -> None:
    with pytest.raises(ValueError, match="at least 3 points"):
        SecondaryFootprintEvidence(
            evidence_id="ev-bad", source_sha256=SHA, revision_id=REV,
            snapshot_id=SNAP, page_id=PAGE, viewport_id=VP,
            category=FootprintCategory.VERANDAH, polygon_points_pt=((0.0, 0.0), (10.0, 0.0)),
            kind="outline", confidence=0.9,
        )


def test_selector_empty_field_raises() -> None:
    with pytest.raises(ValueError):
        SecondaryFootprintSelector(
            document_id="", revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
            footprint_id=FOOTPRINT_A,
        )
