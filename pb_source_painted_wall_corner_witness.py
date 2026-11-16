"""Original native painted wall-path corner witnesses (never physical enclosure authority).

An original Finish_Floor outline may suggest a corner, but only two distinct
native dark wall-fills with perpendicular sources can corroborate it. A near
touch here is a DIAGNOSTIC witness: it never closes a wall, creates polygon
geometry, invents a dimension, or issues customer quantities.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
import re
from typing import Any

from pb_three_laurel_floor_wall_face_correspondence_shadow import (
    FloorWallCandidateReceipt, PHYSICAL_WALL_LAYERS, WallFaceCandidate,
)


@dataclass(frozen=True)
class SourcePaintedWallCorner:
    vertex_pdf_pt: tuple[float, float]
    before_side: str
    after_side: str
    source_wall_path_ids: tuple[int, int]
    native_wall_fill_gap_pdf_pt: float
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "vertex_pdf_pt": [round(v, 3) for v in self.vertex_pdf_pt],
            "before_side": self.before_side,
            "after_side": self.after_side,
            "source_wall_path_ids": list(self.source_wall_path_ids),
            "native_wall_fill_gap_pdf_pt": round(self.native_wall_fill_gap_pdf_pt, 3),
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
        }


@dataclass(frozen=True)
class SourcePaintedWallCornerReview:
    source_floor_path_id: int
    source_page_index: int
    source_sha256: str
    expected_corner_count: int
    observed_corners: tuple[SourcePaintedWallCorner, ...]
    missing_corner_indices: tuple[int, ...]
    physical_room_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "source_floor_path_id": self.source_floor_path_id,
            "source_page_index": self.source_page_index,
            "source_sha256": self.source_sha256,
            "expected_corner_count": self.expected_corner_count,
            "observed_corner_count": len(self.observed_corners),
            "observed_corners": [v.to_dict() for v in self.observed_corners],
            "missing_corner_indices": list(self.missing_corner_indices),
            "physical_room_authenticated": False,
            "measurement_authorized": False,
        }


def _orientation(face: WallFaceCandidate) -> str | None:
    x0, y0 = face.from_pdf_pt
    x1, y1 = face.to_pdf_pt
    if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
        return None
    if abs(y1 - y0) < 0.2 and abs(x1 - x0) > 5:
        return "horizontal"
    if abs(x1 - x0) < 0.2 and abs(y1 - y0) > 5:
        return "vertical"
    return None


def _source_wall_rectangle(
    drawings: Sequence[Mapping[str, Any] | object],
    path_id: int,
    *,
    orientation: str,
    floor_scope: str,
) -> tuple[tuple[float, float, float, float], str] | None:
    if type(path_id) is not int or not 0 <= path_id < len(drawings):
        return None
    row = drawings[path_id]
    if not isinstance(row, Mapping):
        return None
    if row.get("layer") not in PHYSICAL_WALL_LAYERS or row.get("type") != "f":
        return None
    fill = row.get("fill")
    if not isinstance(fill, (tuple, list)) or len(fill) < 3:
        return None
    try:
        if not all(0 <= float(v) < 0.3 and math.isfinite(float(v)) for v in fill[:3]):
            return None
        x0, y0, x1, y1 = (float(v) for v in row["rect"])
    except (ValueError, TypeError, KeyError, OverflowError):
        return None
    if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
        return None
    dx, dy = x1 - x0, y1 - y0
    if dx <= 0 or dy <= 0:
        return None
    if orientation == "horizontal":
        if dx <= max(6.0, 4.0 * dy):
            return None
    elif orientation == "vertical":
        if dy <= max(6.0, 4.0 * dx):
            return None
    else:
        return None
    scope = str(row.get("source_viewport_id") or row.get("viewport_id") or "").strip()
    if scope and floor_scope and scope != floor_scope:
        return None
    return (x0, y0, x1, y1), scope


def _point_to_box(
    vertex: tuple[float, float], rect: tuple[float, float, float, float],
) -> float:
    x, y = vertex
    a, b, c, d = rect
    return math.hypot(max(a - x, 0.0, x - c), max(b - y, 0.0, y - d))


def _box_to_box(
    one: tuple[float, float, float, float],
    two: tuple[float, float, float, float],
) -> float:
    a, b, c, d = one
    w, x, y, z = two
    return math.hypot(max(w - c, a - y, 0.0), max(x - d, b - z, 0.0))


def review_source_painted_wall_corners(
    drawings: Sequence[Mapping[str, Any] | object],
    receipt: FloorWallCandidateReceipt,
    *,
    max_native_gap_pdf_pt: float = 0.65,
) -> SourcePaintedWallCornerReview | None:
    """Corroborate polygon vertices without sealing or reshaping any room.

    All required source bar path IDs must already be independently owned
    by the two adjacent physical-side wall receipts. Missing/competing owners
    or unsupported diagonals remain missing, not nearest-neighbour snapped.
    """
    if (
        not isinstance(receipt, FloorWallCandidateReceipt)
        or receipt.floor_candidate_native_path_id is None
        or not 0 <= receipt.floor_candidate_native_path_id < len(drawings)
        or receipt.page_index < 0
        or re.fullmatch(r"[0-9a-f]{64}", receipt.source_sha256) is None
        or type(max_native_gap_pdf_pt) not in (float, int)
        or not math.isfinite(max_native_gap_pdf_pt)
        or not 0 < max_native_gap_pdf_pt <= 1.0
        or len(drawings) > 20_000
    ):
        return None
    floor_row = drawings[receipt.floor_candidate_native_path_id]
    if (
        not isinstance(floor_row, Mapping)
        or floor_row.get("layer") != "Finish_Floor"
        or floor_row.get("type") != "f"
    ):
        return None
    faces = receipt.wall_face_candidates
    if len(faces) < 3 or len(faces) > 200:
        return None
    witnessed: list[SourcePaintedWallCorner] = []
    missing: list[int] = []
    for i, before in enumerate(faces):
        after = faces[(i + 1) % len(faces)]
        vertex = before.to_pdf_pt
        first_axis, second_axis = _orientation(before), _orientation(after)
        if (
            not first_axis or not second_axis or first_axis == second_axis
            or math.dist(vertex, after.from_pdf_pt) > 0.1
        ):
            missing.append(i)
            continue
        eligible = []
        for face, axis in ((before, first_axis), (after, second_axis)):
            choices = []
            for path_id in face.supporting_native_wall_paths:
                bar = _source_wall_rectangle(
                    drawings, path_id, orientation=axis,
                    floor_scope=receipt.viewport_id,
                )
                if bar is None:
                    continue
                rect, scope = bar
                if _point_to_box(vertex, rect) <= max_native_gap_pdf_pt:
                    choices.append((path_id, rect, scope))
            eligible.append(choices)
        if len(eligible[0]) != 1 or len(eligible[1]) != 1:
            missing.append(i)
            continue
        (a_id, a_rect, a_scope), (b_id, b_rect, b_scope) = (
            eligible[0][0], eligible[1][0]
        )
        if a_id == b_id or (a_scope and b_scope and a_scope != b_scope):
            missing.append(i)
            continue
        gap = _box_to_box(a_rect, b_rect)
        if gap > max_native_gap_pdf_pt:
            missing.append(i)
            continue
        witnessed.append(SourcePaintedWallCorner(
            vertex, before.side, after.side, (a_id, b_id), gap,
        ))
    return SourcePaintedWallCornerReview(
        receipt.floor_candidate_native_path_id,
        receipt.page_index,
        receipt.source_sha256,
        len(faces),
        tuple(witnessed),
        tuple(missing),
    )
