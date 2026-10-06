from __future__ import annotations

import cv2
import numpy as np

from pb_raster_opening_source_primitives import (
    MAX_PRIMITIVES,
    RASTER_LINE_RUN,
    detect_raster_opening_source_primitives,
)


DPI = 300


def _png(gray: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    return bytes(encoded)


def test_dense_thick_poche_does_not_explode_neutral_line_runs() -> None:
    """Thick wall mass must not be republished once per raster row."""

    gray = np.full((1200, 1200), 255, np.uint8)
    # Thirty source-owned filled wall strips. Historical row-wise scanning of
    # the full ink mask generated > 20k neutral line runs from this pattern.
    for x0 in range(10, 1170, 40):
        cv2.rectangle(gray, (x0, 0), (x0 + 11, 1199), 0, -1)

    primitives = detect_raster_opening_source_primitives(
        _png(gray),
        dpi=DPI,
    )

    assert len(primitives) < MAX_PRIMITIVES
    assert not tuple(
        primitive
        for primitive in primitives
        if primitive.primitive_kind == RASTER_LINE_RUN
    )


def test_nonthick_frame_runs_recover_one_pixel_jamb_contact() -> None:
    """Removing thick poche must not erase true frame-to-jamb contact."""

    gray = np.full((260, 520), 255, np.uint8)
    cv2.rectangle(gray, (30, 100), (200, 116), 0, -1)
    cv2.rectangle(gray, (320, 100), (490, 116), 0, -1)
    for y in (104, 112):
        cv2.line(gray, (200, y), (320, y), 0, 1)

    primitives = detect_raster_opening_source_primitives(
        _png(gray),
        dpi=DPI,
    )
    horizontal = tuple(
        primitive.pixel_geometry
        for primitive in primitives
        if primitive.primitive_kind == RASTER_LINE_RUN
        and abs(primitive.pixel_geometry[1] - primitive.pixel_geometry[3]) < 1e-9
        and primitive.pixel_geometry[0] <= 200.0
        and primitive.pixel_geometry[2] >= 320.0
    )

    assert len(horizontal) >= 2
    assert any(row[0] == 200.0 and row[2] == 320.0 for row in horizontal)


def test_dense_poche_compaction_is_quarter_turn_symmetric() -> None:
    gray = np.full((900, 1200), 255, np.uint8)
    for x0 in range(10, 1170, 40):
        cv2.rectangle(gray, (x0, 0), (x0 + 11, 899), 0, -1)

    first = detect_raster_opening_source_primitives(_png(gray), dpi=DPI)
    rotated = detect_raster_opening_source_primitives(
        _png(np.ascontiguousarray(np.rot90(gray))),
        dpi=DPI,
    )

    assert len(first) < MAX_PRIMITIVES
    assert len(rotated) < MAX_PRIMITIVES
    assert sum(p.primitive_kind == RASTER_LINE_RUN for p in first) == 0
    assert sum(p.primitive_kind == RASTER_LINE_RUN for p in rotated) == 0
