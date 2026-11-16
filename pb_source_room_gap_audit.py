"""Source-only diagnostic of floor-outline gaps after independently hosted openings.

A painted floor polygon is NOT a physical room. Even zero remaining gaps in
this diagnostic does not authorize wall, floor, ceiling, or customer measures.
Lengths here are original PDF points only, not physical construction units.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from collections.abc import Sequence

from pb_three_laurel_floor_wall_face_correspondence_shadow import (
    FloorWallCandidateReceipt, WallFaceCandidate,
)
from pb_three_laurel_floor_opening_correspondence_shadow import (
    FloorOpeningBoundaryWitness,
)


@dataclass(frozen=True)
class SourceUnresolvedRoomSide:
    side: str
    from_pdf_pt: tuple[float, float]
    to_pdf_pt: tuple[float, float]
    remaining_intervals_pdf_pt: tuple[tuple[float, float], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "side": self.side,
            "from_pdf_pt": list(self.from_pdf_pt),
            "to_pdf_pt": list(self.to_pdf_pt),
            "remaining_intervals_pdf_pt": [
                [round(a, 3), round(b, 3)]
                for a, b in self.remaining_intervals_pdf_pt
            ],
        }


@dataclass(frozen=True)
class SourceRoomGapAudit:
    room_label: str
    floor_candidate_native_path_id: int
    source_page_index: int
    source_sha256: str
    original_floor_outline_uncovered_pdf_pt: float
    hosted_opening_coverage_pdf_pt: float
    remaining_unproved_pdf_pt: float
    remaining_sides: tuple[SourceUnresolvedRoomSide, ...]
    zero_gap_candidate: bool
    room_enclosure_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "room_label": self.room_label,
            "floor_candidate_native_path_id": self.floor_candidate_native_path_id,
            "source_page_index": self.source_page_index,
            "source_sha256": self.source_sha256,
            "original_floor_outline_uncovered_pdf_pt": round(
                self.original_floor_outline_uncovered_pdf_pt, 3
            ),
            "hosted_opening_coverage_pdf_pt": round(
                self.hosted_opening_coverage_pdf_pt, 3
            ),
            "remaining_unproved_pdf_pt": round(self.remaining_unproved_pdf_pt, 3),
            "remaining_sides": [v.to_dict() for v in self.remaining_sides],
            "zero_gap_candidate": self.zero_gap_candidate,
            "room_enclosure_authenticated": False,
            "measurement_authorized": False,
        }


def _subtract_segments(
    original: tuple[float, float],
    cuts: Sequence[tuple[float, float]],
) -> tuple[tuple[float, float], ...]:
    """Exact interval difference; never extend/round a source boundary."""
    a, b = original
    if not (math.isfinite(a) and math.isfinite(b)) or b <= a:
        return ()
    remaining = [(a, b)]
    for x, y in cuts:
        if not (math.isfinite(x) and math.isfinite(y)) or y <= x:
            continue
        next_remaining = []
        for lo, hi in remaining:
            if y <= lo or x >= hi:
                next_remaining.append((lo, hi))
            else:
                if x > lo:
                    next_remaining.append((lo, min(x, hi)))
                if y < hi:
                    next_remaining.append((max(y, lo), hi))
        remaining = next_remaining
    return tuple((lo, hi) for lo, hi in remaining if hi - lo > 0.01)


def _same_physical_side(
    face: WallFaceCandidate, w: FloorOpeningBoundaryWitness,
    *, normal_tolerance_pdf_pt: float = 0.75,
) -> bool:
    if face.side != w.room_side:
        return False
    (ax, ay), (bx, by) = face.from_pdf_pt, face.to_pdf_pt
    x0, y0, x1, y1 = w.opening_bounds_pdf_pts
    if abs(ay - by) <= .2 and abs(ax - bx) > 1:
        normal = min(abs(ay - y0), abs(ay - y1))
    elif abs(ax - bx) <= .2 and abs(ay - by) > 1:
        normal = min(abs(ax - x0), abs(ax - x1))
    else:
        return False
    if normal > normal_tolerance_pdf_pt or w.boundary_distance_pdf_pt > normal_tolerance_pdf_pt:
        return False
    hosts = set(w.opening_host_path_ids)
    source_wall_paths = set(face.supporting_native_wall_paths)
    required = 2 if w.opening_kind == "fixed_window" else 1
    return len(hosts.intersection(source_wall_paths)) >= required


def audit_source_room_outline_remaining_gaps(
    receipt: FloorWallCandidateReceipt,
    witnesses: Sequence[FloorOpeningBoundaryWitness],
) -> SourceRoomGapAudit | None:
    """Subtract only SAME-SIDE source-owned apertures from source-outline gaps.

    This reports missing boundary evidence; it never seals a room, assumes a
    floor finish, estimates metric dimensions or issues customer quantities.
    """
    if (
        not isinstance(receipt, FloorWallCandidateReceipt)
        or receipt.floor_candidate_native_path_id is None
        or receipt.page_index < 0
        or not receipt.wall_face_candidates
        or len(receipt.source_sha256) != 64
        or any(c not in "0123456789abcdef" for c in receipt.source_sha256)
    ):
        return None
    seen = set()
    valid_witnesses = []
    for w in witnesses:
        if not isinstance(w, FloorOpeningBoundaryWitness):
            continue
        if (
            w.room_label != receipt.label
            or w.floor_candidate_path_id != receipt.floor_candidate_native_path_id
            or w.source_page_index != receipt.page_index
            or w.physical_wall_authenticated
            or w.measurement_authorized
        ):
            continue
        key = (
            w.opening_kind, tuple(sorted(w.opening_host_path_ids)),
            tuple(sorted(w.opening_source_path_ids)),
            w.room_side, w.supported_gap_interval_pdf_pts,
        )
        if key not in seen:
            seen.add(key)
            valid_witnesses.append(w)

    original_uncovered = 0.0
    remaining = 0.0
    side_rows = []
    for face in receipt.wall_face_candidates:
        gaps = []
        matched_cuts = [
            w.supported_gap_interval_pdf_pts
            for w in valid_witnesses if _same_physical_side(face, w)
        ]
        for original in face.uncovered_intervals_pdf_pt:
            if len(original) != 2 or original[1] <= original[0]:
                continue
            original_uncovered += original[1] - original[0]
            for a, b in _subtract_segments(original, matched_cuts):
                remaining += b - a
                gaps.append((a, b))
        if gaps:
            side_rows.append(SourceUnresolvedRoomSide(
                face.side, face.from_pdf_pt, face.to_pdf_pt, tuple(gaps),
            ))
    hosted = max(0.0, original_uncovered - remaining)
    return SourceRoomGapAudit(
        receipt.label, receipt.floor_candidate_native_path_id,
        receipt.page_index, receipt.source_sha256,
        original_uncovered, hosted, remaining, tuple(side_rows),
        zero_gap_candidate=(remaining <= .01 and original_uncovered > .01),
    )
