"""Generic, fail-closed detection of internal partition walls drawn as solid
filled bands or vector wall-line pairs (some native-CAD drawings render wall
thickness as a solid fill, while others draw parallel stroke lines with
diagonal masonry hatching).

Answers a narrow question: does this floor plan's own vector geometry show
a genuine internal partition wall (as opposed to furniture/desk outlines,
which are stroke-only in this drawing convention, or a symbol/annotation),
and if so, what is its real length?

This module never invents the building envelope or wall thickness. It
derives both from the drawing's own geometry:
  - wall thickness is the dominant (modal, low-variance) thickness
    among wall-like elements within the floor-plan viewport -- most
    walls on one drawing share a thickness, so this is a self-consistent,
    data-driven estimate, not a guessed constant;
  - the outer envelope is the combined bounding box of those same
    wall-like elements;
  - a wall-like element is classified "perimeter" (already counted elsewhere)
    when it lies on/near that envelope's own boundary, and "internal
    partition" only when it sits strictly inside it.

Consumers are responsible for deciding whether an internal partition's
length is relevant to their specific quantity (e.g. damp-proof course
scoped explicitly to "all walls" by the drawing's own notes) -- this module
only reports evidenced internal wall segments and their lengths.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple

from pb_wall_hatch_perimeter_correction import _floor_plan_viewport_bbox

# length_m/width_m (caller-supplied, already resolved by production from
# real drawing evidence) ARE the physical scale authority here -- not one
# side of a cross-validation. Scale is computed directly as
# scale_pt_per_m = pixel_major / real_major (the wall-fill bbox's longer
# pixel span divided by the longer of the two known real dimensions).
#
# Only the longer axis is used for this division. The shorter axis is not
# required to agree, for a real, structural reason: a wall drawn as a
# solid fill on one side of a building can legitimately stop well short of
# an open/differently-constructed opposite side (e.g. a verandah whose
# outer edge has no continuous wall fill at all), so the fill bbox's
# shorter axis often will NOT span the full corresponding real dimension.
# Requiring both axes to agree would abstain on exactly the buildings
# worth investigating.
#
# There is no independent fill-derived real-world scale being
# cross-validated against length_m/width_m. The wall-fill thickness check
# below is a SEPARATE, subsequent plausibility/fail-closed check applied
# AFTER scale is already fixed from length_m/width_m -- it asks only
# "does this already-authoritative scale imply a physically realistic
# wall thickness for the fills found," never re-derives or second-guesses
# the scale itself.
_PLAUSIBLE_WALL_THICKNESS_RANGE_M = (0.08, 0.35)

# A wall-like fill must be nearly black (this drawing's own wall-fill
# convention, confirmed against both an exterior wall and the internal
# partition on the same page) and thin-and-long -- excludes furniture/desk
# symbols (stroke-only, no fill, in this drawing) and roughly-square
# symbols (grid bubbles, fixture marks).
_MAX_FILL_RGB_FOR_BLACK = 0.15
_MIN_ASPECT_RATIO = 6.0
_MIN_LONG_SIDE_PT = 30.0

# Wall-thickness candidates (the short side of each wall-like fill) must
# cluster within this relative tolerance of their own median to be trusted
# as one consistent wall-thickness scale for this drawing.
_MAX_THICKNESS_RELATIVE_SPREAD = 0.25

# A wall-like fill counts as "on the perimeter" (already represented in the
# naive envelope, not a new internal partition) when it comes within this
# many multiples of the derived wall thickness of the envelope's own
# bounding edge.
_PERIMETER_PROXIMITY_THICKNESS_MULTIPLE = 2.0


@dataclass(frozen=True)
class InternalPartitionEvidence:
    status: str  # "found" | "abstained"
    reason: str
    total_length_m: float = 0.0
    wall_thickness_m: Optional[float] = None
    scale_pt_per_m: Optional[float] = None
    segment_lengths_m: Tuple[float, ...] = ()


def _is_wall_like_fill(d: dict, page_rect: Optional[Any] = None) -> bool:
    fill = d.get("fill")
    if not fill or any(c > _MAX_FILL_RGB_FOR_BLACK for c in fill[:3]):
        return False
    x0, y0, x1, y1 = d["rect"]
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return False
    if page_rect is not None:
        # A page border/title-block frame line is also thin, long, and
        # often solid-filled -- but unlike any real wall, it spans nearly
        # the entire sheet. Exclude by comparing against the page's own
        # actual size, not a fixed length threshold.
        if w >= 0.9 * page_rect.width or h >= 0.9 * page_rect.height:
            return False
    short, long_ = min(w, h), max(w, h)
    if long_ < _MIN_LONG_SIDE_PT:
        return False
    if short <= 0 or long_ / short < _MIN_ASPECT_RATIO:
        return False
    return True


def resolve_internal_partition_length_m(
    drawings: Sequence[dict],
    *,
    length_m: float,
    width_m: float,
    page: Optional[Any] = None,
) -> InternalPartitionEvidence:
    """Find genuine internal partition walls from solid-fill or vector wall-pair geometry.

    ``drawings`` must be the raw ``page.get_drawings()`` list. ``length_m``/
    ``width_m`` are whatever production has already resolved for the
    envelope from real drawing evidence -- they ARE the physical scale
    authority (scale_pt_per_m = pixel_major / real_major), never merely a
    cross-check against some other fill-derived scale. ``page`` (optional) scopes
    the search to the floor-plan viewport via a "...FLOOR PLAN" title label,
    the same mechanism used in pb_wall_hatch_perimeter_correction, to avoid picking
    up wall-like elements from an unrelated view on a multi-view sheet.
    """
    viewport_bbox = _floor_plan_viewport_bbox(page) if page is not None else None
    if viewport_bbox is None and page is not None:
        try:
            from pb_viewport_segmentation import segment_page_viewports

            pno = getattr(page, "number", 0) + 1
            for vp in segment_page_viewports(page, page_number=pno):
                if vp.view_type == "floor_plan" and vp.bounding_box:
                    viewport_bbox = tuple(vp.bounding_box)
                    break
        except Exception:
            pass

    page_rect = getattr(page, "rect", None) if page is not None else None

    # Step 1: Check for solid-fill walls strictly within viewport_bbox
    candidates = [d for d in drawings if _is_wall_like_fill(d, page_rect)]
    if viewport_bbox is not None:
        vx0, vy0, vx1, vy1 = viewport_bbox
        candidates = [
            d for d in candidates
            if vx0 <= (d["rect"][0] + d["rect"][2]) / 2.0 <= vx1
            and vy0 <= (d["rect"][1] + d["rect"][3]) / 2.0 <= vy1
        ]

    if len(candidates) >= 2:
        return _resolve_from_solid_fills(candidates, length_m=length_m, width_m=width_m)

    # Step 2: Check for vector wall pairs (stroke walls)
    return _resolve_from_wall_pairs(
        drawings,
        length_m=length_m,
        width_m=width_m,
        viewport_bbox=viewport_bbox,
        page_rect=page_rect,
        page=page,
    )


def _resolve_from_solid_fills(
    candidates: Sequence[dict],
    *,
    length_m: float,
    width_m: float,
) -> InternalPartitionEvidence:
    thicknesses = []
    for d in candidates:
        x0, y0, x1, y1 = d["rect"]
        thicknesses.append(min(x1 - x0, y1 - y0))
    median_thickness = statistics.median(thicknesses)
    consistent = [
        t for t in thicknesses
        if median_thickness > 0
        and abs(t - median_thickness) / median_thickness <= _MAX_THICKNESS_RELATIVE_SPREAD
    ]
    if len(consistent) < 2:
        return InternalPartitionEvidence(
            status="abstained",
            reason="wall-like fills do not share a consistent thickness scale",
        )
    wall_thickness_pt = statistics.median(consistent)

    min_x = min(d["rect"][0] for d in candidates)
    min_y = min(d["rect"][1] for d in candidates)
    max_x = max(d["rect"][2] for d in candidates)
    max_y = max(d["rect"][3] for d in candidates)
    bbox_w, bbox_h = max_x - min_x, max_y - min_y
    if bbox_w <= 0 or bbox_h <= 0:
        return InternalPartitionEvidence(status="abstained", reason="degenerate wall-fill bounding box")

    real_major = max(length_m, width_m)
    real_minor = min(length_m, width_m)
    pixel_major = max(bbox_w, bbox_h)
    pixel_minor = min(bbox_w, bbox_h)
    if real_major <= 0 or real_minor <= 0:
        return InternalPartitionEvidence(status="abstained", reason="non-positive envelope dimension")

    real_ratio = real_major / real_minor
    pixel_ratio = pixel_major / pixel_minor
    if abs(pixel_ratio - real_ratio) / real_ratio > 0.35:
        return InternalPartitionEvidence(
            status="abstained",
            reason=(
                f"pixel envelope aspect ratio ({pixel_ratio:.2f}) conflicts with "
                f"real envelope aspect ratio ({real_ratio:.2f}) -- wrong-axis scale inference rejected"
            ),
        )

    scale_pt_per_m = pixel_major / real_major
    implied_thickness_m = wall_thickness_pt / scale_pt_per_m
    lo, hi = _PLAUSIBLE_WALL_THICKNESS_RANGE_M
    if not (lo <= implied_thickness_m <= hi):
        return InternalPartitionEvidence(
            status="abstained",
            reason=(
                f"derived scale ({scale_pt_per_m:.2f}pt/m from the longer envelope "
                f"axis) implies an unrealistic wall thickness ({implied_thickness_m:.3f}m, "
                f"outside {lo}-{hi}m) -- not trusted"
            ),
        )

    margin = wall_thickness_pt * _PERIMETER_PROXIMITY_THICKNESS_MULTIPLE

    internal_lengths_pt: List[float] = []
    for d in candidates:
        x0, y0, x1, y1 = d["rect"]
        w, h = x1 - x0, y1 - y0
        long_ = max(w, h)
        if h >= w:
            on_perimeter = (x0 - min_x <= margin) or (max_x - x1 <= margin)
        else:
            on_perimeter = (y0 - min_y <= margin) or (max_y - y1 <= margin)
        if on_perimeter:
            continue
        internal_lengths_pt.append(long_)

    if not internal_lengths_pt:
        return InternalPartitionEvidence(
            status="abstained",
            reason="no wall-like fill sits strictly inside the derived envelope",
            wall_thickness_m=round(wall_thickness_pt / scale_pt_per_m, 4),
            scale_pt_per_m=scale_pt_per_m,
        )

    segment_lengths_m = tuple(round(length_pt / scale_pt_per_m, 3) for length_pt in internal_lengths_pt)
    return InternalPartitionEvidence(
        status="found",
        reason=(
            f"{len(segment_lengths_m)} internal partition segment(s) found, "
            f"total {sum(segment_lengths_m):.3f}m"
        ),
        wall_thickness_m=round(wall_thickness_pt / scale_pt_per_m, 4),
        scale_pt_per_m=scale_pt_per_m,
        total_length_m=round(sum(segment_lengths_m), 3),
        segment_lengths_m=segment_lengths_m,
    )


def _extract_stroke_lines(
    drawings: Sequence[dict],
    viewport_bbox: Optional[Tuple[float, float, float, float]],
    page_rect: Optional[Any],
) -> Tuple[List[Tuple[float, float, float, float]], List[Tuple[float, float, float, float]]]:
    """Extract horizontal and vertical stroke lines within the floor plan viewport."""
    h_lines: List[Tuple[float, float, float, float]] = []
    v_lines: List[Tuple[float, float, float, float]] = []
    vx0, vy0, vx1, vy1 = viewport_bbox if viewport_bbox else (-1e9, -1e9, 1e9, 1e9)
    max_w = 0.9 * page_rect.width if page_rect else 1e9
    max_h = 0.9 * page_rect.height if page_rect else 1e9

    for d in drawings:
        if d.get("fill"):
            continue
        rx0, ry0, rx1, ry1 = d["rect"]
        cx, cy = (rx0 + rx1) / 2.0, (ry0 + ry1) / 2.0
        if not (vx0 <= cx <= vx1 and vy0 <= cy <= vy1):
            continue
        for item in d.get("items", []):
            if item[0] == "l":
                p1, p2 = item[1], item[2]
                dx = abs(p2.x - p1.x)
                dy = abs(p2.y - p1.y)
                length = (dx * dx + dy * dy) ** 0.5
                if length < 12.0:
                    continue
                if dy < 0.2 and dx <= max_w:  # horizontal line
                    y = (p1.y + p2.y) / 2.0
                    x0, x1 = min(p1.x, p2.x), max(p1.x, p2.x)
                    h_lines.append((y, x0, x1, length))
                elif dx < 0.2 and dy <= max_h:  # vertical line
                    x = (p1.x + p2.x) / 2.0
                    y0, y1 = min(p1.y, p2.y), max(p1.y, p2.y)
                    v_lines.append((x, y0, y1, length))
    return h_lines, v_lines


def _find_wall_pairs(
    h_lines: List[Tuple[float, float, float, float]],
    v_lines: List[Tuple[float, float, float, float]],
) -> List[dict]:
    """Pair parallel lines separated by wall-thickness gap with significant overlap."""
    pairs: List[dict] = []
    # Vertical pairs (walls running vertically along y)
    for i, (x1, y1_0, y1_1, len1) in enumerate(v_lines):
        for j in range(i + 1, len(v_lines)):
            x2, y2_0, y2_1, len2 = v_lines[j]
            gap = abs(x2 - x1)
            if 4.0 <= gap <= 25.0:
                y_start = max(y1_0, y2_0)
                y_end = min(y1_1, y2_1)
                overlap = y_end - y_start
                if overlap >= 12.0:
                    pairs.append({
                        "orientation": "vertical",
                        "coord1": min(x1, x2),
                        "coord2": max(x1, x2),
                        "center": (x1 + x2) / 2.0,
                        "span_start": y_start,
                        "span_end": y_end,
                        "gap": gap,
                        "overlap": overlap,
                        "bbox": (min(x1, x2), y_start, max(x1, x2), y_end),
                    })

    # Horizontal pairs (walls running horizontally along x)
    for i, (y1, x1_0, x1_1, len1) in enumerate(h_lines):
        for j in range(i + 1, len(h_lines)):
            y2, x2_0, x2_1, len2 = h_lines[j]
            gap = abs(y2 - y1)
            if 4.0 <= gap <= 25.0:
                x_start = max(x1_0, x2_0)
                x_end = min(x1_1, x2_1)
                overlap = x_end - x_start
                if overlap >= 12.0:
                    pairs.append({
                        "orientation": "horizontal",
                        "coord1": min(y1, y2),
                        "coord2": max(y1, y2),
                        "center": (y1 + y2) / 2.0,
                        "span_start": x_start,
                        "span_end": x_end,
                        "gap": gap,
                        "overlap": overlap,
                        "bbox": (x_start, min(y1, y2), x_end, max(y1, y2)),
                    })
    return pairs


def _try_recover_scale_from_spacing(
    wall_groups: Sequence[dict],
    med_gap: float,
    page: Optional[Any],
) -> Optional[float]:
    """Recover scale from clear room spacing between adjacent parallel wall pairs."""
    if page is None:
        return None
    dim_values: List[float] = []
    try:
        from pb_dimension_chain_evidence_extractor import extract_dimension_chains_from_page

        pno = getattr(page, "number", 0) + 1
        chains = extract_dimension_chains_from_page(page, page_num=pno)
        dim_values = [
            obs.value_m for ch in chains for obs in getattr(ch, "observations", [])
            if 0.5 <= obs.value_m <= 10.0
        ]
    except Exception:
        dim_values = []

    if not dim_values:
        words = getattr(page, "get_text", lambda x: [])("words")
        for w in words:
            import re

            m = re.fullmatch(r"(\d{3,4})", str(w[4]).strip())
            if m:
                v = float(m.group(1)) / 1000.0
                if 0.5 <= v <= 10.0:
                    dim_values.append(v)

    if not dim_values:
        return None

    # Check spacing between adjacent vertical walls
    v_walls = sorted([g for g in wall_groups if g["orientation"] == "vertical"], key=lambda x: x["center"])
    for i in range(len(v_walls) - 1):
        clear_span = v_walls[i + 1]["center"] - v_walls[i]["center"] - med_gap
        if clear_span <= 0:
            continue
        for dv in dim_values:
            cand_scale = clear_span / dv
            implied_t = med_gap / cand_scale
            if _PLAUSIBLE_WALL_THICKNESS_RANGE_M[0] <= implied_t <= _PLAUSIBLE_WALL_THICKNESS_RANGE_M[1]:
                return cand_scale

    # Check spacing between adjacent horizontal walls
    h_walls = sorted([g for g in wall_groups if g["orientation"] == "horizontal"], key=lambda x: x["center"])
    for i in range(len(h_walls) - 1):
        clear_span = h_walls[i + 1]["center"] - h_walls[i]["center"] - med_gap
        if clear_span <= 0:
            continue
        for dv in dim_values:
            cand_scale = clear_span / dv
            implied_t = med_gap / cand_scale
            if _PLAUSIBLE_WALL_THICKNESS_RANGE_M[0] <= implied_t <= _PLAUSIBLE_WALL_THICKNESS_RANGE_M[1]:
                return cand_scale

    return None


def _resolve_from_wall_pairs(
    drawings: Sequence[dict],
    *,
    length_m: float,
    width_m: float,
    viewport_bbox: Optional[Tuple[float, float, float, float]],
    page_rect: Optional[Any],
    page: Optional[Any] = None,
) -> InternalPartitionEvidence:
    """Resolve internal partition length from vector stroked wall pairs."""
    h_lines, v_lines = _extract_stroke_lines(drawings, viewport_bbox, page_rect)
    pairs = _find_wall_pairs(h_lines, v_lines)
    if not pairs:
        return InternalPartitionEvidence(
            status="abstained",
            reason="only 0 wall-like stroke pair(s) found, need >= 2",
        )

    gaps = [p["gap"] for p in pairs]
    med_gap = statistics.median(gaps)
    consistent_pairs = [p for p in pairs if abs(p["gap"] - med_gap) / med_gap <= _MAX_THICKNESS_RELATIVE_SPREAD]
    if len(consistent_pairs) < 2:
        return InternalPartitionEvidence(
            status="abstained",
            reason="wall linework does not share a consistent thickness scale",
        )
    wall_thickness_pt = med_gap

    # Group parallel pairs into distinct wall lines
    wall_groups: List[dict] = []
    for p in consistent_pairs:
        orient = p["orientation"]
        center = p["center"]
        span = (p["span_start"], p["span_end"])
        found = False
        for g in wall_groups:
            if g["orientation"] == orient and abs(g["center"] - center) <= med_gap:
                g["spans"].append(span)
                found = True
                break
        if not found:
            wall_groups.append({
                "orientation": orient,
                "center": center,
                "spans": [span],
                "gap": p["gap"],
            })

    for g in wall_groups:
        spans = sorted(g["spans"])
        merged = []
        for s_start, s_end in spans:
            if not merged:
                merged.append([s_start, s_end])
            else:
                if s_start <= merged[-1][1] + 2.0:
                    merged[-1][1] = max(merged[-1][1], s_end)
                else:
                    merged.append([s_start, s_end])
        g["merged_spans"] = merged
        g["total_length"] = sum(s[1] - s[0] for s in merged)

    v_groups = [g for g in wall_groups if g["orientation"] == "vertical"]
    h_groups = [g for g in wall_groups if g["orientation"] == "horizontal"]
    if not v_groups or not h_groups:
        return InternalPartitionEvidence(
            status="abstained",
            reason="wall pairs lack orthogonal enclosure",
        )

    v_coords = [g["center"] for g in v_groups]
    h_coords = [g["center"] for g in h_groups]

    # Evaluate candidate outer envelope spans
    cand_x_spans: List[Tuple[float, float, float]] = []
    for i in range(len(v_coords)):
        for j in range(i + 1, len(v_coords)):
            span = abs(v_coords[j] - v_coords[i]) + med_gap
            cand_x_spans.append((span, min(v_coords[i], v_coords[j]) - med_gap / 2.0, max(v_coords[i], v_coords[j]) + med_gap / 2.0))

    cand_y_spans: List[Tuple[float, float, float]] = []
    for i in range(len(h_coords)):
        for j in range(i + 1, len(h_coords)):
            span = abs(h_coords[j] - h_coords[i]) + med_gap
            cand_y_spans.append((span, min(h_coords[i], h_coords[j]) - med_gap / 2.0, max(h_coords[i], h_coords[j]) + med_gap / 2.0))

    best_match: Optional[dict] = None
    best_err = 1e9

    for span_x, x0, x1 in cand_x_spans:
        for span_y, y0, y1 in cand_y_spans:
            for dim_x, dim_y in [(width_m, length_m), (length_m, width_m)]:
                if dim_x <= 0 or dim_y <= 0:
                    continue
                sx = span_x / dim_x
                sy = span_y / dim_y
                err = abs(sx - sy) / max(sx, sy)
                avg_scale = (sx + sy) / 2.0
                implied_t = med_gap / avg_scale
                lo, hi = _PLAUSIBLE_WALL_THICKNESS_RANGE_M
                if lo <= implied_t <= hi and err < best_err:
                    best_err = err
                    best_match = {
                        "scale": avg_scale,
                        "bounds": (x0, y0, x1, y1),
                        "err": err,
                        "implied_thickness_m": implied_t,
                    }

    # If no candidate pair matches within 10% agreement:
    if best_match is None or best_match["err"] > 0.10:
        min_x = min(g["center"] - g["gap"] / 2.0 for g in v_groups)
        max_x = max(g["center"] + g["gap"] / 2.0 for g in v_groups)
        min_y = min(g["center"] - g["gap"] / 2.0 for g in h_groups)
        max_y = max(g["center"] + g["gap"] / 2.0 for g in h_groups)
        pixel_major = max(max_x - min_x, max_y - min_y)
        pixel_minor = min(max_x - min_x, max_y - min_y)
        real_major = max(length_m, width_m)
        real_minor = min(length_m, width_m)
        if real_minor > 0 and pixel_minor > 0:
            real_ratio = real_major / real_minor
            pixel_ratio = pixel_major / pixel_minor
            if abs(pixel_ratio - real_ratio) / real_ratio > 0.35:
                recovered_scale = _try_recover_scale_from_spacing(wall_groups, med_gap, page)
                if recovered_scale is None:
                    return InternalPartitionEvidence(
                        status="abstained",
                        reason=(
                            f"pixel envelope aspect ratio ({pixel_ratio:.2f}) conflicts with "
                            f"real envelope aspect ratio ({real_ratio:.2f}) -- wrong-axis scale inference rejected"
                        ),
                    )
                best_match = {
                    "scale": recovered_scale,
                    "bounds": (min_x, min_y, max_x, max_y),
                    "err": 0.0,
                    "implied_thickness_m": med_gap / recovered_scale,
                }
            else:
                scale_cand = pixel_major / real_major
                implied_t = med_gap / scale_cand
                lo, hi = _PLAUSIBLE_WALL_THICKNESS_RANGE_M
                if not (lo <= implied_t <= hi):
                    return InternalPartitionEvidence(
                        status="abstained",
                        reason=(
                            f"derived scale ({scale_cand:.2f}pt/m from the longer envelope "
                            f"axis) implies an unrealistic wall thickness ({implied_t:.3f}m, "
                            f"outside {lo}-{hi}m) -- not trusted"
                        ),
                    )
                best_match = {
                    "scale": scale_cand,
                    "bounds": (min_x, min_y, max_x, max_y),
                    "err": 0.0,
                    "implied_thickness_m": implied_t,
                }
        else:
            return InternalPartitionEvidence(
                status="abstained",
                reason="unable to determine valid envelope scale",
            )

    scale_pt_per_m = best_match["scale"]
    implied_thickness_m = best_match["implied_thickness_m"]
    bx0, by0, bx1, by1 = best_match["bounds"]

    lo, hi = _PLAUSIBLE_WALL_THICKNESS_RANGE_M
    if not (lo <= implied_thickness_m <= hi):
        return InternalPartitionEvidence(
            status="abstained",
            reason=(
                f"derived scale ({scale_pt_per_m:.2f}pt/m from the longer envelope "
                f"axis) implies an unrealistic wall thickness ({implied_thickness_m:.3f}m, "
                f"outside {lo}-{hi}m) -- not trusted"
            ),
        )

    # Perimeter vs Internal check
    margin = wall_thickness_pt * _PERIMETER_PROXIMITY_THICKNESS_MULTIPLE
    internal_segments_m: List[float] = []

    for g in wall_groups:
        orient = g["orientation"]
        c = g["center"]
        if orient == "vertical":
            # Check if wall is strictly inside horizontal envelope
            if not (bx0 + margin <= c <= bx1 - margin):
                continue
            # Clip vertical spans to envelope [by0, by1]
            for s0, s1 in g["merged_spans"]:
                clip_s0 = max(s0, by0)
                clip_s1 = min(s1, by1)
                if clip_s1 - clip_s0 >= 12.0:
                    internal_segments_m.append(round((clip_s1 - clip_s0) / scale_pt_per_m, 3))
        else:
            # Check if wall is strictly inside vertical envelope
            if not (by0 + margin <= c <= by1 - margin):
                continue
            # Clip horizontal spans to envelope [bx0, bx1]
            for s0, s1 in g["merged_spans"]:
                clip_s0 = max(s0, bx0)
                clip_s1 = min(s1, bx1)
                if clip_s1 - clip_s0 >= 12.0:
                    internal_segments_m.append(round((clip_s1 - clip_s0) / scale_pt_per_m, 3))

    if not internal_segments_m:
        return InternalPartitionEvidence(
            status="abstained",
            reason="no wall-like element sits strictly inside the derived envelope",
            wall_thickness_m=round(implied_thickness_m, 4),
            scale_pt_per_m=scale_pt_per_m,
        )

    tot = sum(internal_segments_m)
    return InternalPartitionEvidence(
        status="found",
        reason=f"{len(internal_segments_m)} internal partition segment(s) found, total {tot:.3f}m",
        total_length_m=round(tot, 3),
        wall_thickness_m=round(implied_thickness_m, 4),
        scale_pt_per_m=scale_pt_per_m,
        segment_lengths_m=tuple(internal_segments_m),
    )
