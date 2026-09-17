"""TEST-ONLY / EXPECTED-RED validator for Item 32 cross-sheet registration.

Production under test: PR #485 head d525970c0c49c610f7bc83d9587932e069aa9a90.

The previous caller-constructible CrossSheetRegistrationProof seam was removed at
this head.  These tests freeze that closure and attack the replacement boundary:
coexistence of the same caller-selected wall_candidate_id in two independent page
scopes is not, by itself, cross-sheet correspondence evidence.

DO NOT weaken these tests to make production green.  The expected-red cases should
become green only when Item 32 consumes/re-resolves producer-owned correspondence
proof (geometric registration, authenticated section/elevation callout, control
points/transform, or another equally strong source-backed relation).
"""
from __future__ import annotations

import inspect

import pytest

import pb_cross_sheet_registration_authority as item32
from pb_cross_sheet_registration_authority import (
    CrossSheetRegistrationProducer,
    CrossSheetRegistrationSelector,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    _AUTHORITY_SEAL as CANDIDATE_AUTHORITY_SEAL,
    _ScopeKey,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_wall_room_topology_contracts import MeasurementAuthorityType, WallCandidate


DOC = "doc-item32-redteam"
REV = "R1"
SHA = "3" * 64
SNAP = "snap-item32-redteam"
SRC_PAGE = "A101"
TGT_PAGE = "A201"
SCOPE_PREFIX = "wall-source:page-"


def _candidate(candidate_id: str, *, viewport_id: str, y: float) -> WallCandidate:
    return WallCandidate(
        candidate_id=candidate_id,
        viewport_id=viewport_id,
        representation="double_line",
        centerline_pts=((0.0, y), (100.0, y)),
        face_a_segment_ids=(f"{viewport_id}-face-a",),
        face_b_segment_ids=(f"{viewport_id}-face-b",),
        is_curved=False,
        curve_control_pts=None,
        thickness_m=0.11,
        thickness_authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION,
        length_m=10.0,
        end_node_ids=(f"{viewport_id}-n1", f"{viewport_id}-n2"),
        junction_types=("free_end", "free_end"),
        interior_exterior="unresolved",
        level_id="L1",
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
    )


def _record(
    candidate_id: str,
    *,
    viewport_id: str,
    y: float,
    identity_suffix: str,
) -> PhysicalWallCandidateRecord:
    return PhysicalWallCandidateRecord(
        wall_candidate_id=candidate_id,
        wall_candidate=_candidate(candidate_id, viewport_id=viewport_id, y=y),
        physical_identity=PhysicalWallIdentity(
            wall_candidate_id=candidate_id,
            viewport_id=viewport_id,
            candidate_identity_id=f"identity-{identity_suffix}",
            path_fingerprint=f"path-{identity_suffix}",
            source_primitive_ids=(f"primitive-{identity_suffix}",),
            edge_ids=(f"edge-{identity_suffix}",),
            status=EvidenceResolutionStatus.CORROBORATED,
        ),
    )


def _scope(page_id: str, records: tuple[PhysicalWallCandidateRecord, ...]):
    key = _ScopeKey(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=page_id,
        decision_scope_id=f"{SCOPE_PREFIX}{page_id}",
    )
    result = PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=records,
        source_observation_ids=(),
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=page_id,
        decision_scope_id=f"{SCOPE_PREFIX}{page_id}",
        reason_codes=(),
    )
    return key, result


def _producer(
    *,
    source_records: tuple[PhysicalWallCandidateRecord, ...],
    target_records: tuple[PhysicalWallCandidateRecord, ...],
) -> CrossSheetRegistrationProducer:
    src_key, src_result = _scope(SRC_PAGE, source_records)
    tgt_key, tgt_result = _scope(TGT_PAGE, target_records)
    candidate_authority = PhysicalWallCandidateAuthority(
        {src_key: src_result, tgt_key: tgt_result},
        _seal=CANDIDATE_AUTHORITY_SEAL,
    )
    return CrossSheetRegistrationProducer.from_authorities(
        physical_wall_candidate_authority=candidate_authority
    )


def _selector(element_id: str) -> CrossSheetRegistrationSelector:
    return CrossSheetRegistrationSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        source_page_id=SRC_PAGE,
        target_page_id=TGT_PAGE,
        physical_element_id=element_id,
    )


def _assert_not_registered(result) -> None:
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.record is None


# ---------------------------------------------------------------------------
# GREEN regression locks for the defect already removed at d525970c...
# ---------------------------------------------------------------------------


def test_public_caller_constructible_proof_type_is_removed() -> None:
    assert not hasattr(item32, "CrossSheetRegistrationProof")


def test_publish_boundary_is_selector_only() -> None:
    params = list(inspect.signature(CrossSheetRegistrationProducer.publish).parameters)
    assert params == ["self", "selector"]


def test_caller_cannot_pass_a_second_proofs_argument() -> None:
    wall_id = "wall-1"
    producer = _producer(
        source_records=(_record(wall_id, viewport_id="vp-src", y=0.0, identity_suffix="src"),),
        target_records=(_record(wall_id, viewport_id="vp-tgt", y=500.0, identity_suffix="tgt"),),
    )
    with pytest.raises(TypeError):
        producer.publish(_selector(wall_id), [])  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# EXPECTED RED: same-id coexistence is not cross-sheet correspondence proof.
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="same wall_candidate_id on unrelated pages currently mints registration",
)
def test_same_id_on_unrelated_page_geometry_cannot_mint_registration() -> None:
    wall_id = "wall-collision"
    producer = _producer(
        source_records=(_record(wall_id, viewport_id="plan-vp", y=0.0, identity_suffix="plan"),),
        target_records=(_record(wall_id, viewport_id="elev-vp", y=900.0, identity_suffix="elev"),),
    )
    _assert_not_registered(producer.publish(_selector(wall_id)))


@pytest.mark.xfail(
    strict=True,
    reason="same mark-like id is treated as physical correspondence without source-backed registration proof",
)
def test_same_mark_like_identifier_across_sheets_is_not_registration() -> None:
    mark = "W-01"
    producer = _producer(
        source_records=(_record(mark, viewport_id="plan-vp", y=0.0, identity_suffix="mark-plan"),),
        target_records=(_record(mark, viewport_id="section-vp", y=300.0, identity_suffix="mark-section"),),
    )
    _assert_not_registered(producer.publish(_selector(mark)))


@pytest.mark.xfail(
    strict=True,
    reason="different physical identities/path fingerprints with same id are currently collapsed",
)
def test_same_id_with_conflicting_physical_identity_must_fail_closed() -> None:
    wall_id = "wall-same-label-different-identity"
    producer = _producer(
        source_records=(_record(wall_id, viewport_id="src-vp", y=0.0, identity_suffix="physical-A"),),
        target_records=(_record(wall_id, viewport_id="tgt-vp", y=100.0, identity_suffix="physical-B"),),
    )
    _assert_not_registered(producer.publish(_selector(wall_id)))


@pytest.mark.xfail(
    strict=True,
    reason="no cross-sheet correspondence observations are required before CORROBORATED",
)
def test_empty_correspondence_evidence_universe_cannot_mint_registration() -> None:
    wall_id = "wall-no-registration-evidence"
    # Both page scopes deliberately have source_observation_ids=().  Item 32 must
    # not convert mere per-page existence into cross-sheet correspondence.
    producer = _producer(
        source_records=(_record(wall_id, viewport_id="src-vp", y=0.0, identity_suffix="noev-src"),),
        target_records=(_record(wall_id, viewport_id="tgt-vp", y=1000.0, identity_suffix="noev-tgt"),),
    )
    _assert_not_registered(producer.publish(_selector(wall_id)))


@pytest.mark.xfail(
    strict=True,
    reason="ambiguous duplicate target candidates sharing the id are not rejected",
)
def test_ambiguous_duplicate_target_candidates_fail_closed() -> None:
    wall_id = "wall-ambiguous-target"
    producer = _producer(
        source_records=(_record(wall_id, viewport_id="src-vp", y=0.0, identity_suffix="amb-src"),),
        target_records=(
            _record(wall_id, viewport_id="tgt-vp-1", y=100.0, identity_suffix="amb-tgt-1"),
            _record(wall_id, viewport_id="tgt-vp-2", y=800.0, identity_suffix="amb-tgt-2"),
        ),
    )
    _assert_not_registered(producer.publish(_selector(wall_id)))
