"""Production and adversarial tests for pb_wall_role_authority (Item 26).

Verifies the required authority chain:
  authenticated physical wall
  +
  authenticated room/envelope topology
  or
  authenticated explicit wall annotation
  or
  authenticated structural/cross-sheet evidence
  → exact wall-role proposition

Verifies all required attacks:
  1. caller says external → cannot mint EXTERNAL
  2. candidate says external → cannot mint EXTERNAL
  3. caller says internal → no authority
  4. candidate says gable → no authority
  5. candidate says party → no authority
  6. perimeter rank only → no authority
  7. thickness only → no role
  8. topology belongs to wrong wall → fail
  9. stale room/topology lineage → fail
  10. conflicting role evidence → CONFLICT
  11. ambiguous adjacency → ABSTAIN
  12. exact producer-owned topology positive case → may resolve
"""
from __future__ import annotations

import pytest

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    _AUTHORITY_SEAL as CANDIDATE_SEAL,
    _ScopeKey,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_role_authority import (
    StructuralCrossSheetAuthority,
    StructuralCrossSheetEvidence,
    StructuralCrossSheetProducer,
    WALL_ROLE_AMBIGUOUS,
    WALL_ROLE_CANDIDATE_LABEL_REJECTED,
    WALL_ROLE_CONFLICT,
    WALL_ROLE_CROSS_PAGE_UNREGISTERED,
    WALL_ROLE_LINEAGE_MISMATCH,
    WALL_ROLE_PERIMETER_ONLY_REJECTED,
    WALL_ROLE_RECORD_UNAVAILABLE,
    WALL_ROLE_RESOLVED,
    WALL_ROLE_STALE_EVIDENCE,
    WALL_ROLE_SOURCE_EVIDENCE_UNAVAILABLE,
    WALL_ROLE_THICKNESS_ONLY_REJECTED,
    WALL_ROLE_TOPOLOGY_WRONG_WALL,
    WALL_ROLE_UNRESOLVED,
    WALL_ROLE_WALL_UNRESOLVED,
    WallAnnotationAuthority,
    WallAnnotationEvidence,
    WallAnnotationProducer,
    WallRoleAuthority,
    WallRoleClassification,
    WallRoleProducer,
    WallRoleRecord,
    WallRoleResult,
    WallRoleSelector,
    WallTopologyAuthority,
    WallTopologyEvidence,
    WallTopologyProducer,
)

DOC = "doc-role-test"
REV = "R1"
SHA = "e" * 64
SNAP = "snap-role-1"
PAGE = "p1"
SCOPE = f"wall-source:page-{PAGE}"
WALL_1 = "phys-wall-1"
WALL_2 = "phys-wall-2"


def _selector(wall_id: str = WALL_1, page_id: str = PAGE) -> WallRoleSelector:
    return WallRoleSelector(
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
    interior_exterior: str = "unresolved",
    thickness_m: float = 0.2,
    metadata: dict | None = None,
) -> PhysicalWallCandidateRecord:
    cand = WallCandidate(
        candidate_id=wall_id,
        viewport_id=SCOPE,
        representation="single_line",
        centerline_pts=((0.0, 0.0), (10.0, 0.0)),
        face_a_segment_ids=("s1",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=thickness_m,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=10.0,
        end_node_ids=("n1", "n2"),
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior=interior_exterior,
        level_id=None,
        supporting_evidence_ids=("s1",),
        metadata=dict(metadata) if metadata else {},
    )
    ident = PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id=SCOPE,
        candidate_identity_id=f"ident-{wall_id}",
        path_fingerprint=((0.0, 0.0), (10.0, 0.0)),
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


# ── Seal & Constructor Enforcement ────────────────────────────────────────────


def test_authority_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        WallRoleAuthority({})


def test_producer_sealed() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    with pytest.raises(TypeError, match="from_authorities"):
        WallRoleProducer(cand_auth)


def test_record_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        WallRoleRecord(
            record_id="rec-1",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            physical_wall_id=WALL_1,
            role=WallRoleClassification.EXTERNAL,
            corroborating_evidence_ids=("s1",),
        )


def test_producer_rejects_invalid_authorities() -> None:
    with pytest.raises(TypeError, match="PhysicalWallCandidateAuthority"):
        WallRoleProducer.from_authorities(physical_wall_candidate_authority=object())  # type: ignore[arg-type]

    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    with pytest.raises(TypeError, match="WallTopologyAuthority"):
        WallRoleProducer.from_authorities(
            physical_wall_candidate_authority=cand_auth,
            wall_topology_authority=object(),  # type: ignore[arg-type]
        )


def test_selector_validation() -> None:
    with pytest.raises(ValueError, match="document_id must be non-empty"):
        WallRoleSelector(
            document_id="",
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            physical_wall_id=WALL_1,
        )


# ── Required Attack 1: Caller says external → cannot mint EXTERNAL ────────────


def test_attack_1_caller_says_external_cannot_mint() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    producer = WallRoleProducer.from_authorities(physical_wall_candidate_authority=cand_auth)
    sel = _selector(WALL_1)

    # Caller attempts to pass role kwargs to publish
    with pytest.raises(TypeError):
        producer.publish(sel, caller_label="external")  # type: ignore[call-arg]

    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_ROLE_UNRESOLVED in res.reason_codes
    assert res.record is None


# ── Required Attack 2: Candidate says external → cannot mint EXTERNAL ─────────


def test_attack_2_candidate_says_external_cannot_mint() -> None:
    # Physical wall candidate metadata says "exterior"
    rec = _make_candidate_record(WALL_1, interior_exterior="exterior")
    cand_auth = _candidate_authority(rec)
    producer = WallRoleProducer.from_authorities(physical_wall_candidate_authority=cand_auth)
    sel = _selector(WALL_1)

    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_ROLE_UNRESOLVED in res.reason_codes
    assert WALL_ROLE_CANDIDATE_LABEL_REJECTED in res.reason_codes
    assert res.record is None


# ── Required Attack 3: Caller says internal → no authority ───────────────────


def test_attack_3_caller_says_internal_no_authority() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    producer = WallRoleProducer.from_authorities(physical_wall_candidate_authority=cand_auth)
    sel = _selector(WALL_1)

    with pytest.raises(TypeError):
        producer.publish(sel, is_internal=True)  # type: ignore[call-arg]

    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert res.record is None


# ── Required Attack 4: Candidate says gable → no authority ────────────────────


def test_attack_4_candidate_says_gable_no_authority() -> None:
    rec = _make_candidate_record(WALL_1, interior_exterior="gable")
    cand_auth = _candidate_authority(rec)
    producer = WallRoleProducer.from_authorities(physical_wall_candidate_authority=cand_auth)
    sel = _selector(WALL_1)

    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_ROLE_UNRESOLVED in res.reason_codes
    assert WALL_ROLE_CANDIDATE_LABEL_REJECTED in res.reason_codes
    assert res.record is None


# ── Required Attack 5: Candidate says party → no authority ────────────────────


def test_attack_5_candidate_says_party_no_authority() -> None:
    rec = _make_candidate_record(WALL_1, interior_exterior="party")
    cand_auth = _candidate_authority(rec)
    producer = WallRoleProducer.from_authorities(physical_wall_candidate_authority=cand_auth)
    sel = _selector(WALL_1)

    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_ROLE_UNRESOLVED in res.reason_codes
    assert WALL_ROLE_CANDIDATE_LABEL_REJECTED in res.reason_codes
    assert res.record is None


# ── Required Attack 6: Perimeter rank only → no authority ─────────────────────


def test_attack_6_perimeter_rank_only_no_authority() -> None:
    rec = _make_candidate_record(
        WALL_1,
        interior_exterior="unresolved",
        metadata={"perimeter_rank": 1, "is_perimeter": True, "largest_perimeter": True},
    )
    cand_auth = _candidate_authority(rec)
    producer = WallRoleProducer.from_authorities(physical_wall_candidate_authority=cand_auth)
    sel = _selector(WALL_1)

    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_ROLE_UNRESOLVED in res.reason_codes
    assert WALL_ROLE_PERIMETER_ONLY_REJECTED in res.reason_codes
    assert res.record is None


# ── Required Attack 7: Thickness only → no role ───────────────────────────────


def test_attack_7_thickness_only_no_role() -> None:
    rec = _make_candidate_record(WALL_1, interior_exterior="unresolved", thickness_m=0.35)
    cand_auth = _candidate_authority(rec)
    producer = WallRoleProducer.from_authorities(physical_wall_candidate_authority=cand_auth)
    sel = _selector(WALL_1)

    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_ROLE_UNRESOLVED in res.reason_codes
    assert WALL_ROLE_THICKNESS_ONLY_REJECTED in res.reason_codes
    assert res.record is None


# ── Required Attack 8: Topology belongs to wrong wall → fail ──────────────────



def test_attack_8_topology_wrong_wall_fails() -> None:
    topo_prod = WallTopologyProducer.create()
    topo_ev = WallTopologyEvidence(
        evidence_id="topo-1", document_id=DOC, revision_id=REV,
        source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
        physical_wall_id=WALL_2, bounds_exterior=True, enclosed_space_count=1,
    )
    with pytest.raises(TypeError, match="source-derived evidence producer unavailable"):
        topo_prod.publish(topo_ev)


def test_attack_9_stale_topology_lineage_fails() -> None:
    topo_prod = WallTopologyProducer.create()
    stale = WallTopologyEvidence(
        evidence_id="topo-stale", document_id=DOC, revision_id="R_OLD",
        source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
        physical_wall_id=WALL_1, bounds_exterior=True, enclosed_space_count=1,
    )
    with pytest.raises(TypeError, match="source-derived evidence producer unavailable"):
        topo_prod.publish(stale)


def test_attack_10_conflicting_role_evidence() -> None:
    topo_prod = WallTopologyProducer.create()
    with pytest.raises(TypeError):
        topo_prod.publish(WallTopologyEvidence(
            evidence_id="topo-ext", document_id=DOC, revision_id=REV,
            source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
            physical_wall_id=WALL_1, bounds_exterior=True, enclosed_space_count=1,
        ))
    annot_prod = WallAnnotationProducer.create()
    with pytest.raises(TypeError):
        annot_prod.publish(WallAnnotationEvidence(
            evidence_id="annot-int", document_id=DOC, revision_id=REV,
            source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
            physical_wall_id=WALL_1, role=WallRoleClassification.INTERNAL,
            annotation_text="INTERNAL PARTITION",
        ))


def test_attack_11_ambiguous_adjacency_abstains() -> None:
    topo_prod = WallTopologyProducer.create()
    with pytest.raises(TypeError):
        topo_prod.publish(WallTopologyEvidence(
            evidence_id="topo-ambig", document_id=DOC, revision_id=REV,
            source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
            physical_wall_id=WALL_1, bounds_exterior=False, enclosed_space_count=3,
            is_ambiguous=True, ambiguity_reason="ambiguous_three_way_adjacency",
        ))


def test_attack_12_exact_producer_owned_positive_external() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    producer = WallRoleProducer.from_authorities(physical_wall_candidate_authority=cand_auth)
    res = producer.publish(_selector(WALL_1))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_ROLE_SOURCE_EVIDENCE_UNAVAILABLE in res.reason_codes
    assert res.record is None


def test_positive_internal_partition() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    producer = WallRoleProducer.from_authorities(physical_wall_candidate_authority=cand_auth)
    res = producer.publish(_selector(WALL_1))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_ROLE_SOURCE_EVIDENCE_UNAVAILABLE in res.reason_codes
    assert res.record is None


def test_positive_gable_wall_corroboration() -> None:
    struct_prod = StructuralCrossSheetProducer.create()
    ev = StructuralCrossSheetEvidence(
        evidence_id="struct-gable-1", document_id=DOC, revision_id=REV,
        source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
        physical_wall_id=WALL_1, role=WallRoleClassification.GABLE,
        source_sheet_id="sheet-roof-truss-01", is_registered=True,
    )
    with pytest.raises(TypeError, match="source-derived evidence producer unavailable"):
        struct_prod.publish(ev)


def test_positive_party_wall_corroboration() -> None:
    annot_prod = WallAnnotationProducer.create()
    ev = WallAnnotationEvidence(
        evidence_id="annot-party-1", document_id=DOC, revision_id=REV,
        source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
        physical_wall_id=WALL_1, role=WallRoleClassification.PARTY,
        annotation_text="PARTY WALL 200MM RC",
    )
    with pytest.raises(TypeError, match="source-derived evidence producer unavailable"):
        annot_prod.publish(ev)


def test_unregistered_cross_sheet_fails() -> None:
    struct_prod = StructuralCrossSheetProducer.create()
    ev = StructuralCrossSheetEvidence(
        evidence_id="struct-unregistered", document_id=DOC, revision_id=REV,
        source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
        physical_wall_id=WALL_1, role=WallRoleClassification.GABLE,
        source_sheet_id="sheet-unregistered-02", is_registered=False,
    )
    with pytest.raises(TypeError, match="source-derived evidence producer unavailable"):
        struct_prod.publish(ev)

def test_uncorroborated_physical_wall_authority_abstains() -> None:
    cand_auth = _candidate_authority(
        _make_candidate_record(WALL_1),
        status=EvidenceResolutionStatus.ABSTAINED,
    )
    producer = WallRoleProducer.from_authorities(physical_wall_candidate_authority=cand_auth)
    res = producer.publish(_selector(WALL_1))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_ROLE_WALL_UNRESOLVED in res.reason_codes
    assert res.record is None


def test_unknown_physical_wall_id_abstains() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    producer = WallRoleProducer.from_authorities(physical_wall_candidate_authority=cand_auth)
    res = producer.publish(_selector("nonexistent-wall-id"))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_ROLE_WALL_UNRESOLVED in res.reason_codes
    assert res.record is None


def test_unresolved_lookup_returns_unavailable() -> None:
    cand_auth = _candidate_authority(_make_candidate_record(WALL_1))
    producer = WallRoleProducer.from_authorities(physical_wall_candidate_authority=cand_auth)
    auth = producer.authority()
    res = auth.resolve(_selector(WALL_1))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_ROLE_RECORD_UNAVAILABLE in res.reason_codes


def test_raster_candidate_geometry_cannot_mint_wall_role() -> None:
    # A candidate wall from raster linework or candidate geometry without topology
    cand = _make_candidate_record(
        "raster-wall-cand-1",
        interior_exterior="exterior",
        metadata={"source_kind": "raster_observation", "pixel_segment_count": 4},
    )
    cand_auth = _candidate_authority(cand)
    producer = WallRoleProducer.from_authorities(physical_wall_candidate_authority=cand_auth)
    res = producer.publish(_selector("raster-wall-cand-1"))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_ROLE_UNRESOLVED in res.reason_codes
    assert res.record is None
