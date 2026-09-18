"""Regressions from the W2-W5 topology gap audit (PlanReader Item 34/35 cycle).

1. ``PhysicalWallCandidateScopeResult.scope_complete`` was hardcoded to
   ``True`` on every successful resolution, regardless of whether any wall's
   dangling end actually terminated on the page's own boundary -- i.e. a
   wall this sheet crops (its true continuation may run onto an adjoining
   sheet, or simply off this page) was indistinguishable from a wall whose
   end is a real, fully-resolved terminus. A cropped wall network must not
   silently claim completeness.
2. Two genuinely separate, non-adjacent parallel walls must each remain
   their own independent wall candidate -- neither discarded nor merged
   into one. Nothing in the current W2-W4 assembly pipeline pairs parallel
   faces into a single double-line wall (see the audit note in
   ``pb_wall_room_topology_wall_assembly.py`` acknowledging double-line
   thickness pairing is not attempted here), so this currently holds by
   omission; this test protects that property so a future face-pairing
   stage cannot silently start collapsing distinct walls that merely
   happen to run parallel to each other.
"""
from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_BOUNDARY,
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer

_PAGE_W, _PAGE_H = 320.0, 240.0


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


def _draw_lines(shape, lines) -> None:
    for start, end in lines:
        shape.draw_line(fitz.Point(*start), fitz.Point(*end))


def _closed_rectangle_pdf() -> bytes:
    """A fully enclosed 4-wall rectangle, no end anywhere near the page edge.

    Drawn as four independent ``page.draw_line`` calls rather than one
    ``Shape`` path: a Shape whose four lines happen to close into an
    axis-aligned rectangle gets serialized as a single stroked rect
    primitive (native "rects", not "segments"), which the wall-segment
    pipeline does not consume at all -- that would test PyMuPDF's path
    optimizer, not this module.
    """
    doc = fitz.open()
    try:
        page = doc.new_page(width=_PAGE_W, height=_PAGE_H)
        x0, y0, x1, y1 = 40.0, 40.0, 200.0, 160.0
        for start, end in (
            ((x0, y0), (x1, y0)),
            ((x1, y0), (x1, y1)),
            ((x1, y1), (x0, y1)),
            ((x0, y1), (x0, y0)),
        ):
            page.draw_line(fitz.Point(*start), fitz.Point(*end))
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _cropped_wall_pdf() -> bytes:
    """A wall whose one end lands exactly on the page's left edge (x=0), with
    no other geometry closing it there -- a genuine dangling ENDPOINT at the
    page boundary, not a real resolved terminus."""
    doc = fitz.open()
    try:
        page = doc.new_page(width=_PAGE_W, height=_PAGE_H)
        shape = page.new_shape()
        _draw_lines(shape, [((0.0, 100.0), (150.0, 100.0))])
        shape.finish(width=1.0)
        shape.commit()
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _two_distinct_parallel_walls_pdf() -> bytes:
    """Two parallel walls, well separated, each fully inside the page --
    genuinely distinct physical walls, not two faces of one cavity wall."""
    doc = fitz.open()
    try:
        page = doc.new_page(width=_PAGE_W, height=_PAGE_H)
        shape = page.new_shape()
        _draw_lines(
            shape,
            [
                ((40.0, 60.0), (280.0, 60.0)),
                ((40.0, 180.0), (280.0, 180.0)),
            ],
        )
        shape.finish(width=1.0)
        shape.commit()
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_fully_enclosed_wall_network_reports_scope_complete() -> None:
    source, published = _ingest(_closed_rectangle_pdf(), document_id="closed-rect")
    result = _resolve(source, published)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.scope_complete is True
    assert PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_BOUNDARY not in result.reason_codes
    assert len(result.records) > 0


def test_wall_dangling_at_page_boundary_reports_scope_incomplete() -> None:
    source, published = _ingest(_cropped_wall_pdf(), document_id="cropped-wall")
    result = _resolve(source, published)
    # The wall's own geometry is still genuinely resolved and returned --
    # only completeness of the SCOPE is affected, not the individual
    # record's own status.
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.scope_complete is False
    assert PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_BOUNDARY in result.reason_codes
    assert len(result.records) > 0


def test_two_distinct_parallel_walls_both_survive_as_separate_candidates() -> None:
    source, published = _ingest(_two_distinct_parallel_walls_pdf(), document_id="two-parallel")
    result = _resolve(source, published)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    # Two separate walls, each its own candidate -- neither merged into the
    # other nor dropped for being "duplicate-looking" parallel geometry.
    assert len(result.records) == 2
    wall_ids = {record.wall_candidate_id for record in result.records}
    assert len(wall_ids) == 2
