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
    assert WALL_THICKNESS_UNRESOLVED in res.reason_codes
    assert WALL_THICKNESS_CANDIDATE_REJECTED in res.reason_codes
    assert res.record is None


# ── Attack 3: Default thickness ───────────────────────────────────────────────


def test_attack_3_default_thickness_rejected() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    scale_auth = _scale_authority()

    thick_prod = WallThicknessProducer.create()
    thick_prod.publish(
        WallThicknessEvidence(
            evidence_id="ev-default",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            physical_wall_id=WALL_1,
            thickness_m=0.2,
            source_kind="default",
            is_default=True,  # DEFAULT CLAIM
        )
    )

    producer = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
        wall_thickness_authority=thick_prod.authority(),
    )
    res = producer.publish(_selector(WALL_1))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_DEFAULT_REJECTED in res.reason_codes
    assert res.record is None


# ── Attack 4: Wrong-wall dimension ────────────────────────────────────────────


def test_attack_4_wrong_wall_dimension_rejected() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    scale_auth = _scale_authority()

    # Evidence published for WALL_2
    thick_prod = WallThicknessProducer.create()
    thick_prod.publish(
        WallThicknessEvidence(
            evidence_id="ev-dim-2",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            physical_wall_id=WALL_2,
            thickness_m=0.2,
            source_kind="figured_dimension",
        )
    )

    # Wrap in authority that queries with WALL_1 key but has WALL_2 evidence
    from pb_wall_thickness_face_authority import _AUTHORITY_SEAL
    wrong_wall_ev = WallThicknessEvidence(
        evidence_id="ev-dim-2",
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        physical_wall_id=WALL_2,
        thickness_m=0.2,
        source_kind="figured_dimension",
    )
    wrong_auth = WallThicknessAuthority(
        {(DOC, REV, SHA, SNAP, PAGE, WALL_1): wrong_wall_ev},
        _seal=_AUTHORITY_SEAL,
    )

    producer = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
        wall_thickness_authority=wrong_auth,
    )
    res = producer.publish(_selector(WALL_1))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_WRONG_WALL in res.reason_codes
    assert res.record is None


# ── Attack 5: Stale dimension ─────────────────────────────────────────────────


def test_attack_5_stale_dimension_fails() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    scale_auth = _scale_authority()

    from pb_wall_thickness_face_authority import _AUTHORITY_SEAL
    stale_ev = WallThicknessEvidence(
        evidence_id="ev-stale",
        document_id=DOC,
        revision_id="OLD_REV",  # STALE
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        physical_wall_id=WALL_1,
        thickness_m=0.2,
        source_kind="figured_dimension",
    )
    stale_auth = WallThicknessAuthority(
        {(DOC, REV, SHA, SNAP, PAGE, WALL_1): stale_ev},
        _seal=_AUTHORITY_SEAL,
    )

    producer = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
        wall_thickness_authority=stale_auth,
    )
    res = producer.publish(_selector(WALL_1))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_STALE_EVIDENCE in res.reason_codes
    assert WALL_THICKNESS_LINEAGE_MISMATCH in res.reason_codes
    assert res.record is None


# ── Attack 6: Conflicting dimension ───────────────────────────────────────────


def test_attack_6_conflicting_dimensions_conflict() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    scale_auth = _scale_authority()

    thick_prod = WallThicknessProducer.create()
    thick_prod.publish(
        WallThicknessEvidence(
            evidence_id="ev-dim-1",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            physical_wall_id=WALL_1,
            thickness_m=0.20,
            source_kind="figured_dimension",
        )
    )
    thick_prod.publish(
        WallThicknessEvidence(
            evidence_id="ev-dim-2",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            physical_wall_id=WALL_1,
            thickness_m=0.25,  # CONFLICT
            source_kind="wall_detail",
        )
    )

    producer = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
        wall_thickness_authority=thick_prod.authority(),
    )
    res = producer.publish(_selector(WALL_1))
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert WALL_THICKNESS_CONFLICT in res.reason_codes
    assert res.record is None


# ── Attack 7: Zero thickness ──────────────────────────────────────────────────


def test_attack_7_zero_thickness_rejected() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    scale_auth = _scale_authority()

    thick_prod = WallThicknessProducer.create()
    thick_prod.publish(
        WallThicknessEvidence(
            evidence_id="ev-zero",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            physical_wall_id=WALL_1,
            thickness_m=0.0,  # ZERO
            source_kind="figured_dimension",
        )
    )

    producer = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
        wall_thickness_authority=thick_prod.authority(),
    )
    res = producer.publish(_selector(WALL_1))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_ZERO_REJECTED in res.reason_codes
    assert res.record is None


# ── Attack 8: Negative thickness ──────────────────────────────────────────────


def test_attack_8_negative_thickness_rejected() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    scale_auth = _scale_authority()

    thick_prod = WallThicknessProducer.create()
    thick_prod.publish(
        WallThicknessEvidence(
            evidence_id="ev-neg",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            physical_wall_id=WALL_1,
            thickness_m=-0.2,  # NEGATIVE
            source_kind="figured_dimension",
        )
    )

    producer = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
        wall_thickness_authority=thick_prod.authority(),
    )
    res = producer.publish(_selector(WALL_1))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_THICKNESS_NEGATIVE_REJECTED in res.reason_codes
    assert res.record is None


# ── Attack 9: Multi-segment bent wall ─────────────────────────────────────────


def test_attack_9_multi_segment_bent_wall() -> None:
    # Wall bends at (10, 0) up to (10, 10)
    bent_pts = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0))
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1, centerline_pts=bent_pts))
    scale_auth = _scale_authority()

    thick_prod = WallThicknessProducer.create()
    thick_prod.publish(
        WallThicknessEvidence(
            evidence_id="ev-dim-bent",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            physical_wall_id=WALL_1,
            thickness_m=0.2,  # 200mm -> d = 0.1
            source_kind="figured_dimension",
        )
    )

    producer = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
        wall_thickness_authority=thick_prod.authority(),
    )
    res = producer.publish(_selector(WALL_1))
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    rec = res.record
    assert rec is not None

    left_geom = wkb.loads(bytes.fromhex(rec.face_left_wkb_hex))
    right_geom = wkb.loads(bytes.fromhex(rec.face_right_wkb_hex))

    left_coords = list(left_geom.coords)
    right_coords = list(right_geom.coords)

    # Segment 1 is along +X -> left normal is (0, 1) -> y = 0.1
    # Segment 2 is along +Y -> left normal is (-1, 0) -> x = 9.9
    # Corner miter is intersection (9.9, 0.1)
    assert pytest.approx(left_coords[0][0], abs=1e-4) == 0.0
    assert pytest.approx(left_coords[0][1], abs=1e-4) == 0.1

    assert pytest.approx(left_coords[1][0], abs=1e-4) == 9.9
    assert pytest.approx(left_coords[1][1], abs=1e-4) == 0.1

    assert pytest.approx(left_coords[2][0], abs=1e-4) == 9.9
    assert pytest.approx(left_coords[2][1], abs=1e-4) == 10.0

    # Right face is offset opposite: x = 10.1, y = -0.1
    assert pytest.approx(right_coords[0][0], abs=1e-4) == 0.0
    assert pytest.approx(right_coords[0][1], abs=1e-4) == -0.1

    assert pytest.approx(right_coords[1][0], abs=1e-4) == 10.1
    assert pytest.approx(right_coords[1][1], abs=1e-4) == -0.1

    assert pytest.approx(right_coords[2][0], abs=1e-4) == 10.1
    assert pytest.approx(right_coords[2][1], abs=1e-4) == 10.0


# ── Attack 10 & 11: Reversed polyline & Stable face identity ──────────────────


def test_attack_10_and_11_reversed_polyline_does_not_swap_faces() -> None:
    pts_forward = ((0.0, 0.0), (10.0, 0.0))
    pts_reversed = ((10.0, 0.0), (0.0, 0.0))

    scale_auth = _scale_authority()

    thick_prod = WallThicknessProducer.create()
    thick_prod.publish(
        WallThicknessEvidence(
            evidence_id="ev-dim-stable",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            physical_wall_id=WALL_1,
            thickness_m=0.2,
            source_kind="figured_dimension",
        )
    )

    # Forward candidate
    cand_auth_fwd = _candidate_authority(_make_candidate_record(WALL_1, centerline_pts=pts_forward))
    prod_fwd = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth_fwd,
        physical_scale_authority=scale_auth,
        wall_thickness_authority=thick_prod.authority(),
    )
    res_fwd = prod_fwd.publish(_selector(WALL_1))
    assert res_fwd.status is EvidenceResolutionStatus.CORROBORATED
    rec_fwd = res_fwd.record
    assert rec_fwd is not None

    # Reversed candidate
    cand_auth_rev = _candidate_authority(_make_candidate_record(WALL_1, centerline_pts=pts_reversed))
    prod_rev = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth_rev,
        physical_scale_authority=scale_auth,
        wall_thickness_authority=thick_prod.authority(),
    )
    res_rev = prod_rev.publish(_selector(WALL_1))
    assert res_rev.status is EvidenceResolutionStatus.CORROBORATED
    rec_rev = res_rev.record
    assert rec_rev is not None

    # Compare face geometries: they must NOT silently swap!
    # Left face in forward candidate: y = +0.1
    # Left face in reversed candidate MUST ALSO BE y = +0.1!
    geom_fwd_left = wkb.loads(bytes.fromhex(rec_fwd.face_left_wkb_hex))
    geom_rev_left = wkb.loads(bytes.fromhex(rec_rev.face_left_wkb_hex))

    assert pytest.approx(geom_fwd_left.coords[0][1], abs=1e-4) == 0.1
    assert pytest.approx(geom_rev_left.coords[0][1], abs=1e-4) == 0.1

    geom_fwd_right = wkb.loads(bytes.fromhex(rec_fwd.face_right_wkb_hex))
    geom_rev_right = wkb.loads(bytes.fromhex(rec_rev.face_right_wkb_hex))

    assert pytest.approx(geom_fwd_right.coords[0][1], abs=1e-4) == -0.1
    assert pytest.approx(geom_rev_right.coords[0][1], abs=1e-4) == -0.1

    # WKB hex strings are identical
    assert rec_fwd.face_left_wkb_hex == rec_rev.face_left_wkb_hex
    assert rec_fwd.face_right_wkb_hex == rec_rev.face_right_wkb_hex


# ── Attack 12: Fake WKB rejected & genuine binary WKB verified ────────────────


def test_attack_12_genuine_wkb_serialization() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    scale_auth = _scale_authority()

    thick_prod = WallThicknessProducer.create()
    thick_prod.publish(
        WallThicknessEvidence(
            evidence_id="ev-wkb",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            physical_wall_id=WALL_1,
            thickness_m=0.2,
            source_kind="figured_dimension",
        )
    )

    producer = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
        wall_thickness_authority=thick_prod.authority(),
    )
    res = producer.publish(_selector(WALL_1))
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    rec = res.record
    assert rec is not None

    # Genuine WKB starts with 01 (little endian)
    assert rec.centerline_wkb_hex.startswith("01")
    assert rec.face_left_wkb_hex.startswith("01")
    assert rec.face_right_wkb_hex.startswith("01")
    assert rec.polygon_wkb_hex.startswith("01")

    # MUST NOT be hex-encoded text "LINESTRING" (which starts with 4c494e45535452494e47)
    fake_wkt_hex = "LINESTRING(0 0, 10 0)".encode("utf-8").hex()
    assert not rec.centerline_wkb_hex.startswith("4c49")

    # Verify that Shapely WKB parser successfully parses them
    cl_geom = wkb.loads(bytes.fromhex(rec.centerline_wkb_hex))
    assert cl_geom.geom_type == "LineString"
    assert cl_geom.length == 10.0

    poly_geom = wkb.loads(bytes.fromhex(rec.polygon_wkb_hex))
    assert poly_geom.geom_type == "Polygon"
    assert pytest.approx(poly_geom.area, abs=1e-4) == 2.0  # 10m * 0.2m


# ── Attack 13: Exact source-dimension positive case ───────────────────────────


def test_attack_13_exact_source_dimension_positive_case() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    scale_auth = _scale_authority()

    thick_prod = WallThicknessProducer.create()
    thick_prod.publish(
        WallThicknessEvidence(
            evidence_id="ev-dim-pos",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            physical_wall_id=WALL_1,
            thickness_m=0.23,  # 230mm brick wall
            source_kind="figured_dimension",
        )
    )

    producer = WallThicknessFaceProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
        wall_thickness_authority=thick_prod.authority(),
    )
    sel = _selector(WALL_1)
    res = producer.publish(sel)

    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.reason_codes == (WALL_THICKNESS_FACE_RESOLVED,)
    rec = res.record
    assert rec is not None
    assert rec.thickness_m == 0.23
    assert rec.thickness_mm == 230.0
    assert rec.length_m == 10.0
    assert "ev-dim-pos" in rec.corroborating_evidence_ids
    assert WALL_1 in rec.corroborating_evidence_ids

    # Authority lookup matches
    auth = producer.authority()
    lookup = auth.resolve(sel)
    assert lookup.status is EvidenceResolutionStatus.CORROBORATED
    assert lookup.record == rec


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

