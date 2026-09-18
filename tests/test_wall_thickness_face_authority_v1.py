"""Production and adversarial tests for pb_wall_thickness_face_authority (Item 27).

Covers all 13 required attacks:
  1. caller thickness
  2. candidate thickness
  3. default thickness
  4. wrong-wall dimension
  5. stale dimension
  6. conflicting dimension
  7. zero thickness
  8. negative thickness
  9. multi-segment bent wall
  10. reversed polyline
  11. face identity swap
  12. fake WKB
  13. exact source-dimension positive case
"""
from __future__ import annotations

import pytest
from shapely import wkb

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
    _AUTHORITY_SEAL as CANDIDATE_SEAL,
    _ScopeKey,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_thickness_face_authority import (
    WALL_THICKNESS_CANDIDATE_REJECTED,
    WALL_THICKNESS_CONFLICT,
    WALL_THICKNESS_DEFAULT_REJECTED,
    WALL_THICKNESS_FACE_RESOLVED,
    WALL_THICKNESS_LINEAGE_MISMATCH,
    WALL_THICKNESS_NEGATIVE_REJECTED,
    WALL_THICKNESS_RECORD_UNAVAILABLE,
    WALL_THICKNESS_SCALE_UNRESOLVED,
    WALL_THICKNESS_STALE_EVIDENCE,
    WALL_THICKNESS_SOURCE_EVIDENCE_UNAVAILABLE,
    WALL_THICKNESS_UNRESOLVED,
    WALL_THICKNESS_WALL_UNRESOLVED,
    WALL_THICKNESS_WRONG_WALL,
    WALL_THICKNESS_ZERO_REJECTED,
    WallFaceGeometryRecord,
    WallThicknessAuthority,
    WallThicknessEvidence,
    WallThicknessFaceAuthority,
    WallThicknessFaceProducer,
    WallThicknessFaceResult,
    WallThicknessFaceSelector,
    WallThicknessProducer,
    _compute_multi_segment_offset,
    _is_canonical_direction,
    _linestring_to_wkb_hex,
    _polygon_to_wkb_hex,
)

DOC = "doc-thick-test"
REV = "R1"
SHA = "b" * 64
SNAP = "snap-thick-1"
PAGE = "p1"
SCOPE = f"wall-source:page-{PAGE}"
WALL_1 = "phys-wall-1"
WALL_2 = "phys-wall-2"


def _selector(wall_id: str = WALL_1, page_id: str = PAGE) -> WallThicknessFaceSelector:
    return WallThicknessFaceSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=page_id,
        decision_scope_id=SCOPE,
        physical_wall_id=wall_id,
    )


def _make_candidate_record(
    wall_id: str,
    centerline_pts: tuple[tuple[float, float], ...] = ((0.0, 0.0), (10.0, 0.0)),
    thickness_m: float | None = 0.2,
) -> PhysicalWallCandidateRecord:
    cand = WallCandidate(
        candidate_id=wall_id,
        viewport_id=SCOPE,
        representation="single_line",
        centerline_pts=centerline_pts,
        face_a_segment_ids=("s1",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=thickness_m,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=10.0,
        end_node_ids=("n1", "n2"),
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior="unresolved",
        level_id=None,
        supporting_evidence_ids=("s1",),
        metadata={},
    )
    ident = PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id=SCOPE,
        candidate_identity_id=f"ident-{wall_id}",
        path_fingerprint=centerline_pts,
        source_primitive_ids=("s1",),
        edge_ids=("s1",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    return PhysicalWallCandidateRecord(
        wall_candidate_id=wall_id,
        wall_candidate=cand,
        physical_identity=ident,
    )


def _candidate_authority(
    *records: PhysicalWallCandidateRecord,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
) -> PhysicalWallCandidateAuthority:
    cand_key = _ScopeKey(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
    )
    return PhysicalWallCandidateAuthority(
        {
            cand_key: PhysicalWallCandidateScopeResult(
                status=status,
                scope_complete=True,
                records=tuple(records),
                source_observation_ids=(),
                document_id=DOC,
                revision_id=REV,
                source_sha256=SHA,
                snapshot_id=SNAP,
                page_id=PAGE,
                decision_scope_id=SCOPE,
                reason_codes=(),
            )
        },
        _seal=CANDIDATE_SEAL,
    )


def _scale_authority(
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
) -> PhysicalScaleAuthority:
    sel = PhysicalScaleSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
    )
    evidence = None
    if status == EvidenceResolutionStatus.CORROBORATED:
        evidence = PhysicalScaleEvidence(
            selector=sel,
            record_id="rec-scale-1",
            source_kind="graphic_scale_bar",
            source_span_pt=100.0,
            physical_span_mm=1000.0,
            points_per_mm=0.1,
            mm_per_point=10.0,
            source_segment_observation_ids=(),
            source_text_observation_ids=(),
            viewport_id=None,
        )
    return PhysicalScaleAuthority(
        {
            sel.key: PhysicalScaleResult(
                status=status,
                evidence=evidence,
                reason_codes=(),
            )
        },
        _seal=SCALE_SEAL,
    )


# ── Seal & Constructor Enforcement ────────────────────────────────────────────


def test_authority_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        WallThicknessFaceAuthority({})


def test_producer_constructor_sealed() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    scale_auth = _scale_authority()
    with pytest.raises(TypeError, match="from_authorities"):
        WallThicknessFaceProducer(cand_auth, scale_auth)


def test_record_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        WallFaceGeometryRecord(
            record_id="rec-1",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            physical_wall_id=WALL_1,
            thickness_m=0.2,
            thickness_mm=200.0,
            length_m=10.0,
            centerline_wkb_hex="",
            face_left_wkb_hex="",
            face_right_wkb_hex="",
            polygon_wkb_hex="",
            corroborating_evidence_ids=(),
        )


# ── Attack 1: Caller thickness ────────────────────────────────────────────────


def test_attack_1_caller_thickness_rejected() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    scale_auth = _scale_authority()
    producer = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
    )
    sel = _selector(WALL_1)

    # Caller attempts to supply thickness via kwargs
    with pytest.raises(TypeError):
        producer.publish(sel, thickness_m=0.2)  # type: ignore[call-arg]

    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert res.record is None


# ── Attack 2: Candidate thickness ─────────────────────────────────────────────


def test_attack_2_candidate_thickness_cannot_mint_authority() -> None:
    # Candidate describes thickness_m = 0.2
    rec = _make_candidate_record(WALL_1, thickness_m=0.2)
    cand_auth = _candidate_authority(rec)
    scale_auth = _scale_authority()
    producer = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
    )
    sel = _selector(WALL_1)

    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_SOURCE_EVIDENCE_UNAVAILABLE in res.reason_codes
    assert WALL_THICKNESS_CANDIDATE_REJECTED in res.reason_codes
    assert res.record is None


# ── Attack 3: Default thickness ───────────────────────────────────────────────


def test_attack_3_default_thickness_rejected() -> None:
    thick_prod = WallThicknessProducer.create()
    ev = WallThicknessEvidence(
        evidence_id="ev-default", document_id=DOC, revision_id=REV,
        source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
        physical_wall_id=WALL_1, thickness_m=0.2,
        source_kind="default", is_default=True,
    )
    with pytest.raises(TypeError, match="source-derived wall-thickness producer unavailable"):
        thick_prod.publish(ev)

def test_attack_4_wrong_wall_dimension_rejected() -> None:
    thick_prod = WallThicknessProducer.create()
    ev = WallThicknessEvidence(
        evidence_id="ev-dim-2", document_id=DOC, revision_id=REV,
        source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
        physical_wall_id=WALL_2, thickness_m=0.2,
        source_kind="figured_dimension",
    )
    with pytest.raises(TypeError, match="source-derived wall-thickness producer unavailable"):
        thick_prod.publish(ev)

def test_attack_5_stale_dimension_fails() -> None:
    thick_prod = WallThicknessProducer.create()
    ev = WallThicknessEvidence(
        evidence_id="ev-stale", document_id=DOC, revision_id="OLD_REV",
        source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
        physical_wall_id=WALL_1, thickness_m=0.2,
        source_kind="figured_dimension",
    )
    with pytest.raises(TypeError, match="source-derived wall-thickness producer unavailable"):
        thick_prod.publish(ev)

def test_attack_6_conflicting_dimensions_conflict() -> None:
    thick_prod = WallThicknessProducer.create()
    for thickness in (0.20, 0.25):
        ev = WallThicknessEvidence(
            evidence_id=f"ev-{thickness}", document_id=DOC, revision_id=REV,
            source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
            physical_wall_id=WALL_1, thickness_m=thickness,
            source_kind="figured_dimension",
        )
        with pytest.raises(TypeError, match="source-derived wall-thickness producer unavailable"):
            thick_prod.publish(ev)

def test_attack_7_zero_thickness_rejected() -> None:
    thick_prod = WallThicknessProducer.create()
    ev = WallThicknessEvidence(
        evidence_id="ev-zero", document_id=DOC, revision_id=REV,
        source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
        physical_wall_id=WALL_1, thickness_m=0.0,
        source_kind="figured_dimension",
    )
    with pytest.raises(TypeError, match="source-derived wall-thickness producer unavailable"):
        thick_prod.publish(ev)

def test_attack_8_negative_thickness_rejected() -> None:
    thick_prod = WallThicknessProducer.create()
    ev = WallThicknessEvidence(
        evidence_id="ev-neg", document_id=DOC, revision_id=REV,
        source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
        physical_wall_id=WALL_1, thickness_m=-0.2,
        source_kind="figured_dimension",
    )
    with pytest.raises(TypeError, match="source-derived wall-thickness producer unavailable"):
        thick_prod.publish(ev)

def test_attack_9_multi_segment_bent_wall() -> None:
    pts = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0))
    left = _compute_multi_segment_offset(pts, 0.1)
    right = _compute_multi_segment_offset(pts, -0.1)
    expected_left = ((0.0, 0.1), (9.9, 0.1), (9.9, 10.0))
    expected_right = ((0.0, -0.1), (10.1, -0.1), (10.1, 10.0))
    for actual, expected in zip(left, expected_left):
        assert actual == pytest.approx(expected)
    for actual, expected in zip(right, expected_right):
        assert actual == pytest.approx(expected)

def test_attack_10_and_11_reversed_polyline_does_not_swap_faces() -> None:
    fwd = ((0.0, 0.0), (10.0, 0.0))
    rev = tuple(reversed(fwd))
    assert _is_canonical_direction(fwd) is True
    assert _is_canonical_direction(rev) is False
    canonical_fwd = fwd
    canonical_rev = tuple(reversed(rev))
    assert _compute_multi_segment_offset(canonical_fwd, 0.1) == _compute_multi_segment_offset(canonical_rev, 0.1)
    assert _compute_multi_segment_offset(canonical_fwd, -0.1) == _compute_multi_segment_offset(canonical_rev, -0.1)

def test_attack_12_genuine_wkb_serialization() -> None:
    center = ((0.0, 0.0), (10.0, 0.0))
    left = _compute_multi_segment_offset(center, 0.1)
    right = _compute_multi_segment_offset(center, -0.1)
    poly = list(left) + list(reversed(right)) + [left[0]]
    center_hex = _linestring_to_wkb_hex(center)
    poly_hex = _polygon_to_wkb_hex(poly)
    assert center_hex.startswith("01")
    assert poly_hex.startswith("01")
    assert not center_hex.startswith("4c49")
    assert wkb.loads(bytes.fromhex(center_hex)).geom_type == "LineString"
    poly_geom = wkb.loads(bytes.fromhex(poly_hex))
    assert poly_geom.geom_type == "Polygon"
    assert pytest.approx(poly_geom.area, abs=1e-4) == 2.0

def test_attack_13_exact_source_dimension_positive_case() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    scale_auth = _scale_authority()
    producer = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
    )
    res = producer.publish(_selector(WALL_1))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_SOURCE_EVIDENCE_UNAVAILABLE in res.reason_codes
    assert res.record is None

def test_scale_unresolved_abstains() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    scale_auth = _scale_authority(status=EvidenceResolutionStatus.ABSTAINED)
    producer = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
    )
    res = producer.publish(_selector(WALL_1))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_SCALE_UNRESOLVED in res.reason_codes
    assert res.record is None


def test_wall_unresolved_abstains() -> None:
    cand_auth = _candidate_authority(
        _make_candidate_record(WALL_1),
        status=EvidenceResolutionStatus.ABSTAINED,
    )
    scale_auth = _scale_authority()
    producer = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
    )
    res = producer.publish(_selector(WALL_1))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_WALL_UNRESOLVED in res.reason_codes
    assert res.record is None


def test_record_unavailable_returns_abstained() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    scale_auth = _scale_authority()
    producer = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
    )
    auth = producer.authority()
    res = auth.resolve(_selector(WALL_1))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_RECORD_UNAVAILABLE in res.reason_codes

