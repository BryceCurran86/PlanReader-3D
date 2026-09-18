"""Production and adversarial tests for pb_ghazi_wall_finish_recovery_authority (Item 28).

Comprehensive verification of fail-closed generic wall and finish quantity recovery:
- Zero hardcoded defaults (no 3.0m height, no 0.2m thickness, no gross=net bypass)
- Root-cause classification for unresolvable quantities across drawing sets
- Sealed constructor enforcement and immutable selectors
- Upstream authority integration (candidate, role, thickness, net wall, cross-sheet, finish)
- Deterministic IDs and lineage verification
"""
from __future__ import annotations

import pytest

from pb_cross_sheet_registration_authority import (
    CrossSheetRegistrationAuthority,
    CrossSheetRegistrationRecord,
    CrossSheetRegistrationResult,
    _AUTHORITY_SEAL as CROSS_SHEET_SEAL,
)
from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_ghazi_wall_finish_recovery_authority import (
    GHAZI_RECOVERY_LINEAGE_MISMATCH,
    GHAZI_RECOVERY_RECORD_UNAVAILABLE,
    GHAZI_RECOVERY_RESOLVED,
    GHAZI_RECOVERY_SCHEMA_VERSION,
    GHAZI_RECOVERY_UNRESOLVED,
    GhaziRecoveryRootCause,
    GhaziWallFinishRecoveryAuthority,
    GhaziWallFinishRecoveryProducer,
    GhaziWallFinishRecoveryRecord,
    GhaziWallFinishRecoveryResult,
    GhaziWallFinishRecoverySelector,
    _AUTHORITY_SEAL as RECOVERY_AUTH_SEAL,
    _PRODUCER_SEAL as RECOVERY_PROD_SEAL,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_net_wall_boolean_union_authority import (
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionRecord,
    NetWallBooleanUnionResult,
    _AUTHORITY_SEAL as NET_WALL_SEAL,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    _AUTHORITY_SEAL as CANDIDATE_SEAL,
    _ScopeKey,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_wall_finish_propagation_authority import (
    WallFinishPropagationAuthority,
    WallFinishPropagationResult,
    _AUTHORITY_SEAL as FINISH_SEAL,
)
from pb_wall_role_authority import (
    WallRoleAuthority,
    WallRoleClassification,
    WallRoleRecord,
    WallRoleResult,
    _AUTHORITY_SEAL as ROLE_SEAL,
    _RECORD_SEAL as ROLE_RECORD_SEAL,
)
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_thickness_face_authority import (
    WallFaceGeometryRecord,
    WallThicknessFaceAuthority,
    WallThicknessFaceResult,
    _AUTHORITY_SEAL as THICKNESS_SEAL,
    _RECORD_SEAL as THICKNESS_RECORD_SEAL,
)

DOC = "doc-ghazi-test"
REV = "rev-01"
SHA = "f" * 64
SNAP = "snap-ghazi-01"
PAGE = "page-01"
TARGET_PAGE = "page-elev-02"
SCOPE = f"wall-source:page-{PAGE}"
WALL_1 = "phys-wall-001"
TRADE = "trade-masonry"


def _make_selector(
    wall_id: str = WALL_1,
    page_id: str = PAGE,
    trade_id: str = TRADE,
    doc_id: str = DOC,
    rev_id: str = REV,
    sha: str = SHA,
    snap_id: str = SNAP,
    scope_id: str = SCOPE,
) -> GhaziWallFinishRecoverySelector:
    return GhaziWallFinishRecoverySelector(
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
        page_id=page_id,
        decision_scope_id=scope_id,
        physical_wall_id=wall_id,
        trade_scope_id=trade_id,
    )


def _make_candidate_record(
    wall_id: str = WALL_1,
    length_m: float = 8.0,
    thickness_m: float = 0.2,
) -> PhysicalWallCandidateRecord:
    cand = WallCandidate(
        candidate_id=wall_id,
        viewport_id=SCOPE,
        representation="single_line",
        centerline_pts=((0.0, 0.0), (length_m, 0.0)),
        face_a_segment_ids=("s1",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=thickness_m,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=length_m,
        end_node_ids=("n1", "n2"),
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior="unresolved",
        level_id=None,
        supporting_evidence_ids=("ev-line-001",),
        metadata={},
    )
    ident = PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id=SCOPE,
        candidate_identity_id=f"ident-{wall_id}",
        path_fingerprint=((0.0, 0.0), (length_m, 0.0)),
        source_primitive_ids=("s1",),
        edge_ids=("s1",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    return PhysicalWallCandidateRecord(
        wall_candidate_id=wall_id,
        wall_candidate=cand,
        physical_identity=ident,
    )


def _make_candidate_authority(
    *records: PhysicalWallCandidateRecord,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
    doc_id: str = DOC,
    rev_id: str = REV,
    sha: str = SHA,
    snap_id: str = SNAP,
    page_id: str = PAGE,
    scope_id: str = SCOPE,
    result_rev_id: str | None = None,
    reason_codes: tuple[str, ...] = (),
) -> PhysicalWallCandidateAuthority:
    cand_key = _ScopeKey(
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        snapshot_id=snap_id,
        page_id=page_id,
        decision_scope_id=scope_id,
    )
    return PhysicalWallCandidateAuthority(
        {
            cand_key: PhysicalWallCandidateScopeResult(
                status=status,
                scope_complete=True,
                records=tuple(records),
                source_observation_ids=(),
                document_id=doc_id,
                revision_id=result_rev_id if result_rev_id is not None else rev_id,
                source_sha256=sha,
                snapshot_id=snap_id,
                page_id=page_id,
                decision_scope_id=scope_id,
                reason_codes=reason_codes,
            )
        },
        _seal=CANDIDATE_SEAL,
    )


def _make_role_authority(
    wall_id: str = WALL_1,
    role: WallRoleClassification = WallRoleClassification.EXTERNAL,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
    reasons: tuple[str, ...] = ("role_resolved",),
) -> WallRoleAuthority:
    key: tuple[str, ...] = (DOC, REV, SHA, SNAP, PAGE, SCOPE, wall_id)
    rec = None
    if status is EvidenceResolutionStatus.CORROBORATED:
        rec = WallRoleRecord(
            record_id=f"role-rec-{wall_id}",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            physical_wall_id=wall_id,
            role=role,
            corroborating_evidence_ids=("ev-role-01",),
            _seal=ROLE_RECORD_SEAL,
        )
    return WallRoleAuthority(
        {key: WallRoleResult(status=status, reason_codes=reasons, record=rec)},
        _seal=ROLE_SEAL,
    )


def _make_thickness_authority(
    wall_id: str = WALL_1,
    thickness_m: float = 0.2,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
    reasons: tuple[str, ...] = ("thickness_resolved",),
) -> WallThicknessFaceAuthority:
    key: tuple[str, ...] = (DOC, REV, SHA, SNAP, PAGE, SCOPE, wall_id)
    rec = None
    if status is EvidenceResolutionStatus.CORROBORATED:
        rec = WallFaceGeometryRecord(
            record_id=f"thick-rec-{wall_id}",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            physical_wall_id=wall_id,
            thickness_m=thickness_m,
            thickness_mm=thickness_m * 1000.0,
            length_m=8.0,
            centerline_wkb_hex="",
            face_left_wkb_hex="",
            face_right_wkb_hex="",
            polygon_wkb_hex="",
            corroborating_evidence_ids=("ev-thick-01",),
            _seal=THICKNESS_RECORD_SEAL,
        )
    return WallThicknessFaceAuthority(
        {key: WallThicknessFaceResult(status=status, reason_codes=reasons, record=rec)},
        _seal=THICKNESS_SEAL,
    )


def _make_net_wall_authority(
    wall_id: str = WALL_1,
    gross_area_m2: float = 24.0,
    net_area_m2: float = 20.0,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
    reasons: tuple[str, ...] = ("net_wall_boolean_union_resolved",),
) -> NetWallBooleanUnionAuthority:
    key: tuple[str, ...] = (DOC, REV, SHA, SNAP, PAGE, SCOPE, wall_id, TRADE)
    rec = None
    if status is EvidenceResolutionStatus.CORROBORATED:
        rec = NetWallBooleanUnionRecord(
            record_id=f"net-wall-rec-{wall_id}",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            physical_wall_id=wall_id,
            gross_geometry_record_id=f"gross-geom-{wall_id}",
            opening_universe_record_id=f"opening-univ-{wall_id}",
            deduction_record_ids=(f"ded-{wall_id}",),
            union_geometry_id=f"union-geom-{wall_id}",
            gross_area_m2=gross_area_m2,
            net_area_m2=net_area_m2,
            trade_scope_id=TRADE,
        )
    return NetWallBooleanUnionAuthority(
        {key: NetWallBooleanUnionResult(status=status, reason_codes=reasons, record=rec)},
        _seal=NET_WALL_SEAL,
    )


def _make_cross_sheet_authority(
    wall_id: str = WALL_1,
    target_page: str = TARGET_PAGE,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
    reasons: tuple[str, ...] = ("cross_sheet_registered",),
) -> CrossSheetRegistrationAuthority:
    key: tuple[str, ...] = (DOC, REV, SHA, SNAP, PAGE, target_page, wall_id)
    rec = None
    if status is EvidenceResolutionStatus.CORROBORATED:
        rec = CrossSheetRegistrationRecord(
            record_id=f"cross-rec-{wall_id}",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            source_page_id=PAGE,
            target_page_id=target_page,
            physical_element_id=wall_id,
            target_physical_element_id=f"target-{wall_id}",
            source_view_type="plan",
            target_view_type="elevation",
            callout_mark="E1",
            referenced_sheet_code="A-201",
        )
    return CrossSheetRegistrationAuthority(
        {key: CrossSheetRegistrationResult(status=status, reason_codes=reasons, record=rec)},
        _seal=CROSS_SHEET_SEAL,
    )


def _make_finish_authority(
    wall_id: str = WALL_1,
    trade_id: str = TRADE,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
    reasons: tuple[str, ...] = ("finish_bound",),
) -> WallFinishPropagationAuthority:
    key: tuple[str, ...] = (DOC, REV, SHA, SNAP, PAGE, SCOPE, wall_id, trade_id)
    return WallFinishPropagationAuthority(
        {key: WallFinishPropagationResult(status=status, reason_codes=reasons, record=None)},
        _seal=FINISH_SEAL,
    )


# ── Seal & Constructor Enforcement ────────────────────────────────────────────

def test_authority_constructor_rejects_unsealed_construction() -> None:
    with pytest.raises(TypeError, match="cannot be constructed directly"):
        GhaziWallFinishRecoveryAuthority({})


def test_producer_constructor_rejects_direct_init() -> None:
    cand_auth = _make_candidate_authority()
    with pytest.raises(TypeError, match="must be obtained via from_authorities"):
        GhaziWallFinishRecoveryProducer(cand_auth)


def test_producer_rejects_invalid_authorities() -> None:
    with pytest.raises(TypeError, match="physical_wall_candidate_authority must be producer-owned"):
        GhaziWallFinishRecoveryProducer.from_authorities(
            physical_wall_candidate_authority="not-an-auth",  # type: ignore[arg-type]
        )


def test_selector_validation() -> None:
    with pytest.raises(ValueError, match="physical_wall_id must be non-empty"):
        GhaziWallFinishRecoverySelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            physical_wall_id="",
            trade_scope_id=TRADE,
        )


# ── Adversarial Tests ──────────────────────────────────────────────────────────

def test_adversarial_missing_physical_wall_candidate() -> None:
    """Missing physical wall candidate abstains with WALL_INSTANCE_MISSING."""
    cand_auth = _make_candidate_authority()  # no records
    prod = GhaziWallFinishRecoveryProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
    )
    sel = _make_selector()
    res = prod.publish(sel)

    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GHAZI_RECOVERY_UNRESOLVED in res.reason_codes
    assert GhaziRecoveryRootCause.WALL_INSTANCE_MISSING.value in res.reason_codes
    assert res.record is None


def test_adversarial_candidate_scope_unresolved() -> None:
    """Unresolved candidate scope status abstains with WALL_INSTANCE_MISSING."""
    cand_auth = _make_candidate_authority(status=EvidenceResolutionStatus.ABSTAINED)
    prod = GhaziWallFinishRecoveryProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
    )
    sel = _make_selector()
    res = prod.publish(sel)

    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GhaziRecoveryRootCause.WALL_INSTANCE_MISSING.value in res.reason_codes


def test_adversarial_candidate_lineage_mismatch() -> None:
    """Candidate lineage mismatch raises conflict with GHAZI_RECOVERY_LINEAGE_MISMATCH."""
    cand_rec = _make_candidate_record()
    cand_auth = _make_candidate_authority(cand_rec, rev_id=REV, result_rev_id="rev-tampered")
    prod = GhaziWallFinishRecoveryProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
    )
    sel = _make_selector(rev_id=REV)
    res = prod.publish(sel)

    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert GHAZI_RECOVERY_LINEAGE_MISMATCH in res.reason_codes


def test_adversarial_missing_wall_role_when_required() -> None:
    """Missing wall role authority when required yields WALL_ROLE_UNRESOLVED."""
    cand_rec = _make_candidate_record()
    cand_auth = _make_candidate_authority(cand_rec)
    prod = GhaziWallFinishRecoveryProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        wall_role_authority=None,
    )
    sel = _make_selector()
    res = prod.publish(sel, require_wall_role=True)

    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GhaziRecoveryRootCause.WALL_ROLE_UNRESOLVED.value in res.reason_codes


def test_adversarial_wall_role_conflict() -> None:
    """Wall role in conflict yields CONFLICT with WALL_ROLE_UNRESOLVED root cause."""
    cand_rec = _make_candidate_record()
    cand_auth = _make_candidate_authority(cand_rec)
    role_auth = _make_role_authority(status=EvidenceResolutionStatus.CONFLICT, reasons=("role_conflict",))
    prod = GhaziWallFinishRecoveryProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        wall_role_authority=role_auth,
    )
    sel = _make_selector()
    res = prod.publish(sel, require_wall_role=True)

    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert GhaziRecoveryRootCause.WALL_ROLE_UNRESOLVED.value in res.reason_codes


def test_adversarial_missing_wall_thickness_when_required() -> None:
    """Missing wall thickness when required yields WALL_THICKNESS_UNRESOLVED."""
    cand_rec = _make_candidate_record()
    cand_auth = _make_candidate_authority(cand_rec)
    prod = GhaziWallFinishRecoveryProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        wall_thickness_face_authority=None,
    )
    sel = _make_selector()
    res = prod.publish(sel, require_wall_thickness=True)

    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GhaziRecoveryRootCause.WALL_THICKNESS_UNRESOLVED.value in res.reason_codes


def test_adversarial_wall_thickness_conflict() -> None:
    """Wall thickness conflict yields CONFLICT with WALL_THICKNESS_UNRESOLVED root cause."""
    cand_rec = _make_candidate_record()
    cand_auth = _make_candidate_authority(cand_rec)
    thick_auth = _make_thickness_authority(status=EvidenceResolutionStatus.CONFLICT, reasons=("thickness_conflict",))
    prod = GhaziWallFinishRecoveryProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        wall_thickness_face_authority=thick_auth,
    )
    sel = _make_selector()
    res = prod.publish(sel, require_wall_thickness=True)

    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert GhaziRecoveryRootCause.WALL_THICKNESS_UNRESOLVED.value in res.reason_codes


def test_adversarial_missing_net_wall_authority_fails_closed_never_defaults_3m() -> None:
    """WITHOUT net wall boolean union authority, height CANNOT be authenticated.
    Must fail closed with WALL_HEIGHT_UNRESOLVED instead of defaulting to 3.0m.
    """
    cand_rec = _make_candidate_record()
    cand_auth = _make_candidate_authority(cand_rec)
    prod = GhaziWallFinishRecoveryProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        net_wall_boolean_union_authority=None,
    )
    sel = _make_selector()
    res = prod.publish(sel)

    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GhaziRecoveryRootCause.WALL_HEIGHT_UNRESOLVED.value in res.reason_codes
    assert "net_wall_boolean_union_authority_unavailable" in res.reason_codes
    assert res.record is None


def test_adversarial_net_wall_height_conflict() -> None:
    """Net wall height failure surfaces WALL_HEIGHT_UNRESOLVED."""
    cand_rec = _make_candidate_record()
    cand_auth = _make_candidate_authority(cand_rec)
    net_auth = _make_net_wall_authority(
        status=EvidenceResolutionStatus.CONFLICT,
        reasons=("wall_height_conflict_datum_mismatch",),
    )
    prod = GhaziWallFinishRecoveryProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        net_wall_boolean_union_authority=net_auth,
    )
    sel = _make_selector()
    res = prod.publish(sel)

    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert GhaziRecoveryRootCause.WALL_HEIGHT_UNRESOLVED.value in res.reason_codes


def test_adversarial_net_wall_opening_deduction_failure() -> None:
    """Net wall opening deduction failure surfaces OPENING_DEDUCTION_UNRESOLVED."""
    cand_rec = _make_candidate_record()
    cand_auth = _make_candidate_authority(cand_rec)
    net_auth = _make_net_wall_authority(
        status=EvidenceResolutionStatus.ABSTAINED,
        reasons=("opening_universe_incomplete", "opening_deduction_unresolved"),
    )
    prod = GhaziWallFinishRecoveryProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        net_wall_boolean_union_authority=net_auth,
    )
    sel = _make_selector()
    res = prod.publish(sel)

    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GhaziRecoveryRootCause.OPENING_DEDUCTION_UNRESOLVED.value in res.reason_codes


def test_adversarial_missing_cross_sheet_evidence() -> None:
    """Missing cross sheet evidence when elevation target requested yields CROSS_SHEET_EVIDENCE_MISSING."""
    cand_rec = _make_candidate_record()
    cand_auth = _make_candidate_authority(cand_rec)
    net_auth = _make_net_wall_authority()
    prod = GhaziWallFinishRecoveryProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        net_wall_boolean_union_authority=net_auth,
        cross_sheet_registration_authority=None,
    )
    sel = _make_selector()
    res = prod.publish(sel, target_elevation_page_id=TARGET_PAGE)

    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GhaziRecoveryRootCause.CROSS_SHEET_EVIDENCE_MISSING.value in res.reason_codes


def test_adversarial_missing_finish_binding() -> None:
    """Missing finish binding when requested yields FINISH_ASSIGNMENT_UNRESOLVED."""
    cand_rec = _make_candidate_record()
    cand_auth = _make_candidate_authority(cand_rec)
    net_auth = _make_net_wall_authority()
    prod = GhaziWallFinishRecoveryProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        net_wall_boolean_union_authority=net_auth,
        wall_finish_propagation_authority=None,
    )
    sel = _make_selector()
    res = prod.publish(sel, require_finish_binding=True)

    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GhaziRecoveryRootCause.FINISH_ASSIGNMENT_UNRESOLVED.value in res.reason_codes


# ── Positive Resolution Test ──────────────────────────────────────────────────

def test_positive_full_recovery_resolution() -> None:
    """All upstream authorities corroborating results in CORROBORATED recovery record."""
    cand_rec = _make_candidate_record(wall_id=WALL_1, length_m=8.0, thickness_m=0.2)
    cand_auth = _make_candidate_authority(cand_rec)
    role_auth = _make_role_authority(wall_id=WALL_1, role=WallRoleClassification.EXTERNAL)
    thick_auth = _make_thickness_authority(wall_id=WALL_1, thickness_m=0.2)
    net_auth = _make_net_wall_authority(wall_id=WALL_1, gross_area_m2=24.0, net_area_m2=20.0)
    cross_auth = _make_cross_sheet_authority(wall_id=WALL_1, target_page=TARGET_PAGE)
    finish_auth = _make_finish_authority(wall_id=WALL_1, trade_id=TRADE)

    prod = GhaziWallFinishRecoveryProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        wall_role_authority=role_auth,
        wall_thickness_face_authority=thick_auth,
        net_wall_boolean_union_authority=net_auth,
        cross_sheet_registration_authority=cross_auth,
        wall_finish_propagation_authority=finish_auth,
    )
    sel = _make_selector()
    res = prod.publish(
        sel,
        require_wall_role=True,
        require_wall_thickness=True,
        require_finish_binding=True,
        target_elevation_page_id=TARGET_PAGE,
    )

    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.reason_codes == (GHAZI_RECOVERY_RESOLVED,)
    assert res.record is not None

    rec = res.record
    assert rec.physical_wall_id == WALL_1
    assert rec.trade_scope_id == TRADE
    assert rec.root_cause is GhaziRecoveryRootCause.RESOLVED
    assert rec.length_m == 8.0
    assert rec.thickness_m == 0.2
    assert rec.gross_area_m2 == 24.0
    assert rec.net_area_m2 == 20.0
    assert rec.height_m == 3.0  # 24.0 gross / 8.0 length = 3.0m derived from net wall authority
    assert rec.wall_role == "external"

    # Evidence IDs gathered from all corroborated upstream records
    assert f"role-rec-{WALL_1}" in rec.corroborating_evidence_ids
    assert f"thick-rec-{WALL_1}" in rec.corroborating_evidence_ids
    assert f"net-wall-rec-{WALL_1}" in rec.corroborating_evidence_ids
    assert f"cross-rec-{WALL_1}" in rec.corroborating_evidence_ids

    # Querying published authority returns identical result
    auth = prod.authority()
    lookup = auth.resolve(sel)
    assert lookup.status is EvidenceResolutionStatus.CORROBORATED
    assert lookup.record == rec

    # Unknown selector returns ABSTAINED unavailable
    unknown_sel = _make_selector(wall_id="unknown-wall")
    unknown_lookup = auth.resolve(unknown_sel)
    assert unknown_lookup.status is EvidenceResolutionStatus.ABSTAINED
    assert GHAZI_RECOVERY_RECORD_UNAVAILABLE in unknown_lookup.reason_codes
