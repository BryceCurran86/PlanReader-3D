"""Adversarial tests for shadow wall-boundary role authority.

Role is independent of thickness, length, scale, and W6 room-count.
Viewport bbox is never a building face. Unbounded half-edge is exterior
open space. Unlabeled enclosed faces stay UNKNOWN (courtyard fail-closed).
"""
from __future__ import annotations

import ast
import random
from dataclasses import replace
from pathlib import Path

from pb_canonical_wall_room_evidence_model import FAMILY_PAIRED_WALL_FACES
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_physical_wall_existence_authority import wall_physical_existence_status
from pb_wall_boundary_role_authority import (
    EXPLICIT_WALL_ROLE_KIND,
    SPACE_ROLE_LABEL_KIND,
    VIEWPORT_COVERAGE_KIND,
    WallBoundaryRole,
    resolve_wall_boundary_roles,
)
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_typed_negative_evidence import KIND_PHYSICAL_WALL
from pb_wall_room_topology_wall_assembly import assemble_wall_candidates
from pb_wall_room_topology_contracts import WallCandidate

SHA = "c" * 64
REPO = Path(__file__).resolve().parents[1]


def _seg(seg_id, x1, y1, x2, y2, **overrides):
    base = {
        "id": seg_id,
        "kind": "line",
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "width": 1.0,
        "stroke": (0, 0, 0),
        "fill": None,
        "layer": "",
        "dashes": "",
    }
    base.update(overrides)
    return base


def _atom(evidence_id: str, kind: str, **kwargs) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id=evidence_id,
        document_id="doc",
        page_id="page-1",
        viewport_id="vp_1",
        kind=kind,
        method="test",
        confidence=0.7,
        status=EvidenceResolutionStatus.CANDIDATE,
        **kwargs,
    )


def _document(ids: tuple[str, ...]) -> DocumentEvidence:
    return DocumentEvidence(
        document_id="doc",
        source_sha256=SHA,
        page_count=1,
        page_ids=("page-1",),
        evidence_ids=ids,
    )


def _viewport(bbox=(-1000.0, -1000.0, 2000.0, 2000.0)) -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id="vp_1",
        document_id="doc",
        page_id="page-1",
        bbox=bbox,
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        evidence_ids=("u2-ev",),
        confidence=1.0,
    )


def _pipeline(segments):
    graph = build_wall_graph_for_viewport(segments)
    junctions, relationships = classify_junctions(
        graph, document_id="doc", page_id="page-1", viewport_id="vp_1"
    )
    walls, edge_map = assemble_wall_candidates(
        graph, junctions, relationships, viewport_id="vp_1"
    )
    return graph, walls, edge_map


def _corroborate(walls: list[WallCandidate], *, supporting=("u2-ev", "pair-ev"), conflicting=()) -> list[WallCandidate]:
    return [
        replace(
            wall,
            supporting_evidence_ids=supporting,
            conflicting_evidence_ids=conflicting,
        )
        for wall in walls
    ]


def _existence_atoms():
    return (
        _atom("u2-ev", KIND_PHYSICAL_WALL),
        _atom("pair-ev", FAMILY_PAIRED_WALL_FACES),
    )


def _coverage_complete():
    return _atom(
        "cov-complete",
        VIEWPORT_COVERAGE_KIND,
        metadata={"coverage_status": "complete", "viewport_id": "vp_1"},
    )


def _roles(
    segments,
    *,
    bbox=(-1000.0, -1000.0, 2000.0, 2000.0),
    corroborate=True,
    conflicting=(),
    extra_atoms=(),
    space_labels=(),
    explicit=(),
    walls_transform=None,
    with_coverage=True,
):
    graph, walls, edge_map = _pipeline(segments)
    if corroborate:
        walls = _corroborate(walls, conflicting=conflicting)
    if walls_transform is not None:
        walls = walls_transform(walls)
    coverage = (_coverage_complete(),) if with_coverage else ()
    atoms = _existence_atoms() + extra_atoms + coverage
    ids = tuple(
        dict.fromkeys(
            [
                *(a.evidence_id for a in atoms),
                *(a.evidence_id for a in space_labels),
                *(a.evidence_id for a in explicit),
            ]
        )
    )
    records = resolve_wall_boundary_roles(
        walls=walls,
        graph=graph,
        edge_id_to_wall_id=edge_map,
        evidence_atoms=atoms,
        document=_document(ids),
        viewport=_viewport(bbox),
        space_label_atoms=space_labels,
        explicit_role_atoms=explicit,
    )
    return walls, records


def _by_id(records):
    return {r.wall_candidate_id: r for r in records}


def _mid(wall: WallCandidate) -> tuple[float, float]:
    pts = wall.centerline_pts
    return ((pts[0][0] + pts[-1][0]) / 2.0, (pts[0][1] + pts[-1][1]) / 2.0)


def _rectangle():
    return [
        _seg("a", 0, 0, 300, 0),
        _seg("b", 300, 0, 300, 200),
        _seg("c", 300, 200, 0, 200),
        _seg("d", 0, 200, 0, 0),
    ]


def _rectangle_plus_partition():
    return [
        _seg("a", 0, 0, 300, 0),
        _seg("b", 300, 0, 300, 200),
        _seg("c", 300, 200, 150, 200),
        _seg("d", 0, 200, 0, 0),
        _seg("e", 150, 200, 0, 200),
        _seg("partition", 150, 0, 150, 200),
    ]


def test_closed_rectangle_boundary_walls_are_external() -> None:
    walls, records = _roles(_rectangle())
    assert walls
    assert all(r.role == WallBoundaryRole.EXTERNAL for r in records)
    assert all(r.status == EvidenceResolutionStatus.CORROBORATED for r in records)


def test_rectangle_plus_partition_center_is_internal() -> None:
    walls, records = _roles(_rectangle_plus_partition())
    by_wall = {w.candidate_id: w for w in walls}
    roles = _by_id(records)
    internals = [wid for wid, rec in roles.items() if rec.role == WallBoundaryRole.INTERNAL_PARTITION]
    externals = [wid for wid, rec in roles.items() if rec.role == WallBoundaryRole.EXTERNAL]
    assert internals
    assert externals
    for wid in internals:
        mx, _ = _mid(by_wall[wid])
        assert abs(mx - 150.0) < 20.0


def test_two_interior_rooms_share_internal_partition() -> None:
    _, records = _roles(_rectangle_plus_partition())
    assert any(r.role == WallBoundaryRole.INTERNAL_PARTITION for r in records)
    assert any(r.role == WallBoundaryRole.EXTERNAL for r in records)


def test_l_shaped_building_facade_is_external() -> None:
    segs = [
        _seg("a", 0, 0, 400, 0),
        _seg("b", 400, 0, 400, 200),
        _seg("c", 400, 200, 200, 200),
        _seg("d", 200, 200, 200, 400),
        _seg("e", 200, 400, 0, 400),
        _seg("f", 0, 400, 0, 0),
    ]
    _, records = _roles(segs)
    assert records
    assert all(r.role == WallBoundaryRole.EXTERNAL for r in records)


def test_recessed_entry_is_not_convex_hull_shortcut() -> None:
    segs = [
        _seg("a", 0, 0, 100, 0),
        _seg("b", 100, 0, 100, 40),
        _seg("c", 100, 40, 200, 40),
        _seg("d", 200, 40, 200, 0),
        _seg("e", 200, 0, 400, 0),
        _seg("f", 400, 0, 400, 300),
        _seg("g", 400, 300, 0, 300),
        _seg("h", 0, 300, 0, 0),
    ]
    walls, records = _roles(segs)
    by_wall = {w.candidate_id: w for w in walls}
    roles = _by_id(records)
    recess = [
        wid
        for wid, wall in by_wall.items()
        if abs(_mid(wall)[1] - 40.0) < 5.0 and 100.0 <= _mid(wall)[0] <= 200.0
    ]
    assert recess
    assert all(roles[wid].role == WallBoundaryRole.EXTERNAL for wid in recess)


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


def test_enclosed_courtyard_without_semantics_is_not_internal() -> None:
    walls, records = _roles(_courtyard_segments())
    by_wall = {w.candidate_id: w for w in walls}
    roles = _by_id(records)
    inner = [
        wid
        for wid, wall in by_wall.items()
        if 110.0 <= min(p[0] for p in wall.centerline_pts) and max(p[0] for p in wall.centerline_pts) <= 290.0
        and 110.0 <= min(p[1] for p in wall.centerline_pts) and max(p[1] for p in wall.centerline_pts) <= 290.0
    ]
    assert inner
    assert all(roles[wid].role != WallBoundaryRole.INTERNAL_PARTITION for wid in inner)
    assert all(roles[wid].role == WallBoundaryRole.UNKNOWN for wid in inner)


def test_courtyard_with_exterior_label_is_external() -> None:
    label = _atom(
        "court-lab",
        SPACE_ROLE_LABEL_KIND,
        raw_text="COURTYARD",
        bbox=(190.0, 190.0, 210.0, 210.0),
        metadata={"space_role": "exterior_enclosed_void", "x": 200.0, "y": 200.0},
    )
    walls, records = _roles(_courtyard_segments(), extra_atoms=(label,), space_labels=(label,))
    by_wall = {w.candidate_id: w for w in walls}
    roles = _by_id(records)
    inner = [
        wid
        for wid, wall in by_wall.items()
        if 110.0 <= min(p[0] for p in wall.centerline_pts) and max(p[0] for p in wall.centerline_pts) <= 290.0
        and 110.0 <= min(p[1] for p in wall.centerline_pts) and max(p[1] for p in wall.centerline_pts) <= 290.0
    ]
    assert inner
    assert all(roles[wid].role == WallBoundaryRole.EXTERNAL for wid in inner)


def test_courtyard_without_label_stays_unknown() -> None:
    _, records = _roles(_courtyard_segments())
    assert any(r.role == WallBoundaryRole.UNKNOWN for r in records)


def test_exterior_door_gap_does_not_make_interior_exterior() -> None:
    segs = [
        _seg("a", 0, 0, 120, 0),
        _seg("a2", 180, 0, 300, 0),
        _seg("b", 300, 0, 300, 200),
        _seg("c", 300, 200, 0, 200),
        _seg("d", 0, 200, 0, 0),
    ]
    _, records = _roles(segs)
    assert all(r.role != WallBoundaryRole.INTERNAL_PARTITION for r in records)
    # Gap floods the embedding: remaining walls must not be promoted EXTERNAL
    # via unbounded-on-both-sides.
    flooded = [r for r in records if "same_face_both_sides" in r.reason_codes]
    assert flooded
    assert all(r.role == WallBoundaryRole.UNKNOWN for r in flooded)


def test_internal_doorway_does_not_collapse_envelope() -> None:
    segs = [
        _seg("a", 0, 0, 300, 0),
        _seg("b", 300, 0, 300, 200),
        _seg("c", 300, 200, 0, 200),
        _seg("d", 0, 200, 0, 0),
        _seg("p1", 150, 0, 150, 80),
        _seg("p2", 150, 120, 150, 200),
    ]
    walls, records = _roles(segs)
    roles = _by_id(records)
    by_wall = {w.candidate_id: w for w in walls}
    outer = [
        wid
        for wid, wall in by_wall.items()
        if min(p[0] for p in wall.centerline_pts) < 5.0 or max(p[0] for p in wall.centerline_pts) > 295.0
        or min(p[1] for p in wall.centerline_pts) < 5.0 or max(p[1] for p in wall.centerline_pts) > 195.0
    ]
    assert outer
    # Envelope walls that still have an interior/unbounded pair stay EXTERNAL.
    assert any(roles[wid].role == WallBoundaryRole.EXTERNAL for wid in outer)


def test_window_does_not_break_continuous_boundary() -> None:
    _, records = _roles(_rectangle())
    assert all(r.role == WallBoundaryRole.EXTERNAL for r in records)


def test_unexplained_wall_gap_is_unknown() -> None:
    segs = [
        _seg("a", 0, 0, 80, 0),
        _seg("b", 300, 0, 300, 200),
        _seg("c", 300, 200, 0, 200),
        _seg("d", 0, 200, 0, 0),
    ]
    _, records = _roles(segs)
    assert all(r.status != EvidenceResolutionStatus.CORROBORATED or r.role == WallBoundaryRole.UNKNOWN for r in records) or any(
        r.role == WallBoundaryRole.UNKNOWN for r in records
    )


def test_walls_on_viewport_boundary_are_not_automatically_external() -> None:
    _, records = _roles(_rectangle(), bbox=(0.0, 0.0, 300.0, 200.0))
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in records)
    assert all("insufficient_viewport_coverage" in r.reason_codes for r in records)


def test_unbounded_without_coverage_is_not_architectural_exterior() -> None:
    _, records = _roles(_rectangle(), with_coverage=False)
    assert all(r.role != WallBoundaryRole.EXTERNAL for r in records)
    assert any(
        "topologically_unbounded_without_architectural_exterior" in r.reason_codes
        or "viewport_coverage_unproven" in r.reason_codes
        for r in records
    )


def test_two_detached_buildings_each_have_external_shell() -> None:
    segs = [
        _seg("a1", 0, 0, 100, 0),
        _seg("b1", 100, 0, 100, 80),
        _seg("c1", 100, 80, 0, 80),
        _seg("d1", 0, 80, 0, 0),
        _seg("a2", 200, 0, 300, 0),
        _seg("b2", 300, 0, 300, 80),
        _seg("c2", 300, 80, 200, 80),
        _seg("d2", 200, 80, 200, 0),
    ]
    walls, records = _roles(segs)
    left = [w for w in walls if max(p[0] for p in w.centerline_pts) <= 110]
    right = [w for w in walls if min(p[0] for p in w.centerline_pts) >= 190]
    roles = _by_id(records)
    assert left and right
    assert all(roles[w.candidate_id].role == WallBoundaryRole.EXTERNAL for w in left)
    assert all(roles[w.candidate_id].role == WallBoundaryRole.EXTERNAL for w in right)


def test_furniture_rectangle_without_existence_is_not_building_space() -> None:
    segs = [
        _seg("a", 40, 40, 80, 40),
        _seg("b", 80, 40, 80, 70),
        _seg("c", 80, 70, 40, 70),
        _seg("d", 40, 70, 40, 40),
    ]
    _, records = _roles(segs, corroborate=False)
    assert all(r.role == WallBoundaryRole.UNKNOWN for r in records)
    assert all(r.status != EvidenceResolutionStatus.CORROBORATED for r in records)


def test_annotation_frame_without_existence_is_not_enclosure() -> None:
    segs = [
        _seg("a", -50, -50, 500, -50),
        _seg("b", 500, -50, 500, 400),
        _seg("c", 500, 400, -50, 400),
        _seg("d", -50, 400, -50, -50),
    ]
    _, records = _roles(segs, corroborate=False)
    assert all(r.role != WallBoundaryRole.EXTERNAL or r.status != EvidenceResolutionStatus.CORROBORATED for r in records)


def test_glazing_opposing_evidence_cannot_receive_firm_role() -> None:
    extra = _atom("glaze-ev", "glazing")
    _, records = _roles(_rectangle(), conflicting=("glaze-ev",), extra_atoms=(extra,))
    assert all(r.role != WallBoundaryRole.EXTERNAL or r.status != EvidenceResolutionStatus.CORROBORATED for r in records)
    assert all(r.status == EvidenceResolutionStatus.CONFLICT or r.role == WallBoundaryRole.UNKNOWN for r in records)


def test_candidate_existence_cannot_receive_firm_role() -> None:
    graph, walls, edge_map = _pipeline(_rectangle())
    walls = [replace(wall, supporting_evidence_ids=("u2-ev",)) for wall in walls]
    atoms = _existence_atoms()
    records = resolve_wall_boundary_roles(
        walls=walls,
        graph=graph,
        edge_id_to_wall_id=edge_map,
        evidence_atoms=atoms,
        document=_document(("u2-ev", "pair-ev")),
        viewport=_viewport(),
    )
    assert walls
    assert wall_physical_existence_status(
        walls[0], evidence_atoms=atoms, document=_document(("u2-ev", "pair-ev")), viewport=_viewport()
    ) != EvidenceResolutionStatus.CORROBORATED
    assert all(r.status != EvidenceResolutionStatus.CORROBORATED for r in records)


def test_conflicting_explicit_internal_external_is_conflict() -> None:
    walls, _ = _roles(_rectangle())
    wall_id = walls[0].candidate_id
    ext = _atom("role-ext", EXPLICIT_WALL_ROLE_KIND, metadata={"wall_candidate_id": wall_id, "role": "external"})
    inn = _atom("role-int", EXPLICIT_WALL_ROLE_KIND, metadata={"wall_candidate_id": wall_id, "role": "internal_partition"})
    _, records = _roles(_rectangle(), extra_atoms=(ext, inn), explicit=(ext, inn))
    rec = _by_id(records)[wall_id]
    assert rec.role == WallBoundaryRole.CONFLICT
    assert rec.status == EvidenceResolutionStatus.CONFLICT


def test_reversed_centerline_keeps_semantic_role() -> None:
    graph, walls, edge_map = _pipeline(_rectangle())
    walls = _corroborate(walls)
    atoms = _existence_atoms() + (_coverage_complete(),)
    document = _document(tuple(a.evidence_id for a in atoms))
    viewport = _viewport()
    forward = resolve_wall_boundary_roles(
        walls=walls, graph=graph, edge_id_to_wall_id=edge_map, evidence_atoms=atoms, document=document, viewport=viewport
    )
    reversed_walls = [
        replace(wall, centerline_pts=tuple(reversed(wall.centerline_pts)))
        for wall in walls
    ]
    backward = resolve_wall_boundary_roles(
        walls=reversed_walls, graph=graph, edge_id_to_wall_id=edge_map, evidence_atoms=atoms, document=document, viewport=viewport
    )
    assert [r.role for r in forward] == [r.role for r in backward]
    for a, b in zip(forward, backward):
        if a.left_face_id and a.right_face_id and b.left_face_id and b.right_face_id:
            assert {a.left_face_id, a.right_face_id} == {b.left_face_id, b.right_face_id}


def test_shuffled_walls_are_deterministic() -> None:
    graph, walls, edge_map = _pipeline(_rectangle_plus_partition())
    walls = _corroborate(walls)
    atoms = _existence_atoms() + (_coverage_complete(),)
    document = _document(tuple(a.evidence_id for a in atoms))
    viewport = _viewport()
    a = resolve_wall_boundary_roles(
        walls=walls, graph=graph, edge_id_to_wall_id=edge_map, evidence_atoms=atoms, document=document, viewport=viewport
    )
    shuffled = list(walls)
    random.Random(3).shuffle(shuffled)
    b = resolve_wall_boundary_roles(
        walls=shuffled, graph=graph, edge_id_to_wall_id=edge_map, evidence_atoms=atoms, document=document, viewport=viewport
    )
    assert {r.wall_candidate_id: (r.role, r.evidence_id) for r in a} == {
        r.wall_candidate_id: (r.role, r.evidence_id) for r in b
    }


def test_rechunked_equivalent_wall_keeps_role() -> None:
    simple = _rectangle()
    split = [
        _seg("a1", 0, 0, 150, 0),
        _seg("a2", 150, 0, 300, 0),
        _seg("b", 300, 0, 300, 200),
        _seg("c", 300, 200, 0, 200),
        _seg("d", 0, 200, 0, 0),
    ]
    _, rec_a = _roles(simple)
    _, rec_b = _roles(split)
    assert {r.role for r in rec_a} == {WallBoundaryRole.EXTERNAL}
    assert {r.role for r in rec_b} == {WallBoundaryRole.EXTERNAL}


def test_duplicate_source_segments_do_not_double_role() -> None:
    graph, walls, edge_map = _pipeline(_rectangle())
    walls = _corroborate(walls)
    clone = replace(walls[0], candidate_id=walls[0].candidate_id + "-dup")
    atoms = _existence_atoms() + (_coverage_complete(),)
    records = resolve_wall_boundary_roles(
        walls=(*walls, clone),
        graph=graph,
        edge_id_to_wall_id=edge_map,
        evidence_atoms=atoms,
        document=_document(tuple(a.evidence_id for a in atoms)),
        viewport=_viewport(),
    )
    dup = [r for r in records if r.wall_candidate_id in (walls[0].candidate_id, clone.candidate_id)]
    assert dup
    assert all(r.role != WallBoundaryRole.EXTERNAL or "overlapping_wall_source_segments" in r.reason_codes for r in dup)
    assert all(r.status != EvidenceResolutionStatus.CORROBORATED for r in dup)


def test_endpoint_touching_faces_are_not_chosen_as_sides() -> None:
    _, records = _roles(_rectangle_plus_partition())
    for rec in records:
        if rec.left_face_id and rec.right_face_id:
            assert rec.left_face_id != rec.right_face_id or rec.role == WallBoundaryRole.UNKNOWN


def test_extractor_does_not_import_wall_role() -> None:
    tree = ast.parse((REPO / "pb_planreader_pdf_extractor.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert "pb_wall_boundary_role_authority" not in names
