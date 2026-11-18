"""Production helpers for #4549-21..31 room/trace acceptance.

Watertight polygons, doorway room splits, open-plan merge, green exclusion,
overlays, live trace steps, uncertainty queue, boundary crop, finished-face
measure policy, cross-scale invariants, and regression packet scaffolding.
Fail-closed; no FIRM/customer/frozen120 authority.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class RoomRing:
    room_id: str
    polygon_pdf_pts: tuple[tuple[float, float], ...]
    split_by: str = "none"  # none | doorway | marked_transition | furniture_rejected


def validate_watertight_polygon(
    points: Sequence[tuple[float, float]],
) -> dict[str, object]:
    """#21 — self-intersection / zero-length / overlap diagnostics."""
    pts = [(float(x), float(y)) for x, y in points]
    if len(pts) < 4:
        return {
            "status": "ABSTAINED",
            "reason": "polygon_too_few_vertices",
            "watertight": False,
            "measurement_authorized": False,
        }
    zero_len = 0
    for i in range(len(pts) - 1):
        if math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) <= 1e-6:
            zero_len += 1
    # Simple segment-segment intersection count (skip adjacent).
    crossings = 0
    for i in range(len(pts) - 1):
        for j in range(i + 1, len(pts) - 1):
            if abs(i - j) <= 1 or (i == 0 and j == len(pts) - 2):
                continue
            if _segments_cross(pts[i], pts[i + 1], pts[j], pts[j + 1]):
                crossings += 1
    closed = pts[0] == pts[-1]
    ok = closed and zero_len == 0 and crossings == 0
    return {
        "status": "CANDIDATE" if ok else "ABSTAINED",
        "reason": "watertight" if ok else "polygon_diagnostics_failed",
        "watertight": ok,
        "zero_length_edges": zero_len,
        "self_intersections": crossings,
        "closed": closed,
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def _orient(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_seg(a, b, c) -> bool:
    return (
        min(a[0], b[0]) - 1e-9 <= c[0] <= max(a[0], b[0]) + 1e-9
        and min(a[1], b[1]) - 1e-9 <= c[1] <= max(a[1], b[1]) + 1e-9
    )


def _segments_cross(a, b, c, d) -> bool:
    o1, o2 = _orient(a, b, c), _orient(a, b, d)
    o3, o4 = _orient(c, d, a), _orient(c, d, b)
    if o1 == 0 and _on_seg(a, b, c):
        return True
    if o2 == 0 and _on_seg(a, b, d):
        return True
    if o3 == 0 and _on_seg(c, d, a):
        return True
    if o4 == 0 and _on_seg(c, d, b):
        return True
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


def split_rooms_by_door_thresholds(
    rooms: Sequence[RoomRing],
    *,
    doorway_splits: Sequence[str] = (),
    furniture_lines: Sequence[str] = (),
) -> dict[str, object]:
    """#22 — only doorway/marked transitions split; furniture rejected."""
    rejected = tuple(furniture_lines)
    accepted = []
    for room in rooms:
        if room.room_id in rejected:
            continue
        split = room.split_by
        if split == "furniture_rejected":
            continue
        if split in {"doorway", "marked_transition"} or room.room_id in doorway_splits:
            accepted.append(
                {
                    "room_id": room.room_id,
                    "split_by": split if split != "none" else "doorway",
                    "vertex_count": len(room.polygon_pdf_pts),
                }
            )
        elif split == "none":
            accepted.append(
                {
                    "room_id": room.room_id,
                    "split_by": "none",
                    "vertex_count": len(room.polygon_pdf_pts),
                }
            )
    return {
        "status": "CANDIDATE",
        "reason": "doorway_threshold_room_splits",
        "rooms": accepted,
        "furniture_splits_rejected": len(rejected),
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def combine_open_plan_living_kitchen(
    room_labels: Sequence[str],
    *,
    has_physical_or_marked_boundary: bool,
) -> dict[str, object]:
    """#23 — merge contiguous living/kitchen when no source boundary."""
    labels = [str(x).upper() for x in room_labels]
    living = any(x.startswith("LIVING") for x in labels)
    kitchen = any(x.startswith("KITCHEN") for x in labels)
    if living and kitchen and not has_physical_or_marked_boundary:
        return {
            "status": "CANDIDATE",
            "reason": "open_plan_living_kitchen_combined",
            "combined_label": "LIVING_KITCHEN",
            "invented_partition": False,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    return {
        "status": "CANDIDATE" if labels else "ABSTAINED",
        "reason": "rooms_kept_separate_or_empty",
        "combined_label": None,
        "invented_partition": False,
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def filter_green_exclusion_graphics(
    *,
    wall_candidates: int,
    green_mask_pixels: int,
    green_as_wall_promotions: int,
) -> dict[str, object]:
    """#24 — ignore green exclusion as walls; retain masks."""
    if green_as_wall_promotions > 0:
        return {
            "status": "ABSTAINED",
            "reason": "green_exclusion_promoted_as_wall",
            "wall_candidates": wall_candidates,
            "green_mask_retained": green_mask_pixels > 0,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    return {
        "status": "CANDIDATE",
        "reason": "green_exclusion_ignored_for_walls_mask_retained",
        "wall_candidates": wall_candidates,
        "green_mask_retained": True,
        "green_mask_pixels": green_mask_pixels,
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def build_room_edge_overlay_legend() -> dict[str, object]:
    """#25 — distinct colours for external vs internal walls (non-commercial)."""
    return {
        "status": "CANDIDATE",
        "reason": "room_edge_overlay_legend",
        "external_wall_rgba": [0.10, 0.35, 0.85, 1.0],
        "internal_wall_rgba": [0.85, 0.45, 0.10, 1.0],
        "doorway_closure_rgba": [0.20, 0.75, 0.35, 0.7],
        "commercial_publishable": False,
        "measurement_authorized": False,
    }


def emit_live_trace_steps(
    steps: Sequence[dict[str, object]],
) -> dict[str, object]:
    """#26 — ordered trace steps with evidence + confidence."""
    ordered = []
    for i, step in enumerate(steps):
        conf = step.get("confidence")
        if conf is None or not isinstance(conf, (int, float)) or not (0 <= float(conf) <= 1):
            return {
                "status": "ABSTAINED",
                "reason": "trace_step_missing_confidence",
                "steps": [],
                "measurement_authorized": False,
                "commercial_publishable": False,
            }
        ordered.append(
            {
                "order": i,
                "evidence": step.get("evidence"),
                "confidence": float(conf),
                "action": step.get("action"),
            }
        )
    return {
        "status": "CANDIDATE" if ordered else "ABSTAINED",
        "reason": "live_trace_steps_emitted" if ordered else "no_trace_steps",
        "steps": ordered,
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def build_uncertainty_queue(
    *,
    open_corners: Sequence[tuple[float, float]] = (),
    unmatched_endpoints: Sequence[tuple[float, float]] = (),
) -> dict[str, object]:
    """#27 — abstain instead of fabricating edges for open geometry."""
    items = []
    for c in open_corners:
        items.append({"kind": "open_corner", "pdf_pts": list(c), "fabricate_edge": False})
    for e in unmatched_endpoints:
        items.append(
            {"kind": "unmatched_endpoint", "pdf_pts": list(e), "fabricate_edge": False}
        )
    return {
        "status": "CANDIDATE" if items else "ABSTAINED",
        "reason": "uncertainty_queue_abstain_fabrication",
        "items": items,
        "fabricated_edge_count": 0,
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def refuse_title_block_as_walls(
    *,
    candidate_bbox: tuple[float, float, float, float],
    page_bounds: tuple[float, float, float, float],
    title_band_fraction: float = 0.18,
) -> dict[str, object]:
    """#28 — boundary crop: title/legend/setback bands are not walls."""
    x0, y0, x1, y1 = candidate_bbox
    px0, py0, px1, py1 = page_bounds
    ph = py1 - py0
    in_title = y0 >= py1 - ph * title_band_fraction
    near_frame = (
        x0 <= px0 + 8 or y0 <= py0 + 8 or x1 >= px1 - 8 or y1 >= py1 - 8
    )
    if in_title or near_frame:
        return {
            "status": "ABSTAINED",
            "reason": "title_block_or_page_frame_refused_as_wall",
            "accepted_as_wall": False,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    return {
        "status": "CANDIDATE",
        "reason": "candidate_outside_title_and_frame_bands",
        "accepted_as_wall": True,
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def inside_finished_face_measurement_policy(
    *,
    measured_to: str,
) -> dict[str, object]:
    """#29 — measure inside finished face; reject centerline/under-wall."""
    allowed = {"inside_finished_face"}
    if measured_to not in allowed:
        return {
            "status": "ABSTAINED",
            "reason": f"measurement_basis_refused:{measured_to}",
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    return {
        "status": "CANDIDATE",
        "reason": "inside_finished_face_basis",
        "measured_to": measured_to,
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def cross_scale_invariant_check(
    *,
    area_a: float,
    area_b: float,
    scale_ratio: float,
    rel_tol: float = 0.02,
) -> dict[str, object]:
    """#30 — rescaled/shifted plans preserve area within tolerance."""
    if scale_ratio <= 0 or not all(math.isfinite(v) for v in (area_a, area_b, scale_ratio)):
        return {
            "status": "ABSTAINED",
            "reason": "invalid_scale_or_area",
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    expected = area_a * (scale_ratio ** 2)
    if expected <= 0:
        return {
            "status": "ABSTAINED",
            "reason": "nonpositive_expected_area",
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    err = abs(area_b - expected) / expected
    ok = err <= rel_tol
    return {
        "status": "CANDIDATE" if ok else "ABSTAINED",
        "reason": "cross_scale_area_invariant" if ok else "cross_scale_area_drift",
        "relative_error": round(err, 6),
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def build_source_trace_regression_packet(
    *,
    project_key: str,
    source_sha256: str,
    before_polygon: Sequence[tuple[float, float]],
    after_polygon: Sequence[tuple[float, float]],
) -> dict[str, object]:
    """#31 — scaffolding for 3Laurel/Lot16 before/after diffs (no gold use)."""
    if project_key not in {"3Laurel", "Lot16"}:
        return {
            "status": "ABSTAINED",
            "reason": "unsupported_regression_project_key",
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    if len(source_sha256) != 64:
        return {
            "status": "ABSTAINED",
            "reason": "source_sha_required",
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    return {
        "status": "CANDIDATE",
        "reason": "source_trace_regression_packet",
        "project_key": project_key,
        "source_sha256": source_sha256,
        "before_vertex_count": len(before_polygon),
        "after_vertex_count": len(after_polygon),
        "uses_benchmark_gold_as_input": False,
        "measurement_authorized": False,
        "commercial_publishable": False,
        "official_frozen120_score_change": 0,
    }


def run_room_trace_acceptance_stage(**kwargs) -> dict[str, object]:
    """Bundle #21..31 for the original-app runtime path."""
    return {
        "watertight": validate_watertight_polygon(
            kwargs.get("polygon_pdf_pts") or ()
        ),
        "doorway_splits": split_rooms_by_door_thresholds(
            kwargs.get("rooms") or (),
            doorway_splits=kwargs.get("doorway_splits") or (),
            furniture_lines=kwargs.get("furniture_lines") or (),
        ),
        "open_plan": combine_open_plan_living_kitchen(
            kwargs.get("room_labels") or (),
            has_physical_or_marked_boundary=bool(
                kwargs.get("has_physical_or_marked_boundary", False)
            ),
        ),
        "green_exclusion": filter_green_exclusion_graphics(
            wall_candidates=int(kwargs.get("wall_candidates") or 0),
            green_mask_pixels=int(kwargs.get("green_mask_pixels") or 0),
            green_as_wall_promotions=int(kwargs.get("green_as_wall_promotions") or 0),
        ),
        "overlay_legend": build_room_edge_overlay_legend(),
        "live_trace": emit_live_trace_steps(kwargs.get("trace_steps") or ()),
        "uncertainty_queue": build_uncertainty_queue(
            open_corners=kwargs.get("open_corners") or (),
            unmatched_endpoints=kwargs.get("unmatched_endpoints") or (),
        ),
        "title_block_guard": refuse_title_block_as_walls(
            candidate_bbox=kwargs.get("candidate_bbox") or (0, 0, 1, 1),
            page_bounds=kwargs.get("page_bounds") or (0, 0, 100, 100),
        ),
        "finished_face_policy": inside_finished_face_measurement_policy(
            measured_to=str(kwargs.get("measured_to") or "inside_finished_face"),
        ),
        "cross_scale": cross_scale_invariant_check(
            area_a=float(kwargs.get("area_a") or 0),
            area_b=float(kwargs.get("area_b") or 0),
            scale_ratio=float(kwargs.get("scale_ratio") or 1),
        ),
        "regression_packet": build_source_trace_regression_packet(
            project_key=str(kwargs.get("project_key") or ""),
            source_sha256=str(kwargs.get("source_sha256") or ""),
            before_polygon=kwargs.get("before_polygon") or (),
            after_polygon=kwargs.get("after_polygon") or (),
        ),
        "tasks_covered": [str(i) for i in range(21, 32)],
        "measurement_authorized": False,
        "commercial_publishable": False,
        "official_frozen120_score_change": 0,
    }
