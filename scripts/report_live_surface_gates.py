"""Read-only, fail-closed room surface stage diagnostics."""

from __future__ import annotations


def first_observed_surface_gate(room, floors):
    """Return a conservative diagnostic; never derive metric area from page points."""
    if not room.geometry_complete:
        return "source_room_geometry_incomplete"
    matches = tuple(f for f in floors if f.source_room_face_record_id == room.source_room_face_record_id)
    if len(matches) != 1:
        return "canonical_floor_identity_unavailable_or_ambiguous"
    floor = matches[0]
    if floor.metric_area_m2 is None or not floor.metric_area_quantity_id or not floor.metric_area_authority:
        return "metric_floor_area_authority_unavailable"
    return "metric_floor_area_producer_present_not_yet_sealing_verified"
