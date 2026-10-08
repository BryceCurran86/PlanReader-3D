"""Source-only candidate lines for maximal solid terminal band intervals."""
import cv2
import numpy as np

from pb_raster_compact_wall_band_segments import (
    CompactRasterBandSegment, _closed_raster_wall_band_segments,
)
from pb_raster_opening_source_primitives import MASS_THRESHOLD, detect_raster_opening_source_primitives
from pb_raster_visible_segment_detector import _MIN_LINE_LENGTH_PT, _line_component_eligible

TERMINAL_WALL_BAND_DETECTOR_VERSION = "terminal_solid_wall_band_v1"
TERMINAL_WALL_BAND_IDENTITY_VERSION = "terminal_solid_wall_band_v1"


def detect_terminal_raster_wall_band_segments(
    png_bytes: bytes, *, dpi: int,
    registration_scale: tuple[float, float] = (1., 1.),
) -> tuple[CompactRasterBandSegment, ...]:
    dpi = int(dpi)
    primitives = detect_raster_opening_source_primitives(
        png_bytes, dpi=dpi, registration_scale=registration_scale,
    )
    gray = cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    minimum = max(5, int(round(_MIN_LINE_LENGTH_PT * dpi / 72.)))
    results = set()
    for band in _closed_raster_wall_band_segments(primitives, dpi=dpi):
        x0, y0, x1, y1 = band.pixel_support_bounds
        roi = gray[y0:y1 + 1, x0:x1 + 1]
        if roi.shape != (y1 - y0 + 1, x1 - x0 + 1):
            continue
        # Work in along-axis rows. Every inset cross-section must be painted;
        # gaps split runs instead of being interpolated by morphology.
        work = roi.T if band.orientation == 'horizontal' else roi
        if np.all(work[1:-1, 1:-1] < MASS_THRESHOLD):
            continue
        solid = np.all(work[:, 1:-1] < MASS_THRESHOLD, axis=1)
        if np.all(solid):
            continue
        changes = np.flatnonzero(np.diff(np.r_[False, solid, False]))
        for first, stop in zip(changes[::2], changes[1::2]):
            if first != 0 and stop != len(solid):
                continue
            last = int(stop) - 1
            first = int(first)
            if band.orientation == 'horizontal':
                bounds = (x0 + first, y0, x0 + last, y1)
                center = (y0 + y1) / 2.
                pixel = (float(bounds[0]), center, float(bounds[2]), center)
            else:
                bounds = (x0, y0 + first, x1, y0 + last)
                center = (x0 + x1) / 2.
                pixel = (center, float(bounds[1]), center, float(bounds[3]))
            width, height = bounds[2] - bounds[0] + 1, bounds[3] - bounds[1] + 1
            if not _line_component_eligible(width, height, orientation=band.orientation, min_line_px=minimum):
                continue
            mid = (work.shape[1] - 1) / 2.
            if not np.all(work[first:stop, int(np.floor(mid)):int(np.ceil(mid)) + 1] < MASS_THRESHOLD):
                continue
            geometry = tuple(round(v * 72. / dpi, 6) for v in pixel)
            if (last - first) * 72. / dpi < _MIN_LINE_LENGTH_PT:
                continue
            results.add(CompactRasterBandSegment(pixel, geometry, band.orientation, bounds))
    return tuple(sorted(results, key=lambda s: (s.orientation, s.geometry_pt, s.pixel_geometry)))
