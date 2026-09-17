"""Production + adversarial tests for pb_roof_ceiling_authority (Item 31).

Tests cover:
  - Happy-path ceiling area, roof plan area, pitch, surface area, overhang length
  - Rejection of floor area -> ceiling area shortcut (ABSTAINED)
  - Rejection of plan footprint -> roof surface area shortcut (ABSTAINED)
  - Rejection of assumed pitch (ABSTAINED)
  - Rejection of assumed overhang (ABSTAINED)
  - Rejection of BOQ-only description (ABSTAINED)
  - Rejection of gable wall pitch inference (ABSTAINED)
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
from pb_roof_ceiling_authority import (
    ROOF_CEILING_ASSUMED_OVERHANG_REJECTED,
    ROOF_CEILING_ASSUMED_PITCH_REJECTED,
    ROOF_CEILING_BOQ_ONLY_REJECTED,
    ROOF_CEILING_FLOOR_AREA_SHORTCUT_REJECTED,
    ROOF_CEILING_FOOTPRINT_SURFACE_SHORTCUT_REJECTED,
    ROOF_CEILING_GABLE_INFERENCE_REJECTED,
    ROOF_CEILING_LINEAGE_MISMATCH,
    ROOF_CEILING_RECORD_UNAVAILABLE,
    ROOF_CEILING_RESOLVED,
    ROOF_CEILING_UNRESOLVED,
    RoofCeilingAuthority,
    RoofCeilingEvidence,
    RoofCeilingFamily,
    RoofCeilingProducer,
    RoofCeilingRecord,
    RoofCeilingResult,
    RoofCeilingSelector,
)

DOC = "doc-roof-test"
REV = "R1"
SHA = "f" * 64
SNAP = "snap-roof-1"
PAGE = "page-RF01"
SCOPE = f"roof-source:page-{PAGE}"
VP = "vp-RF01"
TARGET = "roof-zone-1"


def _selector(
    family: RoofCeilingFamily = RoofCeilingFamily.CEILING_AREA,
    target_id: str = TARGET,
) -> RoofCeilingSelector:
    return RoofCeilingSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
        target_id=target_id,
        family=family,
    )


def _obs(
    family: RoofCeilingFamily = RoofCeilingFamily.CEILING_AREA,
    target_id: str = TARGET,
    value: float = 45.0,
    unit: str = "m2",
    kind: str = "ceiling_plan_annotation",
    method: str = "direct_dimension",
    is_sloped: bool = False,
    pitch_deg: float | None = None,
    sha: str = SHA,
    rev: str = REV,
    snap: str = SNAP,
    eid: str | None = None,
) -> RoofCeilingEvidence:
    if eid is None:
        eid = stable_contract_id("obs", {"target": target_id, "fam": family.value})
    return RoofCeilingEvidence(
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
        is_sloped=is_sloped,
        pitch_deg=pitch_deg,
    )


def _setup_scale_authority():
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
    return PhysicalScaleAuthority(
        {scale_sel.key: PhysicalScaleResult(
            status=EvidenceResolutionStatus.CORROBORATED, reason_codes=(), evidence=scale_ev,
        )}, _seal=SCALE_SEAL,
    )


def _producer() -> RoofCeilingProducer:
    scale_auth = _setup_scale_authority()
    return RoofCeilingProducer.from_authorities(physical_scale_authority=scale_auth)


# ── Constructor Seals ─────────────────────────────────────────────────────────

def test_authority_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        RoofCeilingAuthority({})


def test_producer_constructor_sealed() -> None:
    scale_auth = _setup_scale_authority()
    with pytest.raises(TypeError, match="from_authorities"):
        RoofCeilingProducer(scale_auth)  # type: ignore[call-arg]


# ── Happy Path ────────────────────────────────────────────────────────────────

def test_ceiling_area_resolved() -> None:
    prod = _producer()
    sel = _selector(RoofCeilingFamily.CEILING_AREA)
    obs = [_obs(RoofCeilingFamily.CEILING_AREA, value=45.0, unit="m2")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.value == 45.0
    assert res.record.family is RoofCeilingFamily.CEILING_AREA
    assert ROOF_CEILING_RESOLVED in res.reason_codes


def test_roof_pitch_deg_resolved() -> None:
    prod = _producer()
    sel = _selector(RoofCeilingFamily.ROOF_PITCH_DEG)
    obs = [_obs(RoofCeilingFamily.ROOF_PITCH_DEG, value=22.5, unit="deg", kind="roof_elevation_pitch", is_sloped=True, pitch_deg=22.5)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.value == 22.5
    assert res.record.is_sloped is True
    assert res.record.pitch_deg == 22.5


def test_eaves_overhang_length_resolved() -> None:
    prod = _producer()
    sel = _selector(RoofCeilingFamily.EAVES_OVERHANG_LENGTH)
    obs = [_obs(RoofCeilingFamily.EAVES_OVERHANG_LENGTH, value=0.6, unit="m", kind="eaves_detail_dimension")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.value == 0.6


# ── Adversarial: Rejected Shortcuts ─────────────────────────────────────────

def test_floor_area_ceiling_shortcut_rejected() -> None:
    prod = _producer()
    sel = _selector(RoofCeilingFamily.CEILING_AREA)
    obs = [_obs(RoofCeilingFamily.CEILING_AREA, kind="floor_area_ceiling_shortcut")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_FLOOR_AREA_SHORTCUT_REJECTED in res.reason_codes
    assert res.record is None


def test_plan_footprint_roof_surface_shortcut_rejected() -> None:
    prod = _producer()
    sel = _selector(RoofCeilingFamily.ROOF_SURFACE_AREA)
    obs = [_obs(RoofCeilingFamily.ROOF_SURFACE_AREA, kind="plan_footprint_roof_surface_shortcut")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_FOOTPRINT_SURFACE_SHORTCUT_REJECTED in res.reason_codes


def test_assumed_pitch_rejected() -> None:
    prod = _producer()
    sel = _selector(RoofCeilingFamily.ROOF_PITCH_DEG)
    obs = [_obs(RoofCeilingFamily.ROOF_PITCH_DEG, kind="assumed_pitch")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_ASSUMED_PITCH_REJECTED in res.reason_codes


def test_assumed_overhang_rejected() -> None:
    prod = _producer()
    sel = _selector(RoofCeilingFamily.EAVES_OVERHANG_LENGTH)
    obs = [_obs(RoofCeilingFamily.EAVES_OVERHANG_LENGTH, kind="assumed_overhang")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_ASSUMED_OVERHANG_REJECTED in res.reason_codes


def test_boq_description_only_rejected() -> None:
    prod = _producer()
    sel = _selector(RoofCeilingFamily.CEILING_AREA)
    obs = [_obs(RoofCeilingFamily.CEILING_AREA, kind="boq_description_only")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_BOQ_ONLY_REJECTED in res.reason_codes


def test_gable_wall_pitch_inference_rejected() -> None:
    prod = _producer()
    sel = _selector(RoofCeilingFamily.ROOF_PITCH_DEG)
    obs = [_obs(RoofCeilingFamily.ROOF_PITCH_DEG, kind="gable_wall_pitch_inference")]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_GABLE_INFERENCE_REJECTED in res.reason_codes


# ── Adversarial: Stale & Conflict ─────────────────────────────────────────────

def test_stale_lineage_fails_closed() -> None:
    prod = _producer()
    sel = _selector(RoofCeilingFamily.CEILING_AREA)
    obs = [_obs(RoofCeilingFamily.CEILING_AREA, sha="g" * 64)]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert ROOF_CEILING_LINEAGE_MISMATCH in res.reason_codes


def test_conflicting_measured_values_conflicts() -> None:
    prod = _producer()
    sel = _selector(RoofCeilingFamily.CEILING_AREA)
    obs = [
        _obs(RoofCeilingFamily.CEILING_AREA, value=45.0, eid="obs-1"),
        _obs(RoofCeilingFamily.CEILING_AREA, value=55.0, eid="obs-2"),
    ]
    res = prod.publish(sel, obs)
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert ROOF_CEILING_UNRESOLVED in res.reason_codes


# ── Authority Lookup ──────────────────────────────────────────────────────────

def test_authority_lookup_published_record() -> None:
    prod = _producer()
    sel = _selector()
    prod.publish(sel, [_obs()])
    auth = prod.authority()
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.value == 45.0


def test_authority_lookup_missing_abstains() -> None:
    prod = _producer()
    auth = prod.authority()
    sel = _selector()
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_RECORD_UNAVAILABLE in res.reason_codes


def test_authority_lookup_wrong_selector_type_raises() -> None:
    prod = _producer()
    auth = prod.authority()
    with pytest.raises(TypeError, match="RoofCeilingSelector"):
        auth.resolve("not-a-selector")  # type: ignore[arg-type]


# ── Validation ────────────────────────────────────────────────────────────────

def test_evidence_invalid_value_raises() -> None:
    with pytest.raises(ValueError, match="measured_value"):
        RoofCeilingEvidence(
            evidence_id="ev-bad", source_sha256=SHA, revision_id=REV,
            snapshot_id=SNAP, page_id=PAGE, viewport_id=VP,
            family=RoofCeilingFamily.CEILING_AREA, measured_value=-10.0,
            unit="m2", kind="ceiling_plan", method="direct", confidence=0.9,
        )


def test_selector_empty_field_raises() -> None:
    with pytest.raises(ValueError):
        RoofCeilingSelector(
            document_id="", revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
            target_id=TARGET, family=RoofCeilingFamily.CEILING_AREA,
        )
