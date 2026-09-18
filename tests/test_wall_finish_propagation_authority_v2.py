"""Production + adversarial tests for pb_wall_finish_propagation_authority (Item 19A V2).

Item 19A has no positive publication path: caller-supplied
WallFinishAssignment (material, trade, face, both_faces) is diagnostic
information only. Every test here proves either a prerequisite-failure
abstain/conflict, or -- when wall and net-wall geometry are both genuinely
verified -- the deliberate WALL_FINISH_BINDING_UNAVAILABLE abstain that
this item stops at pending a future, separately-reviewed Item 19B.
"""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_net_wall_boolean_union_authority import (
    NET_WALL_BOOLEAN_UNION_RESOLVED,
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionRecord,
    NetWallBooleanUnionResult,
    NetWallBooleanUnionSelector,
    _AUTHORITY_SEAL as NET_AUTH_SEAL,
)
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    _AUTHORITY_SEAL as WALL_AUTH_SEAL,
    _ScopeKey,
    _decision_scope_id,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_wall_finish_propagation_authority import (
    WALL_FINISH_ASSIGNMENT_CONFLICT,
    WALL_FINISH_ASSIGNMENT_UNAVAILABLE,
    WALL_FINISH_BINDING_UNAVAILABLE,
    WALL_FINISH_LINEAGE_MISMATCH,
    WALL_FINISH_NET_GEOMETRY_UNRESOLVED,
    WALL_FINISH_PHYSICAL_WALL_UNRESOLVED,
    WallFinishAssignment,
    WallFinishPropagationAuthority,
    WallFinishPropagationProducer,
    WallFinishPropagationSelector,
)

DOC = "doc-1"
REV = "rev-1"
SHA = "a" * 64
SNAP = "snap-1"
PAGE = "page_1"
SCOPE = _decision_scope_id(PAGE)


def _wall_auth(wall_id: str, *, page_id: str = PAGE) -> PhysicalWallCandidateAuthority:
    identity = PhysicalWallIdentity(
        wall_candidate_id=wall_id, viewport_id="view-1", candidate_identity_id=wall_id,
        path_fingerprint=((0.0, 0.0), (100.0, 0.0)), source_primitive_ids=("prim-1",),
        edge_ids=("edge-1",), status=EvidenceResolutionStatus.CORROBORATED,
    )
    record = PhysicalWallCandidateRecord(wall_candidate_id=wall_id, wall_candidate=None, physical_identity=identity)
    scope = PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED, scope_complete=True, records=(record,),
        source_observation_ids=("obs-1",), document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=page_id, decision_scope_id=_decision_scope_id(page_id),
        reason_codes=(PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,),
    )
    key = _ScopeKey(
        document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
        page_id=page_id, decision_scope_id=_decision_scope_id(page_id),
    )
    return PhysicalWallCandidateAuthority({key: scope}, _seal=WALL_AUTH_SEAL)


def _empty_wall_auth() -> PhysicalWallCandidateAuthority:
    return PhysicalWallCandidateAuthority({}, _seal=WALL_AUTH_SEAL)


def _net_auth(
    wall_id: str, trade_scope_id: str, *, net_area_m2: float = 10.0, page_id: str = PAGE, lineage_ok: bool = True
) -> NetWallBooleanUnionAuthority:
    selector = NetWallBooleanUnionSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
        page_id=page_id, decision_scope_id=_decision_scope_id(page_id),
        physical_wall_id=wall_id, trade_scope_id=trade_scope_id,
    )
    record = NetWallBooleanUnionRecord(
        record_id=f"net-{wall_id}-{trade_scope_id}",
        document_id=selector.document_id if lineage_ok else "wrong-doc",
        revision_id=selector.revision_id, source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id, page_id=selector.page_id, decision_scope_id=selector.decision_scope_id,
        physical_wall_id=wall_id, gross_geometry_record_id=f"gross-{wall_id}",
        opening_universe_record_id=f"universe-{wall_id}", deduction_record_ids=(),
        union_geometry_id=f"geom-{wall_id}", net_area_m2=net_area_m2, gross_area_m2=net_area_m2,
        void_union_area_m2=0.0, trade_scope_id=trade_scope_id,
    )
    result = NetWallBooleanUnionResult(
        status=EvidenceResolutionStatus.CORROBORATED, reason_codes=(NET_WALL_BOOLEAN_UNION_RESOLVED,), record=record,
    )
    return NetWallBooleanUnionAuthority({selector.key: result}, _seal=NET_AUTH_SEAL)


def _empty_net_auth() -> NetWallBooleanUnionAuthority:
    return NetWallBooleanUnionAuthority({}, _seal=NET_AUTH_SEAL)


def _selector(wall_id: str, trade_scope_id: str, *, page_id: str = PAGE) -> WallFinishPropagationSelector:
    return WallFinishPropagationSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
        page_id=page_id, decision_scope_id=_decision_scope_id(page_id),
        physical_wall_id=wall_id, trade_scope_id=trade_scope_id,
    )


# ── Constructor Seals & Type Checks ────────────────────────────────────────────

def test_authority_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        WallFinishPropagationAuthority({})


def test_producer_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="from_authorities"):
        WallFinishPropagationProducer(_wall_auth("w1"), _net_auth("w1", "t1"), [])  # type: ignore[call-arg]


def test_producer_rejects_non_wall_authority_type() -> None:
    with pytest.raises(TypeError, match="PhysicalWallCandidateAuthority"):
        WallFinishPropagationProducer.from_authorities(object(), _net_auth("w1", "t1"), [])  # type: ignore[arg-type]


def test_producer_rejects_non_net_authority_type() -> None:
    with pytest.raises(TypeError, match="NetWallBooleanUnionAuthority"):
        WallFinishPropagationProducer.from_authorities(_wall_auth("w1"), object(), [])  # type: ignore[arg-type]


def test_producer_rejects_non_assignment_instances() -> None:
    with pytest.raises(TypeError, match="WallFinishAssignment"):
        WallFinishPropagationProducer.from_authorities(_wall_auth("w1"), _net_auth("w1", "t1"), [{"not": "an assignment"}])  # type: ignore[list-item]


@pytest.mark.parametrize("face", ["top_face", "", "BOTH_FACES", "left"])
def test_assignment_rejects_invalid_face_target(face) -> None:
    with pytest.raises(ValueError):
        WallFinishAssignment("a1", "w1", "t1", face)


# ── Core: verified geometry still never mints authority ────────────────────────

@pytest.mark.parametrize("face", ["left_face", "right_face", "both_faces"])
def test_verified_geometry_still_abstains_binding_unavailable(face) -> None:
    wall_id, trade = "w1", "internal_plaster"
    producer = WallFinishPropagationProducer.from_authorities(
        _wall_auth(wall_id), _net_auth(wall_id, trade),
        [WallFinishAssignment("a1", wall_id, trade, face)],
    )
    res = producer.publish(_selector(wall_id, trade))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert res.record is None
    assert WALL_FINISH_BINDING_UNAVAILABLE in res.reason_codes


def test_no_matching_assignment_abstains() -> None:
    producer = WallFinishPropagationProducer.from_authorities(_wall_auth("w1"), _net_auth("w1", "t1"), [])
    res = producer.publish(_selector("w1", "t1"))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_FINISH_ASSIGNMENT_UNAVAILABLE in res.reason_codes


def test_duplicate_assignments_for_same_wall_and_trade_conflict() -> None:
    wall_id, trade = "w1", "t1"
    producer = WallFinishPropagationProducer.from_authorities(
        _wall_auth(wall_id), _net_auth(wall_id, trade),
        [
            WallFinishAssignment("a1", wall_id, trade, "left_face"),
            WallFinishAssignment("a2", wall_id, trade, "right_face"),
        ],
    )
    res = producer.publish(_selector(wall_id, trade))
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert WALL_FINISH_ASSIGNMENT_CONFLICT in res.reason_codes


def test_unresolved_physical_wall_abstains() -> None:
    wall_id, trade = "w1", "t1"
    producer = WallFinishPropagationProducer.from_authorities(
        _empty_wall_auth(), _net_auth(wall_id, trade),
        [WallFinishAssignment("a1", wall_id, trade, "left_face")],
    )
    res = producer.publish(_selector(wall_id, trade))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_FINISH_PHYSICAL_WALL_UNRESOLVED in res.reason_codes


def test_unresolved_net_wall_geometry_abstains() -> None:
    wall_id, trade = "w1", "t1"
    producer = WallFinishPropagationProducer.from_authorities(
        _wall_auth(wall_id), _empty_net_auth(),
        [WallFinishAssignment("a1", wall_id, trade, "left_face")],
    )
    res = producer.publish(_selector(wall_id, trade))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_FINISH_NET_GEOMETRY_UNRESOLVED in res.reason_codes


def test_wall_scope_lineage_mismatch_conflicts() -> None:
    wall_id, trade = "w1", "t1"
    # Wall authority scope is keyed to a different page than the selector.
    producer = WallFinishPropagationProducer.from_authorities(
        _wall_auth(wall_id, page_id="page_2"), _net_auth(wall_id, trade),
        [WallFinishAssignment("a1", wall_id, trade, "left_face")],
    )
    res = producer.publish(_selector(wall_id, trade))
    assert res.status in (EvidenceResolutionStatus.ABSTAINED, EvidenceResolutionStatus.CONFLICT)
    assert res.record is None


def test_net_record_lineage_mismatch_conflicts() -> None:
    wall_id, trade = "w1", "t1"
    producer = WallFinishPropagationProducer.from_authorities(
        _wall_auth(wall_id), _net_auth(wall_id, trade, lineage_ok=False),
        [WallFinishAssignment("a1", wall_id, trade, "left_face")],
    )
    res = producer.publish(_selector(wall_id, trade))
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert WALL_FINISH_LINEAGE_MISMATCH in res.reason_codes


# ── Scope summary never publishes numeric authority ────────────────────────────

def test_scope_summary_always_incomplete_with_no_total() -> None:
    wall_id, trade = "w1", "internal_plaster"
    producer = WallFinishPropagationProducer.from_authorities(
        _wall_auth(wall_id), _net_auth(wall_id, trade, net_area_m2=12.0),
        [WallFinishAssignment("a1", wall_id, trade, "both_faces")],
    )
    summary = producer.publish_scope_summary(
        document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
        page_id=PAGE, decision_scope_id=SCOPE, trade_scope_id=trade,
    )
    assert summary.is_scope_complete is False
    assert summary.total_trade_area_m2 is None
    assert summary.contributing_wall_records == ()
    assert summary.unresolved_wall_ids == (wall_id,)


def test_scope_summary_with_zero_assignments_is_also_incomplete() -> None:
    producer = WallFinishPropagationProducer.from_authorities(_wall_auth("w1"), _net_auth("w1", "t1"), [])
    summary = producer.publish_scope_summary(
        document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
        page_id=PAGE, decision_scope_id=SCOPE, trade_scope_id="t1",
    )
    assert summary.is_scope_complete is False
    assert summary.total_trade_area_m2 is None


# ── Authority Lookup ──────────────────────────────────────────────────────────

def test_authority_lookup_published_result_matches() -> None:
    wall_id, trade = "w1", "t1"
    producer = WallFinishPropagationProducer.from_authorities(
        _wall_auth(wall_id), _net_auth(wall_id, trade), [WallFinishAssignment("a1", wall_id, trade, "left_face")],
    )
    sel = _selector(wall_id, trade)
    producer.publish(sel)
    res = producer.authority().resolve(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert res.record is None


def test_authority_lookup_missing_abstains() -> None:
    producer = WallFinishPropagationProducer.from_authorities(_wall_auth("w1"), _net_auth("w1", "t1"), [])
    res = producer.authority().resolve(_selector("w1", "t1"))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_FINISH_ASSIGNMENT_UNAVAILABLE in res.reason_codes


def test_authority_lookup_wrong_selector_type_raises() -> None:
    producer = WallFinishPropagationProducer.from_authorities(_wall_auth("w1"), _net_auth("w1", "t1"), [])
    with pytest.raises(TypeError, match="WallFinishPropagationSelector"):
        producer.authority().resolve("not-a-selector")  # type: ignore[arg-type]


def test_publish_wrong_selector_type_raises() -> None:
    producer = WallFinishPropagationProducer.from_authorities(_wall_auth("w1"), _net_auth("w1", "t1"), [])
    with pytest.raises(TypeError, match="WallFinishPropagationSelector"):
        producer.publish("not-a-selector")  # type: ignore[arg-type]


def test_selector_empty_field_raises() -> None:
    with pytest.raises(ValueError):
        WallFinishPropagationSelector(
            document_id="", revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
            page_id=PAGE, decision_scope_id=SCOPE, physical_wall_id="w1", trade_scope_id="t1",
        )
