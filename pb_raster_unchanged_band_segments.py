"""Perception-only terminal runs of original raster bands with unchanged paint.

No native overlay is interpreted. A changed pixel splits source coverage; it
can never extend or bridge a run. All boxes come from the existing bounded
raster source compiler, and all geometry is in render pixels / PDF points.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math

import cv2
import numpy as np

from pb_raster_opening_source_primitives import (
    MASS_THRESHOLD, RASTER_WALL_BAND_END, RASTER_WALL_BAND_FACE,
    detect_raster_opening_source_primitives,
)
from pb_raster_visible_segment_detector import RasterDetectedSegment, _MIN_LINE_LENGTH_PT
from pb_wall_room_topology_stage_a import DEFAULT_GAP_SNAP_TOLERANCE_PT

UNCHANGED_BAND_IDENTITY_VERSION = "unchanged_terminal_band_v1"
UNCHANGED_BAND_DETECTOR_VERSION = "unchanged_terminal_band_v1"


@dataclass(frozen=True)
class UnchangedRasterBandSegment(RasterDetectedSegment):
    pixel_support_bounds: tuple[int, int, int, int]


def _closed_source_boxes(primitives):
    faces, starts, ends = defaultdict(set), defaultdict(set), set()
    for p in primitives:
        x0, y0, x1, y1 = p.pixel_geometry
        if p.primitive_kind == RASTER_WALL_BAND_FACE:
            if y0 == y1 and x0 < x1:
                faces[("horizontal", x0, x1)].add(y0)
            elif x0 == x1 and y0 < y1:
                faces[("vertical", y0, y1)].add(x0)
        elif p.primitive_kind == RASTER_WALL_BAND_END:
            ends.add(p.pixel_geometry)
            if x0 == x1 and y0 < y1:
                starts[("horizontal", x0, y0)].add(y1)
            elif y0 == y1 and x0 < x1:
                starts[("vertical", y0, x0)].add(x1)
    boxes = set()
    for (axis, lo, hi), offsets in faces.items():
        for a in offsets:
            for b in starts.get((axis, lo, a), ()):
                if b not in offsets:
                    continue
                opposite = (hi, a, hi, b) if axis == "horizontal" else (a, hi, b, hi)
                box = (lo, a, hi, b) if axis == "horizontal" else (a, lo, b, hi)
                if opposite in ends and all(int(v) == v for v in box):
                    boxes.add((axis, tuple(int(v) for v in box)))
    return tuple(sorted(boxes))


def detect_unchanged_terminal_band_segments(
    image_png: bytes, full_png: bytes, *, dpi: int,
    registration_scale: tuple[float, float] = (1.0, 1.0),
    shadow_inclusive_source_cells: bool = False,
) -> tuple[UnchangedRasterBandSegment, ...]:
    """Return solid unchanged terminal runs; opt-in inclusive source shadow only.

    The production default intentionally retains the historical endpoint-centre
    rule and therefore cannot churn signed source snapshots or W4/host receipts.
    The alternative counts painted SOURCE PIXEL CELLS (not inferred wall
    length), solely for read-only original source-stage diagnostics.
    """
    if type(dpi) is not int or dpi <= 0:
        raise ValueError("positive integer DPI required")
    if type(shadow_inclusive_source_cells) is not bool:
        raise ValueError("shadow source-cell mode must be bool")
    image, full = (cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
                   for png in (image_png, full_png))
    if image is None or full is None or image.shape != full.shape:
        raise ValueError("matched source render extents required")
    primitives = detect_raster_opening_source_primitives(
        image_png, dpi=dpi, registration_scale=registration_scale,
    )
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    result = set()
    for axis, (x0, y0, x1, y1) in _closed_source_boxes(primitives):
        if min(x0, y0) < 0 or x1 >= image.shape[1] or y1 >= image.shape[0]:
            continue
        if min(x1 - x0, y1 - y0) < 2:
            continue
        a, b = image[y0:y1+1, x0:x1+1], full[y0:y1+1, x0:x1+1]
        g = gray[y0:y1+1, x0:x1+1]
        # Along-axis rows, cross-axis columns. Every retained cross-section
        # must have solid original core and complete unchanged centerline.
        if axis == "horizontal":
            a, b, g = a.transpose(1, 0, 2), b.transpose(1, 0, 2), g.T
        mid = (g.shape[1] - 1) / 2.0
        low, high = math.floor(mid), math.ceil(mid) + 1
        solid = np.all(g[:, 1:-1] < MASS_THRESHOLD, axis=1)
        solid &= np.all(g[:, low:high] < MASS_THRESHOLD, axis=1)
        equal = np.all(a[:, 1:-1] == b[:, 1:-1], axis=(1, 2))
        equal &= np.all(a[:, low:high] == b[:, low:high], axis=(1, 2))
        changes = np.flatnonzero(np.diff(np.r_[False, solid & equal, False]))
        for first, stop in zip(changes[::2], changes[1::2]):
            first, last = int(first), int(stop) - 1
            if first != 0 and stop != len(solid):
                continue
            # The normal producer keeps endpoint-centre distance unchanged.
            # Read-only source shadow may count all actual original RGB-equal
            # pixel CELLS, including both end cells. Neither calculation may
            # become physical wall, metric or quantity authority by itself.
            painted_cells = last - first + (1 if shadow_inclusive_source_cells else 0)
            if painted_cells * 72.0 / dpi < _MIN_LINE_LENGTH_PT:
                continue
            if axis == "horizontal":
                bounds = (x0 + first, y0, x0 + last, y1)
                center = (y0 + y1) / 2.0
                pixel = (float(bounds[0]), center, float(bounds[2]), center)
            else:
                bounds = (x0, y0 + first, x1, y0 + last)
                center = (x0 + x1) / 2.0
                pixel = (center, float(bounds[1]), center, float(bounds[3]))
            geometry = tuple(round(v * 72.0 / dpi, 6) for v in pixel)
            result.add(UnchangedRasterBandSegment(pixel, geometry, axis, bounds))
    return tuple(sorted(result, key=lambda s: (s.orientation, s.geometry_pt, s.pixel_geometry)))


def band_segment_already_observed(segment, ordinary_segments, *, dpi: int, ordinary_dpi: int) -> bool:
    """Avoid a second representation of the same already captured solid run.

    This is nomination deduplication, not physical wall equivalence. Existing
    source contact at either real band end is enough to withhold a redundant
    nomination; it does not grant that source or its W4 owner host authority.
    The original topology snap bound is used only for nomination suppression.
    """
    bounds = tuple(v * 72.0 / dpi for v in segment.pixel_support_bounds)
    tol = 72.0 / dpi + 72.0 / ordinary_dpi
    x0, y0, x1, y1 = segment.geometry_pt
    for old in ordinary_segments:
        if old.orientation != segment.orientation:
            continue
        a, b, c, d = old.geometry_pt
        if segment.orientation == 'horizontal':
            overlap = min(c, x1) - max(a, x0)
            contact = min(abs(a-x0), abs(a-x1), abs(c-x0), abs(c-x1))
            covered = a <= x0 + tol and c >= x1 - tol
            if (overlap > 72.0/dpi
                    and (covered or contact <= DEFAULT_GAP_SNAP_TOLERANCE_PT)
                    and bounds[1] - tol <= b <= bounds[3] + tol):
                return True
        else:
            overlap = min(d, y1) - max(b, y0)
            contact = min(abs(b-y0), abs(b-y1), abs(d-y0), abs(d-y1))
            covered = b <= y0 + tol and d >= y1 - tol
            if (overlap > 72.0/dpi
                    and (covered or contact <= DEFAULT_GAP_SNAP_TOLERANCE_PT)
                    and bounds[0] - tol <= a <= bounds[2] + tol):
                return True
    return False
