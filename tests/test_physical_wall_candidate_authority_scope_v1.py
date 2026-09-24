"""Regressions from the W2-W5 topology gap audit (PlanReader Item 34/35 cycle).

1. ``PhysicalWallCandidateScopeResult.scope_complete`` was hardcoded to
   ``True`` on every successful resolution, regardless of whether any
   wall's dangling end actually terminated on a genuine scope boundary.
   Three boundary states matter, and only one proves a real terminus:

   - PAGE_SCOPE_BOUNDARY: the wall's dangling end sits on the PDF page's
     own edge. The drawing may simply be cropped by this sheet, with the
     wall's true continuation on an adjoining sheet or off-page.
   - VIEWPORT_SCOPE_BOUNDARY: a floor-plan (or other) drawing occupies
     only part of the sheet, framed by a real, RESOLVED vector-frame
     viewport smaller than the page. A wall ending exactly on THAT
     frame's edge is equally unproven, even nowhere near the page edge.
   - SCOPE_BOUNDS_UNRESOLVED: the page has attempted viewport structure
     (title anchors exist) but no RESOLVED (really-drawn-frame) viewport
     covers this wall's dangling end -- only DERIVED (inferred
     page-partition, no real boundary primitive -- already established
     elsewhere in this codebase as insufficient proof of a physical
     boundary) or ambiguous regions do, or viewport segmentation itself
     failed outright.
   - RESOLVED_INTERIOR_TERMINUS: every dangling end sits strictly inside
     both the page and any containing RESOLVED viewport -- the only state
     that leaves ``scope_complete`` unaffected.

   An end that meets another wall (any junction type other than
   ``ENDPOINT``) is a real, resolved terminus regardless of its position,
   and is never a candidate for cropped classification in the first place
   -- a fully-drawn, closed RESOLVED viewport frame necessarily junctions
   with anything that touches its own boundary line (there is no way for
   a wall to be both "touching the frame" and "an unconnected dangling
   end" at the same coordinate), so the VIEWPORT_SCOPE_BOUNDARY /
   SCOPE_BOUNDS_UNRESOLVED / interior-terminus classification logic
   (``_scope_boundary_reason``) is exercised directly against constructed
   ``WallCandidate`` fixtures below, the same way this codebase already
   unit-tests other narrow decision branches in isolation (e.g.
   ``learn_vector_vent_signature`` in the vent extractor's own tests)
   rather than fighting PyMuPDF's path/frame geometry to reconstruct every
   case end-to-end. The simpler PAGE_SCOPE_BOUNDARY, closed-network, and
   distinct-parallel-wall cases are still proven fully end-to-end via real
   PDF ingestion, since those do not have this conflict.

2. Two genuinely separate, non-adjacent parallel walls must each remain
   their own independent wall candidate -- neither discarded nor merged
   into one. Nothing in the current W2-W4 assembly pipeline pairs parallel
   faces into a single double-line wall (see the audit note in
   ``pb_wall_room_topology_wall_assembly.py`` acknowledging double-line
   thickness pairing is not attempted here), so this currently holds by
   omission; this test protects that property so a future face-pairing
   stage cannot silently start collapsing distinct walls that merely
   happen to run parallel to each other.

Boundary-tolerance derivation: coordinates are compared using this
module's own pre-existing ``_COORD_TOL`` (1e-6), the same exact-coincidence
tolerance already used throughout ``pb_physical_wall_candidate_authority``
for point/line comparisons (``_line``, ``_canonical_direction``,
``_trusted_face_break``, ``_same_gap``, ``_segment_matches``). No new,
hand-picked proximity constant was introduced: a native PDF coordinate
drawn exactly at a page or viewport edge decodes back to that exact value
(verified directly), so boundary detection is an exactness check, not a
tuned heuristic.
"""
from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_BOUNDS_UNRESOLVED,
    PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_PAGE_BOUNDARY,
    PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY,
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
    _resolved_viewports,
    _scope_boundary_reason,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_room_topology_contracts import JunctionType, WallCandidate

_PAGE_W, _PAGE_H = 400.0, 400.0
_FRAME = (60.0, 60.0, 300.0, 300.0)


# ── End-to-end PDF fixtures (page-boundary, closed network, distinct walls) ─


def _ingest(pdf_bytes: bytes, *, document_id: str):
    source = SourceVisibilityProducer(
        producer_method="w2-w5-scope-audit-v1", producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=document_id, source_bytes=pdf_bytes,
        source_locator=f"memory://{document_id}.pdf",
    )
    return source, published


def _resolve(source, published):
    wall_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(source).authority()
    return wall_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            decision_scope_id="wall-source:page-1",
        )
    )


def _new_page(*, width: float = _PAGE_W, height: float = _PAGE_H) -> tuple[fitz.Document, fitz.Page]:
    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    return doc, page


def _finish(doc: fitz.Document) -> bytes:
    data = bytes(doc.tobytes(garbage=4, deflate=True))
    doc.close()
    return data


def _closed_rectangle_pdf() -> bytes:
    """A fully enclosed 4-wall rectangle, no end anywhere near the page edge.

    Drawn as four independent ``page.draw_line`` calls rather than one
    ``Shape`` path: a Shape whose four lines happen to close into an
    axis-aligned rectangle gets serialized as a single stroked rect
    primitive (native "rects", not "segments"), which the wall-segment
    pipeline does not consume at all.
    """
    doc, page = _new_page()
    x0, y0, x1, y1 = 40.0, 40.0, 200.0, 160.0
    for start, end in (
        ((x0, y0), (x1, y0)),
        ((x1, y0), (x1, y1)),
        ((x1, y1), (x0, y1)),
        ((x0, y1), (x0, y0)),
    ):
        page.draw_line(fitz.Point(*start), fitz.Point(*end))
    return _finish(doc)


def _cropped_wall_pdf() -> bytes:
    """A wall whose one end lands exactly on the page's left edge (x=0), with
    no other geometry closing it there -- a genuine dangling ENDPOINT at the
    page boundary, not a real resolved terminus."""
    doc, page = _new_page()
    page.draw_line(fitz.Point(0.0, 100.0), fitz.Point(150.0, 100.0))
    return _finish(doc)


def _two_distinct_parallel_walls_pdf() -> bytes:
    """Two parallel walls, well separated, each fully inside the page --
    genuinely distinct physical walls, not two faces of one cavity wall."""
    doc, page = _new_page()
    page.draw_line(fitz.Point(40.0, 60.0), fitz.Point(280.0, 60.0))
    page.draw_line(fitz.Point(40.0, 180.0), fitz.Point(280.0, 180.0))
    return _finish(doc)


def test_fully_enclosed_wall_network_reports_scope_complete() -> None:
    source, published = _ingest(_closed_rectangle_pdf(), document_id="closed-rect")
    result = _resolve(source, published)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.scope_complete is True
    assert PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_PAGE_BOUNDARY not in result.reason_codes
    assert len(result.records) > 0


def test_wall_dangling_at_page_edge_reports_page_boundary_incomplete() -> None:
    source, published = _ingest(_cropped_wall_pdf(), document_id="cropped-wall")
    result = _resolve(source, published)
    # The wall's own geometry is still genuinely resolved and returned --
    # only completeness of the SCOPE is affected, not the individual
    # record's own status.
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.scope_complete is False
    assert PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_PAGE_BOUNDARY in result.reason_codes
    assert len(result.records) > 0


def test_two_distinct_parallel_walls_both_survive_as_separate_candidates() -> None:
    source, published = _ingest(_two_distinct_parallel_walls_pdf(), document_id="two-parallel")
    result = _resolve(source, published)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) == 2
    wall_ids = {record.wall_candidate_id for record in result.records}
    assert len(wall_ids) == 2


# ── Direct unit tests of _scope_boundary_reason / _resolved_viewports ──────


def _wall(
    *,
    pts: tuple[tuple[float, float], ...],
    ends: tuple[JunctionType, JunctionType] = (JunctionType.ENDPOINT, JunctionType.ENDPOINT),
) -> WallCandidate:
    return WallCandidate(
        candidate_id="wall-under-test",
        viewport_id="wall-source:page-1",
        representation="single_line",
        centerline_pts=pts,
        face_a_segment_ids=("seg-1",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=None,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=None,
        end_node_ids=("n1", "n2"),
        junction_types=ends,
        interior_exterior="unresolved",
        level_id=None,
        supporting_evidence_ids=("seg-1",),
    )


def _framed_page(*, offset: tuple[float, float] = (0.0, 0.0), scale: float = 1.0) -> fitz.Page:
    ox, oy = offset
    fx0, fy0, fx1, fy1 = (v * scale for v in _FRAME)
    fx0, fy0, fx1, fy1 = fx0 + ox, fy0 + oy, fx1 + ox, fy1 + oy
    doc = fitz.open()
    page = doc.new_page(width=_PAGE_W * scale + max(ox, 0.0) * 2, height=_PAGE_H * scale + max(oy, 0.0) * 2)
    page.draw_rect(fitz.Rect(fx0, fy0, fx1, fy1))
    page.insert_text((fx0 + 4.0, fy1 - 6.0), "GROUND FLOOR PLAN", fontsize=10)
    return page


def _unresolved_bounds_page() -> fitz.Page:
    """Two titled regions with no real drawn frame around either -- viewport
    structure was attempted but neither resolves (DERIVED, not RESOLVED)."""
    doc = fitz.open()
    page = doc.new_page(width=_PAGE_W, height=_PAGE_H)
    page.insert_text((30.0, 40.0), "GROUND FLOOR PLAN", fontsize=10)
    page.insert_text((30.0, 220.0), "FIRST FLOOR PLAN", fontsize=10)
    return page


def test_wall_dangling_at_viewport_edge_is_incomplete() -> None:
    page = _framed_page()
    fx0, fy0, fx1, fy1 = _FRAME
    wall = _wall(pts=((fx0 + 30.0, (fy0 + fy1) / 2.0), (fx1, (fy0 + fy1) / 2.0)))
    reason = _scope_boundary_reason(
        wall, page=page, page_number=1, page_width=_PAGE_W, page_height=_PAGE_H,
    )
    assert reason == PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY


def test_wall_clearly_inside_viewport_is_resolved_interior_terminus() -> None:
    page = _framed_page()
    fx0, fy0, fx1, fy1 = _FRAME
    wall = _wall(pts=((fx0 + 40.0, fy0 + 40.0), (fx1 - 40.0, fy0 + 40.0)))
    reason = _scope_boundary_reason(
        wall, page=page, page_number=1, page_width=_PAGE_W, page_height=_PAGE_H,
    )
    assert reason is None


def test_junction_end_at_viewport_boundary_is_never_flagged() -> None:
    """A wall end classified as a real junction (not ENDPOINT) sitting
    exactly on the viewport boundary must never be treated as cropped --
    it is a resolved connection, not a dangling end."""
    page = _framed_page()
    fx0, fy0, fx1, fy1 = _FRAME
    wall = _wall(
        pts=((fx0 + 30.0, fy0 + 30.0), (fx1, (fy0 + fy1) / 2.0)),
        ends=(JunctionType.ENDPOINT, JunctionType.T_JUNCTION),
    )
    reason = _scope_boundary_reason(
        wall, page=page, page_number=1, page_width=_PAGE_W, page_height=_PAGE_H,
    )
    assert reason is None


def test_closed_network_has_no_dangling_ends_so_no_boundary_question_arises() -> None:
    page = _framed_page()
    fx0, fy0, fx1, fy1 = _FRAME
    wall = _wall(
        pts=((fx0 + 40.0, fy0 + 40.0), (fx1 - 40.0, fy0 + 40.0)),
        ends=(JunctionType.L_CORNER, JunctionType.L_CORNER),
    )
    reason = _scope_boundary_reason(
        wall, page=page, page_number=1, page_width=_PAGE_W, page_height=_PAGE_H,
    )
    assert reason is None


def test_unresolved_viewport_bounds_do_not_claim_completeness() -> None:
    page = _unresolved_bounds_page()
    wall = _wall(pts=((80.0, 100.0), (150.0, 100.0)))
    reason = _scope_boundary_reason(
        wall, page=page, page_number=1, page_width=_PAGE_W, page_height=_PAGE_H,
    )
    assert reason == PHYSICAL_WALL_CANDIDATE_SCOPE_BOUNDS_UNRESOLVED


def test_viewport_edge_crop_detection_is_translation_invariant() -> None:
    page = _framed_page(offset=(25.0, 15.0))
    fx0, fy0, fx1, fy1 = (v for v in (_FRAME[0] + 25.0, _FRAME[1] + 15.0, _FRAME[2] + 25.0, _FRAME[3] + 15.0))
    wall = _wall(pts=((fx0 + 30.0, (fy0 + fy1) / 2.0), (fx1, (fy0 + fy1) / 2.0)))
    reason = _scope_boundary_reason(
        wall, page=page, page_number=1, page_width=_PAGE_W + 50.0, page_height=_PAGE_H + 30.0,
    )
    assert reason == PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY


def test_viewport_edge_crop_detection_is_scale_invariant() -> None:
    scale = 1.35
    page = _framed_page(scale=scale)
    fx0, fy0, fx1, fy1 = (v * scale for v in _FRAME)
    wall = _wall(pts=((fx0 + 30.0 * scale, (fy0 + fy1) / 2.0), (fx1, (fy0 + fy1) / 2.0)))
    reason = _scope_boundary_reason(
        wall, page=page, page_number=1, page_width=_PAGE_W * scale, page_height=_PAGE_H * scale,
    )
    assert reason == PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY


def test_resolved_viewports_returns_none_when_segmentation_raises(monkeypatch) -> None:
    import pb_physical_wall_candidate_authority as module

    def _boom(page, *, page_number):
        raise RuntimeError("segmentation exploded")

    monkeypatch.setattr(module, "segment_page_viewports", _boom)
    page = _unresolved_bounds_page()
    assert _resolved_viewports(page, page_number=1) is None


def _validated_columnar_grid_page() -> fitz.Page:
    doc = fitz.open()
    page = doc.new_page(width=900.0, height=700.0)

    # Three independently separated columns, two title rows each. This is the
    # exact producer-owned columnar grid subtype admitted by F.07.
    page.insert_text((80.0, 250.0), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((90.0, 620.0), "ROOF PLAN", fontsize=11)

    page.insert_text((380.0, 200.0), "ELEVATION E-01", fontsize=11)
    page.insert_text((380.0, 560.0), "SECTION S-01", fontsize=11)

    page.insert_text((680.0, 200.0), "ELEVATION E-02", fontsize=11)
    page.insert_text((680.0, 560.0), "SECTION S-02", fontsize=11)
    return page


def test_validated_columnar_grid_interior_can_prove_not_cropped() -> None:
    from pb_viewport_segmentation import (
        is_authoritative_derived_viewport,
        segment_page_viewports,
    )

    page = _validated_columnar_grid_page()
    viewports = segment_page_viewports(page, page_number=1)
    plan = next(
        v
        for v in viewports
        if v.label.upper() == "GROUND FLOOR PLAN"
        and is_authoritative_derived_viewport(v)
    )
    assert plan.bounding_box is not None
    x0, y0, x1, y1 = plan.bounding_box

    wall = _wall(
        pts=(
            (x0 + 0.30 * (x1 - x0), y0 + 0.35 * (y1 - y0)),
            (x0 + 0.70 * (x1 - x0), y0 + 0.35 * (y1 - y0)),
        )
    )
    reason = _scope_boundary_reason(
        wall,
        page=page,
        page_number=1,
        page_width=900.0,
        page_height=700.0,
    )
    assert reason is None


def test_validated_columnar_grid_synthetic_edge_still_fails_closed() -> None:
    from pb_viewport_segmentation import (
        is_authoritative_derived_viewport,
        segment_page_viewports,
    )

    page = _validated_columnar_grid_page()
    viewports = segment_page_viewports(page, page_number=1)
    plan = next(
        v
        for v in viewports
        if v.label.upper() == "GROUND FLOOR PLAN"
        and is_authoritative_derived_viewport(v)
    )
    assert plan.bounding_box is not None
    x0, y0, x1, y1 = plan.bounding_box

    wall = _wall(
        pts=(
            (x0 + 0.35 * (x1 - x0), y0 + 0.35 * (y1 - y0)),
            (x1, y0 + 0.35 * (y1 - y0)),
        )
    )
    reason = _scope_boundary_reason(
        wall,
        page=page,
        page_number=1,
        page_width=900.0,
        page_height=700.0,
    )
    assert reason == PHYSICAL_WALL_CANDIDATE_SCOPE_BOUNDS_UNRESOLVED
