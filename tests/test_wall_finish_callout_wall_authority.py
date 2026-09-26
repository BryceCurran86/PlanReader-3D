from __future__ import annotations

from types import SimpleNamespace

from pb_physical_wall_identity import PhysicalEquivalenceClass
from pb_wall_finish_callout_wall_authority import (
    _local_owner_universe_safe,
    _target_provenance,
)
from pb_wall_finish_face_binding_authority import _Line, _Terminator


def _line(obs: str, raw: str, x1: float, y1: float, x2: float, y2: float) -> _Line:
    return _Line(
        observation_id=obs,
        raw_id=raw,
        geometry=(x1, y1, x2, y2),
    )


def _term(x0: float = 10.0, y0: float = 10.0, x1: float = 12.0, y1: float = 12.0) -> _Terminator:
    return _Terminator(
        primitive_id="term",
        bbox=(x0, y0, x1, y1),
        center=((x0 + x1) / 2.0, (y0 + y1) / 2.0),
    )


def _record(wall_id: str, *raw_ids: str):
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        physical_identity=SimpleNamespace(source_primitive_ids=tuple(raw_ids)),
    )


def test_unrelated_boundary_primitive_does_not_poison_local_owner_universe() -> None:
    wall_scope = SimpleNamespace(
        scope_boundary_observation_ids=("boundary-far",),
        ambiguous_source_observation_ids=(),
    )
    page_lines = (
        _line("boundary-far", "raw-far", 100.0, 100.0, 120.0, 100.0),
    )
    assert _local_owner_universe_safe(
        terminator=_term(),
        page_lines=page_lines,
        wall_scope=wall_scope,
    ) is True


def test_boundary_primitive_touching_terminator_blocks_local_owner_universe() -> None:
    wall_scope = SimpleNamespace(
        scope_boundary_observation_ids=("boundary-hit",),
        ambiguous_source_observation_ids=(),
    )
    page_lines = (
        _line("boundary-hit", "raw-hit", 0.0, 11.0, 20.0, 11.0),
    )
    assert _local_owner_universe_safe(
        terminator=_term(),
        page_lines=page_lines,
        wall_scope=wall_scope,
    ) is False


def test_ambiguous_primitive_touching_terminator_blocks_local_owner_universe() -> None:
    wall_scope = SimpleNamespace(
        scope_boundary_observation_ids=(),
        ambiguous_source_observation_ids=("amb-hit",),
    )
    page_lines = (
        _line("amb-hit", "raw-amb", 11.0, 0.0, 11.0, 20.0),
    )
    assert _local_owner_universe_safe(
        terminator=_term(),
        page_lines=page_lines,
        wall_scope=wall_scope,
    ) is False


def test_unreplayable_withheld_structural_observation_blocks_local_owner_universe() -> None:
    wall_scope = SimpleNamespace(
        scope_boundary_observation_ids=("missing",),
        ambiguous_source_observation_ids=(),
    )
    assert _local_owner_universe_safe(
        terminator=_term(),
        page_lines=(),
        wall_scope=wall_scope,
    ) is False


def test_positive_same_group_preserves_raw_owner_provenance() -> None:
    wall_scope = SimpleNamespace(
        records=(
            _record("wall-a", "face-a"),
            _record("wall-b", "face-b"),
            _record("grid", "grid-raw"),
        ),
        equivalence=SimpleNamespace(
            equivalence_groups=(("wall-a", "wall-b"),),
            pair_classifications=(
                (
                    "wall-a",
                    "wall-b",
                    PhysicalEquivalenceClass.SAME_PHYSICAL_WALL.value,
                ),
                (
                    "wall-a",
                    "grid",
                    PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS.value,
                ),
            ),
        ),
    )
    lines = (
        _line("obs-a", "face-a", 0.0, 11.0, 20.0, 11.0),
        _line("obs-b", "face-b", 0.0, 10.5, 20.0, 10.5),
    )
    target = wall_scope.records[0]

    raw_owners, group, pairs = _target_provenance(
        terminator=_term(),
        wall_lines=lines,
        wall_scope=wall_scope,
        target=target,
    )

    assert raw_owners == ("wall-a", "wall-b")
    assert group == ("wall-a", "wall-b")
    assert pairs == (
        (
            "wall-a",
            "wall-b",
            PhysicalEquivalenceClass.SAME_PHYSICAL_WALL.value,
        ),
    )


def test_unrelated_nearby_wall_is_not_added_to_equivalence_group() -> None:
    wall_scope = SimpleNamespace(
        records=(
            _record("wall-a", "face-a"),
            _record("wall-b", "face-b"),
            _record("nearby", "near-raw"),
        ),
        equivalence=SimpleNamespace(
            equivalence_groups=(("wall-a", "wall-b"),),
            pair_classifications=(),
        ),
    )
    lines = (
        _line("obs-a", "face-a", 0.0, 11.0, 20.0, 11.0),
        _line("obs-b", "face-b", 0.0, 10.5, 20.0, 10.5),
    )
    raw_owners, group, _pairs = _target_provenance(
        terminator=_term(),
        wall_lines=lines,
        wall_scope=wall_scope,
        target=wall_scope.records[0],
    )
    assert raw_owners == ("wall-a", "wall-b")
    assert group == ("wall-a", "wall-b")
    assert "nearby" not in group


def test_raw_owner_provenance_can_show_two_independent_walls_before_target_abstains() -> None:
    wall_scope = SimpleNamespace(
        records=(
            _record("wall-a", "face-a"),
            _record("wall-c", "face-c"),
        ),
        equivalence=SimpleNamespace(
            equivalence_groups=(),
            pair_classifications=(
                (
                    "wall-a",
                    "wall-c",
                    PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS.value,
                ),
            ),
        ),
    )
    lines = (
        _line("obs-a", "face-a", 0.0, 11.0, 20.0, 11.0),
        _line("obs-c", "face-c", 0.0, 10.8, 20.0, 10.8),
    )
    raw_owners, group, pairs = _target_provenance(
        terminator=_term(),
        wall_lines=lines,
        wall_scope=wall_scope,
        target=wall_scope.records[0],
    )
    assert raw_owners == ("wall-a", "wall-c")
    assert group == ("wall-a",)
    assert pairs == (
        (
            "wall-a",
            "wall-c",
            PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS.value,
        ),
    )
