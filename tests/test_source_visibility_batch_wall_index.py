from __future__ import annotations

from io import BytesIO

import fitz
from PIL import Image
import pytest

import pb_source_visibility_authority as visibility_module
from pb_physical_wall_candidate_authority import _visible_observations_by_page
from pb_raster_visible_segment_detector import RasterDetectedSegment
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityAuthority, SourceVisibilityProducer


def _vector_pdf() -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=300, height=200)
        shape = page.new_shape()
        for index in range(40):
            y = 20 + index * 3
            shape.draw_line((20, y), (280, y))
        shape.finish(width=1)
        shape.commit()
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _image_pdf() -> bytes:
    image = Image.new("RGB", (400, 240), "white")
    out = BytesIO()
    image.save(out, format="PNG")
    doc = fitz.open()
    try:
        page = doc.new_page(width=200, height=120)
        page.insert_image(page.rect, stream=out.getvalue(), keep_proportion=False)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def test_bulk_visible_authentication_matches_scalar_native_results() -> None:
    producer = SourceVisibilityProducer(
        producer_method="batch-visible-native",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="batch-visible-native",
        source_bytes=_vector_pdf(),
        source_locator="memory://batch-visible-native.pdf",
        page_ids=("1",),
    )
    authority = producer.authority()
    batch = authority.authenticated_visible_observations(published)
    scalar = tuple(
        (
            observation_id,
            authority.resolve_visible(_selector(published, observation_id)).observation,
        )
        for observation_id in published.visible_observation_ids
    )
    assert batch == scalar


def test_bulk_visible_authentication_matches_scalar_raster_results(monkeypatch) -> None:
    segment = RasterDetectedSegment(
        pixel_geometry=(40.0, 120.0, 360.0, 120.0),
        geometry_pt=(20.0, 60.0, 180.0, 60.0),
        orientation="horizontal",
    )
    monkeypatch.setattr(
        visibility_module,
        "detect_axis_aligned_raster_segments",
        lambda *args, **kwargs: (segment,),
    )
    producer = SourceVisibilityProducer(
        producer_method="batch-visible-raster",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="batch-visible-raster",
        source_bytes=_image_pdf(),
        source_locator="memory://batch-visible-raster.pdf",
        page_ids=("1",),
    )
    published = producer.augment_with_raster_visible_segments(
        published.revision.revision_id,
        page_ids=("1",),
    )
    authority = producer.authority()
    batch = authority.authenticated_visible_observations(published)
    scalar = tuple(
        (
            observation_id,
            authority.resolve_visible(_selector(published, observation_id)).observation,
        )
        for observation_id in published.visible_observation_ids
    )
    assert batch == scalar


def test_wall_visible_index_uses_bulk_authority_not_scalar_calls(monkeypatch) -> None:
    producer = SourceVisibilityProducer(
        producer_method="batch-visible-wall-index",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="batch-visible-wall-index",
        source_bytes=_vector_pdf(),
        source_locator="memory://batch-visible-wall-index.pdf",
        page_ids=("1",),
    )

    def forbidden_scalar(self, selector):
        raise AssertionError("wall indexing must not resolve visible observations one-by-one")

    monkeypatch.setattr(SourceVisibilityAuthority, "resolve_visible", forbidden_scalar)
    indexed = _visible_observations_by_page(
        source_producer=producer,
        published=published,
    )
    assert set(indexed) == {"1"}
    assert len(indexed["1"]) == len(published.visible_observation_ids)


def test_bulk_visible_authentication_fails_closed_on_fingerprint_tamper() -> None:
    producer = SourceVisibilityProducer(
        producer_method="batch-visible-tamper",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="batch-visible-tamper",
        source_bytes=_vector_pdf(),
        source_locator="memory://batch-visible-tamper.pdf",
        page_ids=("1",),
    )
    observation_id = published.visible_observation_ids[0]
    key = (published.snapshot.snapshot_id, observation_id)
    producer._producer._store.record_fingerprints[key] = "0" * 64

    with pytest.raises(RuntimeError):
        producer.authority().authenticated_visible_observations(published)
