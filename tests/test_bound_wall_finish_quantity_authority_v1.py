from __future__ import annotations

import pytest

import pb_net_wall_boolean_union_authority as netmod
import pb_wall_finish_face_binding_authority as finishmod
from pb_bound_wall_finish_quantity_authority import (
    FINISH_QUANTITY_BINDING_LINEAGE_MISMATCH,
    FINISH_QUANTITY_BINDING_MISSING,
    FINISH_QUANTITY_NET_WALL_LINEAGE_MISMATCH,
    FINISH_QUANTITY_NET_WALL_UNRESOLVED,
    FINISH_QUANTITY_RESOLVED,
    FINISH_QUANTITY_SCOPE_INCOMPLETE,
    SourceBoundWallFinishQuantityProducer,
    SourceBoundWallFinishQuantitySelector,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_net_wall_boolean_union_authority import (
    NET_WALL_BOOLEAN_UNION_RESOLVED,
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionRecord,
    NetWallBooleanUnionResult,
    NetWallBooleanUnionSelector,
)
from pb_wall_finish_face_binding_authority import (
    FinishScopeStatus,
    PhysicalFaceRole,
    WallFinishCompleteScopeRecord,
    WallFinishFaceBindingAuthority,
    WallFinishFaceBindingRecord,
    WallFinishFaceBindingScopeResult,
    WallFinishFaceBindingScopeSelector,
)
from pb_wall_role_authority import WallRoleClassification


DOC = "doc"
REV = "rev"
SHA = "a" * 64
SNAP = "snap"
PAGE = "54"
VIEWPORT = "vp"
SCOPE = "wall-scope"
TRADE = "external_key_pointing"
MATERIAL = "key_pointing"


def _selector() -> SourceBoundWallFinishQuantitySelector:
    return SourceBoundWallFinishQuantitySelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        viewport_id=VIEWPORT,
        decision_scope_id=SCOPE,
        trade_scope_id=TRADE,
        finish_material=MATERIAL,
    )


def _binding(
    binding_id: str,
    face_id: str,
    wall_id: str,
    *,
    revision_id: str = REV,
) -> WallFinishFaceBindingRecord:
    return WallFinishFaceBindingRecord(
        binding_id=binding_id,
        document_id=DOC,
        revision_id=revision_id,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        viewport_id=VIEWPORT,
        decision_scope_id=SCOPE,
        physical_wall_id=wall_id,
        physical_face_id=face_id,
        physical_face_role=PhysicalFaceRole.EXTERIOR_FACE,
        source_face_segment_ids=(f"seg-{wall_id}",),
        trade_scope_id=TRADE,
        finish_material=MATERIAL,
        annotation_observation_ids=(f"ann-{binding_id}",),
        leader_path_ids=(f"leader-{binding_id}",),
        terminator_primitive_ids=(f"term-{binding_id}",),
        wall_role_record_id=f"role-{wall_id}",
        wall_role=WallRoleClassification.EXTERNAL,
        source_evidence_ids=(f"ann-{binding_id}", f"role-{wall_id}"),
        source_evidence_kind="native_direct_finish_callout",
        decision_scope_complete=False,
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("wall_finish_face_binding_resolved",),
        _seal=finishmod._RECORD_SEAL,
    )


def _finish_authority(
    bindings: tuple[WallFinishFaceBindingRecord, ...],
    *,
    complete: bool = True,
    binding_ids: tuple[str, ...] | None = None,
    target_faces: tuple[str, ...] | None = None,
) -> WallFinishFaceBindingAuthority:
    selector = WallFinishFaceBindingScopeSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        viewport_id=VIEWPORT,
        decision_scope_id=SCOPE,
    )
    covered = tuple(sorted({binding.physical_face_id for binding in bindings}))
    ids = binding_ids if binding_ids is not None else tuple(
        binding.binding_id for binding in bindings
    )
    if complete:
        targets = target_faces if target_faces is not None else covered
        scope = WallFinishCompleteScopeRecord(
            scope_id="finish-scope",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            viewport_id=VIEWPORT,
            decision_scope_id=SCOPE,
            trade_scope_id=TRADE,
            finish_material=MATERIAL,
            target_face_ids=targets,
            covered_face_ids=targets,
            binding_ids=ids,
            decision_scope_complete=True,
            scope_status=FinishScopeStatus.COMPLETE,
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("wall_finish_scope_complete",),
            _seal=finishmod._RECORD_SEAL,
        )
    else:
        scope = WallFinishCompleteScopeRecord(
            scope_id="finish-scope-partial",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            viewport_id=VIEWPORT,
            decision_scope_id=SCOPE,
            trade_scope_id=TRADE,
            finish_material=MATERIAL,
            target_face_ids=(),
            covered_face_ids=covered,
            binding_ids=ids,
            decision_scope_complete=False,
            scope_status=FinishScopeStatus.PARTIAL,
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("wall_finish_scope_partial",),
            _seal=finishmod._RECORD_SEAL,
        )
    result = WallFinishFaceBindingScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        bindings=bindings,
        scope_records=(scope,),
    )
    return WallFinishFaceBindingAuthority(
        {selector.key: result},
        _seal=finishmod._AUTHORITY_SEAL,
    )


def _net_record(wall_id: str, area: float, *, record_wall_id: str | None = None):
    return NetWallBooleanUnionRecord(
        record_id=f"net-{wall_id}",
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
        physical_wall_id=record_wall_id or wall_id,
        gross_geometry_record_id=f"gross-{wall_id}",
        opening_universe_record_id="opening-universe",
        deduction_record_ids=(),
        union_geometry_id=f"union-{wall_id}",
        net_area_m2=area,
        gross_area_m2=area,
        void_union_area_m2=0.0,
        trade_scope_id=TRADE,
    )


def _net_authority(
    areas: dict[str, float],
    *,
    unresolved_wall: str | None = None,
    mismatched_wall: str | None = None,
) -> NetWallBooleanUnionAuthority:
    results = {}
    for wall_id, area in areas.items():
        selector = NetWallBooleanUnionSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            physical_wall_id=wall_id,
            trade_scope_id=TRADE,
        )
        if unresolved_wall == wall_id:
            results[selector.key] = NetWallBooleanUnionResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=("upstream_opening_universe_incomplete",),
                record=None,
            )
        else:
            results[selector.key] = NetWallBooleanUnionResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(NET_WALL_BOOLEAN_UNION_RESOLVED,),
                record=_net_record(
                    wall_id,
                    area,
                    record_wall_id=(
                        "different-wall" if mismatched_wall == wall_id else None
                    ),
                ),
            )
    return NetWallBooleanUnionAuthority(
        results,
        _seal=netmod._AUTHORITY_SEAL,
    )


def _producer(
    finish: WallFinishFaceBindingAuthority,
    net: NetWallBooleanUnionAuthority,
) -> SourceBoundWallFinishQuantityProducer:
    return SourceBoundWallFinishQuantityProducer.from_authorities(finish, net)


def test_complete_source_owned_face_scope_publishes_net_finish_quantity() -> None:
    binding = _binding("b1", "face-1", "wall-1")
    result = _producer(
        _finish_authority((binding,)),
        _net_authority({"wall-1": 12.5}),
    ).publish(_selector())

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (FINISH_QUANTITY_RESOLVED,)
    assert result.record is not None
    assert result.record.quantity_m2 == 12.5
    assert result.record.physical_face_ids == ("face-1",)
    assert result.record.physical_wall_ids == ("wall-1",)
    assert result.record.net_wall_record_ids == ("net-wall-1",)


def test_partial_finish_scope_never_publishes_quantity() -> None:
    binding = _binding("b1", "face-1", "wall-1")
    result = _producer(
        _finish_authority((binding,), complete=False),
        _net_authority({"wall-1": 12.5}),
    ).publish(_selector())

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert FINISH_QUANTITY_SCOPE_INCOMPLETE in result.reason_codes


def test_duplicate_source_evidence_for_same_face_does_not_double_count() -> None:
    b1 = _binding("b1", "face-1", "wall-1")
    b2 = _binding("b2", "face-1", "wall-1")
    result = _producer(
        _finish_authority((b2, b1)),
        _net_authority({"wall-1": 9.0}),
    ).publish(_selector())

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.quantity_m2 == 9.0
    assert result.record.physical_face_ids == ("face-1",)
    assert result.record.finish_binding_ids == ("b1", "b2")


def test_two_distinct_proven_faces_on_same_wall_each_contribute_once() -> None:
    b1 = _binding("b1", "face-a", "wall-1")
    b2 = _binding("b2", "face-b", "wall-1")
    result = _producer(
        _finish_authority((b1, b2)),
        _net_authority({"wall-1": 7.25}),
    ).publish(_selector())

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.quantity_m2 == 14.5
    assert result.record.physical_face_ids == ("face-a", "face-b")
    assert result.record.net_wall_record_ids == ("net-wall-1",)


def test_scope_referencing_missing_binding_abstains() -> None:
    binding = _binding("b1", "face-1", "wall-1")
    finish = _finish_authority(
        (binding,),
        binding_ids=("missing-binding",),
        target_faces=("face-1",),
    )
    result = _producer(
        finish,
        _net_authority({"wall-1": 5.0}),
    ).publish(_selector())

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert FINISH_QUANTITY_BINDING_MISSING in result.reason_codes


def test_binding_lineage_mismatch_is_conflict() -> None:
    stale = _binding("b1", "face-1", "wall-1", revision_id="other-revision")
    result = _producer(
        _finish_authority((stale,)),
        _net_authority({"wall-1": 5.0}),
    ).publish(_selector())

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.record is None
    assert FINISH_QUANTITY_BINDING_LINEAGE_MISMATCH in result.reason_codes


def test_unresolved_net_wall_geometry_abstains_instead_of_using_gross_area() -> None:
    binding = _binding("b1", "face-1", "wall-1")
    result = _producer(
        _finish_authority((binding,)),
        _net_authority({"wall-1": 8.0}, unresolved_wall="wall-1"),
    ).publish(_selector())

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert FINISH_QUANTITY_NET_WALL_UNRESOLVED in result.reason_codes


def test_net_wall_physical_identity_mismatch_is_conflict() -> None:
    binding = _binding("b1", "face-1", "wall-1")
    result = _producer(
        _finish_authority((binding,)),
        _net_authority({"wall-1": 8.0}, mismatched_wall="wall-1"),
    ).publish(_selector())

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.record is None
    assert FINISH_QUANTITY_NET_WALL_LINEAGE_MISMATCH in result.reason_codes


def test_input_order_does_not_change_quantity_or_record_id() -> None:
    b1 = _binding("b1", "face-a", "wall-1")
    b2 = _binding("b2", "face-b", "wall-2")
    net = _net_authority({"wall-1": 4.0, "wall-2": 6.0})

    first = _producer(_finish_authority((b1, b2)), net).publish(_selector())
    second = _producer(_finish_authority((b2, b1)), net).publish(_selector())

    assert first.status is second.status is EvidenceResolutionStatus.CORROBORATED
    assert first.record is not None and second.record is not None
    assert first.record.quantity_m2 == second.record.quantity_m2 == 10.0
    assert first.record.record_id == second.record.record_id


def test_constructor_rejects_caller_shaped_authorities() -> None:
    with pytest.raises(TypeError):
        SourceBoundWallFinishQuantityProducer.from_authorities(  # type: ignore[arg-type]
            {},
            _net_authority({"wall-1": 1.0}),
        )

    with pytest.raises(TypeError):
        SourceBoundWallFinishQuantityProducer.from_authorities(  # type: ignore[arg-type]
            _finish_authority((_binding("b1", "face-1", "wall-1"),)),
            {},
        )
