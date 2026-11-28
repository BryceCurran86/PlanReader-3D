"""Which single inside-face ring holds each room label, with its wall support (report only; CL-R07).

Takes ring candidates already combined without choosing
(pb_room_ring_candidate_union_shadow) and label positions from the source. A
label is assigned only when exactly one candidate ring contains it and that ring
holds no other label; otherwise it abstains, naming why. The wall support
summary is the finish-face check's, panel candidates reported but never counted.
No area, measurement, room, finish or quantity authority; nothing imports it.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from shapely.geometry import Point, Polygon

from pb_finish_face_wall_support_shadow import face_wall_support
from pb_migration_contracts import EvidenceResolutionStatus

REASON_ONE_RING = "one_ring_holds_the_label"
REASON_NO_RING = "no_ring_holds_the_label"
REASON_SEVERAL_RINGS = "several_rings_hold_the_label"
REASON_SHARED_RING = "ring_holds_several_labels"


def labelled_ring_ownership(
    labels: Mapping[str, Sequence[float]],
    union_entries: Sequence[Mapping[str, Any]],
    drawings: Sequence[Any],
) -> dict[str, dict[str, Any]]:
    """One typed record per label id; ``labels`` are (x, y) points in the drawings' page frame."""
    candidates = [entry for entry in union_entries if entry.get("status") is EvidenceResolutionStatus.CANDIDATE]
    shapes = [Polygon(entry["polygon_pdf_pts"]) for entry in candidates]
    holders = {label: [i for i, shape in enumerate(shapes) if shape.contains(Point(*point))]
               for label, point in sorted(labels.items())}
    crowd: dict[int, int] = {}
    for found in holders.values():
        if len(found) == 1:
            crowd[found[0]] = crowd.get(found[0], 0) + 1
    result = {}
    for label, found in holders.items():
        if not found:
            reason = REASON_NO_RING
        elif len(found) > 1:
            reason = REASON_SEVERAL_RINGS
        elif crowd[found[0]] > 1:
            reason = REASON_SHARED_RING
        else:
            reason = REASON_ONE_RING
        record: dict[str, Any] = {
            "status": EvidenceResolutionStatus.CANDIDATE if reason == REASON_ONE_RING else EvidenceResolutionStatus.ABSTAINED,
            "reason": reason, "record_ids": {}, "runs": (), "wall_support": None,
            "measurement_authority": False,
        }
        if reason == REASON_ONE_RING:
            entry = candidates[found[0]]
            support = face_wall_support(list(entry["polygon_pdf_pts"]), drawings)
            record.update(
                record_ids=dict(entry.get("record_ids") or {}), runs=tuple(entry.get("runs") or ()),
                polygon_pdf_pts=tuple(entry["polygon_pdf_pts"]),
                wall_support={key: support.get(key) for key in
                              ("reason", "unsupported_share", "wide_candidate_share", "panel_candidate_share")},
            )
        result[label] = record
    return result
