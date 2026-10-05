from __future__ import annotations

import cv2
import fitz
import numpy as np

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    RASTER_OPENING_VISIBLE_PRIMITIVE_KINDS,
    SourceVisibilityProducer,
    VISIBILITY_RECEIPT_UNAVAILABLE,
)


def _png(gray: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    return bytes(encoded)


def _raster_pdf(*, overlay: bool = False, with_image: bool = True) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=320.0, height=180.0)
    if with_image:
        gray = np.full((360, 640), 255, np.uint8)
        cv2.rectangle(gray, (30, 140), (240, 165), 0, -1)
        cv2.rectangle(gray, (400, 140), (610, 165), 0, -1)
        cv2.line(gray, (240, 147), (400, 147), 0, 2)
        cv2.line(gray, (240, 158), (400, 158), 0, 2)
        page.insert_image(page.rect, stream=_png(gray), keep_proportion=False)
    if overlay:
        page.insert_text((35.0, 35.0), "VECTOR LABEL 2127", fontsize=12.0)
        page.draw_line(
            fitz.Point(20.0, 60.0),
            fitz.Point(300.0, 60.0),
            color=(0, 0, 0),
            width=2.0,
        )
    payload = bytes(doc.tobytes(garbage=4, deflate=True))
    doc.close()
    return payload


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _publish(
    *,
    producer_method: str = "raster-opening-primitive-publication",
    producer_version: str = "1",
    overlay: bool = False,
):
    producer = SourceVisibilityProducer(
        producer_method=producer_method,
        producer_version=producer_version,
    )
    base = producer.ingest_native_pdf_bytes(
        document_id="raster-opening-primitive-publication",
        source_bytes=_raster_pdf(overlay=overlay),
        source_locator="memory://raster-opening-primitive-publication.pdf",
        page_ids=("1",),
    )
    updated = producer.augment_with_raster_opening_primitives(
        base.revision.revision_id,
        page_ids=("1",),
    )
    return producer, base, updated


def test_primitive_publication_is_isolated_from_visible_universe() -> None:
    producer, base, updated = _publish()
    assert updated.raster_opening_primitive_observation_ids
    assert updated.visible_observation_ids == base.visible_observation_ids
    assert not (
        set(updated.raster_opening_primitive_observation_ids)
        & set(updated.visible_observation_ids)
    )

    authority = producer.authority()
    for observation_id in updated.raster_opening_primitive_observation_ids:
        selector = _selector(updated, observation_id)
        isolated = authority.resolve_raster_opening_primitive(selector)
        assert isolated.status is EvidenceResolutionStatus.CORROBORATED
        assert isolated.observation is not None
        assert (
            isolated.observation.observation_kind
            in RASTER_OPENING_VISIBLE_PRIMITIVE_KINDS
        )
        assert isolated.observation.raw_text == ""

        generic = authority.resolve_visible(selector)
        assert generic.status is EvidenceResolutionStatus.ABSTAINED
        assert generic.reason_codes == (VISIBILITY_RECEIPT_UNAVAILABLE,)


def test_primitive_ids_ignore_producer_method_and_version() -> None:
    first_producer, _first_base, first = _publish(
        producer_method="raster-opening-primitive-a",
        producer_version="1.0.0",
    )
    second_producer, _second_base, second = _publish(
        producer_method="raster-opening-primitive-b",
        producer_version="9.9.9",
    )

    assert first.snapshot.snapshot_id != second.snapshot.snapshot_id
    assert (
        first.raster_opening_primitive_observation_ids
        == second.raster_opening_primitive_observation_ids
    )
    assert all(
        first_producer.authority().resolve_raster_opening_primitive(
            _selector(first, observation_id)
        ).status
        is EvidenceResolutionStatus.CORROBORATED
        for observation_id in first.raster_opening_primitive_observation_ids
    )
    assert all(
        second_producer.authority().resolve_raster_opening_primitive(
            _selector(second, observation_id)
        ).status
        is EvidenceResolutionStatus.CORROBORATED
        for observation_id in second.raster_opening_primitive_observation_ids
    )


def test_vector_overlay_cannot_change_raster_primitive_geometry() -> None:
    plain_producer, _plain_base, plain = _publish(overlay=False)
    overlay_producer, _overlay_base, overlay = _publish(overlay=True)

    def rows(producer, published):
        authority = producer.authority()
        result = []
        for observation_id in published.raster_opening_primitive_observation_ids:
            resolved = authority.resolve_raster_opening_primitive(
                _selector(published, observation_id)
            )
            assert resolved.observation is not None
            result.append(
                (
                    resolved.observation.raw_text,
                    tuple(resolved.observation.geometry),
                )
            )
        return tuple(sorted(result))

    assert rows(plain_producer, plain) == rows(overlay_producer, overlay)


def test_vector_only_page_publishes_no_raster_opening_primitives() -> None:
    producer = SourceVisibilityProducer(
        producer_method="raster-opening-vector-control",
        producer_version="1",
    )
    base = producer.ingest_native_pdf_bytes(
        document_id="raster-opening-vector-control",
        source_bytes=_raster_pdf(overlay=True, with_image=False),
        source_locator="memory://raster-opening-vector-control.pdf",
        page_ids=("1",),
    )
    updated = producer.augment_with_raster_opening_primitives(
        base.revision.revision_id,
        page_ids=("1",),
    )
    assert updated == base
    assert updated.raster_opening_primitive_observation_ids == ()


def test_later_raster_visibility_augmentation_preserves_primitive_receipts() -> None:
    producer, _base, primitives = _publish()
    before_ids = primitives.raster_opening_primitive_observation_ids

    updated = producer.augment_with_raster_visible_segments(
        primitives.revision.revision_id,
        page_ids=("1",),
    )
    assert updated.raster_opening_primitive_observation_ids == before_ids
    authority = producer.authority()
    assert all(
        authority.resolve_raster_opening_primitive(
            _selector(updated, observation_id)
        ).status
        is EvidenceResolutionStatus.CORROBORATED
        for observation_id in before_ids
    )


def test_repeated_primitive_augmentation_is_idempotent() -> None:
    producer, _base, first = _publish()
    second = producer.augment_with_raster_opening_primitives(
        first.revision.revision_id,
        page_ids=("1",),
    )
    assert second == first
