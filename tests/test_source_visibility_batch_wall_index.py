from __future__ import annotations

from dataclasses import replace
from io import BytesIO

import fitz
from PIL import Image
import pytest

import pb_source_visibility_authority as visibility_module
from pb_physical_wall_candidate_authority import _visible_observations_by_page
from pb_raster_visible_segment_detector import RasterDetectedSegment
from pb_migration_contracts import EvidenceResolutionStatus
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


@pytest.mark.parametrize("damage", ["parent-fingerprint", "parent-record", "receipt-repointed"])
def test_bulk_visible_authentication_fails_closed_on_fingerprint_tamper(damage: str) -> None:
    """A native visible line is a read view of its native parent (no stored record or fingerprint of its own).

    So the evidence that can be tampered with is the parent's stored record and fingerprint, and the receipt that
    names the parent. Each must fail closed in the bulk read and in the scalar read.
    """
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
    snapshot_id = published.snapshot.snapshot_id
    store = producer._producer._store
    parent_id = producer._visibility_receipts[(snapshot_id, observation_id)]
    assert (snapshot_id, observation_id) not in store.observations
    if damage == "parent-fingerprint":
        store.record_fingerprints[(snapshot_id, parent_id)] = "0" * 64
    elif damage == "parent-record":
        record = store.observations[(snapshot_id, parent_id)]
        store.observations[(snapshot_id, parent_id)] = replace(
            record, geometry=tuple(value + 1.0 for value in record.geometry)
        )
    else:
        other = next(
            candidate
            for (receipt_snapshot, _visible), candidate in producer._visibility_receipts.items()
            if receipt_snapshot == snapshot_id and candidate != parent_id
        )
        producer._visibility_receipts[(snapshot_id, observation_id)] = other

    with pytest.raises(RuntimeError):
        producer.authority().authenticated_visible_observations(published)
    scalar = producer.authority().resolve_visible(_selector(published, observation_id))
    assert scalar.status is not EvidenceResolutionStatus.CORROBORATED
    assert scalar.observation is None


def test_visible_alias_identity_binds_parent_geometry_and_origin_kind() -> None:
    """The visible id hashes parent, geometry and origin kind, so no field of the read view can be swapped."""
    producer = SourceVisibilityProducer(
        producer_method="batch-visible-identity",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="batch-visible-identity",
        source_bytes=_vector_pdf(),
        source_locator="memory://batch-visible-identity.pdf",
        page_ids=("1",),
    )
    snapshot_id = published.snapshot.snapshot_id
    store = producer._producer._store
    checked = 0
    for observation_id in published.visible_observation_ids:
        parent = store.observations[
            (snapshot_id, producer._visibility_receipts[(snapshot_id, observation_id)])
        ]
        origin_kind = producer._visible_origin_kinds[(snapshot_id, observation_id)]
        assert visibility_module._native_visible_alias_identity_holds(parent, observation_id, origin_kind)
        assert not visibility_module._native_visible_alias_identity_holds(
            replace(parent, geometry=tuple(value + 1.0 for value in parent.geometry)), observation_id, origin_kind
        )
        assert not visibility_module._native_visible_alias_identity_holds(
            parent, observation_id, "native_visible_segment_other"
        )
        checked += 1
    assert checked == len(published.visible_observation_ids) > 0
