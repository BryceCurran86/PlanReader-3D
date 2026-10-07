"""SHADOW per-face boundary-ownership evaluation on SourceRoomFaceScopeResult.

The evaluation is the face-level twin of the wall-scope boundary evaluation: it
reports, per planar face, whether every face edge has a unique authenticated
wall owner (the rule that fails a whole scope with
``source_room_face_boundary_unresolved``). It must never change a decision, so
these tests pin (a) that it mirrors the production ownership rule exactly,
(b) that the legacy outcome is independent of it, and (c) the invariances every
geometric hypothesis in this repository must satisfy.
"""
from __future__ import annotations

import math
import random
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

import pb_source_room_face_authority as R
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _record(wall_id, first, second):
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        wall_candidate=SimpleNamespace(centerline_pts=(first, second)),
    )


def _scope(records, *, complete=True, status=EvidenceResolutionStatus.CORROBORATED):
    return SimpleNamespace(
        status=status,
        scope_complete=complete,
        records=tuple(records),
        document_id="doc-own",
        revision_id="rev-own",
        source_sha256="e" * 64,
        snapshot_id="snap-own",
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )


def _box(prefix, x0, y0, x1, y1):
    return [
        _record(f"{prefix}-top", (x0, y0), (x1, y0)),
        _record(f"{prefix}-right", (x1, y0), (x1, y1)),
        _record(f"{prefix}-bottom", (x1, y1), (x0, y1)),
        _record(f"{prefix}-left", (x0, y1), (x0, y0)),
    ]


def _two_rooms():
    return _box("room", 0.0, 0.0, 20.0, 10.0) + [
        _record("partition", (10.0, 0.0), (10.0, 10.0))
    ]


def _with_competing_owner():
    # A second wall overlapping part of the top wall: the planarized sub-edges
    # along the overlap have two competing containing walls.
    return _two_rooms() + [_record("dup-top", (5.0, 0.0), (15.0, 0.0))]


def _decision(result):
    """Everything the legacy derivation decides (the evaluation is excluded)."""
    return (
        result.status,
        result.scope_complete,
        result.reason_codes,
        tuple(r.record_id for r in result.records),
        tuple((a.face_id, a.reason) for a in result.abstained_faces),
        result.face_universe_complete,
    )


def _ownership_inputs(records):
    wall_edges, edge_owner = {}, {}
    for record in records:
        wall_id = R._clean(record.wall_candidate_id)
        edges = R._wall_edges(record)
        wall_edges[wall_id] = edges
        for edge in edges:
            edge_owner.setdefault(edge, wall_id)
    raw_faces = R.extract_planar_faces(
        [(e[0], e[1]) for w in sorted(wall_edges) for e in wall_edges[w]],
        min_area=1e-6,
    )
    return wall_edges, edge_owner, raw_faces


# ---------------------------------------------------------------- synthetic ---


def test_clean_plan_is_fully_owned_and_decision_is_unchanged() -> None:
    result = R._derive_scope(_scope(_two_rooms()))
    evaluation = result.ownership_evaluation

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) == 2
    assert evaluation.status == R.OWNERSHIP_EVALUATION_EVALUATED
    assert evaluation.scope_complete_at_evaluation is True
    assert evaluation.face_count == 2
    assert evaluation.unresolved_faces == ()
    assert evaluation.competing_edge_count == 0 and evaluation.unowned_edge_count == 0
    # Face identities are the identities the authority publishes.
    assert set(evaluation.owned_face_ids) >= {r.face_id for r in result.records}
    assert all(evaluation.is_face_ownership_clean(r.face_id) for r in result.records)


def test_competing_owner_face_is_listed_while_the_whole_scope_still_blocks() -> None:
    result = R._derive_scope(_scope(_with_competing_owner()))
    evaluation = result.ownership_evaluation

    # Unchanged legacy behaviour: one ambiguous edge fails the whole scope.
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (R.SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED,)
    assert result.records == ()
    # The shadow shows exactly what is local about it.
    assert evaluation.status == R.OWNERSHIP_EVALUATION_EVALUATED
    assert evaluation.face_count == 2
    assert len(evaluation.owned_face_ids) == 1
    assert len(evaluation.unresolved_faces) == 1
    finding = evaluation.unresolved_faces[0]
    assert finding.reason_codes == (R.SOURCE_ROOM_FACE_EDGE_OWNER_COMPETING,)
    assert finding.competing_wall_ids == ("dup-top", "room-top")
    assert all(f.kind == R.EDGE_OWNERSHIP_COMPETING for f in finding.edge_findings)
    assert all(set(f.wall_ids) == {"dup-top", "room-top"} for f in finding.edge_findings)
    assert evaluation.competing_edge_count == len(finding.edge_findings) >= 1
    assert not evaluation.is_face_ownership_clean(finding.face_id)


def test_exact_edge_ownership_remains_authoritative_like_the_legacy_rule() -> None:
    # The overlapping partition fragment owns its exact planarized edge, so the
    # legacy rule accepts it; the shadow must classify it identically.
    records = _two_rooms() + [_record("dup-part", (10.0, 2.0), (10.0, 8.0))]
    result = R._derive_scope(_scope(records))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.ownership_evaluation.unresolved_faces == ()


def test_unowned_edge_is_reported_distinctly_from_competing_owners() -> None:
    wall_edges, edge_owner, raw_faces = _ownership_inputs(_two_rooms())
    # Remove the top wall from the ownership universe: its face edges are now
    # contained by no wall at all.
    wall_edges = {k: v for k, v in wall_edges.items() if k != "room-top"}
    edge_owner = {e: w for e, w in edge_owner.items() if w != "room-top"}

    evaluation = R._evaluate_face_ownership(
        _scope(_two_rooms()),
        wall_edges=wall_edges,
        edge_owner=edge_owner,
        raw_faces=raw_faces,
    )

    assert evaluation.unowned_edge_count >= 1
    assert evaluation.competing_edge_count == 0
    kinds = {f.kind for u in evaluation.unresolved_faces for f in u.edge_findings}
    assert kinds == {R.EDGE_OWNERSHIP_NONE}
    assert all(
        u.reason_codes == (R.SOURCE_ROOM_FACE_EDGE_OWNER_MISSING,)
        for u in evaluation.unresolved_faces
    )


def test_incomplete_scope_is_evaluated_as_a_what_if_without_changing_the_decision() -> None:
    complete = R._derive_scope(_scope(_with_competing_owner(), complete=True))
    incomplete = R._derive_scope(_scope(_with_competing_owner(), complete=False))

    assert incomplete.reason_codes == (R.SOURCE_ROOM_FACE_SCOPE_UNAVAILABLE,)
    assert incomplete.records == ()
    assert incomplete.ownership_evaluation.status == R.OWNERSHIP_EVALUATION_EVALUATED
    assert incomplete.ownership_evaluation.scope_complete_at_evaluation is False
    # Same faces, same classification: only the completeness flag differs.
    a, b = complete.ownership_evaluation, incomplete.ownership_evaluation
    assert (a.owned_face_ids, a.unresolved_faces) == (b.owned_face_ids, b.unresolved_faces)


def test_degenerate_owned_faces_use_the_existing_rule_and_match_legacy_abstentions() -> None:
    records = _two_rooms() + _box("speck", 30.0, 0.0, 30.5, 0.5)
    result = R._derive_scope(_scope(records))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.abstained_faces) == 1
    abstained = result.abstained_faces[0]
    assert abstained.boundary_wall_edges
    assert {wall_id for wall_id, _edge in abstained.boundary_wall_edges} == set(
        abstained.bounding_wall_ids
    )
    assert len(abstained.boundary_wall_edges) == len(abstained.polygon_pdf_pts)
    assert set(result.ownership_evaluation.degenerate_owned_face_ids) == {
        a.face_id for a in result.abstained_faces
    }
    assert result.ownership_evaluation.largest_owned_face_area_pt2 == pytest.approx(200.0 / 2)


@pytest.mark.parametrize(
    "scope, reason",
    [
        (_scope(_two_rooms(), status=EvidenceResolutionStatus.ABSTAINED),
         "ownership_evaluation_scope_not_corroborated"),
        (_scope([]), "ownership_evaluation_no_wall_records"),
        (_scope(_two_rooms() + [_record("twin", (0.0, 0.0), (20.0, 0.0))]),
         "ownership_evaluation_duplicate_edge_ownership"),
    ],
)
def test_scopes_that_never_reach_the_face_stage_are_not_evaluated(scope, reason) -> None:
    evaluation = R._derive_scope(scope).ownership_evaluation

    assert evaluation.status == R.OWNERSHIP_EVALUATION_NOT_EVALUATED
    assert evaluation.reason_code == reason
    assert evaluation.face_count == 0 and not evaluation.is_face_ownership_clean("x")


def test_default_evaluation_is_not_evaluated_and_empty() -> None:
    evaluation = R.SourceRoomFaceOwnershipEvaluation()
    assert evaluation.status == R.OWNERSHIP_EVALUATION_NOT_EVALUATED
    assert evaluation.owned_face_ids == () and evaluation.unresolved_faces == ()
    assert evaluation.face_count == 0 and evaluation.unresolved_face_ids == ()


# ---------------------------------------------- shadow can never change a decision


@pytest.mark.parametrize("records", [_two_rooms(), _with_competing_owner()])
def test_shadow_failure_cannot_change_the_legacy_decision(monkeypatch, records) -> None:
    baseline = R._derive_scope_outcome(_scope(records))

    def boom(*_a, **_k):
        raise RuntimeError("shadow bug")

    monkeypatch.setattr(R, "_evaluate_face_ownership", boom)
    result = R._derive_scope(_scope(records))

    assert _decision(result) == _decision(baseline)
    assert result.ownership_evaluation.status == R.OWNERSHIP_EVALUATION_UNAVAILABLE
    assert result.ownership_evaluation.reason_code == "ownership_evaluation_error:RuntimeError"


@pytest.mark.parametrize("records", [_two_rooms(), _with_competing_owner()])
def test_a_wrong_shadow_result_cannot_change_the_legacy_decision(monkeypatch, records) -> None:
    baseline = R._derive_scope_outcome(_scope(records))
    bogus = R.SourceRoomFaceOwnershipEvaluation(
        status=R.OWNERSHIP_EVALUATION_EVALUATED,
        owned_face_ids=("not-a-face",),
        unresolved_faces=(),
    )
    monkeypatch.setattr(R, "_evaluate_face_ownership", lambda *a, **k: bogus)

    assert _decision(R._derive_scope(_scope(records))) == _decision(baseline)


def test_size_cap_only_skips_the_shadow(monkeypatch) -> None:
    baseline = R._derive_scope_outcome(_scope(_two_rooms()))
    monkeypatch.setattr(R, "_OWNERSHIP_EVALUATION_MAX_EDGES", 1)
    result = R._derive_scope(_scope(_two_rooms()))

    assert _decision(result) == _decision(baseline)
    assert result.ownership_evaluation.status == R.OWNERSHIP_EVALUATION_NOT_EVALUATED
    assert result.ownership_evaluation.reason_code == "ownership_evaluation_scope_too_large"


def test_spatial_prefilter_parameters_do_not_change_the_evaluation(monkeypatch) -> None:
    records = _with_competing_owner() + _box("far", 500.0, 500.0, 530.0, 520.0)
    reference = R._derive_scope(_scope(records)).ownership_evaluation
    for name, value in (
        ("_OWNERSHIP_GRID_CELL_PT", 0.5),
        ("_OWNERSHIP_GRID_CELL_PT", 1.0e9),
        ("_OWNERSHIP_GRID_MAX_CELLS_PER_EDGE", 1),  # every edge takes the oversized path
        ("_OWNERSHIP_GRID_MAX_CELLS_PER_EDGE", 10**9),
    ):
        with monkeypatch.context() as ctx:
            ctx.setattr(R, name, value)
            assert R._derive_scope(_scope(records)).ownership_evaluation == reference


def test_the_same_canonical_polygon_is_counted_once() -> None:
    wall_edges, edge_owner, _ = _ownership_inputs(_box("room", 0.0, 0.0, 10.0, 10.0))
    ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    variants = [ring, ring[1:] + ring[:1], list(reversed(ring))]

    evaluation = R._evaluate_face_ownership(
        _scope(_box("room", 0.0, 0.0, 10.0, 10.0)),
        wall_edges=wall_edges,
        edge_owner=edge_owner,
        raw_faces=variants,
    )

    assert evaluation.face_count == 1 and evaluation.face_edge_count == 4


def test_oversized_edge_paths_agree_with_the_grid_path(monkeypatch) -> None:
    records = _with_competing_owner() + _box("far", 500.0, 500.0, 530.0, 520.0)
    reference = R._derive_scope(_scope(records)).ownership_evaluation
    assert reference.competing_wall_ids == ("dup-top", "room-top")
    with monkeypatch.context() as ctx:
        # Tiny cells + a cap of one cell: every parent edge is "oversized" and
        # every query edge takes the exhaustive-scan fallback.
        ctx.setattr(R, "_OWNERSHIP_GRID_CELL_PT", 0.5)
        ctx.setattr(R, "_OWNERSHIP_GRID_MAX_CELLS_PER_EDGE", 1)
        assert R._derive_scope(_scope(records)).ownership_evaluation == reference


def test_absolute_degenerate_rule_applies_to_owned_faces() -> None:
    # 0.5 pt2 is under the absolute 1 pt2 floor but NOT under 1% of the largest
    # face (20 pt2), so only the absolute rule can classify it as degenerate.
    evaluation = R._derive_scope(
        _scope(_box("room", 0.0, 0.0, 4.0, 5.0) + _box("speck", 10.0, 0.0, 11.0, 0.5))
    ).ownership_evaluation

    assert evaluation.face_count == 2 and evaluation.largest_owned_face_area_pt2 == 20.0
    assert len(evaluation.degenerate_owned_face_ids) == 1


def test_tiny_reference_is_the_largest_owned_face_not_an_unresolved_one() -> None:
    # A 20_000 pt2 face has a competing-owner top edge (strictly inside two
    # overlapping walls, so no exact owner); a 50 pt2 room is fully owned. The
    # room must be judged against the largest OWNED face (itself): judged against
    # the unresolved giant it would look tiny (< 1%) purely because of an
    # ambiguity elsewhere. Driven through the helper so the fixture does not
    # depend on how the production planarizer happens to attach doubled edges.
    walls = {
        "top-a": (((0.0, 0.0), (300.0, 0.0)),),
        "top-b": (((-100.0, 0.0), (250.0, 0.0)),),
        "right": (((200.0, 0.0), (200.0, 100.0)),),
        "bottom": (((0.0, 100.0), (200.0, 100.0)),),
        "left": (((0.0, 0.0), (0.0, 100.0)),),
        "s-top": (((500.0, 0.0), (505.0, 0.0)),),
        "s-right": (((505.0, 0.0), (505.0, 10.0)),),
        "s-bottom": (((500.0, 10.0), (505.0, 10.0)),),
        "s-left": (((500.0, 0.0), (500.0, 10.0)),),
    }
    edge_owner = {
        edge: wall
        for wall, edges in walls.items()
        if not wall.startswith("top")
        for edge in edges
    }
    giant = [(0.0, 0.0), (200.0, 0.0), (200.0, 100.0), (0.0, 100.0)]
    room = [(500.0, 0.0), (505.0, 0.0), (505.0, 10.0), (500.0, 10.0)]

    evaluation = R._evaluate_face_ownership(
        _scope([]), wall_edges=walls, edge_owner=edge_owner, raw_faces=[giant, room]
    )

    assert [f.area_page_pts2 for f in evaluation.unresolved_faces] == [20_000.0]
    assert evaluation.unresolved_faces[0].competing_wall_ids == ("top-a", "top-b")
    assert evaluation.largest_owned_face_area_pt2 == 50.0
    assert evaluation.degenerate_owned_face_ids == ()


def test_evaluation_is_independent_of_the_order_of_extracted_faces() -> None:
    records = (
        _with_competing_owner()
        + _box("a", 30.0, 0.0, 40.0, 10.0)
        + _box("b", 50.0, 0.0, 60.0, 10.0)
        + _box("c", 70.0, 0.0, 80.0, 10.0)
    )
    wall_edges, edge_owner, raw_faces = _ownership_inputs(records)
    faces = list(raw_faces)
    reference = R._evaluate_face_ownership(
        _scope(records), wall_edges=wall_edges, edge_owner=edge_owner, raw_faces=faces
    )
    assert len(reference.owned_face_ids) >= 4 and reference.unresolved_faces
    for seed in range(12):
        shuffled = list(faces)
        random.Random(seed).shuffle(shuffled)
        assert (
            R._evaluate_face_ownership(
                _scope(records), wall_edges=wall_edges, edge_owner=edge_owner, raw_faces=shuffled
            )
            == reference
        )


def test_unresolved_faces_are_reported_in_a_stable_sorted_order() -> None:
    walls, edge_owner, faces = {}, {}, []
    for index, x in enumerate((0.0, 1000.0, 2000.0)):
        walls[f"top-a{index}"] = (((x, 0.0), (x + 300.0, 0.0)),)
        walls[f"top-b{index}"] = (((x - 100.0, 0.0), (x + 250.0, 0.0)),)
        for name, edge in (
            ("right", ((x + 200.0, 0.0), (x + 200.0, 100.0))),
            ("bottom", ((x, 100.0), (x + 200.0, 100.0))),
            ("left", ((x, 0.0), (x, 100.0))),
        ):
            walls[f"{name}{index}"] = (edge,)
            edge_owner[edge] = f"{name}{index}"
        faces.append([(x, 0.0), (x + 200.0, 0.0), (x + 200.0, 100.0), (x, 100.0)])

    reference = R._evaluate_face_ownership(
        _scope([]), wall_edges=walls, edge_owner=edge_owner, raw_faces=faces
    )
    ids = [f.face_id for f in reference.unresolved_faces]
    assert len(ids) == 3 and ids == sorted(ids)
    for seed in range(8):
        shuffled = list(faces)
        random.Random(seed).shuffle(shuffled)
        assert (
            R._evaluate_face_ownership(
                _scope([]), wall_edges=walls, edge_owner=edge_owner, raw_faces=shuffled
            )
            == reference
        )


def test_prefilter_never_misses_a_containing_wall_across_a_cell_boundary() -> None:
    # The right wall sits exactly on a 64 pt grid line while the planarized face
    # edge is 3e-6 inside it (within the 5.7e-6 containment tolerance), i.e. in
    # the neighbouring cell. The prefilter must still find it.
    walls = {
        "top": (((50.0, 10.0), (64.0, 10.0)),),
        "bottom": (((50.0, 0.0), (64.0, 0.0)),),
        "left": (((50.0, 0.0), (50.0, 10.0)),),
        "right": (((64.0, 0.0), (64.0, 10.0)),),
    }
    edge_owner = {edge: wall for wall, edges in walls.items() for edge in edges}
    face = [(63.999997, 0.0), (63.999997, 10.0), (50.0, 10.0), (50.0, 0.0)]

    evaluation = R._evaluate_face_ownership(
        _scope([]), wall_edges=walls, edge_owner=edge_owner, raw_faces=[face]
    )

    assert len(evaluation.owned_face_ids) == 1 and evaluation.unresolved_faces == ()


# ------------------------------------------------ differential vs production rule


def _random_arrangement(seed):
    rng = random.Random(seed)
    records, used = [], set()
    for index in range(rng.randint(8, 16)):
        horizontal = rng.random() < 0.5
        a, b = sorted(rng.sample(range(0, 9), 2))
        fixed = rng.randint(0, 8)
        first, second = ((a, fixed), (b, fixed)) if horizontal else ((fixed, a), (fixed, b))
        key = (first, second)
        if key in used:  # avoid exact duplicate edges (a different, earlier gate)
            continue
        used.add(key)
        records.append(_record(f"w{index:02d}", (float(first[0]), float(first[1])), (float(second[0]), float(second[1]))))
    return records


@pytest.mark.parametrize("seed", range(60))
def test_shadow_mirrors_the_production_ownership_rule_edge_by_edge(seed) -> None:
    records = _random_arrangement(seed)
    if len(records) < 4:
        pytest.skip("degenerate random draw")
    scope = _scope(records)
    wall_edges, edge_owner, raw_faces = _ownership_inputs(records)

    legacy_unresolved: dict[str, set] = {}
    expected_kinds: dict[str, dict] = {}
    for raw_face in raw_faces:
        polygon = R._canonical_polygon(raw_face)
        if not polygon:
            continue
        face_id = None
        for i, first in enumerate(polygon):
            edge = R._edge(first, polygon[(i + 1) % len(polygon)])
            owner = R._unique_containing_wall_owner(edge, edge_owner=edge_owner, wall_edges=wall_edges)
            if owner is None:
                containing = sorted(
                    w for w, edges in wall_edges.items()
                    if any(R._edge_contains_edge(p, edge) for p in edges)
                )
                face_id = face_id or R.stable_contract_id(
                    "source_room_face",
                    {"document_id": scope.document_id, "revision_id": scope.revision_id,
                     "source_sha256": scope.source_sha256, "snapshot_id": scope.snapshot_id,
                     "page_id": scope.page_id, "decision_scope_id": scope.decision_scope_id,
                     "polygon": polygon},
                    digest_chars=32,
                )
                legacy_unresolved.setdefault(face_id, set()).add(edge)
                expected_kinds.setdefault(face_id, {})[edge] = tuple(containing)

    evaluation = R._evaluate_face_ownership(
        scope, wall_edges=wall_edges, edge_owner=edge_owner, raw_faces=raw_faces
    )
    assert set(evaluation.unresolved_face_ids) == set(legacy_unresolved)
    for finding in evaluation.unresolved_faces:
        got = {f.edge: f for f in finding.edge_findings}
        assert set(got) == legacy_unresolved[finding.face_id]
        for edge, f in got.items():
            walls = expected_kinds[finding.face_id][edge]
            assert f.wall_ids == walls
            assert f.kind == (R.EDGE_OWNERSHIP_COMPETING if walls else R.EDGE_OWNERSHIP_NONE)


@pytest.mark.parametrize("seed", range(60))
def test_live_publication_never_uses_an_unowned_shadow_face(seed) -> None:
    records = _random_arrangement(seed)
    if len(records) < 4:
        pytest.skip("degenerate random draw")
    result = R._derive_scope(_scope(records))
    evaluation = result.ownership_evaluation
    if evaluation.status != R.OWNERSHIP_EVALUATION_EVALUATED:
        assert evaluation.reason_code == "ownership_evaluation_duplicate_edge_ownership"
        assert result.reason_codes == (R.SOURCE_ROOM_FACE_DUPLICATE_EDGE,)
        return

    if evaluation.face_count == 0 or evaluation.unowned_edge_count:
        assert R.SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED in result.reason_codes
        assert result.records == ()
        return

    if result.status is EvidenceResolutionStatus.CORROBORATED:
        published_ids = {r.face_id for r in result.records}
        assert published_ids <= set(evaluation.owned_face_ids)
        assert published_ids.isdisjoint(evaluation.unresolved_face_ids)
        # Degenerate shadow faces remain locally withheld. Live ownership
        # abstention may conservatively withhold additional OWNED faces that
        # share positive-length boundary with a competing span, so equality is
        # intentionally not required here.
        abstained_ids = {a.face_id for a in result.abstained_faces}
        assert set(evaluation.degenerate_owned_face_ids) <= abstained_ids


# ------------------------------------------------------------------ invariances


def _signature(evaluation):
    """Classification content that must survive a similarity transform."""
    return (
        evaluation.status,
        len(evaluation.owned_face_ids),
        len(evaluation.unresolved_faces),
        len(evaluation.degenerate_owned_face_ids),
        evaluation.competing_edge_count,
        evaluation.unowned_edge_count,
        evaluation.face_edge_count,
        sorted(
            (f.reason_codes, f.vertex_count, len(f.edge_findings), len(f.competing_wall_ids))
            for f in evaluation.unresolved_faces
        ),
    )


def _transformed(records, fn):
    return [
        _record(r.wall_candidate_id, fn(r.wall_candidate.centerline_pts[0]), fn(r.wall_candidate.centerline_pts[1]))
        for r in records
    ]


@pytest.mark.parametrize(
    "fn",
    [
        lambda p: (p[0] + 40.0, p[1] - 25.0),    # translation
        lambda p: (-p[1], p[0]),                 # rotation by 90 degrees
        lambda p: (p[0] * 2.0, p[1] * 2.0),      # uniform scale (exact in binary)
    ],
    ids=["translate", "rotate90", "scale2"],
)
def test_classification_is_invariant_under_similarity_transforms(fn) -> None:
    records = _two_rooms()
    base = R._derive_scope(_scope(records)).ownership_evaluation
    moved = R._derive_scope(_scope(_transformed(records, fn))).ownership_evaluation
    assert _signature(moved) == _signature(base)


@pytest.mark.parametrize(
    "fn",
    [
        lambda p: (p[0] + 40.0, p[1] - 25.0),
        lambda p: (-p[1], p[0]),
        lambda p: (p[0] * 2.0, p[1] * 2.0),
    ],
    ids=["translate", "rotate90", "scale2"],
)
def test_overlap_ambiguity_is_invariant_even_though_the_planarizer_is_not(fn) -> None:
    """Collinear overlaps make extract_planar_faces coordinate-dependent.

    The production planarizer hangs the doubled collinear edge on whichever
    adjacent face it happens to traverse first (observed: a pure translation
    moves it to the other room). The face that carries the ambiguity is
    therefore NOT stable, but the decision and the set of competing walls are.
    """
    records = _with_competing_owner()
    base = R._derive_scope(_scope(records))
    moved = R._derive_scope(_scope(_transformed(records, fn)))

    assert base.reason_codes == moved.reason_codes == (R.SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED,)
    assert base.ownership_evaluation.unresolved_faces and moved.ownership_evaluation.unresolved_faces
    assert (
        base.ownership_evaluation.competing_wall_ids
        == moved.ownership_evaluation.competing_wall_ids
        == ("dup-top", "room-top")
    )


def test_evaluation_is_input_order_invariant_and_deterministic() -> None:
    records = _with_competing_owner() + _box("speck", 30.0, 0.0, 30.5, 0.5)
    reference = R._derive_scope(_scope(records)).ownership_evaluation
    rng = random.Random(7)
    for _ in range(10):
        shuffled = list(records)
        rng.shuffle(shuffled)
        assert R._derive_scope(_scope(shuffled)).ownership_evaluation == reference
    assert R._derive_scope(_scope(records)).ownership_evaluation == reference  # replay


def test_unrelated_far_away_content_does_not_change_existing_face_ownership() -> None:
    base = R._derive_scope(_scope(_with_competing_owner())).ownership_evaluation
    extended = R._derive_scope(
        _scope(_with_competing_owner() + _box("far", 900.0, 900.0, 960.0, 940.0))
    ).ownership_evaluation

    assert set(base.owned_face_ids) < set(extended.owned_face_ids)
    assert base.unresolved_faces == extended.unresolved_faces


def test_splitting_a_wall_into_collinear_halves_does_not_change_ownership() -> None:
    whole = _two_rooms()
    split = [r for r in whole if r.wall_candidate_id != "partition"] + [
        _record("partition-a", (10.0, 0.0), (10.0, 5.0)),
        _record("partition-b", (10.0, 5.0), (10.0, 10.0)),
    ]
    a = R._derive_scope(_scope(whole)).ownership_evaluation
    b = R._derive_scope(_scope(split)).ownership_evaluation
    # The split adds a vertex to both adjacent polygons, so their identity hashes
    # legitimately change (as they do for the published records); the ownership
    # content (counts, areas, no ambiguity) must not.
    assert a.face_count == b.face_count == 2
    assert not a.unresolved_faces and not b.unresolved_faces
    assert a.largest_owned_face_area_pt2 == b.largest_owned_face_area_pt2
    assert a.face_edge_count < b.face_edge_count


def test_inputs_are_not_mutated() -> None:
    scope = _scope(_with_competing_owner())
    before = (tuple(scope.records), [r.wall_candidate.centerline_pts for r in scope.records])
    R._derive_scope(scope)
    after = (tuple(scope.records), [r.wall_candidate.centerline_pts for r in scope.records])
    assert before == after and all(a is b for a, b in zip(before[0], after[0]))


def test_face_universe_complete_is_unaffected_by_the_evaluation() -> None:
    result = R._derive_scope(_scope(_with_competing_owner()))
    assert result.face_universe_complete is False
    clean = R._derive_scope(_scope(_two_rooms()))
    assert clean.face_universe_complete is True


# --------------------------------------------------------- real source-owned plan


def _write_plan(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    for first, second in (
        ((50.0, 50.0), (250.0, 50.0)),
        ((250.0, 50.0), (250.0, 150.0)),
        ((250.0, 150.0), (50.0, 150.0)),
        ((50.0, 150.0), (50.0, 50.0)),
        ((150.0, 50.0), (150.0, 150.0)),
    ):
        page.draw_line(fitz.Point(*first), fitz.Point(*second), color=(0, 0, 0), width=1)
    doc.save(path)
    doc.close()


def test_real_authority_result_carries_the_evaluation_for_published_faces(tmp_path: Path) -> None:
    path = tmp_path / "two-room.pdf"
    _write_plan(path)
    source = SourceVisibilityProducer(producer_method="own-eval-test", producer_version="1.0")
    published = source.ingest_native_pdf_bytes(
        document_id=f"test:{path.name}",
        source_bytes=path.read_bytes(),
        source_locator=str(path),
    )
    wall_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source, page_ids=("1",)
    ).authority()
    assert wall_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            decision_scope_id="wall-source:page-1",
        )
    ).scope_complete is True
    result = R.build_source_room_face_authority(wall_authority).resolve_scope(
        R.SourceRoomFaceSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            decision_scope_id="wall-source:page-1",
        )
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED and len(result.records) == 2
    evaluation = result.ownership_evaluation
    assert evaluation.status == R.OWNERSHIP_EVALUATION_EVALUATED
    assert evaluation.unresolved_faces == ()
    assert set(evaluation.owned_face_ids) == {r.face_id for r in result.records}
    assert all(math.isfinite(f) for f in (evaluation.largest_owned_face_area_pt2,))
