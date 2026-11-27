"""Focused tests for bounded display-list eviction and OOM fallback in render_native_page_png."""
from __future__ import annotations

import hashlib

import fitz
import pytest

import pb_source_observation_authority as obs
from pb_source_observation_authority import (
    _NATIVE_CLIP_DISPLAY_LIST_CACHE_MAX_PAGES,
    SourceObservationProducer,
)


def _make_multipage_annotated_pdf(rotations: tuple[int, ...] = (0, 90, 180, 270)) -> bytes:
    doc = fitz.open()
    for idx, rot in enumerate(rotations, start=1):
        page = doc.new_page(width=400, height=300)
        page.insert_text((60, 100), f"ROOM {idx} 3450x2800", fontsize=14)
        page.draw_rect(fitz.Rect(40, 60, 260, 200), color=(0, 0, 0), width=1.5)
        annot = page.add_rect_annot(fitz.Rect(70, 120, 180, 160))
        annot.set_colors(stroke=(0.8, 0.1, 0.1))
        annot.update()
        if rot:
            page.set_rotation(rot)
    data = doc.tobytes()
    doc.close()
    return data


def _ingest(pdf_bytes: bytes):
    producer = SourceObservationProducer(
        producer_method="test-clip-render",
        producer_version="1.0.0",
    )
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    published = producer.ingest_native_pdf_bytes(
        document_id=f"doc:{digest[:16]}",
        source_bytes=pdf_bytes,
        source_locator="memory://test-clip-render.pdf",
    )
    return producer, published, digest


@pytest.mark.parametrize(
    "page_index,rotation,dpi",
    [(1, 0, 144.0), (2, 90, 144.0), (2, 90, 216.0)],
)
def test_display_list_and_direct_clipped_render_are_pixel_identical_across_rotations_and_annots(
    monkeypatch,
    page_index: int,
    rotation: int,
    dpi: float,
) -> None:
    pdf_bytes = _make_multipage_annotated_pdf((0, 90))
    producer_dl, pub_dl, digest = _ingest(pdf_bytes)
    producer_direct, pub_direct, _ = _ingest(pdf_bytes)

    clip = (30.0, 40.0, 220.0, 190.0)
    png_dl, parent_dl, frame_dl = producer_dl.render_native_page_png(
        document_id=pub_dl.revision.document_id,
        revision_id=pub_dl.revision.revision_id,
        source_sha256=digest,
        snapshot_id=pub_dl.snapshot.snapshot_id,
        page_id=str(page_index),
        dpi=dpi,
        clip_pt=clip,
        include_native_frame=True,
    )

    # Simulate MuPDF C-heap OOM on first get_displaylist call; after cache
    # eviction + gc.collect + store_shrink(100), the direct clipped retry succeeds.
    oom_cls = getattr(getattr(fitz, "mupdf", None), "FzErrorSystem", MemoryError)
    real_get_displaylist = fitz.Page.get_displaylist
    attempts = {"n": 0}

    def _boom_once_displaylist(self, annots=True):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise oom_cls("code=2: realloc (1048576 bytes) failed")
        return real_get_displaylist(self, annots=annots)

    monkeypatch.setattr(fitz.Page, "get_displaylist", _boom_once_displaylist)
    monkeypatch.setattr(obs, "_NATIVE_RENDER_METHODS", (fitz.Page.get_pixmap, _boom_once_displaylist))

    png_direct, parent_direct, frame_direct = producer_direct.render_native_page_png(
        document_id=pub_direct.revision.document_id,
        revision_id=pub_direct.revision.revision_id,
        source_sha256=digest,
        snapshot_id=pub_direct.snapshot.snapshot_id,
        page_id=str(page_index),
        dpi=dpi,
        clip_pt=clip,
        include_native_frame=True,
    )

    assert png_direct == png_dl
    assert parent_direct.source_sha256 == parent_dl.source_sha256 == digest
    assert frame_direct == frame_dl
    assert frame_direct.rotation == rotation
    stats = producer_direct.native_render_stats()
    assert stats["display_list_oom_fallbacks"] == 1
    assert len(producer_direct._native_clip_display_lists) == 0


def test_display_list_cache_evicts_before_allocating_new_page_and_tracks_hits() -> None:
    pdf_bytes = _make_multipage_annotated_pdf((0, 0, 0, 0))
    producer, pub, digest = _ingest(pdf_bytes)
    clip = (20.0, 20.0, 200.0, 180.0)

    # Render page 1 twice (miss + hit), then pages 2 and 3 (eviction before allocating page 3)
    for page_id in ("1", "1", "2", "3", "4"):
        png, _parent = producer.render_native_page_png(
            document_id=pub.revision.document_id,
            revision_id=pub.revision.revision_id,
            source_sha256=digest,
            snapshot_id=pub.snapshot.snapshot_id,
            page_id=page_id,
            dpi=144.0,
            clip_pt=clip,
        )
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(producer._native_clip_display_lists) <= _NATIVE_CLIP_DISPLAY_LIST_CACHE_MAX_PAGES

    stats = producer.native_render_stats()
    assert stats["clip_calls"] == 5
    assert stats["display_list_hits"] == 1
    assert stats["display_list_misses"] == 4
    assert stats["display_list_evictions"] == 2
    assert stats["display_list_oom_fallbacks"] == 0


def test_oom_fallback_clears_previously_cached_display_lists_and_succeeds(monkeypatch) -> None:
    pdf_bytes = _make_multipage_annotated_pdf((0, 0, 0))
    producer, pub, digest = _ingest(pdf_bytes)
    clip = (25.0, 25.0, 210.0, 175.0)

    # Populate cache with pages 1 and 2
    for page_id in ("1", "2"):
        producer.render_native_page_png(
            document_id=pub.revision.document_id,
            revision_id=pub.revision.revision_id,
            source_sha256=digest,
            snapshot_id=pub.snapshot.snapshot_id,
            page_id=page_id,
            dpi=144.0,
            clip_pt=clip,
        )
    assert len(producer._native_clip_display_lists) == 2

    # Simulate MemoryError on first page-3 display-list allocation; after
    # evicting cached display lists + store_shrink, direct clipped retry succeeds.
    real_get_displaylist = fitz.Page.get_displaylist
    attempts = {"n": 0}

    def _boom_once_mem(self, annots=True):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise MemoryError("simulated C heap exhaustion")
        return real_get_displaylist(self, annots=annots)

    monkeypatch.setattr(fitz.Page, "get_displaylist", _boom_once_mem)
    monkeypatch.setattr(obs, "_NATIVE_RENDER_METHODS", (fitz.Page.get_pixmap, _boom_once_mem))

    png, _parent = producer.render_native_page_png(
        document_id=pub.revision.document_id,
        revision_id=pub.revision.revision_id,
        source_sha256=digest,
        snapshot_id=pub.snapshot.snapshot_id,
        page_id="3",
        dpi=144.0,
        clip_pt=clip,
    )
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(producer._native_clip_display_lists) == 0
    stats = producer.native_render_stats()
    assert stats["display_list_oom_fallbacks"] == 1


def test_invalid_clip_still_fails_closed() -> None:
    pdf_bytes = _make_multipage_annotated_pdf((0,))
    producer, pub, digest = _ingest(pdf_bytes)
    with pytest.raises(ValueError, match="invalid_render_clip"):
        producer.render_native_page_png(
            document_id=pub.revision.document_id,
            revision_id=pub.revision.revision_id,
            source_sha256=digest,
            snapshot_id=pub.snapshot.snapshot_id,
            page_id="1",
            dpi=144.0,
            clip_pt=(-10.0, 0.0, 100.0, 100.0),
        )
