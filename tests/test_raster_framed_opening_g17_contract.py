from __future__ import annotations

import cv2
import fitz
import numpy as np

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
from pb_semantic_opening_enumeration_authority import (
    SEMANTIC_OPENING_CANDIDATE_UNIVERSE_COMPLETE,
    SEMANTIC_OPENING_RASTER_CANDIDATE_CLOSURE_UNPROVEN,
    SemanticOpeningEnumerationProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _png(gray: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    return bytes(encoded)


def _sheet(
    *,
    frame_lines: int,
    continue_faces: bool = False,
) -> np.ndarray:
    """One generic raster wall-band interruption; no text or dimensions."""

    gray = np.full((360, 640), 255, np.uint8)
    # 7 pt source wall thickness when the 640 px image fills a 320 pt page.
    cv2.rectangle(gray, (30, 150), (240, 164), 0, -1)
    cv2.rectangle(gray, (400, 150), (610, 164), 0, -1)

    for y in (154, 160)[:frame_lines]:
        cv2.line(gray, (240, y), (400, y), 0, 1)

    if continue_faces:
        # A recess / glazing-style outline keeps the actual wall faces running
        # through the gap. Positive frame lines inside the band cannot override it.
        cv2.line(gray, (240, 150), (400, 150), 0, 1)
        cv2.line(gray, (240, 164), (400, 164), 0, 1)
    return gray


def _pdf(
    *,
    frame_lines: int,
    continue_faces: bool = False,
) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=320.0, height=180.0)
    page.insert_image(
        page.rect,
        stream=_png(
            _sheet(
                frame_lines=frame_lines,
                continue_faces=continue_faces,
            )
        ),
        keep_proportion=False,
    )
    payload = bytes(doc.tobytes(garbage=4, deflate=True))
    doc.close()
    return payload


def _prepare(
    *,
    frame_lines: int,
    continue_faces: bool = False,
):
    producer = SourceVisibilityProducer(
        producer_method="raster-framed-g17-contract",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="raster-framed-g17-contract",
        source_bytes=_pdf(
            frame_lines=frame_lines,
            continue_faces=continue_faces,
        ),
        source_locator="memory://raster-framed-g17-contract.pdf",
        page_ids=("1",),
    )
    published = producer.augment_with_raster_opening_primitives(
        published.revision.revision_id,
        page_ids=("1",),
    )
    assert published.raster_opening_primitive_observation_ids
    return producer, published


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _corroborated_records(producer, published):
    authority = producer.physical_opening_authority()
    records = {}
    for observation_id in published.raster_opening_primitive_observation_ids:
        result = authority.prove_existence(
            _selector(published, observation_id)
        )
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            records[result.existence_record.record_id] = result.existence_record
    return tuple(records[key] for key in sorted(records))


def test_g17_promotes_one_framed_raster_wall_band_interruption() -> None:
    """EXPECTED RED until G17 explicitly consumes isolated raster primitives."""

    producer, published = _prepare(frame_lines=2)
    records = _corroborated_records(producer, published)

    assert len(records) == 1
    record = records[0]
    assert record.proposition == PHYSICAL_OPENING_EXISTS
    assert record.structural_pattern == "raster_framed_wall_band_interruption"
    assert len(record.source_observation_ids) >= 8


def test_bare_raster_wall_break_does_not_prove_an_opening() -> None:
    producer, published = _prepare(frame_lines=0)
    assert _corroborated_records(producer, published) == ()


def test_one_frame_line_is_not_enough_to_prove_an_opening() -> None:
    producer, published = _prepare(frame_lines=1)
    assert _corroborated_records(producer, published) == ()


def test_face_continuation_blocks_frame_lookalike() -> None:
    producer, published = _prepare(
        frame_lines=2,
        continue_faces=True,
    )
    assert _corroborated_records(producer, published) == ()


def test_raster_candidate_closure_resolves_one_framed_opening() -> None:
    producer, published = _prepare(frame_lines=2)
    authority = producer.physical_opening_authority()
    selector = _selector(
        published,
        published.raster_opening_primitive_observation_ids[0],
    )

    closure = authority.assess_raster_candidate_closure(selector)

    assert closure.status is EvidenceResolutionStatus.CORROBORATED
    assert closure.candidate_universe_complete is True
    assert closure.raw_candidate_count == 1
    assert closure.resolved_candidate_count == 1
    assert closure.unresolved_candidate_ids == ()
    assert closure.unresolved_observation_ids == ()


def test_raster_candidate_closure_disposes_primitives_with_no_opening_candidate() -> None:
    producer, published = _prepare(frame_lines=0)
    authority = producer.physical_opening_authority()
    selector = _selector(
        published,
        published.raster_opening_primitive_observation_ids[0],
    )

    closure = authority.assess_raster_candidate_closure(selector)

    assert closure.status is EvidenceResolutionStatus.CORROBORATED
    assert closure.candidate_universe_complete is True
    assert closure.raw_candidate_count == 0
    assert closure.resolved_candidate_count == 0
    assert closure.unresolved_candidate_ids == ()
    assert closure.unresolved_observation_ids == ()


def test_semantic_enumeration_accepts_proven_raster_candidate_closure() -> None:
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=180.0)
        page.insert_image(
            page.rect,
            stream=_png(_sheet(frame_lines=2)),
            keep_proportion=False,
        )
        # One independent vector sentinel gives the semantic enumerator an
        # authenticated visible universe while the opening remains raster-owned.
        page.draw_line(
            fitz.Point(10.0, 20.0),
            fitz.Point(40.0, 20.0),
            color=(0, 0, 0),
            width=1,
        )
        payload = bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()

    producer = SourceVisibilityProducer(
        producer_method="raster-closure-semantic-contract",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="raster-closure-semantic-contract",
        source_bytes=payload,
        source_locator="memory://raster-closure-semantic-contract.pdf",
        page_ids=("1",),
    )
    published = producer.augment_with_raster_opening_primitives(
        published.revision.revision_id,
        page_ids=("1",),
    )
    semantic = SemanticOpeningEnumerationProducer.from_source_visibility_producer(
        producer
    ).publish_page_scope(
        revision_id=published.revision.revision_id,
        decision_scope_id="semantic-opening-enumeration:raster-closure",
        page_ids=("1",),
    )

    assert semantic.status is EvidenceResolutionStatus.CORROBORATED
    assert semantic.record is not None
    assert len(semantic.record.physical_opening_record_ids) == 1
    assert semantic.record.physical_opening_universe_complete is True
    assert (
        SEMANTIC_OPENING_RASTER_CANDIDATE_CLOSURE_UNPROVEN
        not in semantic.record.reason_codes
    )
    assert (
        SEMANTIC_OPENING_CANDIDATE_UNIVERSE_COMPLETE
        in semantic.record.reason_codes
    )
