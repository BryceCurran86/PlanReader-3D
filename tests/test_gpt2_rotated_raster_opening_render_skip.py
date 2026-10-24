"""Source-verified rotated raster-opening render bypass; no authority promotion."""
from __future__ import annotations

import fitz
import numpy as np
import cv2
import pytest

from pb_source_visibility_authority import SourceVisibilityProducer
from pb_source_observation_authority import SourceObservationProducer
from pb_native_page_frame import NativePageFrameUnresolved


def _image_pdf(rotation: int, *, has_image: bool = True) -> bytes:
    pdf = fitz.open()
    page = pdf.new_page(width=320, height=200)
    if has_image:
        gray = np.full((70, 120), 255, np.uint8)
        cv2.rectangle(gray, (10, 25), (110, 40), 0, -1)
        ok, payload = cv2.imencode(".png", gray)
        assert ok
        page.insert_image(fitz.Rect(10, 10, 260, 160), stream=bytes(payload))
    page.set_rotation(rotation)
    result = pdf.tobytes()
    pdf.close()
    return result


def _source(rotation: int, *, has_image: bool = True):
    source = SourceVisibilityProducer(
        producer_method="gpt2-rotated-raster-skip", producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"source-{rotation}-{has_image}",
        source_bytes=_image_pdf(rotation, has_image=has_image),
        source_locator="memory:source.pdf", page_ids=("1",),
    )
    return source, published


def test_rotated_source_image_never_enters_unusable_renderer(monkeypatch):
    source, published = _source(90)
    def render_forbidden(**kwargs):
        raise AssertionError("source-unsupported rotated opening render")
    monkeypatch.setattr(source._producer, "render_native_page_png", render_forbidden)
    result = source.augment_with_raster_opening_primitives(
        published.revision.revision_id, page_ids=("1",),
    )
    assert result.snapshot.snapshot_id == published.snapshot.snapshot_id
    assert result.raster_opening_primitive_observation_ids == ()
    assert result.revision.source_sha256 == published.revision.source_sha256
    result2 = source.augment_with_raster_opening_primitives(
        published.revision.revision_id, page_ids=("1",),
    )
    assert result2.snapshot.snapshot_id == published.snapshot.snapshot_id


def test_zero_rotation_keeps_exact_existing_render(monkeypatch):
    source, published = _source(0)
    called = []
    old_render = source._producer.render_native_page_png
    def recorded(**kwargs):
        called.append(kwargs)
        return old_render(**kwargs)
    monkeypatch.setattr(source._producer, "render_native_page_png", recorded)
    result = source.augment_with_raster_opening_primitives(
        published.revision.revision_id, page_ids=("1",),
    )
    assert len(called) == 1
    assert called[0]["images_only"] is True
    assert called[0]["include_native_frame"] is True
    assert result.revision.source_sha256 == published.revision.source_sha256


@pytest.mark.parametrize("rotation", (0, 90))
def test_optional_frame_preserves_existing_regions_and_exact_source_sha(rotation):
    p = SourceObservationProducer(producer_method="frame-source", producer_version="1")
    published = p.ingest_native_pdf_bytes(
        document_id="source", source_bytes=_image_pdf(rotation),
        source_locator="memory:source.pdf", page_ids=("1",),
    )
    selector = dict(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
    )
    ordinary = p.native_page_image_regions(**selector)
    with_frame, frame = p.native_page_image_regions(
        **selector, include_native_frame=True,
    )
    assert ordinary == with_frame and ordinary
    assert frame.rotation == rotation
    with pytest.raises(ValueError):
        p.native_page_image_regions(
            **{**selector, "source_sha256": "b" * 64},
            include_native_frame=True,
        )


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
def test_image_free_pages_preserve_old_early_return_without_render(monkeypatch, rotation):
    source, published = _source(rotation, has_image=False)
    def render_forbidden(**kwargs):
        raise AssertionError("image-free page should skip raster render")
    monkeypatch.setattr(source._producer, "render_native_page_png", render_forbidden)
    result = source.augment_with_raster_opening_primitives(
        published.revision.revision_id, page_ids=("1",),
    )
    assert result.raster_opening_primitive_observation_ids == ()


@pytest.mark.parametrize("rotation", (180, 270))
def test_unsupported_page_frame_remains_explicitly_unresolved(rotation):
    source, published = _source(rotation)
    with pytest.raises(NativePageFrameUnresolved):
        source.augment_with_raster_opening_primitives(
            published.revision.revision_id, page_ids=("1",),
        )
    assert not source._raster_opening_primitive_attempted_pages
