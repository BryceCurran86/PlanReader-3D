"""Regression coverage for batched source-visibility publication.

The visibility wrapper must not create one immutable whole-source snapshot per
visible segment. SourceObservationProducer already exposes a producer-owned batch
primitive; exercising it here keeps the wrapper linear in source size and
prevents the snapshot-growth failure seen on large drawing packages.
"""
from __future__ import annotations

import fitz

from pb_source_visibility_authority import SourceVisibilityProducer


def _many_segments_pdf(count: int = 120) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=900.0, height=700.0)
        for index in range(count):
            y = 20.0 + (index % 100) * 5.0
            x = 20.0 + (index // 100) * 250.0
            page.draw_line(
                fitz.Point(x, y),
                fitz.Point(x + 180.0, y),
                width=1.0,
            )
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_native_visible_segments_use_one_batch_snapshot(monkeypatch) -> None:
    source = SourceVisibilityProducer(
        producer_method="source-visibility-batch-regression",
        producer_version="1",
    )

    def _single_publish_forbidden(**_kwargs):
        raise AssertionError(
            "SourceVisibilityProducer must not publish visible segments one snapshot at a time"
        )

    original_batch = source._producer.publish_derived_observations
    batch_sizes: list[int] = []

    def _record_batch(**kwargs):
        batch_sizes.append(len(kwargs["observations"]))
        return original_batch(**kwargs)

    monkeypatch.setattr(
        source._producer,
        "publish_derived_observation",
        _single_publish_forbidden,
    )
    monkeypatch.setattr(
        source._producer,
        "publish_derived_observations",
        _record_batch,
    )

    published = source.ingest_native_pdf_bytes(
        document_id="source-visibility-batch-regression",
        source_bytes=_many_segments_pdf(),
        source_locator="memory://source-visibility-batch-regression.pdf",
    )

    assert published.visible_observation_ids
    assert batch_sizes == [len(published.visible_observation_ids)]
    assert published.snapshot.parent_snapshot_id == published.base_source_snapshot_id

    # Base source snapshot + one derived visibility snapshot.  The regression
    # this guards used one additional full snapshot per visible segment.
    assert len(source._producer._store.snapshots) == 2
