from __future__ import annotations

import cv2
import fitz
import numpy as np

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
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
