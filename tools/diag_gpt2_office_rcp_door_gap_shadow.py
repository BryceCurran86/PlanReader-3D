"""Compare original wall-face stroke intervals across two authenticated-by-caller views.

This shadow NEVER authenticates a viewport, a structural wall, room label,
door, scale or customer ceiling quantity. Bboxes are caller-supplied diagnostic
witness scopes, not predictions. Every source path rival remains in output.
"""
from __future__ import annotations

import math


def _bbox(value):
    if (type(value) not in (tuple, list) or len(value) != 4
        or any(type(x) not in (float, int) or not math.isfinite(x) for x in value)):
        raise ValueError("finite_original_bbox_required")
    x0, y0, x1, y1 = map(float, value)
    if not (x0 < x1 and y0 < y1):
        raise ValueError("positive_original_bbox_required")
    return (x0, y0, x1, y1)


def _edge_ink(page, bbox, tol):
    x0, y0, x1, y1 = bbox
    sides = {"left": [], "right": [], "top": [], "bottom": []}
    drawings = page.get_drawings()
    if len(drawings) > 120000:
        raise ValueError("source_path_universe_exceeds_shadow_bound")
    for path_id, drawing in enumerate(drawings):
        width = drawing.get("width")
        if (drawing.get("type") != "s"
            or drawing.get("color") != (0., 0., 0.)
            or drawing.get("stroke_opacity") != 1
            or type(width) not in (float, int)
            or not math.isfinite(width) or width <= 0):
            continue
        for item_id, item in enumerate(drawing.get("items") or ()):
            if len(item) < 3 or item[0] != "l":
                continue
            a, b = item[1:3]
            if abs(a.x - b.x) <= tol:
                x = (a.x + b.x) / 2
                target = ("left" if abs(x-x0)<=tol else
                          "right" if abs(x-x1)<=tol else None)
                if target is None:
                    continue
                lo, hi = max(y0, min(a.y, b.y)), min(y1, max(a.y, b.y))
            elif abs(a.y - b.y) <= tol:
                y = (a.y + b.y) / 2
                target = ("top" if abs(y-y0)<=tol else
                          "bottom" if abs(y-y1)<=tol else None)
                if target is None:
                    continue
                lo, hi = max(x0, min(a.x, b.x)), min(x1, max(a.x, b.x))
            else:
                continue
            if hi-lo > tol:
                sides[target].append((float(lo), float(hi), path_id, item_id))
    return {side: tuple(sorted(rows, key=lambda r:(r[0],r[1],r[2],r[3])))
            for side, rows in sides.items()}


def _gaps(rows, start, stop, tol):
    cursor = start
    gaps = []
    for low, high, *_ in rows:
        if low > cursor + tol:
            gaps.append((round(cursor, 5),round(low, 5)))
        cursor = max(cursor, high)
    if stop > cursor + tol:
        gaps.append((round(cursor, 5),round(stop, 5)))
    return tuple(gaps)


def original_crosssheet_open_wall_ceiling_ink_shadow(
    floor_page, rcp_page, *, floor_face_bbox, rcp_face_bbox,
    tolerance_pt=0.03,
):
    """Witness equal wall-face spans, an original floor doorway and RCP closure.

    No label or numeric dimension is trusted here, even if the actual drawing
    includes a matching door schedule code. A source gap is NOT a wall, and a
    copied area is NOT independently measured ceiling area.
    """
    f = _bbox(floor_face_bbox)
    c = _bbox(rcp_face_bbox)
    if (type(tolerance_pt) not in (float,int) or not math.isfinite(tolerance_pt)
        or tolerance_pt <= 0 or tolerance_pt > 0.1):
        raise ValueError("explicit_source_ink_tolerance_required")
    tol = float(tolerance_pt)
    fx0, fy0, fx1, fy1 = f
    cx0, cy0, cx1, cy1 = c
    translation = (cx0-fx0, cy0-fy0)
    dimensions_match = (
        abs((fx1-fx0)-(cx1-cx0)) <= tol
        and abs((fy1-fy0)-(cy1-cy0)) <= tol
    )
    floor = _edge_ink(floor_page,f,tol)
    ceiling = _edge_ink(rcp_page,c,tol)
    floor_gaps = {side:_gaps(rows,fy0 if side in ("left","right") else fx0,
                             fy1 if side in ("left","right") else fx1,tol)
                  for side,rows in floor.items()}
    rcp_gaps = {side:_gaps(rows,cy0 if side in ("left","right") else cx0,
                           cy1 if side in ("left","right") else cx1,tol)
                for side,rows in ceiling.items()}
    source_status = "source_ink_candidate" if (
        dimensions_match
        and len(floor_gaps["top"]) == 1
        and floor_gaps["left"] == floor_gaps["right"] == floor_gaps["bottom"] == ()
        and all(not holes for holes in rcp_gaps.values())
    ) else "abstained"
    return {
        "status": source_status,
        "source_floor_face_bbox_pdf_pts": f,
        "source_rcp_face_bbox_pdf_pts": c,
        "source_frame_translation_pdf_pts": translation,
        "floor_boundary_source_paths": floor,
        "rcp_boundary_source_paths": ceiling,
        "floor_uncovered_stroke_intervals": floor_gaps,
        "rcp_uncovered_stroke_intervals": rcp_gaps,
        "dimensions_equivalent": dimensions_match,
        "original_room_identity_proven": False,
        "original_door_identity_proven": False,
        "source_metric_scale_proven": False,
        "firm_ceiling_area_m2": None,
        "new_firm_quantities": 0,
        "first_unclosed_gate": "source_owned_room_door_and_metric_authority",
    }
