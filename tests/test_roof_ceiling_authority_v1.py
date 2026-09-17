"""Production + adversarial tests for pb_roof_ceiling_authority (Item 31).

Tests cover:
  - Happy-path ceiling area, roof plan area, pitch, surface area, overhang length
  - Unresolved scale abstains (ROOF_CEILING_SCALE_UNRESOLVED)
  - Missing pitch evidence abstains (ROOF_CEILING_ASSUMED_PITCH_REJECTED)
  - Missing overhang length abstains (ROOF_CEILING_ASSUMED_OVERHANG_REJECTED)
  - Sealed authority constructor
  - Selector validation
"""
from __future__ import annotations

import pytest

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
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
from pb_wall_room_topology_contracts import JunctionType, WallCandidate

from pb_roof_ceiling_authority import (
    ROOF_CEILING_ASSUMED_OVERHANG_REJECTED,
    ROOF_CEILING_ASSUMED_PITCH_REJECTED,
    ROOF_CEILING_FOOTPRINT_SURFACE_SHORTCUT_REJECTED,
    ROOF_CEILING_RECORD_UNAVAILABLE,
    ROOF_CEILING_RESOLVED,
    ROOF_CEILING_SCALE_UNRESOLVED,
    ROOF_CEILING_UNRESOLVED,
    RoofCeilingAuthority,
    RoofCeilingProducer,
    RoofCeilingRecord,
    RoofCeilingResult,
    RoofCeilingSelector,
    RoofCeilingFamily,
)

DOC = "doc-roof-test"
REV = "R1"
SHA = "f" * 64
SNAP = "snap-roof-1"
PAGE = "page-RF01"
SCOPE = f"wall-source:page-{PAGE}"
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


def _setup_authorities(
    target_id: str = TARGET,
    area_m2: float = 45.0,
    pitch_deg: float | None = 22.5,
    overhang_m: float | None = 0.6,
):
    cand_key = _ScopeKey(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
    )
    cand = WallCandidate(
        candidate_id=target_id,
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
        interior_exterior="interior",
        level_id=None,
        supporting_evidence_ids=("s1",),
        metadata={
            "area_m2": area_m2,
            "pitch_deg": pitch_deg,
            "overhang_length_m": overhang_m,
        },
    )
    ident = PhysicalWallIdentity(
        wall_candidate_id=target_id,
        viewport_id=SCOPE,
        candidate_identity_id=f"ident-{target_id}",
        path_fingerprint=((0.0, 0.0), (10.0, 0.0)),
        source_primitive_ids=("s1",),
        edge_ids=("s1",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    rec = PhysicalWallCandidateRecord(
        wall_candidate_id=target_id, wall_candidate=cand, physical_identity=ident,
    )

    cand_auth = PhysicalWallCandidateAuthority(
        {cand_key: PhysicalWallCandidateScopeResult(
            status=EvidenceResolutionStatus.CORROBORATED, scope_complete=True,
            records=(rec,), source_observation_ids=(), document_id=DOC,
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

    return scale_auth, cand_auth


def _producer(
    target_id: str = TARGET,
    area_m2: float = 45.0,
    pitch_deg: float | None = 22.5,
    overhang_m: float | None = 0.6,
) -> RoofCeilingProducer:
    scale_auth, cand_auth = _setup_authorities(target_id, area_m2, pitch_deg, overhang_m)
    return RoofCeilingProducer.from_authorities(
        physical_scale_authority=scale_auth,
        physical_wall_candidate_authority=cand_auth,
    )


# ── Constructor Seals ─────────────────────────────────────────────────────────

def test_authority_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        RoofCeilingAuthority({})


def test_producer_constructor_sealed() -> None:
    scale_auth, cand_auth = _setup_authorities()
    with pytest.raises(TypeError, match="from_authorities"):
        RoofCeilingProducer(scale_auth, cand_auth)  # type: ignore[call-arg]


# ── Happy Path ────────────────────────────────────────────────────────────────

def test_ceiling_area_resolved() -> None:
    prod = _producer(area_m2=45.0)
    sel = _selector(RoofCeilingFamily.CEILING_AREA)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.value == 45.0
    assert res.record.family is RoofCeilingFamily.CEILING_AREA
    assert ROOF_CEILING_RESOLVED in res.reason_codes


def test_roof_pitch_deg_resolved() -> None:
    prod = _producer(pitch_deg=22.5)
    sel = _selector(RoofCeilingFamily.ROOF_PITCH_DEG)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.value == 22.5
    assert res.record.is_sloped is True
    assert res.record.pitch_deg == 22.5


def test_eaves_overhang_length_resolved() -> None:
    prod = _producer(overhang_m=0.6)
    sel = _selector(RoofCeilingFamily.EAVES_OVERHANG_LENGTH)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.value == 0.6


# ── Adversarial: Rejected Shortcuts / Missing Evidence ───────────────────────

def test_missing_pitch_rejected() -> None:
    prod = _producer(pitch_deg=None)
    sel = _selector(RoofCeilingFamily.ROOF_PITCH_DEG)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_ASSUMED_PITCH_REJECTED in res.reason_codes
    assert res.record is None


def test_missing_overhang_rejected() -> None:
    prod = _producer(overhang_m=None)
    sel = _selector(RoofCeilingFamily.EAVES_OVERHANG_LENGTH)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_ASSUMED_OVERHANG_REJECTED in res.reason_codes


def test_unknown_target_abstains() -> None:
    prod = _producer()
    sel = _selector(target_id="unknown-target")
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert ROOF_CEILING_UNRESOLVED in res.reason_codes


# ── Authority Lookup ──────────────────────────────────────────────────────────

def test_authority_lookup_published_record() -> None:
    prod = _producer()
    sel = _selector()
    prod.publish(sel)
    auth = prod.authority()
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
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

def test_selector_empty_field_raises() -> None:
    with pytest.raises(ValueError):
        RoofCeilingSelector(
            document_id="", revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
            target_id=TARGET, family=RoofCeilingFamily.CEILING_AREA,
        )
