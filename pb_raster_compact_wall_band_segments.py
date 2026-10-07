"""Perception-only centerlines for compact, completely painted source bands.

This consumes the existing raster primitive compiler, including its safety
bound. It proves candidate pixel geometry only; no wall, opening, host, metric,
count or quantity authority is created here.
"""
from collections import defaultdict
from dataclasses import dataclass
import cv2
import numpy as np

from pb_raster_opening_source_primitives import (
    MASS_THRESHOLD, RASTER_WALL_BAND_FACE, RASTER_WALL_BAND_END,
    detect_raster_opening_source_primitives,
)
from pb_raster_visible_segment_detector import (
    RasterDetectedSegment, _MIN_LINE_LENGTH_PT, _line_component_eligible,
)

COMPACT_WALL_BAND_DETECTOR_VERSION = "compact_solid_wall_band_v1"
COMPACT_WALL_BAND_IDENTITY_VERSION = "compact_solid_wall_band_v1"


@dataclass(frozen=True)
class CompactRasterBandSegment(RasterDetectedSegment):
    pixel_support_bounds: tuple[int, int, int, int]


def compact_band_has_same_visible_paint(
    segment: CompactRasterBandSegment, image_only: np.ndarray, full: np.ndarray,
) -> bool:
    """Visible core and complete centerline must reproduce the image paint."""
    if image_only.ndim != 2 or full.shape != image_only.shape:
        return False
    x0, y0, x1, y1 = segment.pixel_support_bounds
    height, width = y1 - y0 + 1, x1 - x0 + 1
    if min(width, height) <= 2 or min(x0, y0) < 0:
        return False
    a, b = image_only[y0:y1 + 1, x0:x1 + 1], full[y0:y1 + 1, x0:x1 + 1]
    if a.shape != (height, width) or b.shape != a.shape:
        return False
    if not np.array_equal(a[1:-1, 1:-1], b[1:-1, 1:-1]):
        return False
    mid = (height - 1) / 2 if segment.orientation == 'horizontal' else (width - 1) / 2
    low, high = int(np.floor(mid)), int(np.ceil(mid))
    return bool(np.array_equal(a[low:high + 1, :], b[low:high + 1, :])
                if segment.orientation == 'horizontal'
                else np.array_equal(a[:, low:high + 1], b[:, low:high + 1]))


def _closed_raster_wall_band_segments(primitives, *, dpi: int):
    """Exact four-edge boxes from the existing bounded source inventory."""
    faces = defaultdict(set)
    starts = defaultdict(set)
    ends = set()
    for primitive in primitives:
        x0, y0, x1, y1 = primitive.pixel_geometry
        if primitive.primitive_kind == RASTER_WALL_BAND_FACE:
            if y0 == y1 and x0 < x1:
                faces[("horizontal", x0, x1)].add(y0)
            elif x0 == x1 and y0 < y1:
                faces[("vertical", y0, y1)].add(x0)
        elif primitive.primitive_kind == RASTER_WALL_BAND_END:
            ends.add(primitive.pixel_geometry)
            if x0 == x1 and y0 < y1:
                starts[("horizontal", x0, y0)].add(y1)
            elif y0 == y1 and x0 < x1:
                starts[("vertical", y0, x0)].add(x1)

    results = set()
    for (orientation, along_lo, along_hi), offsets in faces.items():
        for cross_lo in offsets:
            for cross_hi in starts.get((orientation, along_lo, cross_lo), ()):
                if cross_hi not in offsets:
                    continue
                if orientation == "horizontal":
                    opposite = (along_hi, cross_lo, along_hi, cross_hi)
                    box = (along_lo, cross_lo, along_hi, cross_hi)
                    center = (cross_lo + cross_hi) / 2.0
                    pixel = (along_lo, center, along_hi, center)
                else:
                    opposite = (cross_lo, along_hi, cross_hi, along_hi)
                    box = (cross_lo, along_lo, cross_hi, along_hi)
                    center = (cross_lo + cross_hi) / 2.0
                    pixel = (center, along_lo, center, along_hi)
                if opposite not in ends or any(int(v) != v for v in box):
                    continue
                x0, y0, x1, y1 = (int(v) for v in box)
                width, height = x1 - x0 + 1, y1 - y0 + 1
                if min(width, height) <= 2:
                    continue
                point_geometry = tuple(round(v * 72.0 / dpi, 6) for v in pixel)
                results.add(CompactRasterBandSegment(pixel, point_geometry, orientation, (x0, y0, x1, y1)))
    return tuple(sorted(results, key=lambda item: (
        item.orientation, item.geometry_pt, item.pixel_geometry,
    )))


def detect_compact_raster_wall_band_segments(
    png_bytes: bytes, *, dpi: int,
    registration_scale: tuple[float, float] = (1.0, 1.0),
) -> tuple[CompactRasterBandSegment, ...]:
    dpi = int(dpi)
    primitives = detect_raster_opening_source_primitives(
        png_bytes, dpi=dpi, registration_scale=registration_scale,
    )
    gray = cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    results = []
    min_line_px = max(5, int(round(_MIN_LINE_LENGTH_PT * dpi / 72.0)))
    for segment in _closed_raster_wall_band_segments(primitives, dpi=dpi):
        x0, y0, x1, y1 = segment.pixel_support_bounds
        width, height = x1 - x0 + 1, y1 - y0 + 1
        if _line_component_eligible(
            width, height, orientation=segment.orientation, min_line_px=min_line_px,
        ):
            continue
        roi = gray[y0:y1 + 1, x0:x1 + 1]
        if roi.shape != (height, width):
            continue
        # Preserve the historical compact core and exact centerline proof.
        mid = (height - 1) / 2 if segment.orientation == 'horizontal' else (width - 1) / 2
        low, high = int(np.floor(mid)), int(np.ceil(mid))
        line_pixels = roi[low:high + 1, :] if segment.orientation == 'horizontal' else roi[:, low:high + 1]
        if np.all(roi[1:-1, 1:-1] < MASS_THRESHOLD) and np.all(line_pixels < MASS_THRESHOLD):
            results.append(segment)
    return tuple(results)
