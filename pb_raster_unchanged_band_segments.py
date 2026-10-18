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


# A separate original-source identity: unlike the ordinary two-ended band
# detector, these are one-ended G17 source flank *candidates*. Their original
# opening, image-region ownership and face/end closure are proven upstream.
ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION = "original_g17_one_end_paint_v1"
ORIGINAL_G17_ONE_END_SOURCE_DETECTOR_VERSION = "original_g17_one_end_paint_v1"

# Registered image/full-render immutable source parent namespaces only.
# Adding the one-ended source ID does not enable its producer or grant W4 role.
OPENING_LOCAL_SOURCE_IDENTITY_VERSIONS = frozenset((
    UNCHANGED_BAND_IDENTITY_VERSION,
    ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION,
))


def detect_original_one_ended_ink_band_segments(
    image_png: bytes, full_png: bytes, *, dpi: int,
    source_closed_flank_boxes,
) -> tuple[UnchangedRasterBandSegment, ...]:
    """Describe actual one-ended original paint without inventing an end cap.

    The source producer must independently prove both original G17 flanks
    through their physical-opening issuer before passing these boxes here.
    This pure pixel observer is NEVER structural-role, W4, host or quantity
    authority. It explicitly cannot accept a drawn bridging line, loose text
    or incomplete unclosed source boxes as a source ownership assertion.
    """
    if type(dpi) is not int or dpi <= 0:
        raise ValueError("positive original-source integer DPI required")
    if not isinstance(source_closed_flank_boxes, (list, tuple)):
        raise ValueError("source-closed flank inventory required")
    image, full = (cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
                   for png in (image_png, full_png))
    if image is None or full is None or image.shape != full.shape:
        raise ValueError("identical native-frame source renders required")
    found = set()
    seen_boxes = set()
    for item in source_closed_flank_boxes:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError("original source flank address malformed")
        axis, bounds = item
        if axis not in ("horizontal", "vertical"):
            raise ValueError("unsupported original flank orientation")
        if (not isinstance(bounds, (list, tuple)) or len(bounds) != 4
                or any(type(v) not in (int, float) or not math.isfinite(v)
                       for v in bounds)):
            raise ValueError("original source flank coordinates invalid")
        source_address = (axis, tuple(float(v) for v in bounds))
        if source_address in seen_boxes:
            raise ValueError("duplicate original G17 source flank address")
        seen_boxes.add(source_address)
        pixel_values = tuple(float(v) * dpi / 72.0 for v in bounds)
        pixel = tuple(int(round(v)) for v in pixel_values)
        if any(abs(a-b)>1e-4 for a,b in zip(pixel_values,pixel)):
            # A source box cannot borrow paint from adjacent raster pixels.
            raise ValueError("original source flank off the authenticated lattice")
        x0,y0,x1,y1 = pixel
        if (x0<0 or y0<0 or x1>=image.shape[1] or y1>=image.shape[0]
                or x1-x0<2 or y1-y0<2):
            continue
        a = image[y0:y1+1, x0:x1+1]
        b = full[y0:y1+1, x0:x1+1]
        gray = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
        middle = ((a.shape[0] if axis=="horizontal" else a.shape[1])-1)/2.0
        lo, hi = math.floor(middle), math.ceil(middle)
        centre = ((slice(lo,hi+1),slice(None)) if axis=="horizontal"
                  else (slice(None),slice(lo,hi+1)))
        core = (slice(1,-1),slice(1,-1))
        solid = bool(np.all(gray[core]<MASS_THRESHOLD)
                     and np.all(gray[centre]<MASS_THRESHOLD))
        unchanged = bool(np.array_equal(a[core],b[core])
                         and np.array_equal(a[centre],b[centre]))
        painted_cells = (x1-x0+1 if axis=="horizontal" else y1-y0+1)
        # Exactly the historical >=4pt rule: count physical printed cells
        # because a 17-cell unmodified band has 4.08pt of actual source ink.
        if (not solid or not unchanged
                or painted_cells*72.0/dpi < _MIN_LINE_LENGTH_PT):
            continue
        # A source-authenticated 17-cell G17 jamb is 4.08pt of actual
        # ORIGINAL ink, although 17 pixel centre addresses span just 3.84pt.
        # If and ONLY if the cell-coverage minimum passes but the centre-span
        # fails the unchanged 4pt source threshold, emit that exact ink-cell
        # outer extent (half a cell at each end). This is observed physical
        # pixel footprint, not an interpolated or guessed wall extension.
        # Longer already-accepted opening flanks retain their old coordinates
        # byte-for-byte. The historic two-ended detector is NEVER changed.
        cell_edge_extent = (
            (painted_cells - 1) * 72.0 / dpi < _MIN_LINE_LENGTH_PT
        )
        inset = 0.5 if cell_edge_extent else 0.0
        if axis=="horizontal":
            mid=(y0+y1)/2.0
            line=(float(x0)-inset,mid,float(x1)+inset,mid)
        else:
            mid=(x0+x1)/2.0
            line=(mid,float(y0)-inset,mid,float(y1)+inset)
        geometry=tuple(round(v*72.0/dpi,6) for v in line)
        found.add(UnchangedRasterBandSegment(
            line,geometry,axis,(x0,y0,x1,y1)))
    return tuple(sorted(found,key=lambda seg:(
        seg.orientation,seg.geometry_pt,seg.pixel_geometry)))

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
