"""Mandatory first geometry stage: source-PDF external footprint ink trace.

Reads the exact bytes that the original source producer will ingest. This stage
cannot infer scale, classify a roof/site border as a building, mint walls or
authorize customer quantities. The candidate is a review overlay only.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Sequence


@dataclass(frozen=True)
class ExternalFootprintTrace:
    source_sha256: str
    page_index: int
    status: str
    reason: str
    polygon_pdf_pts: tuple[tuple[float, float], ...] = ()
    bbox_pdf_pts: tuple[float, float, float, float] | None = None
    candidate_count: int = 0
    page_drawings_examined: int = 0
    commercial_publishable: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "source_sha256": self.source_sha256,
            "page_index": self.page_index,
            "status": self.status,
            "reason": self.reason,
            "polygon_pdf_pts": [list(p) for p in self.polygon_pdf_pts],
            "bbox_pdf_pts": list(self.bbox_pdf_pts) if self.bbox_pdf_pts else None,
            "candidate_count": self.candidate_count,
            "page_drawings_examined": self.page_drawings_examined,
            "commercial_publishable": False,
            "measurement_authorized": False,
        }


def _abstain(sha: str, index: int, reason: str, drawings: int = 0) -> ExternalFootprintTrace:
    return ExternalFootprintTrace(sha, index, "ABSTAINED", reason, page_drawings_examined=drawings)


def _bounded_raster_scale(page_width_pts: float, page_height_pts: float) -> float:
    """Bound the mandatory first-stage raster to 2400px on its long axis.

    Large CAD sheets can exceed 3428 PDF pt. The previous max(0.7, scale)
    silently defeated the 2400px cap and increased RAM use on those sheets.
    A lower sampling scale is diagnostic only: no measured quantities or
    source geometry are inferred from these raster pixels.
    """
    if not all(math.isfinite(d) and d > 0 for d in (page_width_pts, page_height_pts)):
        raise ValueError("external_footprint_invalid_page_dimensions")
    longest = max(page_width_pts, page_height_pts)
    if not math.isfinite(longest) or longest <= 0:
        raise ValueError("external_footprint_invalid_page_dimensions")
    return min(1.8, 2400.0 / longest)


def trace_external_footprint_first(
    pdf_bytes: bytes,
    *,
    source_sha256: str,
    page_indices: Sequence[int],
) -> tuple[ExternalFootprintTrace, ...]:
    """Attempt one exterior outline per selected topology page, before inner geometry.

    The visual mask is a bounded *diagnostic candidate*, never physical wall
    existence/face ownership. Open or rival building envelopes are not promoted.
    No source locations or hand-drawn polygons are caller inputs.
    """
    if not isinstance(pdf_bytes, bytes) or hashlib.sha256(pdf_bytes).hexdigest() != source_sha256:
        raise ValueError("external_footprint_original_source_sha_mismatch")
    if not isinstance(page_indices, (tuple, list)) or not page_indices or any(
        type(i) is not int or i < 0 for i in page_indices
    ) or len(set(page_indices)) != len(page_indices):
        raise ValueError("external_footprint_requires_unique_topology_pages")
    try:
        import cv2
        import fitz
        import numpy as np
    except ImportError:
        return tuple(_abstain(source_sha256, i, "external_footprint_raster_backend_unavailable")
                     for i in page_indices)

    results: list[ExternalFootprintTrace] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for index in page_indices:
            if index >= len(doc):
                raise ValueError("external_footprint_page_outside_original")
            page = doc[index]
            # Bound raster memory on high-resolution A0/A1 plans.
            scale = _bounded_raster_scale(float(page.rect.width), float(page.rect.height))
            raster = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, colorspace=fitz.csRGB)
            width, height = raster.width, raster.height
            pixels = np.frombuffer(raster.samples, dtype=np.uint8).reshape(height, width, 3)
            # Dark solid wall paint only; pale landscape, furniture fills and
            # green exclusion art never define the exterior wall outline.
            gray = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
            r, g, b = (pixels[:, :, c].astype(np.int16) for c in range(3))
            green = (g > r * 1.25) & (g > b * 1.08) & (g > 40)
            ink = np.where((gray < 125) & ~green, 255, 0).astype(np.uint8)
            # Floor-plan title blocks are commonly printed in the lowest band.
            # This excludes text; never removes physical topological evidence
            # permanently from the original source PDF.
            ink[int(height * .82):, :] = 0
            outer = []
            for radius in (3, 5, 8):
                # The graduated close is for SHADOW connectivity only. It does
                # not instantiate a physical door, wall, or commercial area.
                closed = cv2.morphologyEx(
                    ink, cv2.MORPH_CLOSE,
                    cv2.getStructuringElement(cv2.MORPH_RECT, (radius, radius)),
                    iterations=1,
                )
                contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
                candidates = []
                sheet_area = float(width * height)
                for contour in contours:
                    area = abs(float(cv2.contourArea(contour)))
                    x, y, w, h = cv2.boundingRect(contour)
                    share = area / sheet_area
                    if not (.025 <= share <= .62) or w < width * .17 or h < height * .12:
                        continue
                    # Refuse title/page frames; there is no legitimate building
                    # wall physically traced on the sheet boundary.
                    if x < width * .012 or y < height * .012 or x + w > width * .988:
                        continue
                    if y + h > height * .82:
                        continue
                    polygon = cv2.approxPolyDP(
                        contour, max(1.5, .003 * cv2.arcLength(contour, True)), True
                    ).reshape(-1, 2)
                    if len(polygon) < 4 or len(polygon) > 200:
                        continue
                    candidates.append((area, (x, y, w, h), polygon))
                if candidates:
                    # The largest bounded enclosing trace is a *candidate*
                    # only. A competing building/site envelope cannot be
                    # independently authenticated by visual ink alone.
                    outer = sorted(candidates, key=lambda item: item[0], reverse=True)
                    break
            if not outer:
                results.append(_abstain(
                    source_sha256, index, "external_footprint_no_closed_wall_ink_candidate",
                ))
                continue
            area, (x, y, w, h), polygon = outer[0]
            points = tuple(
                (round(float(px) / scale, 3), round(float(py) / scale, 3))
                for px, py in polygon
            )
            if len(set(points)) < 4 or not all(math.isfinite(q) for xy in points for q in xy):
                results.append(_abstain(source_sha256, index, "external_footprint_invalid_polygon"))
                continue
            bbox = tuple(round(float(v) / scale, 3) for v in (x, y, x + w, y + h))
            results.append(ExternalFootprintTrace(
                source_sha256=source_sha256,
                page_index=index,
                status="CANDIDATE",
                reason="external_footprint_ink_trace_needs_physical_wall_owner_and_scale",
                polygon_pdf_pts=points,
                bbox_pdf_pts=bbox,
                candidate_count=len(outer),
                commercial_publishable=False,
                measurement_authorized=False,
            ))
    return tuple(results)

@dataclass(frozen=True)
class BoundedFootprintDrawingScope:
    """Source-index-preserving diagnostics, never commercial physical walls."""

    status: str
    reason: str
    page_index: int
    drawings: tuple[dict | object, ...]
    selected_source_path_indices: tuple[int, ...]
    wall_native_primitive_count: int
    source_total_paths: int
    commercial_publishable: bool = False


def bound_native_drawings_to_footprint(
    drawings: Sequence[object],
    *,
    trace: ExternalFootprintTrace,
    expected_source_sha256: str,
) -> BoundedFootprintDrawingScope:
    """Scope the EXISTING native path list by a source-hashed exterior candidate.

    Keep the exact original path indices with inert rows outside the selected
    window. This is a candidate room-tracing *diagnostic* only. It cannot
    transform missing wall identity into proven exterior geometry. Cropping a
    dense page does not enlarge the 20,000-primitive owner limit.
    """
    from collections.abc import Mapping

    if trace.source_sha256 != expected_source_sha256:
        raise ValueError("footprint_source_revision_mismatch")
    if trace.status != "CANDIDATE" or trace.bbox_pdf_pts is None:
        return BoundedFootprintDrawingScope(
            "ABSTAINED", "footprint_candidate_required",
            trace.page_index, (), (), 0, len(drawings),
        )
    x0, y0, x1, y1 = trace.bbox_pdf_pts
    if not all(math.isfinite(n) for n in (x0, y0, x1, y1)) or not (
        x0 < x1 and y0 < y1
    ):
        raise ValueError("footprint_nonfinite_or_invalid_bbox")
    # Source-PDF points, never a physical mm scale inference. Expand enough
    # to keep the wall's drawn stroke outside the visual envelope.
    padx = min(24.0, max(3.0, (x1 - x0) * .02))
    pady = min(24.0, max(3.0, (y1 - y0) * .02))
    inert = {"layer": "", "fill": None, "color": None, "items": ()}
    retained: list[object] = []
    indices: list[int] = []
    for index, row in enumerate(drawings):
        if not isinstance(row, Mapping) or not row.get("items"):
            retained.append(inert)
            continue
        box = row.get("rect")
        if box is None:
            retained.append(inert)
            continue
        try:
            a, b, c, d = map(float, (box.x0, box.y0, box.x1, box.y1))
        except (TypeError, ValueError, AttributeError):
            retained.append(inert)
            continue
        if not all(math.isfinite(v) for v in (a, b, c, d)):
            retained.append(inert)
            continue
        if c < x0 - padx or a > x1 + padx or d < y0 - pady or b > y1 + pady:
            retained.append(inert)
            continue
        indices.append(index)
        retained.append(row)

    # Count the exact primitives that the unchanged existing wall tracer
    # considers wall ink, rather than trusting path container count.
    from pb_layered_wall_doorway_room_ring_shadow import (
        _source_wall_ink_candidate_drawings,
    )

    wall_ink, _count, _green = _source_wall_ink_candidate_drawings(retained)
    primitives = sum(len(row.get("items", ())) for row in wall_ink)
    # The raster can return a closed contour from furniture, labels or a
    # page border. A candidate source-native viewport must actually retain
    # at least one eligible original wall-ink primitive. Otherwise it is an
    # empty selection, not a useful source-wall topology candidate.
    if primitives == 0:
        status = "ABSTAINED"
        reason = "bounded_source_viewport_has_no_native_wall_ink"
    elif primitives > 20_000:
        status = "ABSTAINED"
        reason = "bounded_source_viewport_exceeds_20000_primitive_cap"
    else:
        status = "CANDIDATE"
        reason = "bounded_footprint_trace_only_needs_physical_wall_proof"
    return BoundedFootprintDrawingScope(
        status, reason, trace.page_index, tuple(retained) if status == "CANDIDATE" else (),
        tuple(indices) if status == "CANDIDATE" else (),
        primitives, len(drawings),
    )
