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
    WALL_FINISH_ASSIGNMENT_CONFLICT,
    WALL_FINISH_ASSIGNMENT_UNAVAILABLE,
    WALL_FINISH_FACE_AMBIGUOUS,
    WALL_FINISH_LINEAGE_MISMATCH,
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

    with pytest.raises(ValueError, match="assignment_id must be a non-empty string"):
        WallFinishAssignment(
            assignment_id="",
            physical_wall_id="w1",
            trade_scope_id="trade_1",
            wall_face_target="both_faces",
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


# ===========================================================================
# Adversarial Tests A through J (Required for Item 19 Clearance)
# ===========================================================================

def test_A_fake_caller_created_net_wall_authority_rejected() -> None:
    """A: fake caller-created net-wall authority rejected."""
    wall_auth = _make_physical_wall_auth(["wall_01"])
    assign = WallFinishAssignment("a1", "wall_01", "internal_plaster", "both_faces")

    class FakeNetWallAuthority:
        def resolve(self, sel: object) -> object:
            return None

    with pytest.raises(TypeError, match="net_wall_authority must be NetWallBooleanUnionAuthority"):
        WallFinishPropagationProducer.from_authorities(
            physical_wall_authority=wall_auth,
            net_wall_authority=FakeNetWallAuthority(),  # type: ignore[arg-type]
            assignments=[assign],
        )

    class SubclassedNetWallAuthority(NetWallBooleanUnionAuthority):
        pass

    with pytest.raises(TypeError, match="net_wall_authority must be NetWallBooleanUnionAuthority"):
        WallFinishPropagationProducer.from_authorities(
            physical_wall_authority=wall_auth,
            net_wall_authority=SubclassedNetWallAuthority.__new__(SubclassedNetWallAuthority),
            assignments=[assign],
        )


def test_B_dict_mapping_duck_typed_authority_rejected() -> None:
    """B: dict / mapping / duck-typed authority rejected."""
    wall_auth = _make_physical_wall_auth(["wall_01"])
    net_auth = _make_net_wall_auth({"wall_01": 10.0})
    assign = WallFinishAssignment("a1", "wall_01", "internal_plaster", "both_faces")

    # Dict passed as net_wall_authority
    with pytest.raises(TypeError, match="net_wall_authority must be NetWallBooleanUnionAuthority"):
        WallFinishPropagationProducer.from_authorities(
            physical_wall_authority=wall_auth,
            net_wall_authority={"resolve": lambda sel: None},  # type: ignore[arg-type]
            assignments=[assign],
        )

    # Dict passed as physical_wall_authority
    with pytest.raises(TypeError, match="physical_wall_authority must be PhysicalWallCandidateAuthority"):
        WallFinishPropagationProducer.from_authorities(
            physical_wall_authority={"resolve": lambda sel: None},  # type: ignore[arg-type]
            net_wall_authority=net_auth,
            assignments=[assign],
        )

    # Duck-typed assignment object
    class DuckAssignment:
        assignment_id = "a1"
        physical_wall_id = "wall_01"
        trade_scope_id = "internal_plaster"
        wall_face_target = "both_faces"

    with pytest.raises(TypeError, match="assignments must contain only WallFinishAssignment instances"):
        WallFinishPropagationProducer.from_authorities(
            physical_wall_authority=wall_auth,
            net_wall_authority=net_auth,
            assignments=[DuckAssignment()],  # type: ignore[list-item]
        )


def test_C_copied_valid_authority_with_altered_wall_id_fails_closed() -> None:
    """C: copied valid authority with altered wall id fails closed."""
    wall_auth = _make_physical_wall_auth(["wall_01", "wall_02"])

    # Net wall authority holds a record for wall_01, but authority map returns it for wall_02
    sel_02 = NetWallBooleanUnionSelector(
        document_id="doc_test_100",
        revision_id="rev_test_001",
        source_sha256="a" * 64,
        snapshot_id="snap_test_001",
        page_id="page_1",
        decision_scope_id=DECISION_SCOPE,
        physical_wall_id="wall_02",
        trade_scope_id="internal_plaster",
    )
    # The record inside has physical_wall_id = "wall_01" (copied from wall_01)
    rec_01_copied = NetWallBooleanUnionRecord(
        record_id="net_rec_wall_01",
        document_id="doc_test_100",
        revision_id="rev_test_001",
        source_sha256="a" * 64,
        snapshot_id="snap_test_001",
        page_id="page_1",
        decision_scope_id=DECISION_SCOPE,
        physical_wall_id="wall_01",  # MISMATCH: record is for wall_01, but selector is for wall_02!
        gross_geometry_record_id="gross_rec_01",
        opening_universe_record_id="univ_rec_01",
        deduction_record_ids=(),
        union_geometry_id="geom_rec_01",
        net_area_m2=15.0,
        gross_area_m2=15.0,
        void_union_area_m2=0.0,
        trade_scope_id="internal_plaster",
    )
    from pb_net_wall_boolean_union_authority import _AUTHORITY_SEAL
    spoofed_net_auth = NetWallBooleanUnionAuthority(
        {
            sel_02.key: NetWallBooleanUnionResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(NET_WALL_BOOLEAN_UNION_RESOLVED,),
                record=rec_01_copied,
            )
        },
        _seal=_AUTHORITY_SEAL,
    )

    assign = WallFinishAssignment("a2", "wall_02", "internal_plaster", "both_faces")
    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=spoofed_net_auth,
        assignments=[assign],
    )

    finish_sel = _sample_selector("wall_02")
    res = producer.publish(finish_sel)

    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert WALL_FINISH_PHYSICAL_WALL_UNRESOLVED in res.reason_codes
    assert "net_wall_physical_wall_id_mismatch" in res.reason_codes
    assert res.record is None


def test_D_stale_valid_authority_from_another_source_lineage_fails_closed() -> None:
    """D: stale valid authority from another source lineage fails closed."""
    wall_auth = _make_physical_wall_auth(["wall_01"])

    # Net wall record has stale lineage: document_id="doc_old", sha="b"*64
    stale_rec = NetWallBooleanUnionRecord(
        record_id="net_rec_stale",
        document_id="doc_old",  # STALE
        revision_id="rev_old",
        source_sha256="b" * 64,  # STALE
        snapshot_id="snap_old",
        page_id="page_1",
        decision_scope_id=DECISION_SCOPE,
        physical_wall_id="wall_01",
        gross_geometry_record_id="gross_rec_01",
        opening_universe_record_id="univ_rec_01",
        deduction_record_ids=(),
        union_geometry_id="geom_rec_01",
        net_area_m2=15.0,
        gross_area_m2=15.0,
        void_union_area_m2=0.0,
        trade_scope_id="internal_plaster",
    )
    sel = _sample_selector("wall_01")
    net_sel = NetWallBooleanUnionSelector(
        document_id=sel.document_id,
        revision_id=sel.revision_id,
        source_sha256=sel.source_sha256,
        snapshot_id=sel.snapshot_id,
        page_id=sel.page_id,
        decision_scope_id=sel.decision_scope_id,
        physical_wall_id=sel.physical_wall_id,
        trade_scope_id=sel.trade_scope_id,
    )
    from pb_net_wall_boolean_union_authority import _AUTHORITY_SEAL
    stale_net_auth = NetWallBooleanUnionAuthority(
        {
            net_sel.key: NetWallBooleanUnionResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(NET_WALL_BOOLEAN_UNION_RESOLVED,),
                record=stale_rec,
            )
        },
        _seal=_AUTHORITY_SEAL,
    )

    assign = WallFinishAssignment("a1", "wall_01", "internal_plaster", "both_faces")
    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=stale_net_auth,
        assignments=[assign],
    )

    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert WALL_FINISH_LINEAGE_MISMATCH in res.reason_codes
    assert res.record is None


def test_E_blocked_net_wall_remains_blocked_without_numeric_zero() -> None:
    """E: blocked net-wall remains blocked without numeric zero."""
    wall_auth = _make_physical_wall_auth(["wall_blocked"])
    net_auth = _make_net_wall_auth({}, unresolved_walls=["wall_blocked"])
    assign = WallFinishAssignment("a_b", "wall_blocked", "internal_plaster", "both_faces")

    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[assign],
    )

    sel = _sample_selector("wall_blocked")
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert WALL_FINISH_NET_GEOMETRY_UNRESOLVED in res.reason_codes
    assert res.record is None

    # Scope summary MUST NOT emit 0.0 or any numeric value! It must fail closed with None.
    summary = producer.publish_scope_summary(
        document_id=sel.document_id,
        revision_id=sel.revision_id,
        source_sha256=sel.source_sha256,
        snapshot_id=sel.snapshot_id,
        page_id=sel.page_id,
        decision_scope_id=sel.decision_scope_id,
        trade_scope_id=sel.trade_scope_id,
    )
    assert summary.is_scope_complete is False
    assert summary.total_trade_area_m2 is None
    assert summary.unresolved_wall_ids == ("wall_blocked",)


def test_F_gross_wall_fallback_cannot_masquerade_as_net_wall_finish() -> None:
    """F: gross-wall fallback cannot masquerade as net-wall finish."""
    wall_auth = _make_physical_wall_auth(["wall_gross_only"])
    sel = _sample_selector("wall_gross_only")
    net_sel = NetWallBooleanUnionSelector(
        document_id=sel.document_id,
        revision_id=sel.revision_id,
        source_sha256=sel.source_sha256,
        snapshot_id=sel.snapshot_id,
        page_id=sel.page_id,
        decision_scope_id=sel.decision_scope_id,
        physical_wall_id=sel.physical_wall_id,
        trade_scope_id=sel.trade_scope_id,
    )
    partial_rec = NetWallBooleanUnionRecord(
        record_id="net_rec_partial",
        document_id=sel.document_id,
        revision_id=sel.revision_id,
        source_sha256=sel.source_sha256,
        snapshot_id=sel.snapshot_id,
        page_id=sel.page_id,
        decision_scope_id=sel.decision_scope_id,
        physical_wall_id=sel.physical_wall_id,
        gross_geometry_record_id="gross_rec_01",
        opening_universe_record_id="univ_rec_01",
        deduction_record_ids=(),
        union_geometry_id="",
        net_area_m2=None,  # Net area uncomputed / unresolved
        gross_area_m2=30.0,  # Gross area present
        void_union_area_m2=0.0,
        trade_scope_id=sel.trade_scope_id,
    )
    from pb_net_wall_boolean_union_authority import _AUTHORITY_SEAL
    net_auth = NetWallBooleanUnionAuthority(
        {
            net_sel.key: NetWallBooleanUnionResult(
                status=EvidenceResolutionStatus.CONFLICT,
                reason_codes=(NET_WALL_DEDUCTION_UNRESOLVED,),
                record=partial_rec,
            )
        },
        _seal=_AUTHORITY_SEAL,
    )

    assign = WallFinishAssignment("a1", "wall_gross_only", "internal_plaster", "both_faces")
    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[assign],
    )

    res = producer.publish(sel)

    # Gross area (30.0) MUST NOT masquerade as finish quantity
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert WALL_FINISH_NET_GEOMETRY_UNRESOLVED in res.reason_codes
    assert res.record is None


def test_G_overlapping_openings_not_re_subtracted_downstream() -> None:
    """G: overlapping openings not re-subtracted downstream."""
    # Wall gross area: 20.0 m2
    # Two openings: 3.0 m2 each, overlapping by 1.0 m2 -> void union = 5.0 m2
    # Net wall boolean union area: exactly 15.0 m2 (not 20 - 6 = 14)
    wall_auth = _make_physical_wall_auth(["wall_with_overlapping_openings"])
    sel = _sample_selector("wall_with_overlapping_openings")
    net_sel = NetWallBooleanUnionSelector(
        document_id=sel.document_id,
        revision_id=sel.revision_id,
        source_sha256=sel.source_sha256,
        snapshot_id=sel.snapshot_id,
        page_id=sel.page_id,
        decision_scope_id=sel.decision_scope_id,
        physical_wall_id=sel.physical_wall_id,
        trade_scope_id=sel.trade_scope_id,
    )
    rec = NetWallBooleanUnionRecord(
        record_id="net_rec_overlap",
        document_id=sel.document_id,
        revision_id=sel.revision_id,
        source_sha256=sel.source_sha256,
        snapshot_id=sel.snapshot_id,
        page_id=sel.page_id,
        decision_scope_id=sel.decision_scope_id,
        physical_wall_id=sel.physical_wall_id,
        gross_geometry_record_id="gross_rec_01",
        opening_universe_record_id="univ_rec_01",
        deduction_record_ids=("ded_01", "ded_02"),
        union_geometry_id="geom_union_01",
        net_area_m2=15.0,  # Authoritative boolean union net area
        gross_area_m2=20.0,
        void_union_area_m2=5.0,
        trade_scope_id=sel.trade_scope_id,
    )
    from pb_net_wall_boolean_union_authority import _AUTHORITY_SEAL
    net_auth = NetWallBooleanUnionAuthority(
        {
            net_sel.key: NetWallBooleanUnionResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(NET_WALL_BOOLEAN_UNION_RESOLVED,),
                record=rec,
            )
        },
        _seal=_AUTHORITY_SEAL,
    )

    assign = WallFinishAssignment("a1", "wall_with_overlapping_openings", "internal_plaster", "both_faces")
    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[assign],
    )

    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.net_area_per_face_m2 == 15.0
    assert res.record.face_multiplier == 2.0
    # Exactly 15.0 * 2.0 = 30.0 m2 (openings are NOT re-subtracted downstream)
    assert res.record.total_finish_area_m2 == 30.0


def test_H_one_face_finish_does_not_implicitly_double_count() -> None:
    """H: one-face finish does not implicitly double-count."""
    wall_auth = _make_physical_wall_auth(["wall_left", "wall_right"])
    net_auth = _make_net_wall_auth({"wall_left": 12.0, "wall_right": 18.0})

    assign_left = WallFinishAssignment("a_left", "wall_left", "internal_plaster", "left_face")
    assign_right = WallFinishAssignment("a_right", "wall_right", "internal_plaster", "right_face")

    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[assign_left, assign_right],
    )

    res_left = producer.publish(_sample_selector("wall_left"))
    assert res_left.status == EvidenceResolutionStatus.CORROBORATED
    assert res_left.record is not None
    assert res_left.record.face_multiplier == 1.0
    assert res_left.record.total_finish_area_m2 == 12.0  # NOT double-counted to 24.0

    res_right = producer.publish(_sample_selector("wall_right"))
    assert res_right.status == EvidenceResolutionStatus.CORROBORATED
    assert res_right.record is not None
    assert res_right.record.face_multiplier == 1.0
    assert res_right.record.total_finish_area_m2 == 18.0  # NOT double-counted to 36.0


def test_I_conflicting_finish_bindings_fail_closed() -> None:
    """I: conflicting finish bindings fail closed."""
    wall_auth = _make_physical_wall_auth(["wall_conflict"])
    net_auth = _make_net_wall_auth({"wall_conflict": 10.0})

    # Two conflicting assignments for the exact same wall and trade scope:
    # One specifies both_faces, another specifies left_face with different material
    assign1 = WallFinishAssignment("a1", "wall_conflict", "internal_plaster", "both_faces", finish_material="Paint")
    assign2 = WallFinishAssignment("a2", "wall_conflict", "internal_plaster", "left_face", finish_material="Tiles")

    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[assign1, assign2],
    )

    sel = _sample_selector("wall_conflict")
    res = producer.publish(sel)

    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert WALL_FINISH_ASSIGNMENT_CONFLICT in res.reason_codes
    assert res.record is None


def test_J_legitimate_producer_owned_positive_path_remains_valid() -> None:
    """J: legitimate producer-owned positive path remains valid."""
    wall_ids = ["wall_101", "wall_102"]
    wall_auth = _make_physical_wall_auth(wall_ids)
    net_auth = _make_net_wall_auth({"wall_101": 25.5, "wall_102": 14.25})

    assign1 = WallFinishAssignment("a101", "wall_101", "internal_plaster", "both_faces", finish_material="Gypsum Plaster")
    assign2 = WallFinishAssignment("a102", "wall_102", "internal_plaster", "left_face", finish_material="Ceramic Tiles")

    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[assign1, assign2],
    )

    sel1 = _sample_selector("wall_101")
    sel2 = _sample_selector("wall_102")

    res1 = producer.publish(sel1)
    res2 = producer.publish(sel2)

    assert res1.status == EvidenceResolutionStatus.CORROBORATED
    assert res1.record is not None
    assert res1.record.physical_wall_id == "wall_101"
    assert res1.record.net_area_per_face_m2 == 25.5
    assert res1.record.face_multiplier == 2.0
    assert res1.record.total_finish_area_m2 == 51.0
    assert res1.record.net_wall_record_id == "net_rec_wall_101"
    assert res1.record.gross_geometry_record_id == "gross_rec_wall_101"

    assert res2.status == EvidenceResolutionStatus.CORROBORATED
    assert res2.record is not None
    assert res2.record.physical_wall_id == "wall_102"
    assert res2.record.net_area_per_face_m2 == 14.25
    assert res2.record.face_multiplier == 1.0
    assert res2.record.total_finish_area_m2 == 14.25

    # Test scope summary
    summary = producer.publish_scope_summary(
        document_id=sel1.document_id,
        revision_id=sel1.revision_id,
        source_sha256=sel1.source_sha256,
        snapshot_id=sel1.snapshot_id,
        page_id=sel1.page_id,
        decision_scope_id=sel1.decision_scope_id,
        trade_scope_id="internal_plaster",
    )
    assert summary.is_scope_complete is True
    # 51.0 + 14.25 = 65.25
    assert summary.total_trade_area_m2 == 65.25
    assert len(summary.contributing_wall_records) == 2
    assert summary.unresolved_wall_ids == ()

    # Test authority resolution
    auth = producer.authority()
    auth_res1 = auth.resolve(sel1)
    assert auth_res1.status == EvidenceResolutionStatus.CORROBORATED
    assert auth_res1.record.total_finish_area_m2 == 51.0


def test_physical_wall_scope_lineage_mismatch_fails_closed() -> None:
    """Physical wall candidate scope result from mismatched document fails closed."""
    # Scope result with mismatched document_id
    identity = PhysicalWallIdentity(
        wall_candidate_id="wall_01",
        viewport_id="view-1",
        candidate_identity_id="wall_01",
        path_fingerprint=((0.0, 0.0), (100.0, 0.0)),
        source_primitive_ids=("prim-1",),
        edge_ids=("edge-1",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    rec = PhysicalWallCandidateRecord(
        wall_candidate_id="wall_01",
        wall_candidate=None,
        physical_identity=identity,
    )
    mismatched_scope_res = PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=(rec,),
        source_observation_ids=("obs_01",),
        document_id="doc_DIFFERENT",  # Lineage mismatch
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
    wall_auth = PhysicalWallCandidateAuthority({key: mismatched_scope_res}, _seal=_WALL_AUTH_SEAL)
    net_auth = _make_net_wall_auth({"wall_01": 10.0})
    assign = WallFinishAssignment("a1", "wall_01", "internal_plaster", "both_faces")

    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[assign],
    )
    res = producer.publish(_sample_selector("wall_01"))
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert WALL_FINISH_LINEAGE_MISMATCH in res.reason_codes
    assert "physical_wall_scope_lineage_mismatch" in res.reason_codes
    assert res.record is None


def test_net_area_exceeding_gross_area_fails_closed() -> None:
    """Net wall record claiming net area > gross area fails closed."""
    wall_auth = _make_physical_wall_auth(["wall_01"])
    sel = _sample_selector("wall_01")
    net_sel = NetWallBooleanUnionSelector(
        document_id=sel.document_id,
        revision_id=sel.revision_id,
        source_sha256=sel.source_sha256,
        snapshot_id=sel.snapshot_id,
        page_id=sel.page_id,
        decision_scope_id=sel.decision_scope_id,
        physical_wall_id=sel.physical_wall_id,
        trade_scope_id=sel.trade_scope_id,
    )
    # Impossible geometry: net area 25 m2 on a 10 m2 wall
    corrupt_rec = NetWallBooleanUnionRecord(
        record_id="net_rec_corrupt",
        document_id=sel.document_id,
        revision_id=sel.revision_id,
        source_sha256=sel.source_sha256,
        snapshot_id=sel.snapshot_id,
        page_id=sel.page_id,
        decision_scope_id=sel.decision_scope_id,
        physical_wall_id=sel.physical_wall_id,
        gross_geometry_record_id="gross_rec_01",
        opening_universe_record_id="univ_rec_01",
        deduction_record_ids=(),
        union_geometry_id="geom_01",
        net_area_m2=25.0,  # 25 > 10!
        gross_area_m2=10.0,
        void_union_area_m2=0.0,
        trade_scope_id=sel.trade_scope_id,
    )
    from pb_net_wall_boolean_union_authority import _AUTHORITY_SEAL
    net_auth = NetWallBooleanUnionAuthority(
        {
            net_sel.key: NetWallBooleanUnionResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(NET_WALL_BOOLEAN_UNION_RESOLVED,),
                record=corrupt_rec,
            )
        },
        _seal=_AUTHORITY_SEAL,
    )
    assign = WallFinishAssignment("a1", "wall_01", "internal_plaster", "both_faces")
    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[assign],
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert WALL_FINISH_NET_GEOMETRY_UNRESOLVED in res.reason_codes
    assert "net_area_exceeds_gross_area" in res.reason_codes
    assert res.record is None


def test_missing_net_wall_record_id_fails_closed() -> None:
    """Net wall record with empty record_id fails closed."""
    wall_auth = _make_physical_wall_auth(["wall_01"])
    sel = _sample_selector("wall_01")
    net_sel = NetWallBooleanUnionSelector(
        document_id=sel.document_id,
        revision_id=sel.revision_id,
        source_sha256=sel.source_sha256,
        snapshot_id=sel.snapshot_id,
        page_id=sel.page_id,
        decision_scope_id=sel.decision_scope_id,
        physical_wall_id=sel.physical_wall_id,
        trade_scope_id=sel.trade_scope_id,
    )
    corrupt_rec = NetWallBooleanUnionRecord(
        record_id="",  # Missing record id
        document_id=sel.document_id,
        revision_id=sel.revision_id,
        source_sha256=sel.source_sha256,
        snapshot_id=sel.snapshot_id,
        page_id=sel.page_id,
        decision_scope_id=sel.decision_scope_id,
        physical_wall_id=sel.physical_wall_id,
        gross_geometry_record_id="gross_rec_01",
        opening_universe_record_id="univ_rec_01",
        deduction_record_ids=(),
        union_geometry_id="geom_01",
        net_area_m2=10.0,
        gross_area_m2=10.0,
        void_union_area_m2=0.0,
        trade_scope_id=sel.trade_scope_id,
    )
    from pb_net_wall_boolean_union_authority import _AUTHORITY_SEAL
    net_auth = NetWallBooleanUnionAuthority(
        {
            net_sel.key: NetWallBooleanUnionResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(NET_WALL_BOOLEAN_UNION_RESOLVED,),
                record=corrupt_rec,
            )
        },
        _seal=_AUTHORITY_SEAL,
    )
    assign = WallFinishAssignment("a1", "wall_01", "internal_plaster", "both_faces")
    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[assign],
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert WALL_FINISH_NET_GEOMETRY_UNRESOLVED in res.reason_codes
    assert "missing_net_wall_record_id" in res.reason_codes
    assert res.record is None


def test_scope_summary_input_validation() -> None:
    """Empty or whitespace strings passed to scope summary methods raise ValueError."""
    wall_auth = _make_physical_wall_auth(["wall_01"])
    net_auth = _make_net_wall_auth({"wall_01": 10.0})
    assign = WallFinishAssignment("a1", "wall_01", "internal_plaster", "both_faces")
    producer = WallFinishPropagationProducer.from_authorities(
        physical_wall_authority=wall_auth,
        net_wall_authority=net_auth,
        assignments=[assign],
    )
    with pytest.raises(ValueError, match="document_id must be a non-empty string"):
        producer.publish_scope_summary("", "rev", "sha", "snap", "page", "scope", "trade")

    auth = producer.authority()
    with pytest.raises(ValueError, match="trade_scope_id must be a non-empty string"):
        auth.resolve_scope_summary("doc", "rev", "sha", "snap", "page", "scope", "   ")



