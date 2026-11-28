"""Report only (#4764 7227402524, Lot16 raster walls): which paint made each raster segment?

See docs/engineering/claude_raster_paint_lineage_note_20261128.md. A segment whose pixels are in the producer's
images-only render is image ink; one whose pixels are not, but which native line segments cover within the render's pixel
size, is those lines' ink (all of them listed, none chosen). It names no new identities and changes nothing, and no live
path imports it. Segments and native lines must be given in the same page frame.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

import cv2
import numpy as np

from pb_raster_visible_segment_detector import _foreground_mask

IMAGE_INK, VECTOR_INK, IMAGE_AND_VECTOR, UNATTRIBUTED = "image_ink", "vector_ink", "image_and_vector", "unattributed"
_PRESENT, _ABSENT = 0.9, 0.1  # sampling tolerance on one rendered line


def _image_mask(images_only_png: bytes) -> np.ndarray | None:
    gray = cv2.imdecode(np.frombuffer(bytes(images_only_png), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if gray is None or gray.size == 0:
        return None
    mask = _foreground_mask(gray)
    return None if mask is None else cv2.dilate(mask, np.ones((3, 3), dtype=np.uint8))  # one pixel of rounding


def _image_share(mask: np.ndarray | None, geometry, pixels_per_point: float) -> float:
    if mask is None:
        return 0.0
    x0, y0, x1, y1 = (v * pixels_per_point for v in geometry)
    count = max(2, int(np.hypot(x1 - x0, y1 - y0)) + 1)
    xs = np.clip(np.round(np.linspace(x0, x1, count)).astype(int), 0, mask.shape[1] - 1)
    ys = np.clip(np.round(np.linspace(y0, y1, count)).astype(int), 0, mask.shape[0] - 1)
    return float(np.count_nonzero(mask[ys, xs])) / count


def _native_cover(orientation: str, geometry, native_lines, pixel_pt: float) -> tuple[float, list[str]]:
    along, across = (0, 1) if orientation == "horizontal" else (1, 0)
    ends = ((geometry[0], geometry[1]), (geometry[2], geometry[3]))
    start, end = sorted(point[along] for point in ends)
    level = (ends[0][across] + ends[1][across]) / 2.0
    if end <= start:
        return 0.0, []
    spans, ids = [], []
    for native_id, x0, y0, x1, y1, width in native_lines:
        a, b = (x0, y0), (x1, y1)
        if abs(a[across] - b[across]) > pixel_pt or abs((a[across] + b[across]) / 2.0 - level) > width / 2.0 + pixel_pt:
            continue
        lo, hi = sorted((a[along], b[along]))
        if min(hi, end) > max(lo, start):
            spans.append((max(lo, start), min(hi, end)))
            ids.append(str(native_id))
    covered, reach = 0.0, start
    for lo, hi in sorted(spans):
        covered += max(0.0, hi - max(lo, reach))
        reach = max(reach, hi)
    return covered / (end - start), sorted(set(ids))


def classify_raster_segment_paint(segments: Iterable[tuple[str, str, Sequence[float]]], images_only_png: bytes,
                                  native_lines: Sequence[tuple[str, float, float, float, float, float]], *,
                                  dpi: int) -> list[dict]:
    """``segments``: (id, orientation, (x0, y0, x1, y1) points); ``native_lines``: (id, x0, y0, x1, y1, width)."""
    pixels_per_point = float(dpi) / 72.0
    mask = _image_mask(images_only_png)
    natives = tuple(native_lines)
    found = []
    for segment_id, orientation, geometry in segments:
        share = _image_share(mask, geometry, pixels_per_point)
        cover, ids = _native_cover(orientation, geometry, natives, 1.0 / pixels_per_point)
        if share >= _PRESENT and cover >= _PRESENT:
            kind = IMAGE_AND_VECTOR
        elif share >= _PRESENT:  # the picture alone explains every pixel, whatever lines also cross it
            kind = IMAGE_INK
        elif share <= _ABSENT and cover >= _PRESENT:
            kind = VECTOR_INK
        else:
            kind = UNATTRIBUTED
        found.append({"segment_id": str(segment_id), "kind": kind, "image_share": round(share, 3),
                      "native_cover": round(cover, 3),
                      "native_ids": ids if kind in (VECTOR_INK, IMAGE_AND_VECTOR) else []})
    return sorted(found, key=lambda row: row["segment_id"])
