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
            scale = min(1.8, 2400.0 / max(float(page.rect.width), float(page.rect.height)))
            scale = max(0.7, scale)
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
