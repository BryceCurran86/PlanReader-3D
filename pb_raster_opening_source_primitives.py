"""Source-only raster primitives for physical-opening evidence compilation.

This module is perception only. It converts an images-only producer-owned page
render into conservative source geometry primitives. It does not pair gaps,
classify openings, bind hosts, infer semantic kind, measure quantities, or
publish commercial output.

The thresholds and primitive construction were promoted from the independently
reviewed shadow study in PR #1276. Opening-existence decisions remain outside
this module and belong to PhysicalOpeningAuthority.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import cv2
import numpy as np


RASTER_OPENING_PRIMITIVE_SCHEMA_VERSION = "1.1.0"
RASTER_OPENING_PRIMITIVE_DETECTOR_VERSION = "raster_opening_source_primitives_v4"

RASTER_WALL_BAND_FACE = "raster_wall_band_face"
RASTER_WALL_BAND_END = "raster_wall_band_end"
RASTER_THIN_INK_RUN = "raster_thin_ink_run"
RASTER_LINE_RUN = "raster_line_run"

# Paper-unit / relative geometry constants inherited from the reviewed shadow
# primitive layer. None is a drawing scale, project coordinate, or BOQ value.
MASS_THRESHOLD = 200
LINE_THRESHOLD = 160
POCHE_MIN_PT = 2.0
BAND_MIN_RUN_PT = 4.0
BAND_MAX_THICKNESS_PT = 12.0
BAND_MIN_ASPECT = 1.5
THIN_RUN_MIN_PT = 4.0
THIN_RUN_MAX_THICKNESS_PT = 1.5
MAX_PRIMITIVES = 20_000


@dataclass(frozen=True, order=True)
class RasterOpeningSourcePrimitive:
    """One source-derived raster geometry primitive in page-point coordinates."""

    primitive_kind: str
    pixel_geometry: tuple[float, float, float, float]
    geometry_pt: tuple[float, float, float, float]


def _px(value_pt: float, dpi: int, *, minimum: int = 1) -> int:
    return max(int(minimum), int(round(float(value_pt) * float(dpi) / 72.0)))


def _scaled_px(
    value_pt: float,
    dpi: int,
    scale: float,
    *,
    minimum: int = 1,
) -> int:
    if not math.isfinite(float(scale)) or float(scale) <= 0.0:
        raise ValueError("registration scale must be positive and finite")
    return max(
        int(minimum),
        int(round(float(value_pt) * float(dpi) / 72.0 * float(scale))),
    )


def _axis_registration_scales(
    axis: str,
    registration_scale: tuple[float, float],
) -> tuple[float, float]:
    sx, sy = (float(value) for value in registration_scale)
    if (
        not math.isfinite(sx)
        or not math.isfinite(sy)
        or sx <= 0.0
        or sy <= 0.0
    ):
        raise ValueError("registration_scale must contain positive finite values")
    if axis == "horizontal":
        return sx, sy
    if axis == "vertical":
        return sy, sx
    raise ValueError("axis must be horizontal or vertical")


def _odd(value: int) -> int:
    value = int(value)
    return value if value % 2 else value + 1


def _to_pt(value_px: float, dpi: int) -> float:
    return round(float(value_px) * 72.0 / float(dpi), 6)


def _canonical_segment(
    first: tuple[float, float],
    second: tuple[float, float],
) -> tuple[float, float, float, float]:
    if second < first:
        first, second = second, first
    return (float(first[0]), float(first[1]), float(second[0]), float(second[1]))


def _primitive(
    kind: str,
    pixel_geometry: tuple[float, float, float, float],
    *,
    dpi: int,
) -> RasterOpeningSourcePrimitive:
    pixel_geometry = _canonical_segment(
        (pixel_geometry[0], pixel_geometry[1]),
        (pixel_geometry[2], pixel_geometry[3]),
    )
    geometry_pt = tuple(_to_pt(value, dpi) for value in pixel_geometry)
    return RasterOpeningSourcePrimitive(
        primitive_kind=kind,
        pixel_geometry=pixel_geometry,
        geometry_pt=geometry_pt,  # type: ignore[arg-type]
    )


def _band_boxes(
    thick: np.ndarray,
    *,
    dpi: int,
    axis: str,
    registration_scale: tuple[float, float] = (1.0, 1.0),
) -> tuple[tuple[int, int, int, int], ...]:
    work = thick if axis == "horizontal" else np.ascontiguousarray(thick.T)
    along_scale, cross_scale = _axis_registration_scales(
        axis,
        registration_scale,
    )
    run = _odd(_scaled_px(BAND_MIN_RUN_PT, dpi, along_scale))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (run, 1))
    band = cv2.morphologyEx(work, cv2.MORPH_OPEN, kernel)
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        band,
        connectivity=8,
    )
    solid = _scaled_px(POCHE_MIN_PT, dpi, cross_scale)
    tmax = _scaled_px(BAND_MAX_THICKNESS_PT, dpi, cross_scale)
    boxes: list[tuple[int, int, int, int]] = []
    for index in range(1, int(count)):
        x = int(stats[index, cv2.CC_STAT_LEFT])
        y = int(stats[index, cv2.CC_STAT_TOP])
        width = int(stats[index, cv2.CC_STAT_WIDTH])
        height = int(stats[index, cv2.CC_STAT_HEIGHT])
        if (
            height < solid
            or height > tmax
            or (width / along_scale)
            < BAND_MIN_ASPECT * (height / cross_scale)
        ):
            continue
        box = (x, y, x + width - 1, y + height - 1)
        if axis == "vertical":
            box = (box[1], box[0], box[3], box[2])
        boxes.append(box)
    return tuple(sorted(set(boxes)))


def _band_edge_primitives(
    thick: np.ndarray,
    *,
    dpi: int,
    registration_scale: tuple[float, float] = (1.0, 1.0),
) -> Iterable[RasterOpeningSourcePrimitive]:
    for axis in ("horizontal", "vertical"):
        for x0, y0, x1, y1 in _band_boxes(
            thick,
            dpi=dpi,
            axis=axis,
            registration_scale=registration_scale,
        ):
            if axis == "horizontal":
                faces = (
                    (x0, y0, x1, y0),
                    (x0, y1, x1, y1),
                )
                ends = (
                    (x0, y0, x0, y1),
                    (x1, y0, x1, y1),
                )
            else:
                faces = (
                    (x0, y0, x0, y1),
                    (x1, y0, x1, y1),
                )
                ends = (
                    (x0, y0, x1, y0),
                    (x0, y1, x1, y1),
                )
            for geometry in faces:
                yield _primitive(RASTER_WALL_BAND_FACE, geometry, dpi=dpi)
            for geometry in ends:
                yield _primitive(RASTER_WALL_BAND_END, geometry, dpi=dpi)


def _raw_axis_line_run_primitives(
    line_mask: np.ndarray,
    *,
    dpi: int,
    axis: str,
    exclude_mask: np.ndarray | None = None,
    registration_scale: tuple[float, float] = (1.0, 1.0),
) -> Iterable[RasterOpeningSourcePrimitive]:
    """Publish neutral axis-line evidence without re-publishing thick poche.

    Frame lines can touch jamb or wall ink and therefore cannot be recovered
    safely from connected-component boxes. Scan rows (or columns) independently,
    but when exclude_mask is supplied remove pixels already classified as thick
    wall/poche mass before run enumeration. This prevents dense filled wall
    regions from exploding into one neutral line primitive per raster row.

    A retained run may recover at most one excluded source-ink pixel at each end.
    That preserves exact jamb contact for a thin frame line without walking back
    through the thick mass or manufacturing a wall-spanning line. This remains
    perception only: no gap, frame, opening, or host relation is decided here.
    """

    source_work = (
        line_mask
        if axis == "horizontal"
        else np.ascontiguousarray(line_mask.T)
    )
    excluded_work: np.ndarray | None = None
    if exclude_mask is not None:
        if exclude_mask.shape != line_mask.shape:
            raise ValueError("exclude_mask must match line_mask shape")
        excluded_work = (
            exclude_mask
            if axis == "horizontal"
            else np.ascontiguousarray(exclude_mask.T)
        )
        work = (source_work & (excluded_work == 0)).astype(np.uint8)
    else:
        work = source_work
    along_scale, _cross_scale = _axis_registration_scales(
        axis,
        registration_scale,
    )
    minimum = _scaled_px(THIN_RUN_MIN_PT, dpi, along_scale)
    for row_index, row in enumerate(work):
        padded = np.pad(row.astype(np.int8, copy=False), (1, 1))
        transitions = np.diff(padded)
        starts = np.flatnonzero(transitions == 1)
        ends = np.flatnonzero(transitions == -1) - 1
        for start, end in zip(starts.tolist(), ends.tolist()):
            if end - start + 1 < minimum:
                continue

            # Recover only immediate source-ink contact with excluded wall mass.
            # Never traverse further into the excluded region.
            if excluded_work is not None:
                if (
                    start > 0
                    and bool(source_work[row_index, start - 1])
                    and bool(excluded_work[row_index, start - 1])
                ):
                    start -= 1
                if (
                    end + 1 < source_work.shape[1]
                    and bool(source_work[row_index, end + 1])
                    and bool(excluded_work[row_index, end + 1])
                ):
                    end += 1

            center = float(row_index)
            geometry = (float(start), center, float(end), center)
            if axis == "vertical":
                geometry = (center, float(start), center, float(end))
            yield _primitive(RASTER_LINE_RUN, geometry, dpi=dpi)


def _axis_run_primitives(
    thin_mask: np.ndarray,
    *,
    dpi: int,
    axis: str,
    registration_scale: tuple[float, float] = (1.0, 1.0),
) -> Iterable[RasterOpeningSourcePrimitive]:
    work = thin_mask if axis == "horizontal" else np.ascontiguousarray(thin_mask.T)
    along_scale, cross_scale = _axis_registration_scales(
        axis,
        registration_scale,
    )
    run = _odd(_scaled_px(THIN_RUN_MIN_PT, dpi, along_scale))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (run, 1))
    opened = cv2.morphologyEx(work, cv2.MORPH_OPEN, kernel)
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        opened,
        connectivity=8,
    )
    max_thickness = _scaled_px(
        THIN_RUN_MAX_THICKNESS_PT,
        dpi,
        cross_scale,
    )
    for index in range(1, int(count)):
        x = int(stats[index, cv2.CC_STAT_LEFT])
        y = int(stats[index, cv2.CC_STAT_TOP])
        width = int(stats[index, cv2.CC_STAT_WIDTH])
        height = int(stats[index, cv2.CC_STAT_HEIGHT])
        if width < run or height > max_thickness:
            continue
        center = y + (height - 1) / 2.0
        geometry = (float(x), center, float(x + width - 1), center)
        if axis == "vertical":
            geometry = (center, float(x), center, float(x + width - 1))
        yield _primitive(RASTER_THIN_INK_RUN, geometry, dpi=dpi)


def detect_raster_opening_source_primitives(
    png_bytes: bytes,
    *,
    dpi: int,
    registration_scale: tuple[float, float] = (1.0, 1.0),
) -> tuple[RasterOpeningSourcePrimitive, ...]:
    """Extract perception-only raster primitives from an images-only PNG render."""

    if not isinstance(png_bytes, (bytes, bytearray, memoryview)):
        raise TypeError("png_bytes must be bytes-like")
    dpi = int(dpi)
    if dpi <= 0:
        raise ValueError("dpi must be positive")

    encoded = np.frombuffer(bytes(png_bytes), dtype=np.uint8)
    gray = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if gray is None or gray.ndim != 2 or gray.size == 0:
        raise ValueError("raster opening primitive render is unreadable")

    mass = (gray < MASS_THRESHOLD).astype(np.uint8)
    line_mask = (gray < LINE_THRESHOLD).astype(np.uint8)
    sx, sy = (float(value) for value in registration_scale)
    if (
        not math.isfinite(sx)
        or not math.isfinite(sy)
        or sx <= 0.0
        or sy <= 0.0
    ):
        raise ValueError("registration_scale must contain positive finite values")
    solid_x = _odd(_scaled_px(POCHE_MIN_PT, dpi, sx))
    solid_y = _odd(_scaled_px(POCHE_MIN_PT, dpi, sy))
    thick = cv2.morphologyEx(
        mass,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (solid_x, solid_y),
        ),
    )
    halo = cv2.dilate(thick, np.ones((3, 3), np.uint8))
    thin_mask = (line_mask & (halo == 0)).astype(np.uint8)

    primitives = set(_band_edge_primitives(
        thick,
        dpi=dpi,
        registration_scale=registration_scale,
    ))
    primitives.update(
        _raw_axis_line_run_primitives(
            line_mask,
            dpi=dpi,
            axis="horizontal",
            exclude_mask=thick,
            registration_scale=registration_scale,
        )
    )
    primitives.update(
        _raw_axis_line_run_primitives(
            line_mask,
            dpi=dpi,
            axis="vertical",
            exclude_mask=thick,
            registration_scale=registration_scale,
        )
    )
    # Preserve the stricter hairline primitive for later swing evidence. It is
    # intentionally distinct from RASTER_LINE_RUN, which is the neutral source
    # evidence required by framed-opening G17 review.
    primitives.update(_axis_run_primitives(
        thin_mask,
        dpi=dpi,
        axis="horizontal",
        registration_scale=registration_scale,
    ))
    primitives.update(_axis_run_primitives(
        thin_mask,
        dpi=dpi,
        axis="vertical",
        registration_scale=registration_scale,
    ))
    if len(primitives) > MAX_PRIMITIVES:
        raise ValueError("raster opening primitive count exceeds safety bound")

    result = tuple(sorted(primitives))
    for primitive in result:
        if not all(math.isfinite(value) for value in primitive.geometry_pt):
            raise ValueError("raster opening primitive geometry is non-finite")
        x0, y0, x1, y1 = primitive.geometry_pt
        if math.hypot(x1 - x0, y1 - y0) <= 0.0:
            raise ValueError("raster opening primitive geometry is degenerate")
    return result


__all__ = [
    "RASTER_OPENING_PRIMITIVE_DETECTOR_VERSION",
    "RASTER_OPENING_PRIMITIVE_SCHEMA_VERSION",
    "RASTER_LINE_RUN",
    "RASTER_THIN_INK_RUN",
    "RASTER_WALL_BAND_END",
    "RASTER_WALL_BAND_FACE",
    "MASS_THRESHOLD",
    "LINE_THRESHOLD",
    "POCHE_MIN_PT",
    "BAND_MIN_RUN_PT",
    "BAND_MAX_THICKNESS_PT",
    "BAND_MIN_ASPECT",
    "RasterOpeningSourcePrimitive",
    "detect_raster_opening_source_primitives",
]
