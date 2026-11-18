"""Shadow: finished interior face recovery with false-wall veto.

Cursor-07 (#4537). Requires genuine mitred/parallel wall supports and positive
thickness evidence. Labels are geometry-located source words only — never
hardcoded room lists as prediction inputs. Does not issue FIRM areas.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pb_layered_wall_doorway_room_ring_shadow import NOISE_PT


@dataclass(frozen=True)
class FinishedInteriorFaceCandidate:
    room_label: str
    label_bbox_pdf_pts: tuple[float, float, float, float]
    support_path_ids: tuple[int, ...]
    thickness_pt: float | None
    status: str
    reason: str
    physical_face_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "room_label": self.room_label,
            "label_bbox_pdf_pts": list(self.label_bbox_pdf_pts),
            "support_path_ids": list(self.support_path_ids),
            "thickness_pt": self.thickness_pt,
            "status": self.status,
            "reason": self.reason,
            "physical_face_authenticated": False,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }


def _word_rows(source_words: Sequence[Any]) -> tuple[tuple[str, tuple[float, float, float, float]], ...]:
    out = []
    for row in source_words:
        try:
            if isinstance(row, Mapping):
                text = str(row.get("text") or "").strip()
                bounds = row.get("bbox_pdf_pts") or row.get("bbox")
            else:
                text = str(row[4]).strip()
                bounds = row[:4]
            box = tuple(float(v) for v in bounds)
            if text and len(box) == 4 and all(math.isfinite(v) for v in box):
                out.append((text, box))
        except (TypeError, ValueError, IndexError, KeyError):
            continue
    return tuple(out)


def _is_wall_row(row: Mapping[str, Any]) -> bool:
    layer = "".join(ch for ch in str(row.get("layer") or "").lower() if ch.isalnum())
    if any(tok in layer for tok in ("dim", "anno", "title", "grid", "hatch", "furniture")):
        return False
    return "wall" in layer


def _strip_thickness(row: Mapping[str, Any]) -> float | None:
    rect = row.get("rect")
    if rect is None:
        return None
    try:
        x0, y0, x1, y1 = (float(v) for v in rect[:4])
    except (TypeError, ValueError, IndexError):
        return None
    if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
        return None
    return min(abs(x1 - x0), abs(y1 - y0))


def recover_finished_interior_face_candidates(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Any],
    *,
    room_labels: Sequence[str],
    min_thickness_pt: float = 1.5,
) -> tuple[FinishedInteriorFaceCandidate, ...]:
    """Unique-or-abstain finished-face candidates for caller-supplied labels."""
    words = _word_rows(source_words)
    wall_rows = [
        (index, row)
        for index, row in enumerate(drawings)
        if isinstance(row, Mapping) and _is_wall_row(row)
    ]
    results: list[FinishedInteriorFaceCandidate] = []
    for label in room_labels:
        tokens = str(label).split()
        if not tokens:
            continue
        matches = []
        for i in range(len(words) - len(tokens) + 1):
            if all(tokens[k].upper() == words[i + k][0].upper() for k in range(len(tokens))):
                boxes = [words[i + k][1] for k in range(len(tokens))]
                matches.append(
                    (
                        min(b[0] for b in boxes),
                        min(b[1] for b in boxes),
                        max(b[2] for b in boxes),
                        max(b[3] for b in boxes),
                    )
                )
        if len(matches) != 1:
            results.append(
                FinishedInteriorFaceCandidate(
                    room_label=str(label),
                    label_bbox_pdf_pts=(0.0, 0.0, 0.0, 0.0),
                    support_path_ids=(),
                    thickness_pt=None,
                    status="ABSTAINED",
                    reason=(
                        "room_label_not_unique_on_page"
                        if matches
                        else "room_label_missing_on_page"
                    ),
                )
            )
            continue
        bbox = matches[0]
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0
        supports: list[tuple[float, int, float]] = []
        for index, row in wall_rows:
            thickness = _strip_thickness(row)
            if thickness is None or thickness <= 0.0:
                continue
            rect = row.get("rect")
            x0, y0, x1, y1 = (float(v) for v in rect[:4])
            # Distance from label centre to strip AABB.
            dx = max(x0 - cx, 0.0, cx - x1)
            dy = max(y0 - cy, 0.0, cy - y1)
            dist = math.hypot(dx, dy)
            supports.append((dist, index, thickness))
        supports.sort()
        if len(supports) < 2:
            results.append(
                FinishedInteriorFaceCandidate(
                    room_label=str(label),
                    label_bbox_pdf_pts=bbox,
                    support_path_ids=tuple(i for _d, i, _t in supports),
                    thickness_pt=None,
                    status="ABSTAINED",
                    reason="insufficient_mitred_or_parallel_wall_supports",
                )
            )
            continue
        # False-wall veto: paper-thin decoration strips are not lined faces.
        (_d0, id0, t0), (_d1, id1, t1) = supports[0], supports[1]
        if min(t0, t1) <= NOISE_PT or min(t0, t1) < float(min_thickness_pt):
            results.append(
                FinishedInteriorFaceCandidate(
                    room_label=str(label),
                    label_bbox_pdf_pts=bbox,
                    support_path_ids=(id0, id1),
                    thickness_pt=min(t0, t1),
                    status="ABSTAINED",
                    reason="false_wall_thickness_veto",
                )
            )
            continue
        results.append(
            FinishedInteriorFaceCandidate(
                room_label=str(label),
                label_bbox_pdf_pts=bbox,
                support_path_ids=(id0, id1),
                thickness_pt=round(min(t0, t1), 4),
                status="CANDIDATE",
                reason="finished_interior_face_needs_build_up_statement",
            )
        )
    return tuple(results)
