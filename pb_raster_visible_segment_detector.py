"""Conservative raster line-segment detector for source visibility.

The detector converts producer-owned page render pixels into axis-aligned line
observations only. It does not classify openings, doors, windows, schedules, or
commercial quantities.

The output is deliberately geometric:
- horizontal and vertical rendered line runs only;
- exact pixel and PDF-point geometry;
- deterministic polarity selection and morphology;
- endpoint snapping only to intersecting perpendicular rendered line runs.

PhysicalOpeningAuthority remains the sole owner of PHYSICAL_OPENING_EXISTS.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import cv2
import numpy as np


RASTER_VISIBLE_SEGMENT_DETECTOR_VERSION = "1.0.0"
_MIN_LINE_LENGTH_PT = 4.0
_MIN_FOREGROUND_FRACTION = 0.0002
_MAX_FOREGROUND_FRACTION = 0.45


@dataclass(frozen=True)
class RasterDetectedSegment:
    pixel_geometry: tuple[float, float, float, float]
    geometry_pt: tuple[float, float, float, float]
    orientation: str

    def __post_init__(self) -> None:
        if self.orientation not in {"horizontal", "vertical"}:
            raise ValueError("orientation must be horizontal or vertical")
        if len(self.pixel_geometry) != 4 or len(self.geometry_pt) != 4:
            raise ValueError("segment geometry must contain four coordinates")
        if not all(math.isfinite(v) for v in self.pixel_geometry + self.geometry_pt):
            raise ValueError("segment geometry must be finite")


def _foreground_mask(gray: np.ndarray) -> np.ndarray | None:
    if gray.ndim != 2 or gray.size == 0:
        return None

    _threshold, dark = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
    )
    _threshold, light = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )

    candidates: list[tuple[float, np.ndarray]] = []
    for mask in (dark, light):
        fraction = float(np.count_nonzero(mask)) / float(mask.size)
        if _MIN_FOREGROUND_FRACTION <= fraction <= _MAX_FOREGROUND_FRACTION:
            candidates.append((fraction, mask))

    if not candidates:
        return None

    # Linework is normally the minority class. Picking the lower foreground
    # fraction also handles dark-background / light-line CAD rasters.
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _component_segments(
    mask: np.ndarray,
    *,
    orientation: str,
    min_line_px: int,
) -> list[tuple[float, float, float, float]]:
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        mask,
        connectivity=8,
    )
    segments: list[tuple[float, float, float, float]] = []
    for index in range(1, int(count)):
        x = int(stats[index, cv2.CC_STAT_LEFT])
        y = int(stats[index, cv2.CC_STAT_TOP])
        width = int(stats[index, cv2.CC_STAT_WIDTH])
        height = int(stats[index, cv2.CC_STAT_HEIGHT])
        area = int(stats[index, cv2.CC_STAT_AREA])
        if area <= 0:
            continue

        if orientation == "horizontal":
            if width < min_line_px or width < max(3, 3 * height):
                continue
            center_y = y + (height - 1) / 2.0
            segments.append(
                (float(x), float(center_y), float(x + width - 1), float(center_y))
            )
        else:
            if height < min_line_px or height < max(3, 3 * width):
                continue
            center_x = x + (width - 1) / 2.0
            segments.append(
                (float(center_x), float(y), float(center_x), float(y + height - 1))
            )
    return segments


def _dedupe(
    segments: Iterable[tuple[float, float, float, float]],
) -> list[tuple[float, float, float, float]]:
    seen: set[tuple[float, float, float, float]] = set()
    result: list[tuple[float, float, float, float]] = []
    for segment in segments:
        key = tuple(round(float(value), 3) for value in segment)
        if key in seen:
            continue
        seen.add(key)
        result.append(tuple(float(value) for value in key))
    result.sort()
    return result


def _snap_intersections(
    horizontal: list[tuple[float, float, float, float]],
    vertical: list[tuple[float, float, float, float]],
    *,
    tolerance_px: float,
) -> tuple[
    list[tuple[float, float, float, float]],
    list[tuple[float, float, float, float]],
]:
    snapped_h: list[tuple[float, float, float, float]] = []
    for x0, y0, x1, _y1 in horizontal:
        left = x0
        right = x1
        for vx0, vy0, _vx1, vy1 in vertical:
            vx = vx0
            if vy0 - tolerance_px <= y0 <= vy1 + tolerance_px:
                if abs(left - vx) <= tolerance_px:
                    left = vx
                if abs(right - vx) <= tolerance_px:
                    right = vx
        if right - left > 0.0:
            snapped_h.append((left, y0, right, y0))

    snapped_v: list[tuple[float, float, float, float]] = []
    for x0, y0, _x1, y1 in vertical:
        top = y0
        bottom = y1
        for hx0, hy0, hx1, _hy1 in snapped_h:
            if hx0 - tolerance_px <= x0 <= hx1 + tolerance_px:
                if abs(top - hy0) <= tolerance_px:
                    top = hy0
                if abs(bottom - hy0) <= tolerance_px:
                    bottom = hy0
        if bottom - top > 0.0:
            snapped_v.append((x0, top, x0, bottom))

    # A second horizontal pass picks up any y coordinates standardized by the
    # vertical pass without ever bridging a real gap.
    final_h: list[tuple[float, float, float, float]] = []
    for x0, y0, x1, _y1 in snapped_h:
        left = x0
        right = x1
        for vx0, vy0, _vx1, vy1 in snapped_v:
            if vy0 - tolerance_px <= y0 <= vy1 + tolerance_px:
                if abs(left - vx0) <= tolerance_px:
                    left = vx0
                if abs(right - vx0) <= tolerance_px:
                    right = vx0
        final_h.append((left, y0, right, y0))

    return _dedupe(final_h), _dedupe(snapped_v)


def detect_axis_aligned_raster_segments(
    png_bytes: bytes,
    *,
    dpi: int = 144,
) -> tuple[RasterDetectedSegment, ...]:
    """Return conservative rendered line observations in page-point space."""

    if not isinstance(png_bytes, (bytes, bytearray, memoryview)):
        raise TypeError("png_bytes must be bytes-like")
    if int(dpi) <= 0:
        raise ValueError("dpi must be positive")

    encoded = np.frombuffer(bytes(png_bytes), dtype=np.uint8)
    gray = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if gray is None or gray.size == 0:
        return ()

    foreground = _foreground_mask(gray)
    if foreground is None:
        return ()

    pixels_per_point = float(dpi) / 72.0
    min_line_px = max(5, int(round(_MIN_LINE_LENGTH_PT * pixels_per_point)))
    horizontal_kernel = np.ones((1, min_line_px), dtype=np.uint8)
    vertical_kernel = np.ones((min_line_px, 1), dtype=np.uint8)

    horizontal_mask = cv2.morphologyEx(
        foreground,
        cv2.MORPH_OPEN,
        horizontal_kernel,
    )
    vertical_mask = cv2.morphologyEx(
        foreground,
        cv2.MORPH_OPEN,
        vertical_kernel,
    )

    horizontal = _component_segments(
        horizontal_mask,
        orientation="horizontal",
        min_line_px=min_line_px,
    )
    vertical = _component_segments(
        vertical_mask,
        orientation="vertical",
        min_line_px=min_line_px,
    )

    # Snap only within approximately one rendered source point. The tolerance
    # scales from the producer-owned render resolution rather than page/project
    # identity or expected opening sizes.
    snap_tolerance_px = max(1.0, pixels_per_point)
    horizontal, vertical = _snap_intersections(
        _dedupe(horizontal),
        _dedupe(vertical),
        tolerance_px=snap_tolerance_px,
    )

    scale_to_pt = 72.0 / float(dpi)
    result: list[RasterDetectedSegment] = []
    for orientation, segments in (
        ("horizontal", horizontal),
        ("vertical", vertical),
    ):
        for segment in segments:
            geometry_pt = tuple(
                round(float(value) * scale_to_pt, 4)
                for value in segment
            )
            if math.hypot(
                geometry_pt[2] - geometry_pt[0],
                geometry_pt[3] - geometry_pt[1],
            ) < _MIN_LINE_LENGTH_PT:
                continue
            result.append(
                RasterDetectedSegment(
                    pixel_geometry=segment,
                    geometry_pt=geometry_pt,
                    orientation=orientation,
                )
            )

    result.sort(
        key=lambda item: (
            item.orientation,
            item.geometry_pt,
            item.pixel_geometry,
        )
    )
    return tuple(result)


__all__ = [
    "RASTER_VISIBLE_SEGMENT_DETECTOR_VERSION",
    "RasterDetectedSegment",
    "detect_axis_aligned_raster_segments",
]
