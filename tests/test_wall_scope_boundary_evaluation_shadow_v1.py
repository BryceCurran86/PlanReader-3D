"""Shadow per-candidate scope-boundary evaluation.

The evaluation is additive evidence: it must never change scope_complete,
reason_codes, records or any consumer decision. The first group of tests pins
the LEGACY contract (it passes on the code before this change too); the second
group tests the new shadow evaluation.
"""
from __future__ import annotations

import math
import random
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

import pb_physical_wall_candidate_authority as module
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    BOUNDARY_EVALUATION_EVALUATED,
    BOUNDARY_EVALUATION_UNAVAILABLE,
    BOUNDARY_PRIMITIVE_CROSSES_SCOPE_BOUNDARY,
    BOUNDARY_PRIMITIVE_LIES_ON_SCOPE_BOUNDARY_PARTIAL,
    PHYSICAL_WALL_CANDIDATE_BOUNDARY_GEOMETRY_NOT_EVALUABLE,
    PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY,
    PHYSICAL_WALL_CANDIDATE_SCOPE_BOUNDS_UNRESOLVED,
    PHYSICAL_WALL_CANDIDATE_SOURCE_PRIMITIVE_OWNERSHIP_AMBIGUOUS,
    PHYSICAL_WALL_CANDIDATE_TOUCHES_EXCLUDED_BOUNDARY_PRIMITIVE,
    ExcludedBoundaryPrimitive,
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
    PhysicalWallScopeBoundaryEvaluation,
    _evaluate_scope_boundary,
    _segment_segment_distance,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import ViewportSegmentationStatus, segment_page_viewports
from pb_wall_room_topology_stage_a import DEFAULT_GAP_SNAP_TOLERANCE_PT

# ---------------------------------------------------------------- fixtures

_BOX = [
    ((90.0, 80.0), (330.0, 80.0)),
    ((330.0, 80.0), (330.0, 230.0)),
    ((330.0, 230.0), (90.0, 230.0)),
    ((90.0, 230.0), (90.0, 80.0)),
    ((210.0, 80.0), (210.0, 230.0)),
]


def _draw(
    path: Path,
    *,
    extra=(),
    dx: float = 0.0,
    dy: float = 0.0,
    scale: float = 1.0,
    order_seed: int | None = None,
    split_east: bool = False,
) -> None:
    doc = fitz.open()
    page = doc.new_page(width=520.0 * scale + dx, height=400.0 * scale + dy)
    frame = fitz.Rect(
        (40.0 + dx) * scale, (30.0 + dy) * scale, (420.0 + dx) * scale, (330.0 + dy) * scale
    )
    page.draw_rect(frame, color=(0, 0, 0), width=1)
    page.insert_text(
        ((80.0 + dx) * scale, (310.0 + dy) * scale),
        "GROUND FLOOR PLAN",
        fontsize=max(8.0, 11.0 * scale),
    )
    lines = list(_BOX)
    if split_east:
        lines.remove(((330.0, 80.0), (330.0, 230.0)))
        lines += [((330.0, 80.0), (330.0, 150.0)), ((330.0, 150.0), (330.0, 230.0))]
    lines += list(extra)
    if order_seed is not None:
        random.Random(order_seed).shuffle(lines)
    for first, second in lines:
        page.draw_line(
            ((first[0] + dx) * scale, (first[1] + dy) * scale),
            ((second[0] + dx) * scale, (second[1] + dy) * scale),
            color=(0, 0, 0),
            width=1,
        )
    doc.save(path)
    doc.close()


def _viewport_id(path: Path) -> str:
    doc = fitz.open(path)
    try:
        rows = [
            v
            for v in segment_page_viewports(doc[0], page_number=1)
            if v.view_type == "floor_plan"
            and v.status == ViewportSegmentationStatus.RESOLVED.value
        ]
    finally:
        doc.close()
    assert len(rows) == 1
    return rows[0].view_id


def _viewport_scope(path: Path):
    source = SourceVisibilityProducer(producer_method="boundary-shadow", producer_version="1.0")
    published = source.ingest_native_pdf_bytes(
        document_id="test:boundary-shadow",
        source_bytes=path.read_bytes(),
        source_locator=str(path),
    )
    authority = PhysicalWallCandidateProducer.from_authenticated_viewports(
        source, page_ids=("1",)
    ).authority()
    selector = authority.selector_for_viewport(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        viewport_id=_viewport_id(path),
    )
    assert selector is not None
    return authority.resolve_scope(selector)


def _page_scope(path: Path):
    source = SourceVisibilityProducer(producer_method="boundary-shadow-page", producer_version="1.0")
    published = source.ingest_native_pdf_bytes(
        document_id="test:boundary-shadow-page",
        source_bytes=path.read_bytes(),
        source_locator=str(path),
    )
    authority = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source, page_ids=("1",)
    ).authority()
    current = source.published_snapshot_for_revision(published.revision.revision_id)
    return authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            page_id="1",
            decision_scope_id="wall-source:page-1",
        )
    )


def _centerlines(scope, ids):
    wanted = set(ids)
    return {
        tuple(sorted(tuple(round(c, 3) for c in point) for point in rec.wall_candidate.centerline_pts))
        for rec in scope.records
        if rec.wall_candidate_id in wanted
    }


# crossing line that touches NO wall (starts 20pt east of the east wall)
UNTOUCHED = [((350.0, 150.0), (450.0, 150.0))]
# crossing line that starts ON the east wall
TOUCHING = [((330.0, 150.0), (450.0, 150.0))]
# partial line lying on the right frame edge (x=420), not a whole edge
PARTIAL = [((420.0, 100.0), (420.0, 200.0))]


# ------------------------------------------------- legacy contract (unchanged)


def test_legacy_complete_scope_contract(tmp_path: Path) -> None:
    path = tmp_path / "plain.pdf"
    _draw(path)
    scope = _viewport_scope(path)

    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    assert scope.scope_complete is True
    assert scope.reason_codes == (module.PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,)
    assert scope.records


@pytest.mark.parametrize("extra", [UNTOUCHED, TOUCHING])
def test_legacy_crossing_primitive_still_makes_scope_incomplete_and_leaves_records_alone(
    tmp_path: Path, extra
) -> None:
    plain = _viewport_scope(_save(tmp_path / "plain.pdf", []))
    crossed = _viewport_scope(_save(tmp_path / "crossed.pdf", extra))

    assert crossed.scope_complete is False
    assert PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY in crossed.reason_codes
    # The crossing primitive is excluded from the owned graph, so the legacy
    # candidate geometry is exactly that of the plain drawing (ids embed the
    # source revision and legitimately differ between two different PDFs).
    def geometry(scope):
        return sorted(
            tuple(tuple(round(c, 3) for c in point) for point in r.wall_candidate.centerline_pts)
            for r in scope.records
        )

    assert geometry(crossed) == geometry(plain)


def test_legacy_partial_boundary_line_is_still_ownership_ambiguous(tmp_path: Path) -> None:
    scope = _viewport_scope(_save(tmp_path / "partial.pdf", PARTIAL))

    assert scope.scope_complete is False
    assert PHYSICAL_WALL_CANDIDATE_SOURCE_PRIMITIVE_OWNERSHIP_AMBIGUOUS in scope.reason_codes


def _save(path: Path, extra, **kwargs) -> Path:
    _draw(path, extra=extra, **kwargs)
    return path


# -------------------------------------------------------- shadow evaluation


def test_complete_scope_evaluation_has_no_taint_and_no_excluded_primitives(tmp_path: Path) -> None:
    scope = _viewport_scope(_save(tmp_path / "plain.pdf", []))
    ev = scope.boundary_evaluation

    assert isinstance(ev, PhysicalWallScopeBoundaryEvaluation)
    assert ev.status == BOUNDARY_EVALUATION_EVALUATED
    assert set(ev.evaluated_wall_candidate_ids) == {r.wall_candidate_id for r in scope.records}
    assert ev.boundary_tainted_wall_candidate_ids == ()
    assert ev.excluded_boundary_primitives == ()
    assert ev.authenticated_frame_edge_primitive_count >= 1
    assert ev.boundary_clean_wall_candidate_count == len(scope.records)
    assert ev.contact_tolerance_pt == DEFAULT_GAP_SNAP_TOLERANCE_PT


def test_crossing_primitive_touching_no_wall_leaves_every_candidate_clean(tmp_path: Path) -> None:
    """The real-world case: one stray crossing line makes the whole scope
    incomplete, yet no candidate is actually cut by it."""
    scope = _viewport_scope(_save(tmp_path / "untouched.pdf", UNTOUCHED))
    ev = scope.boundary_evaluation

    assert scope.scope_complete is False
    assert ev.status == BOUNDARY_EVALUATION_EVALUATED
    assert ev.boundary_tainted_wall_candidate_ids == ()
    assert ev.boundary_clean_wall_candidate_count == len(scope.records) > 0
    assert [p.category for p in ev.excluded_boundary_primitives] == [
        BOUNDARY_PRIMITIVE_CROSSES_SCOPE_BOUNDARY
    ]
    assert all(ev.is_boundary_clean(r.wall_candidate_id) for r in scope.records)


def test_crossing_primitive_touching_one_wall_taints_only_that_wall(tmp_path: Path) -> None:
    scope = _viewport_scope(_save(tmp_path / "touching.pdf", TOUCHING))
    ev = scope.boundary_evaluation

    assert scope.scope_complete is False
    tainted = _centerlines(scope, ev.boundary_tainted_wall_candidate_ids)
    # exactly the east wall (x == 330), nothing else
    assert tainted and all(
        all(abs(x - 330.0) < 1e-3 for x, _y in line) for line in tainted
    )
    for _wall_id, reasons in ev.boundary_taint_reason_codes:
        assert PHYSICAL_WALL_CANDIDATE_TOUCHES_EXCLUDED_BOUNDARY_PRIMITIVE in reasons
    clean_ids = set(ev.evaluated_wall_candidate_ids) - set(ev.boundary_tainted_wall_candidate_ids)
    assert clean_ids  # the other walls stay clean
    assert ev.boundary_clean_wall_candidate_count == len(clean_ids)


def test_partial_boundary_line_is_recorded_but_taints_nothing_it_does_not_touch(
    tmp_path: Path,
) -> None:
    scope = _viewport_scope(_save(tmp_path / "partial.pdf", PARTIAL))
    ev = scope.boundary_evaluation

    assert scope.scope_complete is False
    assert [p.category for p in ev.excluded_boundary_primitives] == [
        BOUNDARY_PRIMITIVE_LIES_ON_SCOPE_BOUNDARY_PARTIAL
    ]
    assert ev.boundary_tainted_wall_candidate_ids == ()


def test_wall_with_a_dangling_end_on_the_boundary_is_tainted_by_the_existing_rule(
    tmp_path: Path,
) -> None:
    # a wall running from the east wall out to the frame edge: its end lies ON
    # the viewport boundary (the existing per-wall rule), independent of any
    # excluded primitive.
    scope = _viewport_scope(_save(tmp_path / "to-frame.pdf", [((330.0, 160.0), (420.0, 160.0))]))
    ev = scope.boundary_evaluation

    reasons = dict(ev.boundary_taint_reason_codes)
    assert any(
        PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY in r for r in reasons.values()
    )


def test_page_scope_records_unresolved_bounds_per_candidate(tmp_path: Path) -> None:
    # a stray free-ended line outside the plan frame (title-block-like content)
    scope = _page_scope(_save(tmp_path / "page.pdf", [((440.0, 60.0), (480.0, 60.0))]))
    ev = scope.boundary_evaluation

    assert scope.scope_complete is False
    assert ev.status == BOUNDARY_EVALUATION_EVALUATED
    reasons = dict(ev.boundary_taint_reason_codes)
    assert reasons, "the stray line must be tainted"
    assert all(
        PHYSICAL_WALL_CANDIDATE_SCOPE_BOUNDS_UNRESOLVED in r for r in reasons.values()
    )
    # the plan walls are not tainted by the stray outside content
    assert ev.boundary_clean_wall_candidate_count > 0
    assert ev.excluded_boundary_primitives == ()  # page scope has no excluded primitives


def test_blocked_scope_has_no_boundary_evaluation() -> None:
    selector = PhysicalWallCandidateSelector(
        document_id="d", revision_id="r", source_sha256="s", snapshot_id="n",
        page_id="1", decision_scope_id="wall-source:page-1",
    )
    blocked = module._blocked(selector, module.PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE)
    assert blocked.boundary_evaluation is None


# ------------------------------------------------------------- invariances


def _pattern(scope):
    ev = scope.boundary_evaluation
    return (
        scope.scope_complete,
        len(ev.evaluated_wall_candidate_ids),
        len(ev.boundary_tainted_wall_candidate_ids),
        tuple(p.category for p in ev.excluded_boundary_primitives),
        tuple(sorted({r for _w, rs in ev.boundary_taint_reason_codes for r in rs})),
    )


@pytest.mark.parametrize("extra", [UNTOUCHED, TOUCHING, PARTIAL])
def test_classification_pattern_is_translation_and_scale_invariant(tmp_path: Path, extra) -> None:
    base = _pattern(_viewport_scope(_save(tmp_path / "base.pdf", extra)))
    moved = _pattern(_viewport_scope(_save(tmp_path / "moved.pdf", extra, dx=37.0, dy=-11.0 + 20.0)))
    scaled = _pattern(_viewport_scope(_save(tmp_path / "scaled.pdf", extra, scale=2.0)))

    assert moved == base
    assert scaled == base


@pytest.mark.parametrize("extra", [UNTOUCHED, TOUCHING])
def test_classification_is_input_order_invariant(tmp_path: Path, extra) -> None:
    base_scope = _viewport_scope(_save(tmp_path / "base.pdf", extra))
    base_lines = _centerlines(base_scope, base_scope.boundary_evaluation.boundary_tainted_wall_candidate_ids)
    for seed in range(4):
        scope = _viewport_scope(_save(tmp_path / f"shuffled{seed}.pdf", extra, order_seed=seed))
        assert _pattern(scope) == _pattern(base_scope)
        assert (
            _centerlines(scope, scope.boundary_evaluation.boundary_tainted_wall_candidate_ids)
            == base_lines
        )


def test_classification_is_segment_splitting_invariant(tmp_path: Path) -> None:
    whole = _viewport_scope(_save(tmp_path / "whole.pdf", TOUCHING))
    split = _viewport_scope(_save(tmp_path / "split.pdf", TOUCHING, split_east=True))

    def tainted_x(scope):
        return {
            round(x, 3)
            for line in _centerlines(scope, scope.boundary_evaluation.boundary_tainted_wall_candidate_ids)
            for x, _y in line
        }

    assert tainted_x(whole) == tainted_x(split) == {330.0}


def test_unrelated_far_content_does_not_change_existing_classification(tmp_path: Path) -> None:
    base = _viewport_scope(_save(tmp_path / "base.pdf", TOUCHING))
    # a detached closed box well inside the frame, nowhere near the crossing line
    box = [
        ((100.0, 260.0), (140.0, 260.0)),
        ((140.0, 260.0), (140.0, 290.0)),
        ((140.0, 290.0), (100.0, 290.0)),
        ((100.0, 290.0), (100.0, 260.0)),
    ]
    more = _viewport_scope(_save(tmp_path / "more.pdf", TOUCHING + box))

    base_taint = _centerlines(base, base.boundary_evaluation.boundary_tainted_wall_candidate_ids)
    more_taint = _centerlines(more, more.boundary_evaluation.boundary_tainted_wall_candidate_ids)
    assert more_taint == base_taint
    assert len(more.boundary_evaluation.evaluated_wall_candidate_ids) > len(
        base.boundary_evaluation.evaluated_wall_candidate_ids
    )


def test_deterministic_replay(tmp_path: Path) -> None:
    path = _save(tmp_path / "replay.pdf", TOUCHING)
    assert _viewport_scope(path).boundary_evaluation == _viewport_scope(path).boundary_evaluation


# -------------------------------------------------- failure containment


def test_evaluation_failure_cannot_change_legacy_fields_and_never_reports_clean(
    tmp_path: Path, monkeypatch
) -> None:
    path = _save(tmp_path / "boom.pdf", UNTOUCHED)
    baseline = _viewport_scope(path)

    def boom(**_kwargs):
        raise ValueError("synthetic failure")

    monkeypatch.setattr(module, "_evaluate_scope_boundary", boom)
    degraded = _viewport_scope(path)

    ev = degraded.boundary_evaluation
    assert ev.status == BOUNDARY_EVALUATION_UNAVAILABLE
    assert ev.reason_code == "boundary_evaluation_error:ValueError"
    assert ev.boundary_clean_wall_candidate_count == 0
    assert not any(ev.is_boundary_clean(r.wall_candidate_id) for r in degraded.records)
    # legacy surface is byte-identical to the unmocked run
    assert degraded.scope_complete == baseline.scope_complete
    assert degraded.reason_codes == baseline.reason_codes
    assert degraded.records == baseline.records
    assert degraded.equivalence == baseline.equivalence
    assert degraded.scope_boundary_observation_ids == baseline.scope_boundary_observation_ids
    assert degraded.ambiguous_source_observation_ids == baseline.ambiguous_source_observation_ids


# ------------------------------------------------------- pure evaluator


def _wall(wall_id, points, representation="single_line"):
    return SimpleNamespace(candidate_id=wall_id, centerline_pts=tuple(points), representation=representation)


def _prim(x1, y1, x2, y2, category=BOUNDARY_PRIMITIVE_CROSSES_SCOPE_BOUNDARY):
    return ExcludedBoundaryPrimitive(category, "obs", x1, y1, x2, y2)


def _eval(walls, prims=(), reasons=None):
    return _evaluate_scope_boundary(
        ordered_walls=walls,
        wall_boundary_reasons=reasons or {},
        excluded_boundary_primitives=prims,
        authenticated_frame_edge_primitive_count=0,
    )


def test_contact_boundary_is_the_wall_graph_gap_snap_tolerance() -> None:
    wall = _wall("w", [(0.0, 0.0), (10.0, 0.0)])
    tol = DEFAULT_GAP_SNAP_TOLERANCE_PT
    # primitive endpoint exactly tol away from the wall -> contact (<=)
    assert _eval([wall], [_prim(5.0, tol, 5.0, 50.0)]).boundary_tainted_wall_candidate_ids == ("w",)
    # just beyond tol -> clean
    assert _eval([wall], [_prim(5.0, tol + 1e-3, 5.0, 50.0)]).boundary_tainted_wall_candidate_ids == ()


def test_crossing_through_a_wall_is_contact() -> None:
    wall = _wall("w", [(0.0, 0.0), (10.0, 0.0)])
    ev = _eval([wall], [_prim(5.0, -20.0, 5.0, 20.0)])
    assert ev.boundary_tainted_wall_candidate_ids == ("w",)


def test_non_single_line_candidate_is_not_evaluable_and_tainted_only_when_primitives_exist() -> None:
    curved = _wall("c", [(0.0, 0.0), (10.0, 0.0)], representation="curved")
    assert _eval([curved]).boundary_tainted_wall_candidate_ids == ()
    ev = _eval([curved], [_prim(500.0, 500.0, 600.0, 600.0)])
    assert dict(ev.boundary_taint_reason_codes)["c"] == (
        PHYSICAL_WALL_CANDIDATE_BOUNDARY_GEOMETRY_NOT_EVALUABLE,
    )


def test_existing_per_wall_reason_is_carried_without_any_excluded_primitive() -> None:
    wall = _wall("w", [(0.0, 0.0), (10.0, 0.0)])
    ev = _eval([wall], reasons={"w": PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY})
    assert dict(ev.boundary_taint_reason_codes)["w"] == (
        PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY,
    )


def test_non_finite_geometry_is_conservatively_contact_and_never_raises() -> None:
    wall = _wall("w", [(0.0, 0.0), (10.0, 0.0)])
    assert _eval([wall], [_prim(math.nan, 0.0, 1.0, 1.0)]).boundary_tainted_wall_candidate_ids == ("w",)
    assert _eval([wall], [_prim(math.inf, 0.0, 1.0, 1.0)]).boundary_tainted_wall_candidate_ids == ("w",)


def test_evaluator_does_not_mutate_inputs_and_is_order_independent() -> None:
    walls = [
        _wall("b", [(0.0, 10.0), (10.0, 10.0)]),
        _wall("a", [(0.0, 0.0), (10.0, 0.0)]),
        _wall("c", [(100.0, 0.0), (110.0, 0.0)]),
    ]
    prims = [_prim(5.0, -5.0, 5.0, 5.0), _prim(200.0, 0.0, 210.0, 0.0)]
    snapshot = [(w.candidate_id, w.centerline_pts) for w in walls], list(prims)
    first = _eval(walls, prims)
    assert ([(w.candidate_id, w.centerline_pts) for w in walls], list(prims)) == snapshot
    second = _eval(list(reversed(walls)), list(reversed(prims)))
    assert first == second
    assert first.boundary_tainted_wall_candidate_ids == ("a",)


@pytest.mark.parametrize(
    "a,b,c,d,expected",
    [
        ((0, 0), (10, 0), (5, -5), (5, 5), 0.0),          # crossing
        ((0, 0), (10, 0), (10, 0), (20, 0), 0.0),         # shared endpoint
        ((0, 0), (10, 0), (3, 0), (7, 0), 0.0),           # collinear overlap
        ((0, 0), (10, 0), (0, 3), (10, 3), 3.0),          # parallel
        ((0, 0), (10, 0), (13, 4), (20, 4), 5.0),         # endpoint to endpoint
    ],
)
def test_segment_distance_geometry_and_symmetry(a, b, c, d, expected) -> None:
    assert _segment_segment_distance(a, b, c, d) == pytest.approx(expected)
    assert _segment_segment_distance(c, d, a, b) == pytest.approx(expected)
    assert _segment_segment_distance(b, a, d, c) == pytest.approx(expected)


def test_unavailable_status_is_never_clean_even_with_ids_present() -> None:
    # Defense in depth: status alone must veto cleanliness, not just empty ids.
    ev = PhysicalWallScopeBoundaryEvaluation(
        status=BOUNDARY_EVALUATION_UNAVAILABLE,
        reason_code="boundary_evaluation_error:ValueError",
        evaluated_wall_candidate_ids=("w",),
        boundary_tainted_wall_candidate_ids=(),
        boundary_taint_reason_codes=(),
        excluded_boundary_primitives=(),
        authenticated_frame_edge_primitive_count=0,
        contact_tolerance_pt=DEFAULT_GAP_SNAP_TOLERANCE_PT,
    )
    assert ev.is_boundary_clean("w") is False
    assert ev.boundary_clean_wall_candidate_count == 0


def test_unknown_candidate_is_never_clean() -> None:
    ev = _eval([_wall("a", [(0.0, 0.0), (10.0, 0.0)])])
    assert ev.is_boundary_clean("a") is True
    assert ev.is_boundary_clean("not-in-this-scope") is False


def test_multiple_tainted_candidates_are_reported_in_sorted_order_regardless_of_input_order() -> None:
    walls = [
        _wall("z", [(0.0, 0.0), (10.0, 0.0)]),
        _wall("m", [(0.0, 20.0), (10.0, 20.0)]),
        _wall("a", [(0.0, 40.0), (10.0, 40.0)]),
    ]
    prims = [_prim(5.0, -50.0, 5.0, 50.0)]  # crosses all three
    forward = _eval(walls, prims)
    backward = _eval(list(reversed(walls)), prims)

    assert forward.boundary_tainted_wall_candidate_ids == ("a", "m", "z")
    assert backward.boundary_tainted_wall_candidate_ids == ("a", "m", "z")
    assert [w for w, _r in forward.boundary_taint_reason_codes] == ["a", "m", "z"]
