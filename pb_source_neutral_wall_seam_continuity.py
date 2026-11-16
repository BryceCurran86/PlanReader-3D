"""Native neutral-grey wall seam receipts for footprint graph continuity only.

Adjacent black exterior wall bars can already be joined by exact original
neutral-grey source-painted fills. Retain those fills as *graph* evidence,
without pretending a nearest-endpoint snap is a drawn physical wall, and
without issuing a material, area, window or frame quantity.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from shapely.geometry import box
from shapely.ops import unary_union

from pb_source_window_footprint_continuity import _EXTERIOR_WALL_LAYER, _rect


@dataclass(frozen=True)
class SourceNeutralWallSeam:
    first_host_path_id: int
    second_host_path_id: int
    neutral_fill_path_ids: tuple[int, ...]
    bounds_pdf_pts: tuple[float, float, float, float]
    axis: str
    page_index: int = -1
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "source_neutral_grey_wall_seam_continuity_only",
            "first_host_path_id": self.first_host_path_id,
            "second_host_path_id": self.second_host_path_id,
            "neutral_fill_path_ids": list(self.neutral_fill_path_ids),
            "bounds_pdf_pts": list(self.bounds_pdf_pts),
            "axis": self.axis,
            "page_index": self.page_index,
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
        }


def _same_viewport(
    drawings: Sequence[Mapping[str, Any] | object], paths: tuple[int, ...]
) -> bool:
    scopes = {
        str(
            drawings[i].get("viewport_id")
            or drawings[i].get("source_viewport_id")
            or ""
        ).strip()
        for i in paths
        if isinstance(drawings[i], Mapping)
    }
    scopes.discard("")
    return len(scopes) <= 1


def detect_source_neutral_wall_seams(
    drawings: Sequence[Mapping[str, Any] | object],
    *,
    page_index: int = -1,
) -> tuple[SourceNeutralWallSeam, ...]:
    """Accept ONLY an existing, fully covering original grey source fill.

    No distance snap. Nothing is authenticated if source paint is absent,
    has a conflicting viewport/layer, fails wall-band alignment, is colored
    rather than neutral-grey, or cannot cover every part of the ink gap.
    """
    dark: dict[str, list[tuple[int, tuple[float, float, float, float]]]] = defaultdict(
        list
    )
    gray: dict[str, list[tuple[int, tuple[float, float, float, float]]]] = defaultdict(
        list
    )
    for idx, row in enumerate(drawings):
        if not isinstance(row, Mapping):
            continue
        layer = str(row.get("layer") or "")
        if not _EXTERIOR_WALL_LAYER.search(layer):
            continue
        rect = _rect(row)
        fill = row.get("fill")
        if rect is None or not isinstance(fill, (tuple, list)) or len(fill) < 3:
            continue
        rgb = tuple(float(v) for v in fill[:3])
        if not all(math.isfinite(v) for v in rgb):
            continue
        dx, dy = rect[2] - rect[0], rect[3] - rect[1]
        if min(dx, dy) < 0.1:
            continue
        if max(rgb) < 0.3:
            dark[layer].append((idx, rect))
        elif 0.3 < min(rgb) and max(rgb) < 0.75 and max(rgb) - min(rgb) < 0.035:
            gray[layer].append((idx, rect))
    seams = []
    for layer, hosts in dark.items():
        fills = gray.get(layer, [])
        if not fills:
            continue
        for axis in ("h", "v"):
            if axis == "h":
                starts = sorted((b[0], idx, b) for idx, b in hosts)
            else:
                starts = sorted((b[1], idx, b) for idx, b in hosts)
            start_coords = [x for x, _, _ in starts]
            for i, a in hosts:
                end = a[2] if axis == "h" else a[3]
                lo = bisect_left(start_coords, end + 0.2)
                hi = bisect_right(start_coords, end + 8)
                for _, j, b in starts[lo:hi]:
                    if i == j:
                        continue
                    if axis == "h":
                        thick1, thick2 = a[3] - a[1], b[3] - b[1]
                        gap = b[0] - a[2]
                        align = abs((a[1] + a[3]) - (b[1] + b[3])) / 2
                        bounds = (a[2], max(a[1], b[1]), b[0], min(a[3], b[3]))
                        host_length = min(a[2] - a[0], b[2] - b[0])
                    else:
                        thick1, thick2 = a[2] - a[0], b[2] - b[0]
                        gap = b[1] - a[3]
                        align = abs((a[0] + a[2]) - (b[0] + b[2])) / 2
                        bounds = (max(a[0], b[0]), a[3], min(a[2], b[2]), b[1])
                        host_length = min(a[3] - a[1], b[3] - b[1])
                    thick = min(thick1, thick2)
                    if not (
                        0.2 <= gap <= min(8, 3 * thick)
                        and 0.7 <= thick <= 8
                        and host_length >= 0.75 * thick
                        and abs(thick1 - thick2) < 0.3
                        and align < 0.1
                        and bounds[2] > bounds[0]
                        and bounds[3] > bounds[1]
                    ):
                        continue
                    gap_geom = box(*bounds)
                    owners = [
                        (k, box(*c))
                        for k, c in fills
                        if box(*c).intersection(gap_geom).area > 0.001
                    ]
                    if not owners:
                        continue
                    # Two redundant full-gap native owners are not a unique
                    # physical witness. Actual adjacent half-gap fills are.
                    full_owners = sum(
                        1 for _, g in owners if g.buffer(0.002).covers(gap_geom)
                    )
                    if full_owners > 1:
                        continue
                    native_union = unary_union([g for _, g in owners])
                    if not native_union.buffer(0.002).covers(gap_geom):
                        continue
                    native_ids = tuple(sorted(k for k, _ in owners))
                    if not _same_viewport(drawings, (i, j, *native_ids)):
                        continue
                    seams.append(
                        SourceNeutralWallSeam(
                            first_host_path_id=i,
                            second_host_path_id=j,
                            neutral_fill_path_ids=native_ids,
                            bounds_pdf_pts=bounds,
                            axis=axis,
                            page_index=page_index,
                        )
                    )
    unique = {(s.first_host_path_id, s.second_host_path_id, s.axis): s for s in seams}
    return tuple(
        sorted(
            unique.values(),
            key=lambda s: (s.first_host_path_id, s.second_host_path_id, s.axis),
        )
    )
