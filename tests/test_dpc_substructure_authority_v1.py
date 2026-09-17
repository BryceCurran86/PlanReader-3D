"""Production + adversarial tests for pb_dpc_substructure_authority (Item 30).

Tests cover:
  - Happy-path DPC length, foundation wall length, strip footing length, substructure area
  - Missing physical wall candidate abstains (DPC_SUBSTRUCTURE_WALL_UNRESOLVED)
  - Missing height abstains for area (DPC_SUBSTRUCTURE_MISSING_SECTION_DETAIL)
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

from pb_dpc_substructure_authority import (
    DPC_SUBSTRUCTURE_MISSING_SECTION_DETAIL,
    DPC_SUBSTRUCTURE_RECORD_UNAVAILABLE,
    DPC_SUBSTRUCTURE_RESOLVED,
    DPC_SUBSTRUCTURE_UNRESOLVED,
    DPC_SUBSTRUCTURE_WALL_UNRESOLVED,
    DPCSubstructureAuthority,
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


def _setup_authorities(*wall_ids: str, length_m: float = 12.5, height_m: float = 2.0):
    if not wall_ids:
        wall_ids = (WALL_FOUNDATION,)
    records = []
    for wid in wall_ids:
        cand = WallCandidate(
            candidate_id=wid,
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
            metadata={"height_m": height_m},
        )
        ident = PhysicalWallIdentity(
            wall_candidate_id=wid,
            viewport_id=SCOPE,
            candidate_identity_id=f"ident-{wid}",
            path_fingerprint=((0.0, 0.0), (length_m, 0.0)),
            source_primitive_ids=("s1",),
            edge_ids=("s1",),
            status=EvidenceResolutionStatus.CORROBORATED,
        )
        rec = PhysicalWallCandidateRecord(
            wall_candidate_id=wid, wall_candidate=cand, physical_identity=ident,
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


def _producer(*wall_ids: str, length_m: float = 12.5, height_m: float = 2.0) -> DPCSubstructureProducer:
    cand_auth, scale_auth = _setup_authorities(*wall_ids, length_m=length_m, height_m=height_m)
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
    prod = _producer(length_m=12.5)
    sel = _selector(SubstructureFamily.DPC_LENGTH)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.value == 12.5
    assert res.record.family is SubstructureFamily.DPC_LENGTH
    assert DPC_SUBSTRUCTURE_RESOLVED in res.reason_codes


def test_foundation_wall_length_resolved() -> None:
    prod = _producer(length_m=15.0)
    sel = _selector(SubstructureFamily.FOUNDATION_WALL_LENGTH)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.value == 15.0


def test_strip_footing_length_resolved() -> None:
    prod = _producer(length_m=18.0)
    sel = _selector(SubstructureFamily.STRIP_FOOTING_LENGTH)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.value == 18.0


def test_substructure_wall_area_resolved() -> None:
    prod = _producer(length_m=10.0, height_m=2.5)
    sel = _selector(SubstructureFamily.SUBSTRUCTURE_WALL_AREA)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.value == 25.0
    assert res.record.unit == "m2"


def test_unknown_foundation_wall_abstains() -> None:
    prod = _producer()
    sel = _selector(SubstructureFamily.DPC_LENGTH, wall_id="phys-UNKNOWN")
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert DPC_SUBSTRUCTURE_WALL_UNRESOLVED in res.reason_codes


# ── Authority Lookup ──────────────────────────────────────────────────────────

def test_authority_lookup_published_record() -> None:
    prod = _producer()
    sel = _selector()
    prod.publish(sel)
    auth = prod.authority()
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
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

def test_selector_empty_field_raises() -> None:
    with pytest.raises(ValueError):
        DPCSubstructureSelector(
            document_id="", revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
            physical_foundation_id=WALL_FOUNDATION,
            family=SubstructureFamily.DPC_LENGTH,
        )
