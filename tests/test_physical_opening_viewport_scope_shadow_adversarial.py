"""Adversarial contract tests for the SHADOW G17 viewport scope (PR #989 review fixes).

Every test in the first block is a defect two independent reviewers reproduced by
execution on the first revision of this module. The module must stay observation
only and fail closed: ambiguous, contested, unproven, unreadable or unauthenticated
evidence abstains; typed negatives are evidence against promotion, never deletion.
"""
from __future__ import annotations

import ast
import itertools
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

import pb_physical_opening_viewport_scope_shadow as shadow
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_physical_opening_viewport_scope_shadow import (
    AMBIGUOUS_AUTHENTICATED_OWNERSHIP,
    EVIDENCE_DIRECTION_AGAINST_PROMOTION,
    EVIDENCE_DIRECTION_NONE,
    EVIDENCE_DIRECTION_SCOPE_ONLY,
    IN_AUTHENTICATED_FLOOR_PLAN,
    IN_AUTHENTICATED_NON_PLAN,
    IN_AUTHENTICATED_VIEW_TYPE_UNPROVEN,
    NO_AUTHENTICATED_VIEWPORT,
    OPENING_VIEWPORT_SCOPE_SNAPSHOT_INTEGRITY_FAILED,
    OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE,
    OUTSIDE_AUTHENTICATED_VIEWPORTS,
    SUPPORT_GEOMETRY_UNREADABLE,
    AuthenticatedViewportRecord,
    _candidate_scope,
    _contesting_boxes,
    assess_opening_candidate_viewport_scope,
)
from pb_source_observation_authority import STALE_REVISION
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import segment_page_viewports, validate_non_overlapping_viewports


def _opening(page, x, y, *, gap=40.0, run=50.0, thick=10.0):
    a, b = x + run, x + run + gap
    for yy in (y, y + thick):
        page.draw_line((x, yy), (a, yy), width=1)
        page.draw_line((b, yy), (b + run, yy), width=1)
    page.draw_line((a, y), (a, y + thick), width=1)
    page.draw_line((b, y), (b, y + thick), width=1)


def _ingest(payload: bytes, name: str = "sheet", document_id: str | None = None):
    source = SourceVisibilityProducer(producer_method="viewport-scope-adversarial", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id=document_id or f"test:{name}",
        source_bytes=payload,
        source_locator=f"memory://{name}.pdf",
    )
    return source, published


def _assess(payload: bytes, name: str = "sheet"):
    source, published = _ingest(payload, name)
    report = assess_opening_candidate_viewport_scope(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_id="1",
    )
    return source, published, report


def _scopes(report) -> set[str]:
    return {item.scope for item in report.candidate_scopes}


def _viewports_of(payload: bytes):
    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        return segment_page_viewports(doc.load_page(0), page_number=1)
    finally:
        doc.close()


def _vp(index, view_type, bbox, *, status="resolved", source="vector_frame"):
    return AuthenticatedViewportRecord(
        view_id=f"v{index}", view_type=view_type, status=status, boundary_source=source, bounding_box=bbox
    )


PLAN = (0.0, 0.0, 100.0, 100.0)
INSIDE = ((10.0, 10.0, 20.0, 20.0),)


# ---------------------------------------------------------------------------
# F1: an AMBIGUOUS nested sub-view must contest ownership, not vanish
# ---------------------------------------------------------------------------
def _nested_subview(title: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)
    page.draw_rect(fitz.Rect(20, 20, 780, 560), color=(0, 0, 0), width=1)
    page.insert_text((60, 540), "GROUND FLOOR PLAN", fontsize=11)
    page.draw_rect(fitz.Rect(400, 60, 740, 300), color=(0, 0, 0), width=1)
    page.insert_text((420, 280), title, fontsize=11)
    _opening(page, 450, 120)
    payload = doc.tobytes()
    doc.close()
    return payload


@pytest.mark.parametrize(
    "title", ["TYPICAL DETAIL", "SECTION A-A", "FRONT ELEVATION", "WINDOW SCHEDULE", "ROOF PLAN"]
)
def test_candidate_inside_ambiguous_nested_subview_is_ambiguous_not_floor_plan(title) -> None:
    payload = _nested_subview(title)
    assert "ambiguous" in {v.status for v in _viewports_of(payload)}  # precondition
    _s, _p, report = _assess(payload, "nested")
    assert report.candidate_scopes
    assert _scopes(report) == {AMBIGUOUS_AUTHENTICATED_OWNERSHIP}
    assert IN_AUTHENTICATED_FLOOR_PLAN not in _scopes(report)


def test_outer_frame_listed_among_candidate_frames_is_not_a_contest_against_itself() -> None:
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)
    page.draw_rect(fitz.Rect(20, 20, 780, 560), color=(0, 0, 0), width=1)
    page.insert_text((60, 540), "GROUND FLOOR PLAN", fontsize=11)
    page.draw_rect(fitz.Rect(400, 60, 740, 300), color=(0, 0, 0), width=1)
    page.insert_text((420, 280), "TYPICAL DETAIL", fontsize=11)
    _opening(page, 60, 400)  # in the plan frame, far from the nested frame
    payload = doc.tobytes()
    doc.close()
    _s, _p, report = _assess(payload, "nested-far")
    assert _scopes(report) == {IN_AUTHENTICATED_FLOOR_PLAN}


# ---------------------------------------------------------------------------
# F2: reuse the existing F.07 gate; DERIVED cells need a non-overlapping sibling set
# ---------------------------------------------------------------------------
def _grid_with_overlapping_frame() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=800, height=1000)
    page.insert_text((100, 300), "FRONT ELEVATION", fontsize=11)
    page.insert_text((100, 800), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((600, 300), "SIDE ELEVATION", fontsize=11)
    page.insert_text((600, 800), "FIRST FLOOR PLAN", fontsize=11)
    page.draw_rect(fitz.Rect(300, 420, 520, 700), color=(0, 0, 0), width=1)
    page.insert_text((360, 440), "DETAIL A", fontsize=11)
    _opening(page, 60, 650)
    payload = doc.tobytes()
    doc.close()
    return payload


def test_derived_cells_are_not_authenticated_when_sibling_set_overlaps() -> None:
    payload = _grid_with_overlapping_frame()
    assert validate_non_overlapping_viewports(_viewports_of(payload)) is False  # precondition
    _s, _p, report = _assess(payload, "grid-overlap")
    assert report.candidate_scopes
    assert IN_AUTHENTICATED_FLOOR_PLAN not in _scopes(report)
    assert all(v.boundary_source == "vector_frame" for v in report.authenticated_viewports)


def test_derived_title_partition_bbox_does_not_contest_authenticated_drawn_frame() -> None:
    authenticated = (_vp(1, "floor_plan", PLAN),)
    derived = SimpleNamespace(
        view_id="derived",
        bounding_box=(0.0, 0.0, 100.0, 100.0),
        boundary_source="title_partition",
        provenance={},
    )
    boxes, unlocalised = _contesting_boxes(
        (derived,),
        frozenset({"v1"}),
        authenticated,
    )
    assert boxes == ()
    assert unlocalised is True
    assert _candidate_scope(
        INSIDE,
        authenticated,
        boxes,
        unlocalised_unauthenticated=unlocalised,
    )[0] == IN_AUTHENTICATED_FLOOR_PLAN


def test_page_wide_derived_partition_cannot_override_drawn_plan_ownership() -> None:
    authenticated = (_vp(1, "floor_plan", PLAN),)
    page_wide = SimpleNamespace(
        view_id="partition",
        bounding_box=(-1000.0, -1000.0, 1000.0, 1000.0),
        boundary_source="title_partition",
        provenance={"partition_mode": "ordinary_title_partition"},
    )
    boxes, unlocalised = _contesting_boxes(
        (page_wide,),
        frozenset({"v1"}),
        authenticated,
    )
    assert boxes == ()
    assert unlocalised is True
    assert _candidate_scope(
        INSIDE,
        authenticated,
        boxes,
        unlocalised_unauthenticated=unlocalised,
    )[0] == IN_AUTHENTICATED_FLOOR_PLAN


def test_ambiguous_candidate_vector_frame_still_contests_drawn_plan() -> None:
    authenticated = (_vp(1, "floor_plan", PLAN),)
    ambiguous = SimpleNamespace(
        view_id="ambiguous",
        bounding_box=None,
        boundary_source="none",
        provenance={"candidate_frames": [(5.0, 5.0, 30.0, 30.0)]},
    )
    boxes, unlocalised = _contesting_boxes(
        (ambiguous,),
        frozenset({"v1"}),
        authenticated,
    )
    assert boxes == ((5.0, 5.0, 30.0, 30.0),)
    assert unlocalised is False
    assert _candidate_scope(
        INSIDE,
        authenticated,
        boxes,
        unlocalised_unauthenticated=unlocalised,
    )[0] == AMBIGUOUS_AUTHENTICATED_OWNERSHIP


# ---------------------------------------------------------------------------
# F3: a bisector partition cell is not a drawn extent -> never a typed negative
# ---------------------------------------------------------------------------
def _grid_title_below() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=800, height=1000)
    page.insert_text((100, 300), "FRONT ELEVATION", fontsize=11)
    page.insert_text((100, 800), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((600, 300), "SIDE ELEVATION", fontsize=11)
    page.insert_text((600, 800), "FIRST FLOOR PLAN", fontsize=11)
    _opening(page, 60, 400)
    payload = doc.tobytes()
    doc.close()
    return payload


def test_partition_cell_never_yields_a_typed_negative() -> None:
    _s, _p, report = _assess(_grid_title_below(), "grid-below")
    assert report.candidate_scopes
    assert IN_AUTHENTICATED_NON_PLAN not in _scopes(report)
    for item in report.candidate_scopes:
        if item.view_id is not None:
            assert item.boundary_source is not None
            if item.boundary_source != "vector_frame":
                assert item.evidence_direction != EVIDENCE_DIRECTION_AGAINST_PROMOTION


def test_typed_negative_requires_a_drawn_vector_frame() -> None:
    frame = _vp(1, "elevation", PLAN)
    cell = _vp(2, "elevation", PLAN, status="derived", source="title_partition")
    assert _candidate_scope(INSIDE, [frame])[0] == IN_AUTHENTICATED_NON_PLAN
    assert _candidate_scope(INSIDE, [cell])[0] == IN_AUTHENTICATED_VIEW_TYPE_UNPROVEN


# ---------------------------------------------------------------------------
# F4: typed negatives are evidence against promotion, never deletion
# ---------------------------------------------------------------------------
def test_scope_records_carry_no_deletion_or_takeoff_authority() -> None:
    payload = _two_view()
    _s, _p, report = _assess(payload, "flags")
    assert report.deletion_authority is False and report.takeoff_eligible is False
    directions = {}
    for item in report.candidate_scopes:
        assert item.deletion_authority is False and item.takeoff_eligible is False
        directions[item.scope] = item.evidence_direction
    assert directions[IN_AUTHENTICATED_FLOOR_PLAN] == EVIDENCE_DIRECTION_SCOPE_ONLY
    assert directions[IN_AUTHENTICATED_NON_PLAN] == EVIDENCE_DIRECTION_AGAINST_PROMOTION
    assert "deletion" not in (shadow.__doc__ or "").replace("never deletion", "").replace(
        "deletion authority", ""
    ).replace("deletion_authority", "").replace("not deletion", "")


@pytest.mark.parametrize(
    "view_type",
    ["unknown", "", "FLOOR_PLAN", "site_plan", "repeated_reference", "adjacent_scope", "detail"],
)
def test_unrecognised_or_unproven_view_type_abstains_instead_of_typed_negative(view_type) -> None:
    scope, viewport = _candidate_scope(INSIDE, [_vp(1, view_type, PLAN)])
    assert scope == IN_AUTHENTICATED_VIEW_TYPE_UNPROVEN
    assert viewport is not None
    assert shadow._evidence_direction(scope) == EVIDENCE_DIRECTION_NONE


# ---------------------------------------------------------------------------
# F5: unreadable geometry abstains; it never relaxes containment
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("segments", [(), ((float("nan"), 5.0, 6.0, 6.0),), ((5.0, 5.0, float("inf"), 6.0),)])
def test_empty_or_non_finite_support_is_unreadable_not_vacuously_inside(segments) -> None:
    assert _candidate_scope(segments, [_vp(1, "floor_plan", PLAN)])[0] == SUPPORT_GEOMETRY_UNREADABLE
    assert _candidate_scope(segments, [])[0] == SUPPORT_GEOMETRY_UNREADABLE


def test_unreadable_support_observation_marks_the_whole_candidate_unreadable(monkeypatch) -> None:
    payload = _two_view(with_straddle=True, with_outside=False)
    original = shadow._line_geometry

    def patched(record):
        line = original(record)
        return None if line is not None and min(line[0], line[2]) >= 300.0 else line

    monkeypatch.setattr(shadow, "_line_geometry", patched)
    _s, _p, report = _assess(payload, "partial-geometry")
    assert SUPPORT_GEOMETRY_UNREADABLE in _scopes(report)
    assert IN_AUTHENTICATED_FLOOR_PLAN not in {
        item.scope for item in report.candidate_scopes if item.scope == SUPPORT_GEOMETRY_UNREADABLE
    }


# ---------------------------------------------------------------------------
# F6: segment crossing a view is not "outside"; unrelated content must not flip the class
# ---------------------------------------------------------------------------
def test_support_that_crosses_a_viewport_with_endpoints_outside_is_ambiguous() -> None:
    assert _candidate_scope(((-50.0, 50.0, 150.0, 50.0),), [_vp(1, "floor_plan", PLAN)])[0] == (
        AMBIGUOUS_AUTHENTICATED_OWNERSHIP
    )
    assert _candidate_scope(((-50.0, 150.0, 150.0, 150.0),), [_vp(1, "floor_plan", PLAN)])[0] == (
        OUTSIDE_AUTHENTICATED_VIEWPORTS
    )


def _plan_only(with_unrelated_frame: bool) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=800, height=500)
    page.insert_text((80, 300), "GROUND FLOOR PLAN", fontsize=11)
    _opening(page, 60, 100)
    if with_unrelated_frame:
        page.draw_rect(fitz.Rect(500, 20, 780, 300), color=(0, 0, 0), width=1)
        page.insert_text((560, 280), "LEGEND", fontsize=11)
    payload = doc.tobytes()
    doc.close()
    return payload


def test_unrelated_framed_legend_does_not_change_the_abstention_class() -> None:
    _s, _p, without = _assess(_plan_only(False), "no-legend")
    _s, _p, with_legend = _assess(_plan_only(True), "legend")
    assert _scopes(without) == _scopes(with_legend) == {NO_AUTHENTICATED_VIEWPORT}


def test_outside_needs_every_unauthenticated_view_localised() -> None:
    plan = [_vp(1, "floor_plan", PLAN)]
    far = ((500.0, 500.0, 510.0, 510.0),)
    assert _candidate_scope(far, plan)[0] == OUTSIDE_AUTHENTICATED_VIEWPORTS
    assert _candidate_scope(far, plan, unlocalised_unauthenticated=True)[0] == NO_AUTHENTICATED_VIEWPORT


def test_touching_a_contesting_rectangle_is_ambiguous_even_inside_one_authenticated_view() -> None:
    plan = [_vp(1, "floor_plan", PLAN)]
    assert _candidate_scope(INSIDE, plan, [(15.0, 15.0, 30.0, 30.0)])[0] == AMBIGUOUS_AUTHENTICATED_OWNERSHIP
    assert _candidate_scope(INSIDE, plan, [(60.0, 60.0, 90.0, 90.0)])[0] == IN_AUTHENTICATED_FLOOR_PLAN


# ---------------------------------------------------------------------------
# Failure typing mirrors the live authority
# ---------------------------------------------------------------------------
def test_stale_revision_is_typed_like_the_live_authority() -> None:
    first = _two_view()
    doc = fitz.open()
    doc.new_page(width=300, height=200)
    second = doc.tobytes()
    doc.close()
    source, old = _ingest(first, "stale", document_id="test:stale-doc")
    source.ingest_native_pdf_bytes(
        document_id="test:stale-doc", source_bytes=second, source_locator="memory://stale2.pdf"
    )
    report = assess_opening_candidate_viewport_scope(
        source_visibility_producer=source, revision_id=old.revision.revision_id, page_id="1"
    )
    assert report.status is EvidenceResolutionStatus.ABSTAINED
    assert report.candidate_scopes == ()
    assert report.reason_codes == (OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE, STALE_REVISION)


def test_snapshot_integrity_conflict_is_a_conflict_not_an_abstention(monkeypatch) -> None:
    conflict = SimpleNamespace(
        status=EvidenceResolutionStatus.CONFLICT, reason_codes=("snapshot_observation_integrity_conflict",)
    )
    monkeypatch.setattr(PhysicalOpeningAuthority, "_visible_snapshot_records", lambda self, seed: ((), (conflict,)))
    _s, _p, report = _assess(_two_view(), "integrity")
    assert report.status is EvidenceResolutionStatus.CONFLICT
    assert report.reason_codes == (
        OPENING_VIEWPORT_SCOPE_SNAPSHOT_INTEGRITY_FAILED,
        "snapshot_observation_integrity_conflict",
    )
    assert report.candidate_scopes == ()


# ---------------------------------------------------------------------------
# Determinism / invariance (AGENTS.md matrix)
# ---------------------------------------------------------------------------
def _two_view(*, scale: float = 1.0, with_outside: bool = True, with_straddle: bool = False) -> bytes:
    s = scale
    doc = fitz.open()
    page = doc.new_page(width=700 * s, height=500 * s)
    page.draw_rect(fitz.Rect(20 * s, 20 * s, 300 * s, 320 * s), color=(0, 0, 0), width=1)
    page.draw_rect(fitz.Rect(300 * s, 20 * s, 600 * s, 320 * s), color=(0, 0, 0), width=1)
    page.insert_text((70 * s, 300 * s), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((365 * s, 300 * s), "FRONT ELEVATION", fontsize=11)
    kw = dict(gap=40.0 * s, run=50.0 * s, thick=10.0 * s)
    _opening(page, 60 * s, 100 * s, **kw)
    _opening(page, 340 * s, 100 * s, **kw)
    if with_outside:
        _opening(page, 80 * s, 360 * s, **kw)
    if with_straddle:
        _opening(page, 250 * s, 200 * s, **kw)
    payload = doc.tobytes()
    doc.close()
    return payload


def test_scale_metamorphic_keeps_every_scope() -> None:
    _s, _p, base = _assess(_two_view(with_straddle=True), "scale-1")
    _s, _p, scaled = _assess(_two_view(scale=1.5, with_straddle=True), "scale-15")
    assert sorted((i.scope, i.view_type) for i in base.candidate_scopes) == sorted(
        (i.scope, i.view_type) for i in scaled.candidate_scopes
    )


def test_scope_is_invariant_under_viewport_contest_and_segment_permutation() -> None:
    plan = _vp(1, "floor_plan", (0.0, 0.0, 200.0, 200.0))
    elev = _vp(2, "elevation", (200.0, 0.0, 400.0, 200.0))
    contest = [(300.0, 100.0, 380.0, 180.0), (10.0, 150.0, 40.0, 190.0)]
    cases = [
        ((10.0, 10.0, 20.0, 20.0), (30.0, 30.0, 40.0, 40.0)),
        ((190.0, 10.0, 210.0, 10.0),),
        ((250.0, 20.0, 260.0, 20.0), (320.0, 30.0, 330.0, 30.0)),
        ((20.0, 160.0, 30.0, 170.0),),
    ]
    for segments in cases:
        expected = None
        for vps in itertools.permutations([plan, elev]):
            for boxes in itertools.permutations(contest):
                for segs in itertools.permutations(segments):
                    scope, viewport = _candidate_scope(segs, list(vps), list(boxes))
                    outcome = (scope, None if viewport is None else viewport.view_id)
                    expected = expected or outcome
                    assert outcome == expected


def test_replay_and_shadow_do_not_mutate_the_producer_store() -> None:
    payload = _two_view(with_straddle=True)
    source, published = _ingest(payload, "mutation")
    store = source._producer._store
    before_bytes = {k: bytes(v) for k, v in store.source_bytes_by_revision.items()}
    before_published = source.published_snapshot_for_revision(published.revision.revision_id)
    reports = [
        assess_opening_candidate_viewport_scope(
            source_visibility_producer=source, revision_id=published.revision.revision_id, page_id="1"
        )
        for _ in range(2)
    ]
    assert reports[0] == reports[1]
    assert {k: bytes(v) for k, v in store.source_bytes_by_revision.items()} == before_bytes
    assert source.published_snapshot_for_revision(published.revision.revision_id) == before_published


def test_all_g17_candidates_are_retained_with_identical_ids() -> None:
    source, published, report = _assess(_two_view(with_straddle=True), "retain")
    visibility = source.authority()
    from pb_source_observation_authority import ObservationSelector

    seed = next(
        visibility.resolve_visible(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=oid,
            )
        )
        for oid in published.visible_observation_ids
    )
    physical = PhysicalOpeningAuthority(visibility)
    records, failures = physical._visible_snapshot_records(seed)
    g17 = physical._visible_candidates_for(seed.observation, records)
    assert not failures
    assert sorted(c.candidate_id for c in g17) == sorted(c.candidate_id for c in report.candidate_scopes)
    assert sum(report.scope_counts.values()) == len(g17)


# ---------------------------------------------------------------------------
# Shadow isolation: nothing in the production tree may import this module
# ---------------------------------------------------------------------------
def test_no_production_module_imports_the_shadow_scope() -> None:
    root = Path(__file__).resolve().parent.parent
    name = "pb_physical_opening_viewport_scope_shadow"
    offenders = []
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if (
            relative.parts[0] in {"tests", "benchmarks", "scripts"}
            or any(part.startswith(".") for part in relative.parts)
            or relative.name == f"{name}.py"
        ):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == name:
                offenders.append(str(relative))
            elif isinstance(node, ast.Import) and any(alias.name == name for alias in node.names):
                offenders.append(str(relative))
            elif isinstance(node, ast.Constant) and node.value == name:
                offenders.append(str(relative))
    assert offenders == []
