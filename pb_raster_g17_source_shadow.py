"""Shared G17 source-only shadow predicates; never physical wall/host authority.

These pure observers do not authenticate caller data. The producer-owned
builder separately re-proves every source observation before calling them.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import math
from typing import Any, Mapping

import cv2
import numpy as np

from pb_raster_opening_source_primitives import MASS_THRESHOLD
from pb_raster_visible_segment_detector import _MIN_LINE_LENGTH_PT
from pb_source_visibility_authority import _axis_aligned_geometry_fully_covered_by_rect_union

def _line(value: object) -> tuple[float, float, float, float]:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        raise ValueError("source G17 geometry must have four coordinates")
    if any(type(x) not in (int, float) or not math.isfinite(float(x)) for x in value):
        raise ValueError("nonfinite/invalid source G17 geometry")
    return tuple(float(x) for x in value)

def source_only_closed_flanks(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Nominate geometry only when the full G17 source face/end graph closes."""
    source_sha = receipt.get("source_sha256")
    physical_id = receipt.get("physical_opening_id")
    if (not isinstance(source_sha, str) or len(source_sha) != 64
            or not isinstance(physical_id, str) or not physical_id
            or receipt.get("host_status") != "abstained"
            or receipt.get("host_granted") is not False
            or receipt.get("metric_quantity_granted") is not False):
        raise ValueError("unauthenticated or promoted G17 input")
    rows = receipt.get("source_g17_observations")
    if not isinstance(rows, list) or not rows:
        raise ValueError("original G17 observations unavailable")
    groups: dict[tuple[str, float, float], list[tuple[float, str]]] = defaultdict(list)
    ends: dict[tuple[str, float, float, float], list[str]] = defaultdict(list)
    seen = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("malformed G17 source observation")
        oid = row.get("observation_id")
        if not isinstance(oid, str) or not oid or oid in seen:
            raise ValueError("duplicate/unbound G17 observation")
        seen.add(oid)
        parents = row.get("authenticated_source_parents")
        if not isinstance(parents, list) or not parents:
            raise ValueError("source G17 parent not authenticated")
        for parent in parents:
            if not isinstance(parent, Mapping) or not parent.get("observation_id"):
                raise ValueError("missing original G17 source parent")
        x0, y0, x1, y1 = _line(row.get("geometry_pdf_pts"))
        kind = row.get("observation_kind")
        if kind == "raster_wall_band_face":
            if y0 == y1 and x0 < x1:
                groups[("horizontal", x0, x1)].append((y0, oid))
            elif x0 == x1 and y0 < y1:
                groups[("vertical", y0, y1)].append((x0, oid))
            else:
                raise ValueError("malformed G17 physical band face")
        elif kind == "raster_wall_band_end":
            if x0 == x1 and y0 < y1:
                ends[("horizontal", x0, y0, y1)].append(oid)
            elif y0 == y1 and x0 < x1:
                ends[("vertical", y0, x0, x1)].append(oid)
            else:
                raise ValueError("malformed G17 end cap")
        elif kind in ("raster_thin_ink_run", "raster_line_run"):
            # Additional physical ink does not supply wall/host authority.
            continue
        else:
            raise ValueError("unexpected original G17 source observation kind")
    flank_rows = []
    if len(groups) == 2 and sum(len(v) for v in groups.values()) == 4 and sum(map(len, ends.values())) == 2:
        candidates = []
        for (axis, lo, hi), faces in groups.items():
            offsets = sorted(faces)
            if len(faces) != 2 or offsets[0][0] >= offsets[1][0]:
                break
            a, b = offsets[0][0], offsets[1][0]
            bbox = [lo, a, hi, b] if axis == "horizontal" else [a, lo, b, hi]
            candidates.append((axis, lo, hi, a, b, bbox, [offsets[0][1], offsets[1][1]]))
        if len(candidates) == 2:
            candidates.sort(key=lambda v: (v[0], v[1]))
            left, right = candidates
            if (left[0] == right[0] and left[2] < right[1]
                    and not (left[3] > right[4] or right[3] > left[4])):
                for side, row, edge in (("first", left, left[2]), ("second", right, right[1])):
                    axis, lo, hi, a, b, bbox, face_ids = row
                    end_ids = ends.get((axis, edge, a, b), [])
                    if len(end_ids) != 1:
                        break
                    flank_rows.append({
                        "side_in_original_source_order": side,
                        "orientation": axis,
                        "source_bbox_pdf_pts": bbox,
                        "source_observation_ids": sorted(face_ids + end_ids),
                    })
    if len(flank_rows) != 2:
        flank_rows = []
    return {
        "physical_opening_id": physical_id,
        "source_sha256": source_sha,
        "host_status": "abstained",
        "closed_source_flank_nomination": bool(flank_rows),
        "source_flank_boxes": flank_rows,
        "unresolved_reason": None if flank_rows else "exact_original_g17_face_end_closure_unavailable",
        "physical_host_granted": False,
        "opening_height_or_count_granted": False,
        "metric_quantity_granted": False,
        "customer_publication_granted": False,
        "benchmark_score_granted": False,
    }

def pixel_paint_profile(image: np.ndarray, full: np.ndarray, box, *, orientation: str) -> dict:
    """Descriptive supplied-array comparison, with no source/role authority."""
    if (image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3
            or full.dtype != np.uint8 or full.shape != image.shape):
        raise ValueError("matching RGB source arrays required")
    if (not isinstance(box, (list, tuple)) or len(box) != 4
            or any(type(v) is not int for v in box) or orientation not in ("horizontal", "vertical")):
        raise ValueError("invalid flank pixel query")
    x0, y0, x1, y1 = box
    if min(x0, y0) < 0 or x1 >= image.shape[1] or y1 >= image.shape[0] or min(x1-x0, y1-y0) < 2:
        raise ValueError("flank query outside render or without inset core")
    a, b = image[y0:y1+1, x0:x1+1], full[y0:y1+1, x0:x1+1]
    ga, gb = (cv2.cvtColor(v, cv2.COLOR_RGB2GRAY) for v in (a, b))
    mid = ((a.shape[0] if orientation == "horizontal" else a.shape[1])-1)/2
    low, high = math.floor(mid), math.ceil(mid)
    line = (slice(low, high+1), slice(None)) if orientation == "horizontal" else (slice(None), slice(low, high+1))
    result = {"pixel_bbox_inclusive": list(box), "orientation": orientation,
              "mass_threshold": MASS_THRESHOLD, "source_ownership_proven": False,
              "native_paint_role_authenticated": False, "host_publication_allowed": False}
    for name, region in (("inset_core", (slice(1, -1), slice(1, -1))), ("complete_centerline", line)):
        sa, sb = a[region], b[region]
        changed = np.any(sa != sb, axis=2)
        result[name] = {"source_mass_solid": bool(np.all(ga[region] < MASS_THRESHOLD)),
                        "full_render_mass_solid": bool(np.all(gb[region] < MASS_THRESHOLD)),
                        "rgb_equal": bool(not changed.any()),
                        "changed_rgb_pixel_count": int(changed.sum()),
                        "source_rgb_sha256": sha256(sa.tobytes()).hexdigest(),
                        "full_render_rgb_sha256": sha256(sb.tobytes()).hexdigest()}
    changed = np.any(a != b, axis=2)
    ys, xs = np.where(changed)
    result["changed_rgb_pixel_bbox_inclusive"] = ([int(xs.min())+x0, int(ys.min())+y0,
        int(xs.max())+x0, int(ys.max())+y0] if len(xs) else None)
    return result

def authenticated_one_end_g17_paint_shadow(
    original_image_rgb: np.ndarray,
    original_full_rgb: np.ndarray,
    flank: Mapping[str, Any],
    *,
    dpi: int,
    image_regions: tuple,
) -> dict[str, Any]:
    """Nominate only actual solid source ink under already-authenticated G17.

    The caller must FIRST prove the four source faces and two jamb end receipts
    using `source_only_closed_flanks`; no raster rectangle supplied by a
    customer can invoke this observer. This source candidate never creates a
    W2 line, physical W4 owner, host/frame, dimension, count or quantity.
    """
    if type(dpi) is not int or dpi <= 0:
        raise ValueError("positive original source DPI required")
    orientation = flank.get("orientation")
    bounds = flank.get("source_bbox_pdf_pts")
    observations = flank.get("source_observation_ids")
    if (orientation not in ("horizontal", "vertical")
            or not isinstance(bounds, (list,tuple)) or len(bounds) != 4
            or not isinstance(observations, list) or len(observations) != 3
            or len(set(observations)) != len(observations)
            or any(type(x) is not str or not x for x in observations)):
        raise ValueError("missing complete original G17 face/end source receipts")
    try:
        raw_pixels = [float(v) * dpi / 72.0 for v in bounds]
        pixels = [int(round(v)) for v in raw_pixels]
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("invalid original source bounds") from exc
    if (not all(np.isfinite(v) for v in raw_pixels)
            or any(abs(raw - rounded) > 1e-4
                   for raw,rounded in zip(raw_pixels,pixels))
            or pixels[0] >= pixels[2] or pixels[1] >= pixels[3]):
        raise ValueError("original source band not aligned with raster pixel grid")
    profile = pixel_paint_profile(
        original_image_rgb, original_full_rgb, pixels,
        orientation=orientation,
    )
    along_cells = (pixels[2]-pixels[0]+1 if orientation=="horizontal"
                   else pixels[3]-pixels[1]+1)
    painted_length_pt = along_cells * 72.0 / dpi
    if orientation == "horizontal":
        geom = (bounds[0], (bounds[1]+bounds[3])/2,
                bounds[2], (bounds[1]+bounds[3])/2)
    else:
        geom = ((bounds[0]+bounds[2])/2,bounds[1],
                (bounds[0]+bounds[2])/2,bounds[3])
    region_owned = _axis_aligned_geometry_fully_covered_by_rect_union(
        geom, image_regions,
    )
    core = profile["inset_core"]
    centre = profile["complete_centerline"]
    solid_source = bool(core["source_mass_solid"] and centre["source_mass_solid"])
    unchanged_source = bool(core["rgb_equal"] and centre["rgb_equal"])
    supported = bool(solid_source and unchanged_source and region_owned
                     and painted_length_pt >= _MIN_LINE_LENGTH_PT)
    return {
        "original_pixel_bbox_inclusive":pixels,
        "original_source_observation_ids":sorted(observations),
        "inclusive_original_painted_cells":along_cells,
        "inclusive_original_painted_length_pt":round(painted_length_pt,6),
        "source_original_rgb_solid":solid_source,
        "source_vs_full_rgb_identical":unchanged_source,
        "original_image_region_owned":region_owned,
        "source_one_end_shadow_eligible":supported,
        "source_shadow_first_failure":(
            None if supported else
            "original_source_ink_not_solid" if not solid_source else
            "original_source_overpaint_conflict" if not unchanged_source else
            "original_source_image_region_unowned" if not region_owned else
            "original_source_painted_span_below_policy"
        ),
        "complete_outer_end_cap_assumed":False,
        "structural_W2_or_W4_proven":False,
        "host_or_frame_granted":False,
        "opening_height_or_count_granted":False,
        "metric_area_granted":False,
    }
