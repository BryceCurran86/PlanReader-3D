"""Production geometry helpers for #4549-11..15 (posts, stubs, T-junctions).

Wired from the inside-face footprint runtime and junction review path.
Fail-closed: never fabricates walls, FIRM quantities, or customer rows.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class GeometryPrimitive:
    primitive_id: int
    start_pdf_pts: tuple[float, float]
    end_pdf_pts: tuple[float, float]
    kind: str = "wall"  # wall | door | post | rail_shadow
    label: str = ""
    stroke_weight_pt: float = 1.0


def _len(p: GeometryPrimitive) -> float:
    return math.hypot(
        p.end_pdf_pts[0] - p.start_pdf_pts[0],
        p.end_pdf_pts[1] - p.start_pdf_pts[1],
    )


def _unit(dx: float, dy: float) -> tuple[float, float] | None:
    h = math.hypot(dx, dy)
    if h <= 1e-9:
        return None
    return dx / h, dy / h


def classify_door_versus_timber_post(
    primitive: GeometryPrimitive,
    *,
    nearby: Sequence[GeometryPrimitive] = (),
) -> dict[str, object]:
    """#11 — refuse freestanding timber posts as walls; retain door objects."""
    label = "".join(ch for ch in primitive.label.upper() if ch.isalnum())
    span = _len(primitive)
    if primitive.kind == "post" or "POST" in label or "140X140" in label:
        return {
            "primitive_id": primitive.primitive_id,
            "role": "timber_post_not_wall",
            "promote_to_wall": False,
            "reason": "source_noted_or_kind_post",
            "measurement_authorized": False,
        }
    if primitive.kind == "door" or label.startswith("D") and label[1:].isdigit():
        return {
            "primitive_id": primitive.primitive_id,
            "role": "door_object",
            "promote_to_wall": False,
            "reason": "door_symbol_retained_as_opening",
            "measurement_authorized": False,
        }
    # Compact isolated stroke without aligned wall neighbors → post-like.
    if span <= 8.0 and primitive.stroke_weight_pt >= 1.5:
        touches = False
        for other in nearby:
            if other.primitive_id == primitive.primitive_id:
                continue
            for tip in (primitive.start_pdf_pts, primitive.end_pdf_pts):
                for ot in (other.start_pdf_pts, other.end_pdf_pts):
                    if math.hypot(tip[0] - ot[0], tip[1] - ot[1]) <= 5.0:
                        touches = True
                        break
        if not touches:
            return {
                "primitive_id": primitive.primitive_id,
                "role": "timber_post_not_wall",
                "promote_to_wall": False,
                "reason": "isolated_compact_stroke_post_like",
                "measurement_authorized": False,
            }
    return {
        "primitive_id": primitive.primitive_id,
        "role": "wall_candidate",
        "promote_to_wall": True,
        "reason": "aligned_or_elongated_wall_stroke",
        "measurement_authorized": False,
    }


def reconstruct_short_wall_stubs(
    primitives: Sequence[GeometryPrimitive],
    *,
    max_gap_pt: float = 4.0,
) -> dict[str, object]:
    """#12 — bridge short gaps only when endpoints align and joins are unique."""
    walls = [
        p for p in primitives
        if classify_door_versus_timber_post(p, nearby=primitives)["promote_to_wall"]
    ]
    proposals: list[dict[str, object]] = []
    for i, a in enumerate(walls):
        for b in walls[i + 1 :]:
            pairs = (
                (a.end_pdf_pts, b.start_pdf_pts, a, b),
                (a.end_pdf_pts, b.end_pdf_pts, a, b),
                (a.start_pdf_pts, b.start_pdf_pts, a, b),
                (a.start_pdf_pts, b.end_pdf_pts, a, b),
            )
            for tip_a, tip_b, left, right in pairs:
                gap = math.hypot(tip_a[0] - tip_b[0], tip_a[1] - tip_b[1])
                if gap <= 0.05 or gap > max_gap_pt:
                    continue
                ua = _unit(
                    left.end_pdf_pts[0] - left.start_pdf_pts[0],
                    left.end_pdf_pts[1] - left.start_pdf_pts[1],
                )
                ub = _unit(
                    right.end_pdf_pts[0] - right.start_pdf_pts[0],
                    right.end_pdf_pts[1] - right.start_pdf_pts[1],
                )
                if ua is None or ub is None:
                    continue
                # Collinear continuation or unique perpendicular stub join.
                collinear = abs(ua[0] * ub[1] - ua[1] * ub[0]) <= 0.08 and (
                    ua[0] * ub[0] + ua[1] * ub[1]
                ) > 0.9
                perpendicular = abs(ua[0] * ub[0] + ua[1] * ub[1]) <= 0.12
                if not (collinear or perpendicular):
                    continue
                proposals.append(
                    {
                        "left_id": left.primitive_id,
                        "right_id": right.primitive_id,
                        "gap_pt": round(gap, 4),
                        "join": "collinear" if collinear else "perpendicular",
                        "physical_wall_authenticated": False,
                    }
                )
    # Ambiguous multi-join on the same tip abstains that tip.
    tip_use: dict[tuple[int, int], int] = {}
    for p in proposals:
        key = (int(p["left_id"]), int(p["right_id"]))
        tip_use[key] = tip_use.get(key, 0) + 1
    accepted = [p for p in proposals if tip_use[(int(p["left_id"]), int(p["right_id"]))] == 1]
    return {
        "status": "CANDIDATE" if accepted else "ABSTAINED",
        "reason": (
            "unique_aligned_stub_joins"
            if accepted
            else "no_unique_short_stub_reconstruction"
        ),
        "stub_joins": accepted,
        "ambiguous_refused": len(proposals) - len(accepted),
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def detect_t_junctions(
    primitives: Sequence[GeometryPrimitive],
    *,
    snap_pt: float = 2.5,
) -> dict[str, object]:
    """#13 — T-junctions split stems without phantom extensions past the crossbar."""
    walls = [
        p for p in primitives
        if classify_door_versus_timber_post(p, nearby=primitives)["promote_to_wall"]
    ]
    junctions: list[dict[str, object]] = []
    for stem in walls:
        su = _unit(
            stem.end_pdf_pts[0] - stem.start_pdf_pts[0],
            stem.end_pdf_pts[1] - stem.start_pdf_pts[1],
        )
        if su is None:
            continue
        for tip_name, tip in (("start", stem.start_pdf_pts), ("end", stem.end_pdf_pts)):
            hits = []
            for bar in walls:
                if bar.primitive_id == stem.primitive_id:
                    continue
                bu = _unit(
                    bar.end_pdf_pts[0] - bar.start_pdf_pts[0],
                    bar.end_pdf_pts[1] - bar.start_pdf_pts[1],
                )
                if bu is None:
                    continue
                # Tip must land on the bar interior, not beyond endpoints.
                ax, ay = bar.start_pdf_pts
                bx, by = tip
                cx, cy = bar.end_pdf_pts
                ab = (cx - ax, cy - ay)
                ap = (bx - ax, by - ay)
                ab2 = ab[0] * ab[0] + ab[1] * ab[1]
                if ab2 <= 1e-9:
                    continue
                t = (ap[0] * ab[0] + ap[1] * ab[1]) / ab2
                if t <= 0.05 or t >= 0.95:
                    continue
                proj = (ax + t * ab[0], ay + t * ab[1])
                if math.hypot(proj[0] - tip[0], proj[1] - tip[1]) > snap_pt:
                    continue
                if abs(su[0] * bu[0] + su[1] * bu[1]) > 0.25:
                    continue  # not a T (need ~perpendicular)
                hits.append((bar.primitive_id, round(t, 4)))
            if len(hits) == 1:
                junctions.append(
                    {
                        "stem_id": stem.primitive_id,
                        "tip": tip_name,
                        "crossbar_id": hits[0][0],
                        "crossbar_param": hits[0][1],
                        "phantom_extension": False,
                        "physical_wall_authenticated": False,
                    }
                )
            elif len(hits) > 1:
                junctions.append(
                    {
                        "stem_id": stem.primitive_id,
                        "tip": tip_name,
                        "status": "ABSTAINED",
                        "reason": "ambiguous_t_junction_hosts",
                        "phantom_extension": False,
                    }
                )
    accepted = [j for j in junctions if j.get("status") != "ABSTAINED"]
    return {
        "status": "CANDIDATE" if accepted else "ABSTAINED",
        "reason": "t_junctions_without_phantom_extension" if accepted else "no_t_junction",
        "junctions": junctions,
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def suppress_rail_shadow_corners(
    primitives: Sequence[GeometryPrimitive],
    *,
    corner_candidates: Sequence[tuple[float, float]],
    rail_weight_max_pt: float = 0.45,
) -> dict[str, object]:
    """#14 — hairline rail shadows cannot promote outer corners."""
    kept: list[tuple[float, float]] = []
    suppressed = 0
    rails = [
        p for p in primitives
        if p.kind == "rail_shadow" or p.stroke_weight_pt <= rail_weight_max_pt
    ]
    for corner in corner_candidates:
        hit_rail = False
        for rail in rails:
            for tip in (rail.start_pdf_pts, rail.end_pdf_pts):
                if math.hypot(corner[0] - tip[0], corner[1] - tip[1]) <= 2.0:
                    hit_rail = True
                    break
            if hit_rail:
                break
        if hit_rail:
            suppressed += 1
        else:
            kept.append(corner)
    return {
        "status": "CANDIDATE",
        "reason": "rail_shadow_corners_suppressed",
        "kept_corners": [list(c) for c in kept],
        "suppressed_count": suppressed,
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def align_cross_page_footprint_scale(
    *,
    cover_anchor_pdf_pts: Sequence[tuple[float, float]] = (),
    plan_anchor_pdf_pts: Sequence[tuple[float, float]] = (),
    cover_page_index: int = -1,
    plan_page_index: int = -1,
) -> dict[str, object]:
    """#15 — scale only from paired trustworthy anchors; else abstain."""
    if cover_page_index < 0 or plan_page_index < 0:
        return {
            "status": "ABSTAINED",
            "reason": "cross_page_indices_required",
            "scale_plan_per_cover": None,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    if len(cover_anchor_pdf_pts) < 2 or len(plan_anchor_pdf_pts) < 2:
        return {
            "status": "ABSTAINED",
            "reason": "insufficient_trustworthy_anchors",
            "scale_plan_per_cover": None,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    if len(cover_anchor_pdf_pts) != len(plan_anchor_pdf_pts):
        return {
            "status": "ABSTAINED",
            "reason": "anchor_cardinality_mismatch",
            "scale_plan_per_cover": None,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    scales: list[float] = []
    for i in range(len(cover_anchor_pdf_pts) - 1):
        c0, c1 = cover_anchor_pdf_pts[i], cover_anchor_pdf_pts[i + 1]
        p0, p1 = plan_anchor_pdf_pts[i], plan_anchor_pdf_pts[i + 1]
        cd = math.hypot(c1[0] - c0[0], c1[1] - c0[1])
        pd = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if cd <= 1e-6 or pd <= 1e-6:
            return {
                "status": "ABSTAINED",
                "reason": "zero_length_anchor_span",
                "scale_plan_per_cover": None,
                "measurement_authorized": False,
                "commercial_publishable": False,
            }
        scales.append(pd / cd)
    if max(scales) - min(scales) > 0.02 * max(scales):
        return {
            "status": "ABSTAINED",
            "reason": "conflicting_anchor_scales",
            "scale_plan_per_cover": None,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    scale = sum(scales) / len(scales)
    return {
        "status": "CANDIDATE",
        "reason": "cross_page_scale_from_paired_anchors",
        "scale_plan_per_cover": round(scale, 8),
        "cover_page_index": cover_page_index,
        "plan_page_index": plan_page_index,
        "measurement_authorized": False,
        "commercial_publishable": False,
        "official_frozen120_score_change": 0,
    }


def run_wall_stub_junction_geometry_stage(
    primitives: Sequence[GeometryPrimitive],
    *,
    corner_candidates: Sequence[tuple[float, float]] = (),
    cover_anchor_pdf_pts: Sequence[tuple[float, float]] = (),
    plan_anchor_pdf_pts: Sequence[tuple[float, float]] = (),
    cover_page_index: int = -1,
    plan_page_index: int = -1,
) -> dict[str, object]:
    """Bundle #11..15 receipts for the original-app runtime path."""
    post_door = [
        classify_door_versus_timber_post(p, nearby=primitives) for p in primitives
    ]
    return {
        "door_versus_post": post_door,
        "short_wall_stubs": reconstruct_short_wall_stubs(primitives),
        "t_junctions": detect_t_junctions(primitives),
        "rail_shadow_corners": suppress_rail_shadow_corners(
            primitives, corner_candidates=corner_candidates,
        ),
        "cross_page_scale": align_cross_page_footprint_scale(
            cover_anchor_pdf_pts=cover_anchor_pdf_pts,
            plan_anchor_pdf_pts=plan_anchor_pdf_pts,
            cover_page_index=cover_page_index,
            plan_page_index=plan_page_index,
        ),
        "tasks_covered": ["11", "12", "13", "14", "15"],
        "measurement_authorized": False,
        "commercial_publishable": False,
        "official_frozen120_score_change": 0,
    }
