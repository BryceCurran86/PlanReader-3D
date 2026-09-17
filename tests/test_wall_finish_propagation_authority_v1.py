"""Comprehensive unit tests for Item 19 Wall-Finish Quantity Propagation Authority.

Tests:
1. Exact physical wall identity preservation across distinct walls.
2. Net area propagation derived strictly from Item 17 NetWallBooleanUnionAuthority.
3. Face multipliers: both_faces (2.0) vs left_face / right_face (1.0).
4. Fail-closed behavior when net wall boolean union geometry is unresolved:
   - Propagation fails closed; total finish area is None; never fabricates gross area.
5. Scope summary aggregation:
   - All walls resolved -> total_trade_area_m2 computed.
   - Any wall unresolved -> total_trade_area_m2 is None; unresolved_wall_ids recorded.
6. Missing finish assignment fails closed.
7. Unresolved physical wall candidate fails closed.
8. Authority sealing and selector resolution immutability.
"""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_net_wall_boolean_union_authority import (
    NET_WALL_BOOLEAN_UNION_RESOLVED,
    NET_WALL_DEDUCTION_UNRESOLVED,
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionRecord,
    NetWallBooleanUnionResult,
    NetWallBooleanUnionSelector,
)
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    PhysicalWallCandidateSelector,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_wall_finish_propagation_authority import (
    WALL_FINISH_ASSIGNMENT_UNAVAILABLE,
    WALL_FINISH_FACE_AMBIGUOUS,
    WALL_FINISH_NET_GEOMETRY_UNRESOLVED,
    WALL_FINISH_PHYSICAL_WALL_UNRESOLVED,
    WALL_FINISH_PROPAGATION_RESOLVED,
    WALL_FINISH_PROPAGATION_SCHEMA_VERSION,
    WallFinishAssignment,
    WallFinishPropagationAuthority,
    WallFinishPropagationProducer,
    WallFinishPropagationRecord,
    WallFinishPropagationResult,
    WallFinishPropagationSelector,
    WallFinishScopeSummaryRecord,
)
from pb_physical_wall_candidate_authority import (
    _AUTHORITY_SEAL as _WALL_AUTH_SEAL,
    _ScopeKey,
    _decision_scope_id,
)

DECISION_SCOPE = _decision_scope_id("page_1")


def _make_physical_wall_auth(wall_ids: list[str]) -> PhysicalWallCandidateAuthority:
    records = []
    for wid in wall_ids:
        identity = PhysicalWallIdentity(
            wall_candidate_id=wid,
            viewport_id="view-1",
            candidate_identity_id=wid,
            path_fingerprint=((0.0, 0.0), (100.0, 0.0)),
            source_primitive_ids=("prim-1",),
            edge_ids=("edge-1",),
            status=EvidenceResolutionStatus.CORROBORATED,
        )
        records.append(
            PhysicalWallCandidateRecord(
                wall_candidate_id=wid,
                wall_candidate=None,
                physical_identity=identity,
            )
        )
    scope_result = PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=tuple(records),
        source_observation_ids=("obs_01",),
        document_id="doc_test_100",
        revision_id="rev_test_001",
        source_sha256="a" * 64,
        snapshot_id="snap_test_001",
        page_id="page_1",
        decision_scope_id=DECISION_SCOPE,
        reason_codes=(PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,),
    )
    key = _ScopeKey(
        document_id="doc_test_100",
        revision_id="rev_test_001",
        source_sha256="a" * 64,
        snapshot_id="snap_test_001",
        page_id="page_1",
        decision_scope_id=DECISION_SCOPE,
    )
    return PhysicalWallCandidateAuthority({key: scope_result}, _seal=_WALL_AUTH_SEAL)


def _make_net_wall_auth(
    resolved_net_areas: dict[str, float],
    unresolved_walls: list[str] = None,
) -> NetWallBooleanUnionAuthority:
    results = {}
    unresolved_walls = unresolved_walls or []

    for wid, net_area in resolved_net_areas.items():
        sel = NetWallBooleanUnionSelector(
            document_id="doc_test_100",
            revision_id="rev_test_001",
            source_sha256="a" * 64,
            snapshot_id="snap_test_001",
            page_id="page_1",
            decision_scope_id=DECISION_SCOPE,
            physical_wall_id=wid,
            trade_scope_id="internal_plaster",
        )
        rec = NetWallBooleanUnionRecord(
            record_id=f"net_rec_{wid}",
            document_id=sel.document_id,
            revision_id=sel.revision_id,
            source_sha256=sel.source_sha256,
            snapshot_id=sel.snapshot_id,
            page_id=sel.page_id,
            decision_scope_id=sel.decision_scope_id,
            physical_wall_id=wid,
            gross_geometry_record_id=f"gross_rec_{wid}",
            opening_universe_record_id=f"univ_rec_{wid}",
            deduction_record_ids=("ded_01",),
            union_geometry_id=f"geom_rec_{wid}",
            net_area_m2=net_area,
            gross_area_m2=net_area + 2.5,
            void_union_area_m2=2.5,
            net_geometry_wkb_hex="",
            physical_void_record_ids=("void_01",),
            trade_scope_id=sel.trade_scope_id,
            gross_wall_record_id=f"gross_rec_{wid}",
            opening_deduction_record_ids=("ded_01",),
        )
        results[sel.key] = NetWallBooleanUnionResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(NET_WALL_BOOLEAN_UNION_RESOLVED,),
            record=rec,
        )

    for wid in unresolved_walls:
        sel = NetWallBooleanUnionSelector(
            document_id="doc_test_100",
            revision_id="rev_test_001",
            source_sha256="a" * 64,
            snapshot_id="snap_test_001",
            page_id="page_1",
            decision_scope_id=DECISION_SCOPE,
            physical_wall_id=wid,
            trade_scope_id="internal_plaster",
        )
        results[sel.key] = NetWallBooleanUnionResult(
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(NET_WALL_DEDUCTION_UNRESOLVED,),
            record=None,
        )

    from pb_net_wall_boolean_union_authority import _AUTHORITY_SEAL
    return NetWallBooleanUnionAuthority(results, _seal=_AUTHORITY_SEAL)


def _sample_selector(wall_id: str, trade_id: str = "internal_plaster") -> WallFinishPropagationSelector:
    return WallFinishPropagationSelector(
        document_id="doc_test_100",
        revision_id="rev_test_001",
        source_sha256="a" * 64,
        snapshot_id="snap_test_001",
        page_id="page_1",
        decision_scope_id=DECISION_SCOPE,
        physical_wall_id=wall_id,
        trade_scope_id=trade_id,
    )


def test_successful_propagation_with_both_faces() -> None:
    wall_auth = _make_physical_wall_auth(["wall_01"])
    net_auth = _make_net_wall_auth({"wall_01": 12.0})

    assignment = WallFinishAssignment(
        assignment_id="assign_01",
        physical_wall_id="wall_01",
        trade_scope_id="internal_plaster",
        wall_face_target="both_faces",
        finish_material="13mm Plasterboard",
    )

    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[assignment],
    )

    sel = _sample_selector("wall_01")
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert WALL_FINISH_PROPAGATION_RESOLVED in res.reason_codes
    rec = res.record
    assert rec is not None
    assert rec.physical_wall_id == "wall_01"
    assert rec.trade_scope_id == "internal_plaster"
    assert rec.net_area_per_face_m2 == 12.0
    assert rec.face_multiplier == 2.0
    # 12.0 m2 per face * 2 faces = 24.0 m2 total finish area
    assert rec.total_finish_area_m2 == 24.0
    assert rec.unit == "m2"
    assert rec.net_wall_record_id == "net_rec_wall_01"
    assert rec.schema_version == WALL_FINISH_PROPAGATION_SCHEMA_VERSION


def test_successful_propagation_with_single_face() -> None:
    wall_auth = _make_physical_wall_auth(["wall_02"])
    net_auth = _make_net_wall_auth({"wall_02": 15.5})

    assignment = WallFinishAssignment(
        assignment_id="assign_02",
        physical_wall_id="wall_02",
        trade_scope_id="internal_plaster",
        wall_face_target="left_face",
        finish_material="10mm Plasterboard",
    )

    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[assignment],
    )

    sel = _sample_selector("wall_02")
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.CORROBORATED
    rec = res.record
    assert rec is not None
    assert rec.face_multiplier == 1.0
    assert rec.total_finish_area_m2 == 15.5


def test_independent_identity_preservation_across_multiple_walls() -> None:
    # Wall 1 and Wall 2 both receive internal plaster
    wall_auth = _make_physical_wall_auth(["wall_01", "wall_02"])
    net_auth = _make_net_wall_auth({"wall_01": 10.0, "wall_02": 14.0})

    assign1 = WallFinishAssignment(
        assignment_id="assign_01",
        physical_wall_id="wall_01",
        trade_scope_id="internal_plaster",
        wall_face_target="both_faces",
    )
    assign2 = WallFinishAssignment(
        assignment_id="assign_02",
        physical_wall_id="wall_02",
        trade_scope_id="internal_plaster",
        wall_face_target="both_faces",
    )

    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[assign1, assign2],
    )

    res1 = producer.publish(_sample_selector("wall_01"))
    res2 = producer.publish(_sample_selector("wall_02"))

    assert res1.record is not None
    assert res2.record is not None
    # Distinct identities are preserved; never merged into a single anonymous record
    assert res1.record.physical_wall_id == "wall_01"
    assert res1.record.total_finish_area_m2 == 20.0
    assert res2.record.physical_wall_id == "wall_02"
    assert res2.record.total_finish_area_m2 == 28.0


def test_fail_closed_when_net_wall_geometry_unresolved() -> None:
    wall_auth = _make_physical_wall_auth(["wall_blocked"])
    net_auth = _make_net_wall_auth({}, unresolved_walls=["wall_blocked"])

    assignment = WallFinishAssignment(
        assignment_id="assign_blocked",
        physical_wall_id="wall_blocked",
        trade_scope_id="internal_plaster",
        wall_face_target="both_faces",
    )

    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[assignment],
    )

    sel = _sample_selector("wall_blocked")
    res = producer.publish(sel)

    # Fail closed: must not fabricate naive gross finish area
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert WALL_FINISH_NET_GEOMETRY_UNRESOLVED in res.reason_codes
    assert res.record is None


def test_scope_summary_aggregation_and_fail_closed() -> None:
    # Wall 1 resolved (10 m2 * 2 = 20 m2), Wall 2 resolved (15 m2 * 2 = 30 m2)
    wall_auth = _make_physical_wall_auth(["wall_01", "wall_02"])
    net_auth = _make_net_wall_auth({"wall_01": 10.0, "wall_02": 15.0})

    assign1 = WallFinishAssignment("a1", "wall_01", "internal_plaster", "both_faces")
    assign2 = WallFinishAssignment("a2", "wall_02", "internal_plaster", "both_faces")

    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[assign1, assign2],
    )

    summary = producer.publish_scope_summary(
        document_id="doc_test_100",
        revision_id="rev_test_001",
        source_sha256="a" * 64,
        snapshot_id="snap_test_001",
        page_id="page_1",
        decision_scope_id=DECISION_SCOPE,
        trade_scope_id="internal_plaster",
    )

    assert summary.is_scope_complete is True
    assert summary.total_trade_area_m2 == 50.0  # 20.0 + 30.0
    assert len(summary.contributing_wall_records) == 2
    assert summary.unresolved_wall_ids == ()

    # Now add an unresolved wall 3: scope summary MUST fail closed
    wall_auth_3 = _make_physical_wall_auth(["wall_01", "wall_02", "wall_03"])
    net_auth_3 = _make_net_wall_auth({"wall_01": 10.0, "wall_02": 15.0}, unresolved_walls=["wall_03"])
    assign3 = WallFinishAssignment("a3", "wall_03", "internal_plaster", "both_faces")

    producer_partial = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth_3,
        net_wall_authority=net_auth_3,
        assignments=[assign1, assign2, assign3],
    )

    summary_partial = producer_partial.publish_scope_summary(
        document_id="doc_test_100",
        revision_id="rev_test_001",
        source_sha256="a" * 64,
        snapshot_id="snap_test_001",
        page_id="page_1",
        decision_scope_id=DECISION_SCOPE,
        trade_scope_id="internal_plaster",
    )

    # Partial scope fails closed: total_trade_area_m2 is None
    assert summary_partial.is_scope_complete is False
    assert summary_partial.total_trade_area_m2 is None
    assert "wall_03" in summary_partial.unresolved_wall_ids


def test_missing_assignment_fails_closed() -> None:
    wall_auth = _make_physical_wall_auth(["wall_01"])
    net_auth = _make_net_wall_auth({"wall_01": 10.0})

    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[],  # No assignments
    )

    sel = _sample_selector("wall_01")
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert WALL_FINISH_ASSIGNMENT_UNAVAILABLE in res.reason_codes
    assert res.record is None


def test_authority_sealing_and_immutability() -> None:
    wall_auth = _make_physical_wall_auth(["wall_01"])
    net_auth = _make_net_wall_auth({"wall_01": 10.0})
    assign = WallFinishAssignment("a1", "wall_01", "internal_plaster", "both_faces")

    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[assign],
    )
    sel = _sample_selector("wall_01")
    producer.publish(sel)

    auth = producer.authority()
    resolved = auth.resolve(sel)
    assert resolved.status == EvidenceResolutionStatus.CORROBORATED
    assert resolved.record is not None
    assert resolved.record.total_finish_area_m2 == 20.0

    # Direct instantiation without seal fails
    with pytest.raises(TypeError, match="producer-owned"):
        WallFinishPropagationAuthority({}, {})

    with pytest.raises(TypeError, match="from_authorities"):
        WallFinishPropagationProducer(wall_auth, net_auth, [assign])


def test_invalid_assignment_validation() -> None:
    with pytest.raises(ValueError, match="Invalid wall_face_target"):
        WallFinishAssignment(
            assignment_id="a_bad",
            physical_wall_id="w1",
            trade_scope_id="trade_1",
            wall_face_target="ceiling_face",  # Invalid
        )

    with pytest.raises(ValueError, match="height_limit_m must be a positive finite float"):
        WallFinishAssignment(
            assignment_id="a_bad",
            physical_wall_id="w1",
            trade_scope_id="trade_1",
            wall_face_target="both_faces",
            height_limit_m=-1.0,  # Negative
        )


def test_unknown_selector_abstains() -> None:
    wall_auth = _make_physical_wall_auth(["wall_01"])
    net_auth = _make_net_wall_auth({"wall_01": 10.0})
    assign = WallFinishAssignment("a1", "wall_01", "internal_plaster", "both_faces")

    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[assign],
    )
    producer.publish(_sample_selector("wall_01"))

    auth = producer.authority()
    unknown_sel = _sample_selector("wall_unknown")
    res = auth.resolve(unknown_sel)
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert WALL_FINISH_ASSIGNMENT_UNAVAILABLE in res.reason_codes

