from __future__ import annotations

from pb_live_canonical_wall_finish_surface import (
    LIVE_CANONICAL_WALL_FINISH_SURFACE_CONFLICT,
    LIVE_CANONICAL_WALL_FINISH_SURFACE_HOST_UNAVAILABLE,
    LIVE_CANONICAL_WALL_FINISH_SURFACE_LINEAGE_MISMATCH,
    LIVE_CANONICAL_WALL_FINISH_SURFACE_PARTIAL,
    LIVE_CANONICAL_WALL_FINISH_SURFACE_RESOLVED,
    project_wall_finish_bindings,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_wall_finish_face_binding_authority import (
    PhysicalFaceRole,
    WallFinishFaceBindingRecord,
    _RECORD_SEAL,
)
from pb_wall_role_authority import WallRoleClassification


def _wall(**changes):
    base = {
        "canonical_wall_id": "cw-1",
        "physical_wall_id": "wall-1",
        "document_id": "doc",
        "revision_id": "r1",
        "source_sha256": "a" * 64,
        "snapshot_id": "snap",
        "page_id": "54",
        "level_ids": ["L1"],
        "net_area_m2": 12.5,
        "quantity_complete": True,
        "physical_identity_resolved": True,
        "evidence_ids": ["wall-evidence-1"],
    }
    base.update(changes)
    return base


def _binding(**changes):
    base = dict(
        binding_id="bind-1",
        document_id="doc",
        revision_id="r1",
        source_sha256="a" * 64,
        snapshot_id="snap",
        page_id="54",
        viewport_id="vp",
        decision_scope_id="finish-callout:vp",
        physical_wall_id="wall-1",
        physical_face_id="face-1",
        physical_face_role=PhysicalFaceRole.EXTERIOR_FACE,
        source_face_segment_ids=("wall-seg",),
        trade_scope_id="external_key_pointing",
        finish_material="key_pointing",
        annotation_observation_ids=("ann",),
        leader_path_ids=("lead-1", "lead-2"),
        terminator_primitive_ids=("term-1",),
        wall_role_record_id="role-1",
        wall_role=WallRoleClassification.EXTERNAL,
        source_evidence_ids=("ann", "lead-1", "lead-2", "term-1", "role-1"),
        source_evidence_kind="native_direct_finish_callout",
        decision_scope_complete=False,
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("wall_finish_face_binding_resolved",),
        _seal=_RECORD_SEAL,
    )
    base.update(changes)
    return WallFinishFaceBindingRecord(**base)


def test_positive_binding_becomes_one_noncommercial_canonical_surface():
    result = project_wall_finish_bindings(
        canonical_walls=(_wall(),),
        bindings=(_binding(),),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (LIVE_CANONICAL_WALL_FINISH_SURFACE_RESOLVED,)
    assert result.unresolved_binding_ids == ()
    assert len(result.surfaces) == 1
    surface = result.surfaces[0]
    assert surface.canonical_wall_id == "cw-1"
    assert surface.physical_wall_id == "wall-1"
    assert surface.physical_face_id
    assert surface.physical_face_id != "face-1"
    assert surface.physical_face_role == "exterior_face"
    assert surface.trade_scope_id == "external_key_pointing"
    assert surface.finish_material == "key_pointing"
    assert surface.level_ids == ("L1",)
    assert surface.host_net_area_m2 == 12.5
    assert surface.host_quantity_complete is True
    assert surface.surface_area_m2 is None
    assert surface.metric_area_complete is False
    assert surface.geometry_complete is False
    assert surface.commercial_quantity_authority is False
    assert "bind-1" in surface.source_evidence_ids


def test_surface_identity_ignores_revision_evidence_and_material_state():
    first = project_wall_finish_bindings(
        canonical_walls=(_wall(),),
        bindings=(_binding(),),
    ).surfaces[0]

    second = project_wall_finish_bindings(
        canonical_walls=(
            _wall(
                canonical_wall_id="cw-republished",
                revision_id="r2",
                source_sha256="b" * 64,
                snapshot_id="snap-2",
            ),
        ),
        bindings=(
            _binding(
                binding_id="bind-r2",
                revision_id="r2",
                source_sha256="b" * 64,
                snapshot_id="snap-2",
                finish_material="paint",
                source_evidence_ids=("ann-r2", "role-r2"),
            ),
        ),
    ).surfaces[0]

    assert first.canonical_surface_id == second.canonical_surface_id
    assert first.physical_wall_id == second.physical_wall_id == "wall-1"
    assert first.physical_face_id == second.physical_face_id
    assert first.physical_face_id != "face-1"
    assert first.finish_material == "key_pointing"
    assert second.finish_material == "paint"


def test_surface_identity_ignores_raw_face_record_but_changes_for_role_or_trade():
    base = project_wall_finish_bindings(
        canonical_walls=(_wall(),),
        bindings=(_binding(),),
    ).surfaces[0]
    other_raw_face_record = project_wall_finish_bindings(
        canonical_walls=(_wall(),),
        bindings=(
            _binding(
                binding_id="bind-face-2",
                physical_face_id="producer-face-record-2",
                source_evidence_ids=("ann-face-2", "role-1"),
            ),
        ),
    ).surfaces[0]
    other_role = project_wall_finish_bindings(
        canonical_walls=(_wall(),),
        bindings=(
            _binding(
                binding_id="bind-interior",
                physical_face_id="producer-interior-face-record",
                physical_face_role=PhysicalFaceRole.ROOM_FACING_INTERIOR_FACE,
                trade_scope_id="internal_paint",
                finish_material="paint",
                source_evidence_ids=("ann-interior", "role-1"),
            ),
        ),
    ).surfaces[0]
    other_trade = project_wall_finish_bindings(
        canonical_walls=(_wall(),),
        bindings=(
            _binding(
                binding_id="bind-trade-2",
                trade_scope_id="external_paint",
                source_evidence_ids=("ann-trade-2", "role-1"),
            ),
        ),
    ).surfaces[0]

    assert base.physical_face_id == other_raw_face_record.physical_face_id
    assert base.canonical_surface_id == other_raw_face_record.canonical_surface_id
    assert base.physical_face_id != other_role.physical_face_id
    assert base.canonical_surface_id != other_role.canonical_surface_id
    assert base.canonical_surface_id != other_trade.canonical_surface_id


def test_equivalent_wall_candidates_join_one_canonical_physical_surface():
    canonical_wall = _wall(
        canonical_wall_id="wall-representative",
        physical_wall_id="wall-representative",
    )
    second = _binding(
        binding_id="bind-2",
        physical_wall_id="wall-candidate-2",
        physical_face_id="source-face-2",
        annotation_observation_ids=("ann-2",),
        source_evidence_ids=("ann-2", "role-1"),
    )
    result = project_wall_finish_bindings(
        canonical_walls=(canonical_wall,),
        bindings=(
            _binding(
                physical_wall_id="wall-candidate-1",
                physical_face_id="source-face-1",
            ),
            second,
        ),
        canonical_wall_ids_by_candidate={
            "wall-candidate-1": "wall-representative",
            "wall-candidate-2": "wall-representative",
        },
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.surfaces) == 1
    surface = result.surfaces[0]
    assert surface.canonical_wall_id == "wall-representative"
    assert surface.physical_wall_id == "wall-representative"
    assert surface.finish_binding_ids == ("bind-1", "bind-2")


def test_repeated_source_support_enriches_one_surface_not_duplicate_geometry():
    second = _binding(
        binding_id="bind-2",
        annotation_observation_ids=("ann-2",),
        leader_path_ids=("lead-3",),
        terminator_primitive_ids=("term-2",),
        source_evidence_ids=("ann-2", "lead-3", "term-2", "role-1"),
    )
    result = project_wall_finish_bindings(
        canonical_walls=(_wall(),),
        bindings=(_binding(), second),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.surfaces) == 1
    surface = result.surfaces[0]
    assert surface.finish_binding_ids == ("bind-1", "bind-2")
    assert "ann" in surface.source_evidence_ids
    assert "ann-2" in surface.source_evidence_ids


def test_conflicting_material_same_face_and_trade_fails_closed():
    conflict = _binding(
        binding_id="bind-2",
        finish_material="paint",
        source_evidence_ids=("ann-2", "role-1"),
    )
    result = project_wall_finish_bindings(
        canonical_walls=(_wall(),),
        bindings=(_binding(), conflict),
    )

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.reason_codes == (LIVE_CANONICAL_WALL_FINISH_SURFACE_CONFLICT,)
    assert result.surfaces == ()


def test_missing_host_wall_abstains_with_exact_unresolved_binding():
    result = project_wall_finish_bindings(
        canonical_walls=(_wall(physical_wall_id="wall-other"),),
        bindings=(_binding(),),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (
        LIVE_CANONICAL_WALL_FINISH_SURFACE_HOST_UNAVAILABLE,
    )
    assert result.surfaces == ()
    assert result.unresolved_binding_ids == ("bind-1",)


def test_lineage_mismatch_abstains_instead_of_attaching_to_same_named_wall():
    result = project_wall_finish_bindings(
        canonical_walls=(_wall(revision_id="r2"),),
        bindings=(_binding(),),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (
        LIVE_CANONICAL_WALL_FINISH_SURFACE_LINEAGE_MISMATCH,
    )
    assert result.surfaces == ()
    assert result.unresolved_binding_ids == ("bind-1",)


def test_mixed_resolved_and_missing_hosts_is_candidate_partial():
    missing = _binding(
        binding_id="bind-2",
        physical_wall_id="wall-missing",
        physical_face_id="face-2",
        source_evidence_ids=("ann-2", "role-2"),
    )
    result = project_wall_finish_bindings(
        canonical_walls=(_wall(),),
        bindings=(_binding(), missing),
    )

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.reason_codes == (
        LIVE_CANONICAL_WALL_FINISH_SURFACE_PARTIAL,
        LIVE_CANONICAL_WALL_FINISH_SURFACE_HOST_UNAVAILABLE,
    )
    assert len(result.surfaces) == 1
    assert result.unresolved_binding_ids == ("bind-2",)


def test_unresolved_physical_wall_identity_is_not_a_surface_host():
    result = project_wall_finish_bindings(
        canonical_walls=(_wall(physical_identity_resolved=False),),
        bindings=(_binding(),),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (
        LIVE_CANONICAL_WALL_FINISH_SURFACE_HOST_UNAVAILABLE,
    )
    assert result.surfaces == ()
