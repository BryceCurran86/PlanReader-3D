from __future__ import annotations

from types import SimpleNamespace

import fitz

from pb_source_visibility_authority import SourceVisibilityProducer


def _single_blank_page_pdf() -> bytes:
    doc = fitz.open()
    try:
        doc.new_page(width=300.0, height=200.0)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_raster_visibility_does_not_rerender_same_revision_page_after_empty_detection(
    monkeypatch,
) -> None:
    payload = _single_blank_page_pdf()
    producer = SourceVisibilityProducer(
        producer_method="test-raster-idempotency",
        producer_version="1.0.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="doc-raster-idempotency",
        source_bytes=payload,
        source_locator="memory://raster-idempotency.pdf",
    )

    render_calls: list[str] = []

    def fake_render_native_page_png(**kwargs):
        render_calls.append(str(kwargs["page_id"]))
        return (
            b"deterministic-render",
            SimpleNamespace(
                source_partition_id=f"page:{kwargs['page_id']}",
                observation_id="unused-for-empty-detection",
            ),
        )

    monkeypatch.setattr(
        producer._producer,
        "render_native_page_png",
        fake_render_native_page_png,
    )
    monkeypatch.setattr(
        "pb_source_visibility_authority.detect_axis_aligned_raster_segments",
        lambda *args, **kwargs: (),
    )

    first = producer.augment_with_raster_visible_segments(
        published.revision.revision_id,
        page_ids=("1",),
    )
    second = producer.augment_with_raster_visible_segments(
        published.revision.revision_id,
        page_ids=("1",),
    )

    assert first.snapshot.snapshot_id == published.snapshot.snapshot_id
    assert second.snapshot.snapshot_id == first.snapshot.snapshot_id
    assert render_calls == ["1"]
