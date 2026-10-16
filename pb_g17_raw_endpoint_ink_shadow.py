"""Original native-raster endpoint ink: source-only witness for unresolved raw G17.

This does not assert a physical opening, wall, host, complete raw universe,
metric quantity or a new original source primitive. A failed full-source line
remains failed. Only the ORIGINAL endpoint's contiguous, unmodified ink is
reported; interior islands cannot become source evidence.
"""
from __future__ import annotations

import math

import cv2
import numpy as np

from pb_raster_opening_source_primitives import MASS_THRESHOLD
from pb_raster_visible_segment_detector import _MIN_LINE_LENGTH_PT


def audit_original_raw_endpoint_ink(image, full, pixel_geometry, *, dpi: int) -> dict:
    """Read only authenticated ORIGINAL 300-DPI raster/full pixel lattices.

    The caller must independently reauthenticate source observation, image-only
    and full render frames, pixel receipt, parent SHA/snapshot and F07 ownership.
    Coordinates and output are original pixel cells, never invented PDF walls.
    """
    if (not isinstance(image, np.ndarray) or not isinstance(full, np.ndarray)
            or image.shape != full.shape or image.ndim != 3
            or image.shape[2] != 3 or image.dtype != np.uint8
            or full.dtype != np.uint8):
        raise ValueError("paired_original_rgb_source_frames_required")
    if type(dpi) is not int or dpi <= 0:
        raise ValueError("original_positive_integer_dpi_required")
    if (not isinstance(pixel_geometry, (tuple, list))
            or len(pixel_geometry) != 4
            or any(type(p) not in (int, float) or not math.isfinite(p)
                   for p in pixel_geometry)):
        raise ValueError("authenticated_original_pixel_line_required")
    x1, y1, x2, y2 = pixel_geometry
    if y1 == y2 and x1 != x2:
        axis = "horizontal"
    elif x1 == x2 and y1 != y2:
        axis = "vertical"
    else:
        raise ValueError("nonzero_axis_aligned_original_source_line_required")
    l, t, rr, bb = (
        math.floor(min(x1, x2)), math.floor(min(y1, y2)),
        math.ceil(max(x1, x2)), math.ceil(max(y1, y2)),
    )
    if l < 0 or t < 0 or rr >= image.shape[1] or bb >= image.shape[0]:
        raise ValueError("original_pixel_lattice_outside_native_frame")
    a, b = image[t:bb+1, l:rr+1], full[t:bb+1, l:rr+1]
    valid = (cv2.cvtColor(a, cv2.COLOR_RGB2GRAY) < MASS_THRESHOLD) & np.all(a == b, axis=2)
    # Demand ALL bracketing source cells in every cross-axis row/column.
    # Never pick the favourable row of a half-pixel original primitive.
    axis_cells = np.all(valid, axis=0 if axis == "horizontal" else 1)
    entire = bool(np.all(axis_cells))
    count = len(axis_cells)
    witnesses = []
    if not entire:
        for endpoint, values in (("minimum", axis_cells), ("maximum", axis_cells[::-1])):
            missed = np.flatnonzero(~values)
            n = int(missed[0]) if missed.size else count
            span_pt = max(0, n - 1) * 72.0 / dpi
            if n == count or span_pt < _MIN_LINE_LENGTH_PT:
                continue
            box = [l, t, rr, bb]
            if axis == "horizontal":
                if endpoint == "minimum":
                    box[2] = l + n - 1
                else:
                    box[0] = rr - n + 1
            else:
                if endpoint == "minimum":
                    box[3] = t + n - 1
                else:
                    box[1] = bb - n + 1
            witnesses.append(dict(
                original_axis_endpoint=endpoint,
                original_contiguous_unchanged_dark_cells=n,
                original_endpoint_span_pt=span_pt,
                contained_original_pixel_bbox_inclusive=box,
                source_only=True, physical_wall_role_granted=False,
                opening_existence_granted=False, opening_host_granted=False,
            ))
    return dict(
        status="source_only_no_physical_authority",
        orientation=axis,
        original_pixel_bbox_inclusive=[l, t, rr, bb],
        original_pixel_cell_count=int(valid.size),
        original_solid_unchanged_cell_count=int(np.count_nonzero(valid)),
        original_whole_source_line_solid_unchanged=entire,
        original_whole_line_negative_preserved=not entire,
        unchanged_minimum_line_length_pt=_MIN_LINE_LENGTH_PT,
        authenticated_contained_original_endpoint_witnesses=witnesses,
        original_source_intervals_not_mutated=True,
        source_wall_identity_granted=False, metric_quantity_granted=False,
    )
