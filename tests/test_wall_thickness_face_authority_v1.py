"""Production + adversarial tests for pb_wall_thickness_face_authority (Item 27).

Tests cover:
  - Happy-path authenticated thickness and face geometry resolution from upstream WallCandidate
  - Rejection of synthesized geometry (missing centerline_pts -> ABSTAINED with WALL_THICKNESS_GEOMETRY_UNAVAILABLE)
  - Unresolved thickness in candidate (thickness_m=None -> ABSTAINED with WALL_THICKNESS_UNRESOLVED)
  - Mismatched physical wall candidate ID abstains
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
from pb_wall_room_topology_contracts import (
    InteriorExterior,
    JunctionType,
    MeasurementAuthorityType,
    WallCandidate,
    WallRepresentation,
)
from pb_wall_thickness_face_authority import (
    WALL_THICKNESS_FACE_RESOLVED,
    WALL_THICKNESS_GEOMETRY_UNAVAILABLE,
    WALL_THICKNESS_RECORD_UNAVAILABLE,
    WALL_THICKNESS_SCALE_UNRESOLVED,
    WALL_THICKNESS_UNRESOLVED,
    WALL_THICKNESS_WALL_UNRESOLVED,
    WallFaceGeometryRecord,
    WallThicknessFaceAuthority,
    WallThicknessFaceProducer,
    WallThicknessFaceResult,
    WallThicknessFaceSelector,
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


def _make_candidate(
    candidate_id: str,
    thickness_m: float | None = 0.11,
    centerline_pts: tuple[tuple[float, float], ...] | None = ((0.0, 0.0), (100.0, 0.0)),
) -> WallCandidate:
    cand_status = EvidenceResolutionStatus.CORROBORATED if thickness_m is not None else EvidenceResolutionStatus.RAW
    thick_auth = MeasurementAuthorityType.DOCUMENTED_DIMENSION if thickness_m is not None else MeasurementAuthorityType.PROVISIONAL
    return WallCandidate(
        candidate_id=candidate_id,
        viewport_id=VP,
        representation="double_line",
        centerline_pts=centerline_pts if centerline_pts else ((0.0, 0.0), (0.0, 0.0)),
        face_a_segment_ids=("seg-a",),
        face_b_segment_ids=("seg-b",),
        is_curved=False,
        curve_control_pts=None,
        thickness_m=thickness_m,
        thickness_authority=thick_auth,
        length_m=10.0,
        end_node_ids=("n1", "n2"),
        junction_types=("free_end", "free_end"),
        interior_exterior="exterior",
        level_id="L1",
        status=cand_status,
        confidence=1.0 if cand_status == EvidenceResolutionStatus.CORROBORATED else 0.0,
    )


def _setup_authorities(
    *wall_ids: str,
    thickness_m: float | None = 0.11,
    centerline_pts: tuple[tuple[float, float], ...] | None = ((0.0, 0.0), (100.0, 0.0)),
):
    records = []
    for wid in wall_ids:
        ident = PhysicalWallIdentity(
            wall_candidate_id=wid, viewport_id=VP, candidate_identity_id=None,
            path_fingerprint=None, source_primitive_ids=(), edge_ids=(),
            status=EvidenceResolutionStatus.CORROBORATED,
        )
        wc = _make_candidate(wid, thickness_m=thickness_m, centerline_pts=centerline_pts)
        rec = PhysicalWallCandidateRecord(
            wall_candidate_id=wid, wall_candidate=wc, physical_identity=ident,
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


def _producer(
    *wall_ids: str,
    thickness_m: float | None = 0.11,
    centerline_pts: tuple[tuple[float, float], ...] | None = ((0.0, 0.0), (100.0, 0.0)),
) -> WallThicknessFaceProducer:
    if not wall_ids:
        wall_ids = (WALL_A,)
    cand_auth, scale_auth = _setup_authorities(*wall_ids, thickness_m=thickness_m, centerline_pts=centerline_pts)
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

def test_authenticated_110mm_thickness_resolved_from_candidate() -> None:
    prod = _producer(WALL_A, thickness_m=0.11)
    sel = _selector(WALL_A)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.thickness_mm == 110.0
    assert res.record.thickness_m == 0.11
    assert WALL_THICKNESS_FACE_RESOLVED in res.reason_codes


def test_authenticated_230mm_thickness_resolved_from_candidate() -> None:
    prod = _producer(WALL_A, thickness_m=0.23)
    sel = _selector(WALL_A)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.thickness_mm == 230.0
    assert res.record.thickness_m == 0.23


# ── Fail Closed: Missing Thickness / Geometry ─────────────────────────────────

def test_missing_candidate_thickness_abstains() -> None:
    prod = _producer(WALL_A, thickness_m=None)
    sel = _selector(WALL_A)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_UNRESOLVED in res.reason_codes
    assert res.record is None


def test_missing_centerline_pts_abstains() -> None:
    prod = _producer(WALL_A, thickness_m=0.11, centerline_pts=())
    sel = _selector(WALL_A)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_GEOMETRY_UNAVAILABLE in res.reason_codes
    assert res.record is None


def test_unknown_physical_wall_abstains() -> None:
    prod = _producer(WALL_A)
    sel = _selector("phys-wall-UNKNOWN")
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_WALL_UNRESOLVED in res.reason_codes


# ── Authority Lookup ──────────────────────────────────────────────────────────

def test_authority_lookup_published_record() -> None:
    prod = _producer(WALL_A, thickness_m=0.11)
    sel = _selector(WALL_A)
    prod.publish(sel)
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


def test_selector_empty_field_raises() -> None:
    with pytest.raises(ValueError):
        WallThicknessFaceSelector(
            document_id="", revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
            physical_wall_id=WALL_A,
        )
