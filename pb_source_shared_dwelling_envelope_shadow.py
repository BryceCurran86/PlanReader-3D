"""Source-only inter-dwelling PARTY wall evidence for a shared building envelope.

A party wall can be drawn in an 'External' CAD wall layer even though it
separates TWO dwellings INSIDE ONE building footprint. The interior-face
walk may trace an individual dwelling and close on this party wall: that
does not prove the building's OUTSIDE boundary.

This is a read-only diagnostic: native source annotation + dark physical
wall geometry + conditioned-space labels on opposite sides. It does NOT
construct a footprint, mint a dwelling count, approve wall roles or bill.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

from shapely.geometry import LineString, Polygon, box


_WALL_LAYERS = frozenset({"Enclosure_WallExternal", "Enclosure_WallInternal"})
_CONDITIONED_LABELS = frozenset(
    {
        "LIVING",
        "MEDIA",
        "DINING",
        "KITCHEN",
        "KIT",
        "BED",
        "BEDROOM",
        "STUDY",
        "OFFICE",
        "BATH",
        "BATHROOM",
        "LAUNDRY",
        "WC",
        "WIR",
        "WIP",
        "MASTER",
        "ENTRY",
        "GARAGE",
        "FAMILY",
        "LOUNGE",
    }
)
_OPEN_AIR_LABELS = frozenset(
    {"ALFRESCO", "PORCH", "VERANDA", "VERANDAH", "PATIO", "DECK"}
)
_MAX_ANNOTATION_WALL_DISTANCE_PT = 95.0


@dataclass(frozen=True)
class CandidateSharedBuildingDivider:
    """Native-source evidence, NOT an authoritative dwelling or wall role."""

    source_page_index: int
    annotation_word_ids: tuple[int, ...]
    annotation_text: str
    wall_native_path_ids: tuple[int, ...]
    wall_layer: str
    wall_bounds_pdf_pts: tuple[float, float, float, float]
    orientation: str
    side_one_label: str
    side_two_label: str
    source_role: str = "candidate_inter_dwelling_party_wall"
    building_envelope_policy: str = "shared_outer_envelope_not_unit_room_loop"
    minimum_dwelling_zones_candidate: int = 2
    wall_role_authenticated: bool = False
    building_footprint_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "source_page_index": self.source_page_index,
            "annotation_word_ids": list(self.annotation_word_ids),
            "annotation_text": self.annotation_text,
            "wall_native_path_ids": list(self.wall_native_path_ids),
            "wall_layer": self.wall_layer,
            "wall_bounds_pdf_pts": list(self.wall_bounds_pdf_pts),
            "orientation": self.orientation,
            "side_one_label": self.side_one_label,
            "side_two_label": self.side_two_label,
            "source_role": self.source_role,
            "building_envelope_policy": self.building_envelope_policy,
            "minimum_dwelling_zones_candidate": self.minimum_dwelling_zones_candidate,
            "wall_role_authenticated": False,
            "building_footprint_authenticated": False,
            "measurement_authorized": False,
        }


def _word(row: Mapping[str, Any] | Sequence[Any], index: int):
    if isinstance(row, Mapping):
        txt = str(row.get("text") or "").strip().upper().strip(".,;:()")
        bounds = row.get("bbox_pdf_pts") or row.get("bbox")
        block = row.get("block_no", row.get("block_id"))
        line = row.get("line_no", row.get("line_id"))
    elif isinstance(row, (tuple, list)) and len(row) >= 5:
        txt = str(row[4]).strip().upper().strip(".,;:()")
        bounds = row[:4]
        block = row[5] if len(row) > 5 else None
        line = row[6] if len(row) > 6 else None
    else:
        return None
    try:
        rect = tuple(float(v) for v in bounds)
    except (TypeError, ValueError, OverflowError):
        return None
    if len(rect) != 4 or not all(math.isfinite(v) for v in rect):
        return None
    if rect[0] >= rect[2] or rect[1] >= rect[3]:
        return None
    return index, txt, rect, block, line


def _annotations_and_rooms(source_words):
    words = [
        item
        for i, raw in enumerate(source_words)
        if (item := _word(raw, i)) is not None
    ]
    notes = []
    for party in words:
        if party[1] != "PARTY":
            continue
        for wall in words:
            if wall[1] != "WALL":
                continue
            same_block = party[3] is not None and party[3] == wall[3]
            same_line = (
                abs(wall[2][1] - party[2][1]) <= 9.0
                and abs(wall[2][0] - party[2][2]) <= 28.0
            )
            if not (same_block or same_line):
                continue
            if (
                same_block
                and party[4] is not None
                and wall[4] is not None
            ):
                try:
                    if abs(int(party[4]) - int(wall[4])) > 3:
                        continue
                except (ValueError, TypeError, OverflowError):
                    continue
            bbox = (
                min(party[2][0], wall[2][0]),
                min(party[2][1], wall[2][1]),
                max(party[2][2], wall[2][2]),
                max(party[2][3], wall[2][3]),
            )
            notes.append(((party[0], wall[0]), bbox))
    # Some PDF exporters preserve an entire note as one native word.
    for word in words:
        if "PARTY WALL" in word[1] or "PARTY_WALL" in word[1]:
            notes.append(((word[0],), word[2]))
    rooms = []
    for item in words:
        if item[1] in _CONDITIONED_LABELS:
            bbox = item[2]
            rooms.append((item[1], ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)))
    return notes, rooms


def _painted_wall(rect, row) -> bool:
    if str(row.get("layer") or "") not in _WALL_LAYERS:
        return False
    fill = row.get("fill")
    if not isinstance(fill, (tuple, list)) or len(fill) < 3:
        return False
    try:
        return all(math.isfinite(float(t)) and 0 <= float(t) < 0.3 for t in fill[:3])
    except (ValueError, TypeError, OverflowError):
        return False


def _wall_rectangles(drawings):
    result = []
    for index, raw in enumerate(drawings):
        if not isinstance(raw, Mapping):
            continue
        rect = raw.get("rect")
        try:
            x0, y0, x1, y1 = (float(t) for t in rect)
        except (TypeError, ValueError, OverflowError):
            continue
        if not (x0 < x1 and y0 < y1):
            continue
        if not _painted_wall(rect, raw):
            continue
        dx, dy = x1 - x0, y1 - y0
        if min(dx, dy) <= 0.01 or max(dx, dy) < 45 or max(dx, dy) < 9 * min(dx, dy):
            continue
        orientation = "vertical" if dy > dx else "horizontal"
        result.append((index, str(raw["layer"]), (x0, y0, x1, y1), orientation))
    return result


def detect_native_shared_dwelling_dividers(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Mapping[str, Any] | Sequence[Any]],
    *,
    source_page_index: int = -1,
) -> tuple[CandidateSharedBuildingDivider, ...]:
    """Classify only labelled, structurally drawn, two-sided party candidates.

    The annotation alone cannot turn a generic interior wall into an
    authenticated PARTY role. Need uniquely located native physical wall ink
    AND conditioned-room words on both sides. Two dwelling ZONES are only
    a candidate, pending source plan/building envelope authority.
    """
    notes, rooms = _annotations_and_rooms(source_words)
    if not notes or not rooms:
        return ()
    walls = _wall_rectangles(drawings)
    if not walls:
        return ()
    results = []
    for word_ids, bounds in notes:
        cx = (bounds[0] + bounds[2]) / 2
        cy = (bounds[1] + bounds[3]) / 2
        plausible = []
        for idx, layer, rect, orientation in walls:
            x0, y0, x1, y1 = rect
            along_inside = (
                y0 - 10 <= cy <= y1 + 10
                if orientation == "vertical"
                else x0 - 10 <= cx <= x1 + 10
            )
            if not along_inside:
                continue
            normal = (
                max(0.0, x0 - cx, cx - x1)
                if orientation == "vertical"
                else max(0.0, y0 - cy, cy - y1)
            )
            if normal > _MAX_ANNOTATION_WALL_DISTANCE_PT:
                continue
            midpoint = (x0 + x1) / 2 if orientation == "vertical" else (y0 + y1) / 2
            low, high = (y0, y1) if orientation == "vertical" else (x0, x1)
            side_a = []
            side_b = []
            for label, (rx, ry) in rooms:
                normal_room = rx if orientation == "vertical" else ry
                along_room = ry if orientation == "vertical" else rx
                if not (low - 3 <= along_room <= high + 3):
                    continue
                # An unrelated room in another faraway part of the sheet
                # must not supply proof of a dwelling on the other side.
                if abs(normal_room - midpoint) > 180:
                    continue
                if normal_room < midpoint - 7:
                    side_a.append((abs(normal_room - midpoint), label))
                elif normal_room > midpoint + 7:
                    side_b.append((abs(normal_room - midpoint), label))
            if not side_a or not side_b:
                continue
            side_a.sort()
            side_b.sort()
            # Prefer full-height, named-physical wall evidence to a short,
            # coincidental wall near the label. This is not a wall-role seal.
            length = high - low
            ranking = (length / (1 + normal), length)
            plausible.append(
                (ranking, idx, layer, rect, orientation, side_a[0][1], side_b[0][1])
            )
        if not plausible:
            continue
        plausible.sort(key=lambda v: v[0], reverse=True)
        _, anchor_idx, anchor_layer, anchor_rect, orientation, left, right = plausible[
            0
        ]
        x0, y0, x1, y1 = anchor_rect
        anchor_normal = (x0 + x1) / 2 if orientation == "vertical" else (y0 + y1) / 2
        anchor_length = (y1 - y0) if orientation == "vertical" else (x1 - x0)
        grouped = []
        for idx, layer, rect, axis in walls:
            if layer != anchor_layer or orientation != axis:
                continue
            a0, a1 = (rect[0], rect[2]) if axis == "vertical" else (rect[1], rect[3])
            b0, b1 = (rect[1], rect[3]) if axis == "vertical" else (rect[0], rect[2])
            normal = (a0 + a1) / 2
            if abs(normal - anchor_normal) > 7.5:
                continue
            ref_start, ref_end = (y0, y1) if axis == "vertical" else (x0, x1)
            overlap = min(ref_end, b1) - max(ref_start, b0)
            if overlap < min(anchor_length * 0.18, 30):
                continue
            grouped.append(idx)
        if anchor_idx not in grouped:
            grouped.append(anchor_idx)
        result = CandidateSharedBuildingDivider(
            source_page_index=source_page_index,
            annotation_word_ids=tuple(sorted(set(word_ids))),
            annotation_text="PARTY WALL",
            wall_native_path_ids=tuple(sorted(set(grouped))),
            wall_layer=anchor_layer,
            wall_bounds_pdf_pts=tuple(anchor_rect),
            orientation=orientation,
            side_one_label=left,
            side_two_label=right,
        )
        if result not in results:
            results.append(result)
    return tuple(results)


def closed_loop_uses_interior_dwelling_divider(
    polygon_pdf_pts: Sequence[tuple[float, float]] | Polygon,
    party_candidates: Sequence[CandidateSharedBuildingDivider],
    *,
    proximity_pdf_pt: float = 1.0,
) -> bool:
    """Never accept an individual-dwelling cycle as the building envelope.

    This is a VETO ONLY, not positive exterior geometry or billable wall.
    It never promotes a different cycle to an envelope.
    """
    if not party_candidates:
        return False
    try:
        ring = (
            polygon_pdf_pts
            if isinstance(polygon_pdf_pts, Polygon)
            else Polygon(polygon_pdf_pts)
        )
        if not ring.is_valid or ring.is_empty:
            return False
    except (ValueError, TypeError):
        return False
    for candidate in party_candidates:
        x0, y0, x1, y1 = candidate.wall_bounds_pdf_pts
        if candidate.orientation == "vertical":
            faces = (
                LineString(((x0, y0), (x0, y1))),
                LineString(((x1, y0), (x1, y1))),
            )
        else:
            faces = (
                LineString(((x0, y0), (x1, y0))),
                LineString(((x0, y1), (x1, y1))),
            )
        # A real whole-building outer perimeter often touches the PARTY
        # wall at its TOP and BOTTOM endpoints. That is fine. Reject only
        # a ring which actually travels ALONG a substantial part of the
        # separating wall face (e.g. the wrong left-dwelling-only loop).
        if any(
            face.length > 0
            and face.intersection(ring.boundary.buffer(proximity_pdf_pt)).length
            / face.length
            >= 0.55
            for face in faces
        ):
            return True
    return False
