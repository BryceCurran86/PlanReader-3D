"""Candidate-local recovery from incomplete authenticated viewport wall scopes."""
from __future__ import annotations

from types import SimpleNamespace

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    BOUNDARY_EVALUATION_EVALUATED,
    BOUNDARY_EVALUATION_UNAVAILABLE,
    BOUNDARY_PRIMITIVE_CROSSES_SCOPE_BOUNDARY,
    ExcludedBoundaryPrimitive,
    PhysicalWallScopeBoundaryEvaluation,
)
from pb_source_room_face_authority import (
    SOURCE_ROOM_FACE_BOUNDARY_LOCAL_RECOVERY,
    SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED,
    SOURCE_ROOM_FACE_SCOPE_RESOLVED,
    SOURCE_ROOM_FACE_SCOPE_UNAVAILABLE,
    SOURCE_ROOM_FACE_UNIVERSE_PARTIAL,
    _derive_scope,
)


def _record(wall_id: str, *points: tuple[float, float]):
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        wall_candidate=SimpleNamespace(centerline_pts=tuple(points)),
    )


def _three_rooms(*, extra_open_wall: bool = False):
    records = [
        _record("top", (0.0, 0.0), (30.0, 0.0)),
        _record("bottom", (0.0, 10.0), (30.0, 10.0)),
        _record("west", (0.0, 0.0), (0.0, 10.0)),
        _record("p10", (10.0, 0.0), (10.0, 10.0)),
        _record("p20", (20.0, 0.0), (20.0, 10.0)),
        _record("east", (30.0, 0.0), (30.0, 10.0)),
    ]
    if extra_open_wall:
        records.append(_record("stray", (40.0, 0.0), (40.0, 4.0)))
    return tuple(records)


def _evaluation(
    records,
    *,
    tainted=(),
    primitives=(),
    status: str = BOUNDARY_EVALUATION_EVALUATED,
):
    ids = tuple(sorted(record.wall_candidate_id for record in records))
    return PhysicalWallScopeBoundaryEvaluation(
        status=status,
        reason_code=None if status == BOUNDARY_EVALUATION_EVALUATED else "synthetic_unavailable",
        evaluated_wall_candidate_ids=ids,
        boundary_tainted_wall_candidate_ids=tuple(sorted(tainted)),
        boundary_taint_reason_codes=tuple(
            (wall_id, ("synthetic_boundary_taint",))
            for wall_id in sorted(tainted)
        ),
        excluded_boundary_primitives=tuple(primitives),
        authenticated_frame_edge_primitive_count=4,
        contact_tolerance_pt=2.0,
    )


def _scope(
    records,
    *,
    tainted=(),
    primitives=(),
    evaluation_status: str = BOUNDARY_EVALUATION_EVALUATED,
    scope_kind: str = "viewport",
    scope_complete: bool = False,
    evaluated_records=None,
):
    evaluation_records = records if evaluated_records is None else evaluated_records
    return SimpleNamespace(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=scope_complete,
        records=records,
        scope_kind=scope_kind,
        boundary_evaluation=_evaluation(
            evaluation_records,
            tainted=tainted,
            primitives=primitives,
            status=evaluation_status,
        ),
        document_id="doc",
        revision_id="rev",
        source_sha256="a" * 64,
        snapshot_id="snap",
        page_id="1",
        decision_scope_id="wall-source:viewport:1:sealed",
    )


def _areas(result):
    return sorted(round(record.area_page_pts2, 6) for record in result.records)


def test_incomplete_viewport_recovers_clean_faces_when_unrelated_wall_is_tainted():
    records = _three_rooms(extra_open_wall=True)
    result = _derive_scope(_scope(records, tainted=("stray",)))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.scope_complete is True
    assert _areas(result) == [100.0, 100.0, 100.0]
    assert SOURCE_ROOM_FACE_SCOPE_RESOLVED in result.reason_codes
    assert SOURCE_ROOM_FACE_BOUNDARY_LOCAL_RECOVERY in result.reason_codes
    assert SOURCE_ROOM_FACE_UNIVERSE_PARTIAL in result.reason_codes
    assert result.face_universe_complete is False


def test_tainted_bounding_wall_withholds_only_affected_room_when_clean_pair_survives():
    records = _three_rooms()
    result = _derive_scope(_scope(records, tainted=("east",)))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert _areas(result) == [100.0, 100.0]
    assert len(result.abstained_faces) == 1
    assert result.abstained_faces[0].reason == SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED
    assert SOURCE_ROOM_FACE_BOUNDARY_LOCAL_RECOVERY in result.reason_codes
    assert result.face_universe_complete is False


def test_excluded_structural_primitive_crossing_a_face_withholds_that_face():
    records = _three_rooms()
    primitive = ExcludedBoundaryPrimitive(
        category=BOUNDARY_PRIMITIVE_CROSSES_SCOPE_BOUNDARY,
        source_observation_id="excluded-crossing",
        x1=25.0,
        y1=-5.0,
        x2=25.0,
        y2=15.0,
    )
    result = _derive_scope(_scope(records, primitives=(primitive,)))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert _areas(result) == [100.0, 100.0]
    assert len(result.abstained_faces) == 1
    assert result.abstained_faces[0].reason == SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED


def test_excluded_primitive_far_from_rooms_does_not_poison_clean_faces():
    records = _three_rooms()
    primitive = ExcludedBoundaryPrimitive(
        category=BOUNDARY_PRIMITIVE_CROSSES_SCOPE_BOUNDARY,
        source_observation_id="far-crossing",
        x1=50.0,
        y1=-5.0,
        x2=50.0,
        y2=15.0,
    )
    result = _derive_scope(_scope(records, primitives=(primitive,)))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert _areas(result) == [100.0, 100.0, 100.0]
    assert result.abstained_faces == ()
    assert result.face_universe_complete is False


def test_unavailable_boundary_audit_keeps_incomplete_viewport_fail_closed():
    records = _three_rooms()
    result = _derive_scope(
        _scope(records, evaluation_status=BOUNDARY_EVALUATION_UNAVAILABLE)
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert result.reason_codes == (SOURCE_ROOM_FACE_SCOPE_UNAVAILABLE,)


def test_incomplete_page_scope_is_not_promoted_by_viewport_local_rule():
    records = _three_rooms()
    result = _derive_scope(_scope(records, scope_kind="page"))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert result.reason_codes == (SOURCE_ROOM_FACE_SCOPE_UNAVAILABLE,)


def test_boundary_audit_must_cover_exact_wall_record_universe():
    records = _three_rooms()
    result = _derive_scope(
        _scope(records, evaluated_records=records[:-1])
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert result.reason_codes == (SOURCE_ROOM_FACE_SCOPE_UNAVAILABLE,)


def test_complete_scope_behavior_does_not_require_boundary_audit():
    records = _three_rooms()
    scope = _scope(
        records,
        scope_complete=True,
        evaluation_status=BOUNDARY_EVALUATION_UNAVAILABLE,
    )
    result = _derive_scope(scope)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert _areas(result) == [100.0, 100.0, 100.0]
    assert result.reason_codes == (SOURCE_ROOM_FACE_SCOPE_RESOLVED,)
    assert result.face_universe_complete is True
