"""Source-only cross-resolution raster-ink witness for opening wall flanks.

Nonpublishing: raster ink never proves a structural wall, W4 equivalence,
an opening host, count, height, or quantity. Both PNGs and their native page
parents must be obtained by the same SourceVisibilityProducer from images-only
renders of the immutable source page.
"""
from __future__ import annotations

from hashlib import sha256
from math import isfinite
from typing import Any, Sequence

import cv2
import numpy as np


def _ink_mask(png: bytes) -> np.ndarray | None:
    image = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None or image.ndim != 2 or image.size == 0:
        return None
    _, dark = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    _, light = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    choices = [mask for mask in (dark, light)
               if 0.0002 <= np.count_nonzero(mask) / mask.size <= 0.45]
    return min(choices, key=np.count_nonzero) if choices else None


def _sample(mask: np.ndarray | None, geometry: tuple[float, ...], dpi: int) -> dict[str, Any]:
    if len(geometry) != 4 or not all(isfinite(v) for v in geometry):
        return {"status": "invalid_source_edge", "ink_fraction": None}
    x0, y0, x1, y1 = geometry
    if not ((x0 == x1 and y0 != y1) or (y0 == y1 and x0 != x1)):
        return {"status": "invalid_source_edge", "ink_fraction": None}
    if mask is None:
        return {"status": "source_paint_mask_unavailable", "ink_fraction": None}
    scale = dpi / 72.0
    (ax, ay), (bx, by) = (
        (round(x0 * scale), round(y0 * scale)),
        (round(x1 * scale), round(y1 * scale)),
    )
    xlo, xhi = sorted((ax, bx))
    ylo, yhi = sorted((ay, by))
    if xlo < 0 or ylo < 0 or xhi >= mask.shape[1] or yhi >= mask.shape[0]:
        return {"status": "edge_outside_source_render", "ink_fraction": None}
    if ylo == yhi:
        strip = mask[max(0, ylo - 1):min(mask.shape[0], yhi + 2), xlo:xhi + 1]
        occupied = np.any(strip != 0, axis=0)
    else:
        strip = mask[ylo:yhi + 1, max(0, xlo - 1):min(mask.shape[1], xhi + 2)]
        occupied = np.any(strip != 0, axis=1)
    if occupied.size == 0:
        return {"status": "empty_source_edge_sample", "ink_fraction": None}
    return {"status": "sampled",
            "ink_fraction": round(float(np.count_nonzero(occupied)) / occupied.size, 6),
            "sampled_axis_pixels": int(occupied.size)}


def source_owned_cross_dpi_pixel_shadow(
    flanks: Sequence[Any], *, original_144_png: bytes, original_300_png: bytes,
    parent_144: Any, parent_300: Any, ordinary_dpi: int = 144, g17_dpi: int = 300,
) -> dict[str, Any]:
    """Compare producer-owned raster paint, preserving unresolved source edges.

    Parent equality is necessary but not sufficient: callers must obtain the
    images from the same producer's authenticated images-only page renders.
    """
    if (type(ordinary_dpi) is not int or type(g17_dpi) is not int
            or ordinary_dpi != 144 or g17_dpi != 300):
        raise ValueError("exact original detector DPIs required")
    keys = ("observation_id", "page_id", "document_id", "revision_id",
            "source_sha256", "snapshot_id", "source_partition_id")
    first = tuple(getattr(parent_144, key, None) for key in keys)
    second = tuple(getattr(parent_300, key, None) for key in keys)
    if any(value is None or value == "" for value in first) or first != second:
        raise ValueError("cross-resolution source page parent mismatch")
    masks = (_ink_mask(original_144_png), _ink_mask(original_300_png))
    rows = []
    for flank in flanks:
        if not getattr(flank, "source_ink_supported", False):
            rows.append({"source_ink_supported": False, "edges": [],
                         "reason_codes": ["source_ink_unavailable"]})
            continue
        records = tuple(getattr(flank, "exact_coordinate_records", ()) or ())
        edges = []
        errors = []
        for record in records:
            fragments = tuple(getattr(record, "source_edge_fragments", ()) or ())
            if len(fragments) != 1:
                errors.append("source_edge_fragment_ownership_unresolved")
            for fragment in fragments:
                ids = tuple(getattr(fragment, "source_primitive_ids", ()) or ())
                if len(ids) != 1 or not str(ids[0]).startswith("raster_opening_primitive:"):
                    errors.append("source_edge_ancestry_unresolved")
                    continue
                try:
                    geometry = tuple(float(v) for v in fragment.geometry)
                except (ValueError, TypeError, AttributeError):
                    geometry = ()
                a = _sample(masks[0], geometry, ordinary_dpi)
                b = _sample(masks[1], geometry, g17_dpi)
                edges.append({
                    "source_primitive_id": str(ids[0]),
                    "geometry_pt": geometry,
                    "ordinary_images_only": a,
                    "g17_images_only": b,
                    "same_source_ink_at_both_dpi": all(
                        sample["status"] == "sampled" and sample["ink_fraction"] >= 0.5
                        for sample in (a, b)
                    ),
                })
        if len(records) != 3 or len(edges) != 3 or len({
                edge["source_primitive_id"] for edge in edges}) != 3:
            errors.append("three_unique_source_edges_unproven")
        rows.append({
            "source_ink_supported": True,
            "edges": edges,
            "reason_codes": sorted(set(errors)),
            "three_edge_same_source_paint_supported": (
                not errors and all(edge["same_source_ink_at_both_dpi"] for edge in edges)
            ),
        })
    return {
        "source_sha256": first[4], "source_page_id": first[1],
        "source_parent_observation_id": first[0],
        "ordinary_dpi": ordinary_dpi, "g17_dpi": g17_dpi,
        "ordinary_images_only_png_sha256": sha256(original_144_png).hexdigest(),
        "g17_images_only_png_sha256": sha256(original_300_png).hexdigest(),
        "flanks": rows,
        "ordinary_w4_source_edge_equivalence_granted": False,
        "structural_wall_role_granted": False,
        "physical_wall_equivalence_granted": False,
        "host_binding_granted": False,
        "metric_quantity_granted": False,
    }
