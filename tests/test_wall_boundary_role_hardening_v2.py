"""Hardening-v2 adversarial attacks for wall-boundary role (crop / courtyard / openings).

These tests are expected to FAIL on fae9327 until coverage authority is required
before treating TOPOLOGICALLY_UNBOUNDED as ARCHITECTURAL_EXTERIOR_OPEN_SPACE.
"""
from __future__ import annotations

from dataclasses import replace

from pb_migration_contracts import EvidenceResolutionStatus
from pb_wall_boundary_role_authority import (
    SPACE_ROLE_LABEL_KIND,
    VIEWPORT_COVERAGE_KIND,
    WallBoundaryRole,
    resolve_wall_boundary_roles,
)
from tests.test_wall_boundary_role_authority import (
    _atom,
    _atoms_for_walls,
    _by_id,
    _context,
    _corroborate,
    _document,
    _existence_atoms,
    _mid,
    _owned_metadata,
    _pipeline,
    _rectangle,
    _rectangle_plus_partition,
    _roles,
    _seg,
    _viewport,
)


def _coverage_complete():
    return _atom(
        "cov-complete",
        VIEWPORT_COVERAGE_KIND,
        metadata=_owned_metadata(coverage_status="complete", viewport_id="vp_1"),
    )


def _coverage_incomplete():
    return _atom(
        "cov-incomplete",
        VIEWPORT_COVERAGE_KIND,
        metadata=_owned_metadata(coverage_status="incomplete", viewport_id="vp_1"),
    )


def _roles_with_coverage(segments, *, coverage=None, **kwargs):
    coverage = coverage if coverage is not None else (_coverage_complete(),)
    extra = kwargs.pop("extra_atoms", ())
    return _roles(segments, extra_atoms=extra + coverage, with_coverage=False, **kwargs)


# ---------------------------------------------------------------------------
# 1. Cropped viewport safety
# ---------------------------------------------------------------------------


def test_building_clipped_on_left_edge_cannot_mint_external_without_coverage() -> None:
    """Left half of a larger building: crop opens faces to unbounded."""
    segs = [
        _seg("bot", 0, 0, 150, 0),
        _seg("right", 150, 0, 150, 200),
        _seg("top", 150, 200, 0, 200),
        _seg("left", 0, 200, 0, 0),
        _seg("part", 75, 0, 75, 200),
    ]
    # Viewport crop coincides with the visible fragment extent — walls are NOT
    # all on the bbox, but topology is incomplete relative to the full building.
    _, records = _roles(segs, bbox=(-50.0, -50.0, 160.0, 250.0), with_coverage=False)
    assert records
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in records)
    assert all(r.status != EvidenceResolutionStatus.CORROBORATED or r.role == WallBoundaryRole.UNKNOWN for r in records)


def test_building_clipped_on_top_edge_abstains_external() -> None:
    segs = [
        _seg("a", 0, 0, 300, 0),
        _seg("b", 300, 0, 300, 120),
        _seg("c", 300, 120, 0, 120),
        _seg("d", 0, 120, 0, 0),
    ]
    _, records = _roles(segs, bbox=(-20.0, -20.0, 320.0, 130.0), with_coverage=False)
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in records)


def test_room_partially_outside_viewport_cannot_force_exterior() -> None:
    segs = [
        _seg("a", 0, 0, 200, 0),
        _seg("b", 200, 0, 200, 200),
        _seg("c", 200, 200, 0, 200),
        _seg("d", 0, 200, 0, 0),
        _seg("p", 100, 0, 100, 200),
    ]
    _, records = _roles(segs, bbox=(50.0, -50.0, 250.0, 250.0), with_coverage=False)
    # Crop cuts through the left room; no coverage authority → no EXTERNAL.
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in records)


def test_corridor_cut_by_crop_stays_unknown() -> None:
    segs = [
        _seg("a", 0, 0, 400, 0),
        _seg("b", 400, 0, 400, 80),
        _seg("c", 400, 80, 0, 80),
        _seg("d", 0, 80, 0, 0),
    ]
    _, records = _roles(segs, bbox=(100.0, -20.0, 300.0, 100.0), with_coverage=False)
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in records)


def test_wall_side_disappearing_beyond_crop_is_unknown() -> None:
    segs = [
        _seg("a", 0, 0, 200, 0),
        _seg("b", 200, 0, 200, 150),
        _seg("c", 200, 150, 0, 150),
        _seg("d", 0, 150, 0, 0),
    ]
    _, records = _roles(segs, bbox=(0.0, 0.0, 180.0, 150.0), with_coverage=False)
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in records)


def test_multiple_disconnected_plan_fragments_without_coverage_abstain() -> None:
    segs = [
        _seg("a1", 0, 0, 80, 0),
        _seg("b1", 80, 0, 80, 60),
        _seg("c1", 80, 60, 0, 60),
        _seg("d1", 0, 60, 0, 0),
        _seg("a2", 200, 0, 280, 0),
        _seg("b2", 280, 0, 280, 60),
        _seg("c2", 280, 60, 200, 60),
        _seg("d2", 200, 60, 200, 0),
    ]
    _, records = _roles(segs, with_coverage=False)
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in records)


def test_viewport_with_only_one_room_from_larger_building_abstains() -> None:
    segs = _rectangle_plus_partition()
    _, records = _roles(segs, bbox=(0.0, 0.0, 160.0, 200.0), with_coverage=False)
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in records)


def test_incomplete_coverage_atom_blocks_external_even_for_closed_shell() -> None:
    _, records = _roles_with_coverage(_rectangle(), coverage=(_coverage_incomplete(),))
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in records)
    assert any("coverage" in " ".join(r.reason_codes).lower() or "unbounded" in " ".join(r.reason_codes) for r in records)


def test_complete_coverage_allows_closed_shell_external() -> None:
    _, records = _roles_with_coverage(_rectangle())
    assert records
    assert all(r.role == WallBoundaryRole.EXTERNAL for r in records)
    assert all(r.status == EvidenceResolutionStatus.CORROBORATED for r in records)


# ---------------------------------------------------------------------------
# 2. Courtyard / lightwell / shafts
# ---------------------------------------------------------------------------


def _courtyard_segments():
    return [
        _seg("o1", 0, 0, 400, 0),
        _seg("o2", 400, 0, 400, 400),
        _seg("o3", 400, 400, 0, 400),
        _seg("o4", 0, 400, 0, 0),
        _seg("i1", 120, 120, 280, 120),
        _seg("i2", 280, 120, 280, 280),
        _seg("i3", 280, 280, 120, 280),
        _seg("i4", 120, 280, 120, 120),
    ]


def test_unlabeled_bounded_hole_is_not_courtyard() -> None:
    walls, records = _roles_with_coverage(_courtyard_segments())
    roles = _by_id(records)
    by_wall = {w.candidate_id: w for w in walls}
    inner = [
        wid
        for wid, wall in by_wall.items()
        if 110.0 <= min(p[0] for p in wall.centerline_pts)
        and max(p[0] for p in wall.centerline_pts) <= 290.0
        and 110.0 <= min(p[1] for p in wall.centerline_pts)
        and max(p[1] for p in wall.centerline_pts) <= 290.0
    ]
    assert inner
    assert all(roles[wid].role == WallBoundaryRole.UNKNOWN for wid in inner)


def test_lift_shaft_unlabeled_stays_unknown() -> None:
    label = _atom(
        "shaft-lab",
        SPACE_ROLE_LABEL_KIND,
        raw_text="LIFT SHAFT",
        bbox=(190.0, 190.0, 210.0, 210.0),
        metadata={"x": 200.0, "y": 200.0},
    )
    # Text alone without explicit space_role must not invent courtyard/exterior.
    walls, records = _roles_with_coverage(
        _courtyard_segments(), extra_atoms=(label,), space_labels=(label,)
    )
    roles = _by_id(records)
    by_wall = {w.candidate_id: w for w in walls}
    inner = [
        wid
        for wid, wall in by_wall.items()
        if 110.0 <= min(p[0] for p in wall.centerline_pts)
        and max(p[0] for p in wall.centerline_pts) <= 290.0
    ]
    assert inner
    assert all(roles[wid].role != WallBoundaryRole.INTERNAL_PARTITION for wid in inner)


def test_stair_void_unlabeled_not_building_interior() -> None:
    _, records = _roles_with_coverage(_courtyard_segments())
    assert any(r.role == WallBoundaryRole.UNKNOWN for r in records)


def test_two_adjacent_holes_different_semantics() -> None:
    segs = [
        _seg("o1", 0, 0, 500, 0),
        _seg("o2", 500, 0, 500, 300),
        _seg("o3", 500, 300, 0, 300),
        _seg("o4", 0, 300, 0, 0),
        _seg("a1", 40, 40, 160, 40),
        _seg("a2", 160, 40, 160, 160),
        _seg("a3", 160, 160, 40, 160),
        _seg("a4", 40, 160, 40, 40),
        _seg("b1", 300, 40, 420, 40),
        _seg("b2", 420, 40, 420, 160),
        _seg("b3", 420, 160, 300, 160),
        _seg("b4", 300, 160, 300, 40),
    ]
    court = _atom(
        "c-lab",
        SPACE_ROLE_LABEL_KIND,
        raw_text="COURTYARD",
        bbox=(90.0, 90.0, 110.0, 110.0),
        metadata={"space_role": "exterior_enclosed_void", "x": 100.0, "y": 100.0},
    )
    # Right hole unlabeled → must not inherit courtyard semantics.
    walls, records = _roles_with_coverage(segs, extra_atoms=(court,), space_labels=(court,))
    roles = _by_id(records)
    by_wall = {w.candidate_id: w for w in walls}
    right_inner = [
        wid
        for wid, wall in by_wall.items()
        if min(p[0] for p in wall.centerline_pts) >= 290.0
        and max(p[0] for p in wall.centerline_pts) <= 430.0
        and min(p[1] for p in wall.centerline_pts) >= 30.0
        and max(p[1] for p in wall.centerline_pts) <= 170.0
    ]
    assert right_inner
    assert all(roles[wid].role == WallBoundaryRole.UNKNOWN for wid in right_inner)


# ---------------------------------------------------------------------------
# 3. Openings / same-face / covered external / monotonicity
# ---------------------------------------------------------------------------


def test_external_wall_with_door_gap_does_not_create_false_internal() -> None:
    segs = [
        _seg("a", 0, 0, 120, 0),
        _seg("a2", 180, 0, 300, 0),
        _seg("b", 300, 0, 300, 200),
        _seg("c", 300, 200, 0, 200),
        _seg("d", 0, 200, 0, 0),
    ]
    _, records = _roles_with_coverage(segs)
    assert all(r.role != WallBoundaryRole.INTERNAL_PARTITION for r in records)


def test_wide_opening_and_corner_opening_fail_closed() -> None:
    segs = [
        _seg("a", 0, 0, 50, 0),
        _seg("a2", 250, 0, 300, 0),
        _seg("b", 300, 0, 300, 200),
        _seg("c", 300, 200, 0, 200),
        _seg("d", 0, 200, 0, 20),
    ]
    _, records = _roles_with_coverage(segs)
    assert not any(
        r.role == WallBoundaryRole.EXTERNAL and r.status == EvidenceResolutionStatus.CORROBORATED
        for r in records
    ) or any(r.role == WallBoundaryRole.UNKNOWN for r in records)


def test_same_face_both_sides_is_unknown() -> None:
    segs = [
        _seg("stub", 0, 0, 100, 0),
        _seg("a", 0, 50, 200, 50),
        _seg("b", 200, 50, 200, 150),
        _seg("c", 200, 150, 0, 150),
        _seg("d", 0, 150, 0, 50),
    ]
    walls, records = _roles_with_coverage(segs)
    roles = _by_id(records)
    stubs = [w for w in walls if abs(_mid(w)[1]) < 5.0]
    if stubs:
        assert all(roles[w.candidate_id].role == WallBoundaryRole.UNKNOWN for w in stubs)


def test_covered_open_space_not_collapsed_to_building_interior() -> None:
    segs = [
        _seg("a", 0, 0, 300, 0),
        _seg("b", 300, 0, 300, 200),
        _seg("c", 300, 200, 0, 200),
        _seg("d", 0, 200, 0, 0),
        _seg("p", 150, 0, 150, 200),
    ]
    verandah = _atom(
        "ver-lab",
        SPACE_ROLE_LABEL_KIND,
        raw_text="VERANDAH",
        bbox=(200.0, 80.0, 220.0, 100.0),
        metadata={"space_role": "covered_open_space", "x": 210.0, "y": 90.0},
    )
    walls, records = _roles_with_coverage(segs, extra_atoms=(verandah,), space_labels=(verandah,))
    roles = _by_id(records)
    by_wall = {w.candidate_id: w for w in walls}
    partition = [w for w in walls if abs(_mid(w)[0] - 150.0) < 10.0]
    assert partition
    for w in partition:
        rec = roles[w.candidate_id]
        # Partition between interior and covered external must not be INTERNAL_PARTITION.
        assert rec.role != WallBoundaryRole.INTERNAL_PARTITION


def test_removing_coverage_cannot_preserve_external() -> None:
    with_cov = _roles_with_coverage(_rectangle())[1]
    assert any(r.role == WallBoundaryRole.EXTERNAL for r in with_cov)
    without = _roles(_rectangle(), with_coverage=False)[1]
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in without)


def test_duplicate_coverage_cannot_strengthen_role() -> None:
    cov = _coverage_complete()
    twin = replace(cov, evidence_id="cov-complete-copy")
    first = _roles_with_coverage(_rectangle(), coverage=(cov,))[1]
    doubled = _roles_with_coverage(_rectangle(), coverage=(cov, twin))[1]
    assert {(r.wall_candidate_id, r.role, r.status) for r in first} == {
        (r.wall_candidate_id, r.role, r.status) for r in doubled
    }


def test_direction_reversal_invariant_with_coverage() -> None:
    graph, walls, edge_map = _pipeline(_rectangle())
    walls = _corroborate(walls)
    atoms = _atoms_for_walls(walls) + (_coverage_complete(),)
    document = _document(tuple(a.evidence_id for a in atoms))
    viewport = _viewport()
    context = _context()
    forward = resolve_wall_boundary_roles(
        walls=walls,
        graph=graph,
        edge_id_to_wall_id=edge_map,
        evidence_atoms=atoms,
        document=document,
        viewport=viewport,
        context=context,
    )
    reversed_walls = [replace(w, centerline_pts=tuple(reversed(w.centerline_pts))) for w in walls]
    backward = resolve_wall_boundary_roles(
        walls=reversed_walls,
        graph=graph,
        edge_id_to_wall_id=edge_map,
        evidence_atoms=atoms,
        document=document,
        viewport=viewport,
        context=context,
    )
    assert {(r.wall_candidate_id, r.role, r.status) for r in forward} == {
        (r.wall_candidate_id, r.role, r.status) for r in backward
    }


def test_rechunk_collinear_edges_keeps_role_with_coverage() -> None:
    base = [
        _seg("a", 0, 0, 300, 0),
        _seg("b", 300, 0, 300, 200),
        _seg("c", 300, 200, 0, 200),
        _seg("d", 0, 200, 0, 0),
    ]
    rechunked = [
        _seg("a1", 0, 0, 150, 0),
        _seg("a2", 150, 0, 300, 0),
        _seg("b", 300, 0, 300, 200),
        _seg("c", 300, 200, 0, 200),
        _seg("d", 0, 200, 0, 0),
    ]
    _, r1 = _roles_with_coverage(base)
    _, r2 = _roles_with_coverage(rechunked)
    assert all(r.role == WallBoundaryRole.EXTERNAL for r in r1)
    assert all(r.role == WallBoundaryRole.EXTERNAL for r in r2)
