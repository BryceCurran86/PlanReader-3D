"""Real-PDF regression for source-owned annotation-mask proof.

Every case drives real PDF bytes through the production wall-candidate
authority.  Mask rectangles are sized from the text receipt geometry the
production text authority actually reports, never from a hand-tuned margin.
"""
from __future__ import annotations

import fitz
import pytest

import pb_physical_wall_candidate_authority as walls
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer

_TEXT = "TAG"
_FONT = 6.0
_AT = (120.0, 118.0)


def _room(page: fitz.Page) -> None:
    for a, b in (
        ((40, 40), (280, 40)),
        ((280, 40), (280, 200)),
        ((280, 200), (40, 200)),
        ((40, 200), (40, 40)),
    ):
        page.draw_line(a, b, width=1.2)


def _doc_bytes(draw) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=240.0)
        draw(page)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _scope(data: bytes):
    producer = SourceVisibilityProducer(
        producer_method="text-mask-real-pdf", producer_version="1"
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="text-mask-real-pdf",
        source_bytes=data,
        source_locator="memory://text-mask-real-pdf.pdf",
    )
    authority = walls.PhysicalWallCandidateProducer.from_source_visibility_producer(
        producer, page_ids=("1",)
    ).authority()
    scope = authority.resolve_scope(
        walls.PhysicalWallCandidateSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            decision_scope_id="wall-source:page-1",
        )
    )
    return producer, published, scope


def _receipt_geometry() -> tuple[float, float, float, float]:
    """Geometry the production text authority reports for the tag text."""

    def draw(page):
        page.insert_text(_AT, _TEXT, fontsize=_FONT)

    producer, published, _scope_result = _scope(_doc_bytes(draw))
    receipts = walls._text_receipts_by_page(
        source_producer=producer, published=published
    )["1"]
    assert len(receipts) == 1
    return walls._receipt_geometry_bbox(receipts[0])


def _mask_rect(pad: float = 0.0) -> fitz.Rect:
    x0, y0, x1, y1 = _receipt_geometry()
    return fitz.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad)


def _baseline_records() -> int:
    _p, _pub, scope = _scope(_doc_bytes(_room))
    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    return len(scope.records)


def _records(draw) -> int:
    _p, _pub, scope = _scope(_doc_bytes(draw))
    assert scope.status is EvidenceResolutionStatus.CORROBORATED
    assert scope.scope_complete is True
    return len(scope.records)


def test_producer_owned_text_backing_mask_is_excluded() -> None:
    def draw(page):
        _room(page)
        page.draw_rect(_mask_rect(0.25), color=None, fill=(1, 1, 1))
        page.insert_text(_AT, _TEXT, fontsize=_FONT)

    # The mask rectangle contributes no wall candidates.
    assert _records(draw) == _baseline_records()


@pytest.mark.parametrize("fill", [(1, 1, 1), (0.5, 0.5, 0.5)])
def test_unmasked_fill_rectangle_without_text_is_retained(fill) -> None:
    def draw(page):
        _room(page)
        page.draw_rect(_mask_rect(0.25), color=None, fill=fill)

    # No text follows the rectangle: no proof, geometry preserved.
    assert _records(draw) > _baseline_records()


def test_large_filled_wall_body_with_contained_tag_is_retained() -> None:
    def draw(page):
        _room(page)
        # A real filled wall body; the tag is contained but is a small
        # fraction of the body, so it is not a text-sized backing mask.
        page.draw_rect(fitz.Rect(60, 100, 260, 108), color=None, fill=(0, 0, 0))
        page.insert_text((150, 106), "W", fontsize=4.0)

    assert _records(draw) > _baseline_records()


def test_text_painted_before_rectangle_does_not_authenticate() -> None:
    def draw(page):
        _room(page)
        page.insert_text(_AT, _TEXT, fontsize=_FONT)
        page.draw_rect(_mask_rect(0.25), color=None, fill=(1, 1, 1))

    # Paint order is part of the proof: text first is ambiguous -> preserved.
    assert _records(draw) > _baseline_records()


def test_text_not_contained_by_rectangle_does_not_authenticate() -> None:
    def draw(page):
        _room(page)
        rect = _mask_rect(0.25)
        page.draw_rect(rect, color=None, fill=(1, 1, 1))
        page.insert_text((_AT[0] + 40.0, _AT[1]), _TEXT, fontsize=_FONT)

    assert _records(draw) > _baseline_records()


def test_stroked_rectangle_does_not_authenticate() -> None:
    def draw(page):
        _room(page)
        page.draw_rect(_mask_rect(0.25), color=(0, 0, 0), fill=(1, 1, 1), width=0.5)
        page.insert_text(_AT, _TEXT, fontsize=_FONT)

    assert _records(draw) > _baseline_records()


def test_rectangle_far_larger_than_text_does_not_authenticate() -> None:
    def draw(page):
        _room(page)
        page.draw_rect(_mask_rect(12.0), color=None, fill=(1, 1, 1))
        page.insert_text(_AT, _TEXT, fontsize=_FONT)

    assert _records(draw) > _baseline_records()


def test_valid_wall_extraction_is_unchanged_by_the_mask_proof(monkeypatch) -> None:
    def draw(page):
        _room(page)
        page.insert_text((60.0, 60.0), "ROOM", fontsize=8.0)

    data = _doc_bytes(draw)
    _p, _pub, with_proof = _scope(data)
    monkeypatch.setattr(
        walls,
        "_annotate_producer_owned_annotation_masks",
        lambda segments, *, text_receipts: tuple(dict(s) for s in segments),
    )
    _p, _pub, without_proof = _scope(data)

    assert [r.wall_candidate_id for r in with_proof.records] == [
        r.wall_candidate_id for r in without_proof.records
    ]
    assert with_proof.reason_codes == without_proof.reason_codes
    assert with_proof.scope_complete == without_proof.scope_complete


def test_mask_proof_is_deterministic_across_replay() -> None:
    def draw(page):
        _room(page)
        page.draw_rect(_mask_rect(0.25), color=None, fill=(1, 1, 1))
        page.insert_text(_AT, _TEXT, fontsize=_FONT)

    data = _doc_bytes(draw)
    first = _scope(data)[2]
    second = _scope(data)[2]
    assert [r.wall_candidate_id for r in first.records] == [
        r.wall_candidate_id for r in second.records
    ]
