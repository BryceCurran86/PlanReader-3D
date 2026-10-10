"""Read-only native word-to-source-face candidate audit.

Native PDF text, native word centres, and even single-face containment are
NOT authenticated SourceRoomLabelAuthority evidence. No label, room, scale,
measurement, or quantity may be published by this diagnostic.
"""
from __future__ import annotations

import math
from typing import Iterable


def _valid_bbox(value):
    try:
        x0, y0, x1, y1 = (float(v) for v in value)
    except (TypeError, ValueError):
        return None
    if not all(map(math.isfinite, (x0, y0, x1, y1))):
        return None
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def _inside(point, polygon):
    """Point in or on a source polygon; does not authenticate the point."""
    x, y = point
    try:
        pts = tuple((float(p[0]), float(p[1])) for p in polygon)
    except (TypeError, ValueError, IndexError):
        return False
    if len(pts) < 3 or not all(math.isfinite(v) for p in pts for v in p):
        return False
    inside = False
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        if length and abs((x - ax) * dy - (y - ay) * dx) / length <= 1e-6:
            if min(ax, bx) - 1e-6 <= x <= max(ax, bx) + 1e-6 and min(ay, by) - 1e-6 <= y <= max(ay, by) + 1e-6:
                return True
        if (ay > y) != (by > y):
            cross = ax + (y - ay) * dx / dy
            if cross > x:
                inside = not inside
    return inside


def inspect_native_word_face_membership(word_bboxes: Iterable[Iterable[float]], source_faces: Iterable[object]) -> dict:
    """Return spatial *candidate* first gate; no producer authority is minted.

    source_faces are already producer-owned physical SourceRoomFaceRecords,
    but native words are untrusted. Face IDs are reported for diagnosis only.
    """
    words = tuple(_valid_bbox(b) for b in word_bboxes)
    if not words or any(b is None for b in words):
        return {"first_gate": "native_word_geometry_unavailable", "candidate_face_ids": [],
                "per_word_containing_face_counts": [], "source_label_authenticated": False,
                "metric_area_authenticated": False}
    memberships = []
    for box in words:
        center = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        hits = set()
        for face in source_faces:
            face_id = getattr(face, "record_id", None)
            if not isinstance(face_id, str) or not face_id:
                continue
            if _inside(center, getattr(face, "polygon_pdf_pts", ())):
                hits.add(face_id)
        memberships.append(hits)
    shared = set.intersection(*memberships)
    if any(not ids for ids in memberships):
        gate = "native_word_center_outside_source_face_universe"
    elif len(shared) == 1 and all(len(ids) == 1 for ids in memberships):
        gate = "unique_native_word_source_face_candidate_only"
    elif len(shared) > 1 or any(len(ids) > 1 for ids in memberships):
        gate = "native_word_competing_source_face_candidates"
    elif not shared:
        gate = "native_words_split_across_source_faces"
    else:
        gate = "native_word_source_face_ownership_unresolved"
    return {"first_gate": gate,
            "candidate_face_ids": sorted(shared),
            "per_word_containing_face_counts": [len(ids) for ids in memberships],
            "source_label_authenticated": False,
            "metric_area_authenticated": False}
