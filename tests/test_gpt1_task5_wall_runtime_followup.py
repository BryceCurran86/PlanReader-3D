from __future__ import annotations

from dataclasses import replace

import fitz
import pytest

from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_source_observation_authority import ObservationSelector, SourceObservationProducer
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import _page_rectangle_primitives


class _Rect:
    def __init__(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1


class _CountingItems(list):
    def __init__(self, *args):
        super().__init__(*args)
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        return super().__iter__()


class _FakePage:
    def __init__(self, items) -> None:
        self.items = items
        self.get_drawings_calls = 0

    def get_drawings(self):
        self.get_drawings_calls += 1
        return ({"items": self.items},)


def _vector_pdf() -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=300.0, height=200.0)
        shape = page.new_shape()
        shape.draw_line((20.0, 60.0), (280.0, 60.0))
        shape.finish(width=1.0)
        shape.commit()
        page.insert_text((30.0, 100.0), "CACHE")
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_rectangle_primitive_normalisation_is_cached_per_page() -> None:
    items = _CountingItems(
        [
            ("re", _Rect(10.0, 10.0, 20.0, 20.0)),
            ("l", (0.0, 0.0), (30.0, 30.0)),
            ("re", _Rect(40.0, 40.0, 70.0, 80.0)),
        ]
    )
    page = _FakePage(items)

    first = _page_rectangle_primitives(page)
    second = _page_rectangle_primitives(page)

    assert first == second == (
        (10.0, 10.0, 20.0, 20.0),
        (40.0, 40.0, 70.0, 80.0),
    )
    assert page.get_drawings_calls == 1
    assert items.iterations == 1


def test_internal_verified_cache_reuses_frozen_record_but_public_reads_copy() -> None:
    producer = SourceObservationProducer(
        producer_method="task5-cache-seed",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="task5-cache-seed",
        source_bytes=_vector_pdf(),
        source_locator="memory://task5-cache-seed.pdf",
        page_ids=("1",),
    )
    observation_id = published.snapshot.observation_ids[0]
    key = (published.snapshot.snapshot_id, observation_id)
    stored = producer._store.observations[key]
    cached_result = producer._store.verified_resolution_cache[key][4]

    assert cached_result.observation is stored

    selector = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )
    first = producer.authority().resolve(selector)
    assert first.observation is not stored
    original_text = stored.raw_text

    object.__setattr__(first.observation, "raw_text", "tampered")
    second = producer.authority().resolve(selector)

    assert stored.raw_text == original_text
    assert second.observation is not stored
    assert second.observation.raw_text == original_text


def test_opening_snapshot_materialization_uses_batch_visibility(monkeypatch) -> None:
    source = SourceVisibilityProducer(
        producer_method="task5-opening-batch",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="task5-opening-batch",
        source_bytes=_vector_pdf(),
        source_locator="memory://task5-opening-batch.pdf",
        page_ids=("1",),
    )
    assert published.visible_observation_ids

    authority = PhysicalOpeningAuthority.from_source_visibility_producer(source)
    selector = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=published.visible_observation_ids[0],
    )
    seed = authority._resolve_visible_cached(selector)
    visibility = authority.source_visibility_authority()
    assert visibility is not None

    def forbidden_scalar(_selector):
        raise AssertionError("snapshot materialization must use batch visibility")

    monkeypatch.setattr(visibility, "resolve_visible", forbidden_scalar)

    records, failures = authority._visible_snapshot_records(seed)

    assert failures == ()
    assert {record.observation_id for record in records} == set(
        published.visible_observation_ids
    )
