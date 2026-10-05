from __future__ import annotations

import cv2
import fitz
import numpy as np
import pytest

from pb_raster_opening_source_primitives import (
    RASTER_LINE_RUN,
    RASTER_THIN_INK_RUN,
    RASTER_WALL_BAND_END,
    RASTER_WALL_BAND_FACE,
    detect_raster_opening_source_primitives,
)
from pb_source_observation_authority import SourceObservationProducer


DPI = 200


def _png(gray: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    return bytes(encoded)


def _primitive_sheet(*, dx: int = 0, dy: int = 0) -> np.ndarray:
    gray = np.full((220, 440), 255, np.uint8)
    cv2.rectangle(gray, (20 + dx, 80 + dy), (160 + dx, 90 + dy), 0, -1)
    cv2.rectangle(gray, (240 + dx, 80 + dy), (400 + dx, 90 + dy), 0, -1)
    # Thin source linework in the interruption. This is perception only; the
    # primitive detector must not decide whether it is an opening.
    cv2.line(gray, (160 + dx, 83 + dy), (240 + dx, 83 + dy), 0, 1)
    cv2.line(gray, (160 + dx, 87 + dy), (240 + dx, 87 + dy), 0, 1)
    return gray


def _geometry_by_kind(gray: np.ndarray):
    result = detect_raster_opening_source_primitives(_png(gray), dpi=DPI)
    return {
        kind: tuple(sorted(p.geometry_pt for p in result if p.primitive_kind == kind))
        for kind in (RASTER_WALL_BAND_FACE, RASTER_WALL_BAND_END, RASTER_THIN_INK_RUN)
    }


def test_detector_emits_source_primitives_but_no_opening_decision() -> None:
    primitives = detect_raster_opening_source_primitives(
        _png(_primitive_sheet()),
        dpi=DPI,
    )
    kinds = {primitive.primitive_kind for primitive in primitives}
    assert RASTER_WALL_BAND_FACE in kinds
    assert RASTER_WALL_BAND_END in kinds
    assert RASTER_THIN_INK_RUN in kinds

    # The perception layer deliberately has no opening/existence proposition.
    assert all(not hasattr(primitive, "proposition") for primitive in primitives)
    assert all(not hasattr(primitive, "opening_id") for primitive in primitives)


def test_raw_line_runs_preserve_frame_ink_that_touches_wall_mass() -> None:
    gray = np.full((220, 440), 255, np.uint8)
    cv2.rectangle(gray, (20, 80), (160, 90), 0, -1)
    cv2.rectangle(gray, (240, 80), (400, 90), 0, -1)
    # These frame rows touch both wall pieces at their ends. A halo-based
    # hairline mask is allowed to suppress them, but neutral source evidence
    # must retain the actual raster runs for later G17 review.
    cv2.line(gray, (160, 83), (240, 83), 0, 1)
    cv2.line(gray, (160, 87), (240, 87), 0, 1)

    primitives = detect_raster_opening_source_primitives(_png(gray), dpi=DPI)
    line_runs = tuple(
        primitive
        for primitive in primitives
        if primitive.primitive_kind == RASTER_LINE_RUN
    )
    horizontal_gap_runs = tuple(
        primitive
        for primitive in line_runs
        if abs(primitive.pixel_geometry[1] - primitive.pixel_geometry[3]) < 1e-9
        and primitive.pixel_geometry[0] <= 160.0
        and primitive.pixel_geometry[2] >= 240.0
    )
    assert len(horizontal_gap_runs) >= 2


def test_detector_is_deterministic_and_input_order_free() -> None:
    payload = _png(_primitive_sheet())
    first = detect_raster_opening_source_primitives(payload, dpi=DPI)
    second = detect_raster_opening_source_primitives(payload, dpi=DPI)
    assert first == second
    assert len(first) == len(set(first))


def test_translation_moves_geometry_without_changing_primitive_roles() -> None:
    base = _geometry_by_kind(_primitive_sheet())
    shifted = _geometry_by_kind(_primitive_sheet(dx=20, dy=10))
    dx_pt = 20 * 72.0 / DPI
    dy_pt = 10 * 72.0 / DPI

    for kind in base:
        expected = tuple(
            sorted(
                (
                    round(x0 + dx_pt, 6),
                    round(y0 + dy_pt, 6),
                    round(x1 + dx_pt, 6),
                    round(y1 + dy_pt, 6),
                )
                for x0, y0, x1, y1 in base[kind]
            )
        )
        assert len(shifted[kind]) == len(expected)
        for actual_row, expected_row in zip(shifted[kind], expected):
            assert actual_row == pytest.approx(expected_row)


def test_quarter_turn_preserves_role_counts() -> None:
    base = _geometry_by_kind(_primitive_sheet())
    rotated = _geometry_by_kind(np.ascontiguousarray(np.rot90(_primitive_sheet())))
    assert {kind: len(rows) for kind, rows in rotated.items()} == {
        kind: len(rows) for kind, rows in base.items()
    }


def _embedded_image_pdf(*, vector_overlay: bool) -> bytes:
    image = np.full((200, 360), 255, np.uint8)
    cv2.rectangle(image, (30, 90), (330, 105), 0, -1)
    image_bytes = _png(image)

    doc = fitz.open()
    page = doc.new_page(width=360.0, height=200.0)
    page.insert_image(page.rect, stream=image_bytes, keep_proportion=False)
    if vector_overlay:
        page.insert_text((40.0, 40.0), "VECTOR LABEL 2127", fontsize=14.0)
        page.draw_line(
            fitz.Point(20.0, 60.0),
            fitz.Point(340.0, 60.0),
            color=(0, 0, 0),
            width=2.0,
        )
    payload = bytes(doc.tobytes(garbage=4, deflate=True))
    doc.close()
    return payload


def _images_only_render(source_bytes: bytes) -> tuple[bytes, bytes]:
    producer = SourceObservationProducer(
        producer_method="images-only-render-test",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="images-only-render-test",
        source_bytes=source_bytes,
        source_locator="memory://images-only-render-test.pdf",
        page_ids=("1",),
    )
    regular, _ = producer.render_native_page_png(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        dpi=float(DPI),
    )
    images_only, _ = producer.render_native_page_png(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        dpi=float(DPI),
        images_only=True,
    )
    return regular, images_only


def test_images_only_render_removes_vector_and_text_overlay() -> None:
    regular_plain, images_plain = _images_only_render(
        _embedded_image_pdf(vector_overlay=False)
    )
    regular_overlay, images_overlay = _images_only_render(
        _embedded_image_pdf(vector_overlay=True)
    )

    assert regular_plain != regular_overlay
    plain_pixels = cv2.imdecode(
        np.frombuffer(images_plain, dtype=np.uint8),
        cv2.IMREAD_GRAYSCALE,
    )
    overlay_pixels = cv2.imdecode(
        np.frombuffer(images_overlay, dtype=np.uint8),
        cv2.IMREAD_GRAYSCALE,
    )
    assert plain_pixels is not None and overlay_pixels is not None
    assert np.array_equal(plain_pixels, overlay_pixels)


def test_images_only_render_cannot_accept_caller_clip() -> None:
    producer = SourceObservationProducer(
        producer_method="images-only-clip-test",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="images-only-clip-test",
        source_bytes=_embedded_image_pdf(vector_overlay=False),
        source_locator="memory://images-only-clip-test.pdf",
        page_ids=("1",),
    )
    with pytest.raises(ValueError, match="images_only render cannot"):
        producer.render_native_page_png(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            dpi=float(DPI),
            clip_pt=(0.0, 0.0, 50.0, 50.0),
            images_only=True,
        )
