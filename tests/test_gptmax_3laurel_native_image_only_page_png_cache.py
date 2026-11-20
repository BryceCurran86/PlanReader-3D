"""Image-only source rendering may reuse pixels but never authority."""
import fitz
import pytest

from pb_source_observation_authority import SourceObservationProducer, ProducerIntegrityError
from tests.test_raster_opening_source_primitives import _embedded_image_pdf


def _scene():
    producer = SourceObservationProducer(producer_method="cache-review", producer_version="1")
    published = producer.ingest_native_pdf_bytes(
        document_id="cache-review", source_bytes=_embedded_image_pdf(vector_overlay=True),
        source_locator="memory://cache-review.pdf", page_ids=("1",),
    )
    args = dict(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1", dpi=144, images_only=True,
    )
    return producer, published, args


def test_duplicate_render_avoids_redacting_again(monkeypatch):
    producer, _, args = _scene()
    first, parent = producer.render_native_page_png(**args)
    assert first and len(producer._native_image_only_png_cache) == 1

    def forbidden(*_a, **_kw):
        raise AssertionError("duplicate page redaction must not run")

    with monkeypatch.context() as ctx:
        ctx.setattr(fitz.Document, "insert_pdf", forbidden)
        repeated, other_parent, frame = producer.render_native_page_png(
            **args, include_native_frame=True,
        )
    assert first == repeated
    assert parent == other_parent and parent is not other_parent
    assert frame.native_width > 0


def test_cached_bytes_do_not_bypass_source_integrity():
    producer, published, args = _scene()
    first, _ = producer.render_native_page_png(**args)
    assert first
    producer._store.source_bytes_by_revision[published.revision.revision_id] = b"corrupt pdf"
    with pytest.raises(ProducerIntegrityError):
        producer.render_native_page_png(**args)


def test_different_dpi_is_not_reused_and_cache_is_bounded():
    producer, _, args = _scene()
    buffers = []
    for dpi in (72, 144, 180, 216):
        png, _ = producer.render_native_page_png(**{**args, "dpi": dpi})
        buffers.append(png)
    assert len({len(png) for png in buffers}) > 1
    assert len(producer._native_image_only_png_cache) == 3
    assert (args["source_sha256"], 1, 72.0) not in producer._native_image_only_png_cache


def test_full_and_images_only_outputs_cannot_share_cache():
    producer, _, args = _scene()
    images, _ = producer.render_native_page_png(**args)
    full, _ = producer.render_native_page_png(**{**args, "images_only": False})
    assert images != full
    images2, _ = producer.render_native_page_png(**args)
    assert images2 == images
