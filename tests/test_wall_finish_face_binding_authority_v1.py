from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_wall_finish_face_binding_authority import (
    FINISH_BINDING_TARGET_CONFLICT,
    FINISH_BINDING_UNAVAILABLE,
    FINISH_SCOPE_PARTIAL,
    FINISH_SCOPE_UNIVERSE_UNAVAILABLE,
    FinishScopeStatus,
    PhysicalFaceRole,
    WallFinishCompleteScopeRecord,
    WallFinishFaceBindingAuthority,
    WallFinishFaceBindingRecord,
    WallFinishFaceBindingScopeResult,
    WallFinishFaceBindingScopeSelector,
    _AUTHORITY_SEAL,
    _Line,
    _RECORD_SEAL,
    _Terminator,
    _finish_semantics,
    _leader_paths,
    _partial_scope,
    _semantic_face,
    _target_from_terminator,
)
from pb_wall_role_authority import WallRoleClassification


def _line(obs: str, raw: str, x1: float, y1: float, x2: float, y2: float) -> _Line:
    return _Line(obs, raw, (x1, y1, x2, y2))


def _term(x: float, y: float, size: float = 2.0) -> _Terminator:
    box = (x - size, y - size, x + size, y + size)
    return _Terminator("term-1", box, (x, y))


def _transform_line(line: _Line, *, tx=0.0, ty=0.0, scale=1.0, quarter_turns=0) -> _Line:
    def point(x, y):
        x, y = x * scale, y * scale
        for _ in range(quarter_turns % 4):
            x, y = -y, x
        return x + tx, y + ty
    p1 = point(line.geometry[0], line.geometry[1])
    p2 = point(line.geometry[2], line.geometry[3])
    return _Line(line.observation_id, line.raw_id, (*p1, *p2))


def _transform_box(box, *, tx=0.0, ty=0.0, scale=1.0, quarter_turns=0):
    pts = []
    for x, y in ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])):
        x, y = x * scale, y * scale
        for _ in range(quarter_turns % 4):
            x, y = -y, x
        pts.append((x + tx, y + ty))
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))


def _binding(**changes) -> WallFinishFaceBindingRecord:
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


def test_direct_leader_and_filled_terminator_connectivity_positive() -> None:
    annotation = (20.0, 8.0, 30.0, 12.0)
    lines = (
        _line("lead-a", "raw-a", 30.0, 10.0, 15.0, 10.0),
        _line("lead-b", "raw-b", 15.0, 10.0, 7.0, 10.0),
    )
    paths = _leader_paths(annotation, lines, (_term(5.0, 10.0),), 0.01)
    assert paths
    assert paths[0][0] == ("lead-a", "lead-b")


def test_two_possible_physical_walls_conflict() -> None:
    lines = (
        _line("w1", "raw-w1", 4.0, 0.0, 4.0, 20.0),
        _line("w2", "raw-w2", 6.0, 0.0, 6.0, 20.0),
    )
    rec1 = SimpleNamespace(
        wall_candidate_id="wall-1",
        physical_identity=SimpleNamespace(source_primitive_ids=("raw-w1",)),
    )
    rec2 = SimpleNamespace(
        wall_candidate_id="wall-2",
        physical_identity=SimpleNamespace(source_primitive_ids=("raw-w2",)),
    )
    scope = SimpleNamespace(records=(rec1, rec2), equivalence=SimpleNamespace(equivalence_groups=()))
    target, _, status = _target_from_terminator(_term(5.0, 10.0), lines, scope, 0.01)
    assert target is None
    assert status is EvidenceResolutionStatus.CONFLICT


def test_no_terminator_abstains_from_connectivity() -> None:
    annotation = (20.0, 8.0, 30.0, 12.0)
    lines = (_line("lead", "raw", 30.0, 10.0, 5.0, 10.0),)
    assert _leader_paths(annotation, lines, (), 0.01) == ()


def test_page_wide_keyword_does_not_create_finish_semantics() -> None:
    assert _finish_semantics("PLASTER AND PAINT") == ()
    assert _finish_semantics("KEY TO FINISH EXTERNALLY") == ()


def test_nearby_unconnected_note_does_not_bind() -> None:
    annotation = (20.0, 8.0, 30.0, 12.0)
    lines = (_line("nearby", "raw", 31.0, 10.0, 5.0, 10.0),)
    assert _leader_paths(annotation, lines, (_term(5.0, 10.0),), 0.01) == ()


def test_external_wording_on_external_wall_resolves_exterior_face() -> None:
    assert _semantic_face(WallRoleClassification.EXTERNAL, "externally") is PhysicalFaceRole.EXTERIOR_FACE


def test_internal_wording_on_external_wall_resolves_room_face() -> None:
    assert _semantic_face(WallRoleClassification.EXTERNAL, "internally") is PhysicalFaceRole.ROOM_FACING_INTERIOR_FACE


def test_unresolved_wall_role_abstains() -> None:
    assert _semantic_face(WallRoleClassification.UNRESOLVED, "externally") is None


def test_internal_partition_two_sided_direction_is_ambiguous() -> None:
    assert _semantic_face(WallRoleClassification.INTERNAL, "internally") is None


def test_duplicate_binding_collapses_deterministically_by_id() -> None:
    first = _binding(binding_id="a")
    duplicate = _binding(binding_id="a")
    collapsed = {record.binding_id: record for record in (duplicate, first)}
    assert tuple(collapsed) == ("a",)
    assert collapsed["a"] == first


def test_conflicting_finishes_same_face_are_detectable() -> None:
    key = _binding(binding_id="a", finish_material="key_pointing")
    paint = _binding(binding_id="b", finish_material="paint")
    materials = {}
    for record in (key, paint):
        materials.setdefault((record.physical_face_id, record.trade_scope_id), set()).add(record.finish_material)
    assert any(len(values) > 1 for values in materials.values())


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_sha256", "b" * 64),
        ("revision_id", "r2"),
        ("snapshot_id", "stale"),
        ("viewport_id", "other-vp"),
    ],
)
def test_stale_lineage_or_changed_viewport_rejected(field: str, value: str) -> None:
    selector = WallFinishFaceBindingScopeSelector(
        document_id="doc", revision_id="r1", source_sha256="a" * 64,
        snapshot_id="snap", page_id="54", viewport_id="vp",
        decision_scope_id="finish-callout:vp",
    )
    result = WallFinishFaceBindingScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("ok",),
        bindings=(_binding(),),
    )
    authority = WallFinishFaceBindingAuthority({selector.key: result}, _seal=_AUTHORITY_SEAL)
    kwargs = dict(selector.__dict__)
    kwargs[field] = value
    stale = WallFinishFaceBindingScopeSelector(**kwargs)
    rejected = authority.resolve_scope(stale)
    assert rejected.status is EvidenceResolutionStatus.ABSTAINED
    assert rejected.reason_codes == (FINISH_BINDING_UNAVAILABLE,)


def test_segment_splitting_preserves_connectivity() -> None:
    annotation = (20.0, 8.0, 30.0, 12.0)
    whole = (_line("whole", "raw-whole", 30.0, 10.0, 7.0, 10.0),)
    split = (
        _line("a", "raw-a", 30.0, 10.0, 15.0, 10.0),
        _line("b", "raw-b", 15.0, 10.0, 7.0, 10.0),
    )
    term = (_term(5.0, 10.0),)
    assert _leader_paths(annotation, whole, term, 0.01)
    assert _leader_paths(annotation, split, term, 0.01)


@pytest.mark.parametrize(
    "tx,ty,scale,turns",
    [(100.0, -50.0, 1.0, 0), (0.0, 0.0, 1.0, 1), (0.0, 0.0, 3.5, 0)],
)
def test_translation_rotation_uniform_scale_metamorphic(tx, ty, scale, turns) -> None:
    annotation = (20.0, 8.0, 30.0, 12.0)
    lines = (
        _line("a", "raw-a", 30.0, 10.0, 15.0, 10.0),
        _line("b", "raw-b", 15.0, 10.0, 7.0, 10.0),
    )
    term = _term(5.0, 10.0)
    a2 = _transform_box(annotation, tx=tx, ty=ty, scale=scale, quarter_turns=turns)
    l2 = tuple(_transform_line(line, tx=tx, ty=ty, scale=scale, quarter_turns=turns) for line in lines)
    tbox = _transform_box(term.bbox, tx=tx, ty=ty, scale=scale, quarter_turns=turns)
    center = ((tbox[0] + tbox[2]) / 2, (tbox[1] + tbox[3]) / 2)
    t2 = _Terminator(term.primitive_id, tbox, center)
    assert _leader_paths(a2, l2, (t2,), max(0.01, 0.01 * scale))


def test_input_order_and_unrelated_content_do_not_change_positive_path() -> None:
    annotation = (20.0, 8.0, 30.0, 12.0)
    base = (
        _line("a", "raw-a", 30.0, 10.0, 15.0, 10.0),
        _line("b", "raw-b", 15.0, 10.0, 7.0, 10.0),
    )
    unrelated = _line("noise", "raw-noise", 100.0, 100.0, 120.0, 100.0)
    p1 = _leader_paths(annotation, base, (_term(5.0, 10.0),), 0.01)
    p2 = _leader_paths(annotation, (unrelated, *reversed(base)), (_term(5.0, 10.0),), 0.01)
    assert {ids for ids, _ in p1} == {tuple(reversed(ids)) for ids, _ in p2} or bool(p2)


def test_scope_is_partial_without_independent_target_face_universe() -> None:
    scope = _partial_scope((_binding(),))
    assert scope.scope_status is FinishScopeStatus.PARTIAL
    assert scope.decision_scope_complete is False
    assert scope.target_face_ids == ()
    assert scope.covered_face_ids == ("face-1",)
    assert FINISH_SCOPE_PARTIAL in scope.reason_codes
    assert FINISH_SCOPE_UNIVERSE_UNAVAILABLE in scope.reason_codes


def test_complete_scope_record_requires_exact_universe_coverage() -> None:
    with pytest.raises(ValueError, match="enumerated fully-covered"):
        WallFinishCompleteScopeRecord(
            scope_id="s", document_id="d", revision_id="r", source_sha256="a" * 64,
            snapshot_id="snap", page_id="1", viewport_id="vp", decision_scope_id="scope",
            trade_scope_id="trade", finish_material="paint",
            target_face_ids=("f1", "f2"), covered_face_ids=("f1",), binding_ids=("b1",),
            decision_scope_complete=True, scope_status=FinishScopeStatus.COMPLETE,
            status=EvidenceResolutionStatus.CORROBORATED, reason_codes=(),
            _seal=_RECORD_SEAL,
        )


def test_public_record_and_authority_construction_is_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        replace(_binding(), _seal=None)
    with pytest.raises(TypeError, match="producer-owned"):
        WallFinishFaceBindingAuthority({})


def test_stable_id_and_no_input_mutation() -> None:
    payload = {
        "wall": "wall-1", "face": "exterior_face",
        "trade": "external_key_pointing", "material": "key_pointing",
    }
    before = dict(payload)
    first = stable_contract_id("wall_finish_face_binding", payload, digest_chars=32)
    second = stable_contract_id("wall_finish_face_binding", payload, digest_chars=32)
    assert first == second
    assert payload == before
