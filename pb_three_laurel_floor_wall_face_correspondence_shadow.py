"""Shadow-only 3Laurel floor-to-native-wall candidate correspondence.

Floor finish paint may locate a room *candidate*, but can NEVER authenticate
its physical wall enclosure or customer measurements. This module recovers
native wall source path receipts per candidate boundary segment and reports
exact uncovered spans. It does NOT close doors, infer materials, seal results,
or give measurement authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

from shapely.geometry import Point, Polygon


PHYSICAL_WALL_LAYERS = frozenset({"Enclosure_WallExternal", "Enclosure_WallInternal"})
FLOOR_CANDIDATE_LAYER = "Finish_Floor"


@dataclass(frozen=True)
class WallFaceCandidate:
    side: str
    from_pdf_pt: tuple[float, float]
    to_pdf_pt: tuple[float, float]
    length_pdf_pt: float
    supported_length_pdf_pt: float
    supporting_native_wall_paths: tuple[int, ...]
    uncovered_intervals_pdf_pt: tuple[tuple[float, float], ...]
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "side": self.side,
            "from_pdf_pt": list(self.from_pdf_pt),
            "to_pdf_pt": list(self.to_pdf_pt),
            "length_pdf_pt": round(self.length_pdf_pt, 3),
            "supported_length_pdf_pt": round(self.supported_length_pdf_pt, 3),
            "supporting_native_wall_paths": list(self.supporting_native_wall_paths),
            "uncovered_intervals_pdf_pt": [
                list(v) for v in self.uncovered_intervals_pdf_pt
            ],
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
        }


@dataclass(frozen=True)
class FloorWallCandidateReceipt:
    label: str
    label_center_pdf_pt: tuple[float, float] | None
    floor_candidate_native_path_id: int | None
    floor_candidate_bounds_pdf_pts: tuple[float, float, float, float] | None
    wall_face_candidates: tuple[WallFaceCandidate, ...]
    supporting_native_wall_paths: tuple[int, ...]
    total_boundary_pdf_pt: float
    supported_boundary_pdf_pt: float
    page_index: int = -1
    source_sha256: str = ""
    viewport_id: str = ""
    status: str = "ABSTAINED"
    reason: str = "floor_outline_not_physical_wall_or_hosted_opening_proof"
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "page_index": self.page_index,
            "source_sha256": self.source_sha256,
            "viewport_id": self.viewport_id,
            "label_center_pdf_pt": list(self.label_center_pdf_pt)
            if self.label_center_pdf_pt
            else None,
            "floor_candidate_native_path_id": self.floor_candidate_native_path_id,
            "floor_candidate_bounds_pdf_pts": list(self.floor_candidate_bounds_pdf_pts)
            if self.floor_candidate_bounds_pdf_pts
            else None,
            "wall_face_candidates": [v.to_dict() for v in self.wall_face_candidates],
            "supporting_native_wall_paths": list(self.supporting_native_wall_paths),
            "total_boundary_pdf_pt": round(self.total_boundary_pdf_pt, 3),
            "supported_boundary_pdf_pt": round(self.supported_boundary_pdf_pt, 3),
            "status": "ABSTAINED",
            "reason": self.reason,
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
        }


def _native_rect(row: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    value = row.get("rect")
    if value is None:
        return None
    try:
        a, b, c, d = (float(v) for v in value)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (a, b, c, d)) or a >= c or b >= d:
        return None
    return (a, b, c, d)


def _native_scope(row: Mapping[str, Any]) -> str:
    return str(row.get("source_viewport_id") or row.get("viewport_id") or "").strip()


def _outline_polygon(row: Mapping[str, Any]) -> Polygon | None:
    if row.get("layer") != FLOOR_CANDIDATE_LAYER or row.get("type") != "f":
        return None
    if row.get("fill") is None:
        return None
    items = row.get("items") or ()
    if len(items) < 4 or any(
        not isinstance(v, (tuple, list)) or v[0] != "l" for v in items
    ):
        return None
    try:
        vertices = [(float(v[1][0]), float(v[1][1])) for v in items]
        last_end = (float(items[-1][2][0]), float(items[-1][2][1]))
    except (TypeError, ValueError, IndexError, AttributeError):
        return None
    # Reject disconnected path sequences that only have a rectangular bbox.
    for a, b in zip(items, items[1:]):
        if (
            math.dist(
                (float(a[2][0]), float(a[2][1])), (float(b[1][0]), float(b[1][1]))
            )
            > 0.1
        ):
            return None
    if math.dist(vertices[0], last_end) > 0.1:
        return None
    polygon = Polygon(vertices)
    if not polygon.is_valid or polygon.area < 30 or polygon.is_empty:
        return None
    return polygon


def _label_centers(
    words: Sequence[Sequence[Any]], label: str
) -> tuple[tuple[float, float], ...]:
    tokens = label.upper().split()
    centers: list[tuple[float, float]] = []
    for i in range(len(words) - len(tokens) + 1):
        group = words[i : i + len(tokens)]
        if any(str(w[4]).upper() != token for w, token in zip(group, tokens)):
            continue
        if len(tokens) > 1 and any(
            (w[5], w[6]) != (group[0][5], group[0][6]) for w in group
        ):
            continue
        try:
            bounds = (
                min(float(w[0]) for w in group),
                min(float(w[1]) for w in group),
                max(float(w[2]) for w in group),
                max(float(w[3]) for w in group),
            )
        except (TypeError, ValueError, IndexError):
            continue
        centers.append(((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2))
    return tuple(centers)


def _merge_intervals(
    a: float, b: float, intervals: Sequence[tuple[float, float]]
) -> tuple[float, tuple[tuple[float, float], ...]]:
    ordered = sorted(
        (max(a, s), min(b, e)) for s, e in intervals if min(b, e) - max(a, s) > 0.01
    )
    merged: list[list[float]] = []
    for s, e in ordered:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    supported = sum(e - s for s, e in merged)
    missing = []
    cursor = a
    for s, e in merged:
        if s > cursor + 0.01:
            missing.append((cursor, s))
        cursor = max(cursor, e)
    if b > cursor + 0.01:
        missing.append((cursor, b))
    return supported, tuple(missing)


def build_floor_to_physical_wall_candidate_receipt(
    drawings: Sequence[Mapping[str, Any] | object],
    words: Sequence[Sequence[Any]],
    label: str,
    *,
    boundary_tolerance_pdf_pt: float = 3.2,
    page_index: int = -1,
    source_sha256: str = "",
) -> FloorWallCandidateReceipt:
    """Locate nearest closed *floor* candidate and correlate with real wall bars.

    This is a WITNESS CENSUS, NOT source-authenticated room closure.
    Windows, portal thresholds and full perimeter authority require other
    separately host-verified evidence; all results remain ABSTAINED.
    """
    centers = _label_centers(words, label)
    fallback = FloorWallCandidateReceipt(
        label,
        None,
        None,
        None,
        (),
        (),
        0,
        0,
        page_index=page_index,
        source_sha256=source_sha256,
        reason="source_label_missing",
    )
    if not centers:
        return fallback

    candidates = []
    walls = []
    for path_id, raw in enumerate(drawings):
        if not isinstance(raw, Mapping):
            continue
        poly = _outline_polygon(raw)
        if poly is not None:
            for center in centers:
                if poly.contains(Point(center)):
                    candidates.append(
                        (poly.area, path_id, poly, center, _native_scope(raw))
                    )
        if raw.get("layer") in PHYSICAL_WALL_LAYERS:
            fill = raw.get("fill")
            rect = _native_rect(raw)
            if (
                rect is not None
                and isinstance(fill, (tuple, list))
                and len(fill) >= 3
                and all(math.isfinite(float(x)) for x in fill[:3])
                and max(float(x) for x in fill[:3]) < 0.3
            ):
                walls.append((path_id, rect, _native_scope(raw)))
    if not candidates:
        return FloorWallCandidateReceipt(
            label,
            centers[0],
            None,
            None,
            (),
            (),
            0,
            0,
            page_index=page_index,
            source_sha256=source_sha256,
            reason="no_source_floor_candidate_containing_label",
        )
    _, floor_id, poly, center, floor_scope = min(candidates, key=lambda z: (z[0], z[1]))
    segments = []
    owner_set = set()
    total = 0.0
    supported_total = 0.0
    coords = list(poly.exterior.coords)
    for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
        axis = (
            "h"
            if abs(y2 - y1) < 0.2 and abs(x2 - x1) > 5
            else "v"
            if abs(x2 - x1) < 0.2 and abs(y2 - y1) > 5
            else None
        )
        if axis is None:
            # Irregular/diagonal edges may be real, but cannot be proved by
            # a rectangular wall-face projector. Their full span is missing.
            length = math.dist((x1, y1), (x2, y2))
            if length <= 0.01:
                continue
            total += length
            segments.append(
                WallFaceCandidate(
                    "unresolved_nonorthogonal",
                    (x1, y1),
                    (x2, y2),
                    length,
                    0.0,
                    (),
                    ((0.0, length),),
                )
            )
            continue
        position = y1 if axis == "h" else x1
        start, end = (
            (min(x1, x2), max(x1, x2)) if axis == "h" else (min(y1, y2), max(y1, y2))
        )
        length = end - start
        intervals = []
        ids = []
        for path_id, (a, b, c, d), wall_scope in walls:
            if floor_scope and wall_scope and floor_scope != wall_scope:
                continue
            wall_long = (c - a) > 2 * (d - b) if axis == "h" else (d - b) > 2 * (c - a)
            if not wall_long:
                continue
            # Physical source-owned *fill*, not a floor hatch or annotation.
            if axis == "h":
                normal = min(
                    abs(position - b),
                    abs(position - d),
                    0.0 if b <= position <= d else math.inf,
                )
                wall_start, wall_end = a, c
            else:
                normal = min(
                    abs(position - a),
                    abs(position - c),
                    0.0 if a <= position <= c else math.inf,
                )
                wall_start, wall_end = b, d
            lo, hi = max(start, wall_start), min(end, wall_end)
            if normal > boundary_tolerance_pdf_pt or hi - lo <= 0.2:
                continue
            intervals.append((lo, hi))
            ids.append(path_id)
        covered, missing = _merge_intervals(start, end, intervals)
        total += length
        supported_total += covered
        owner_set.update(ids)
        side = (
            ("north" if position < center[1] else "south")
            if axis == "h"
            else ("west" if position < center[0] else "east")
        )
        segments.append(
            WallFaceCandidate(
                side,
                (x1, y1),
                (x2, y2),
                length,
                covered,
                tuple(sorted(set(ids))),
                missing,
            )
        )
    return FloorWallCandidateReceipt(
        label,
        center,
        floor_id,
        tuple(float(x) for x in poly.bounds),
        tuple(segments),
        tuple(sorted(owner_set)),
        total,
        supported_total,
        page_index=page_index,
        source_sha256=source_sha256,
        viewport_id=floor_scope,
    )
