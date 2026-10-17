"""Nonpublishing, source-owned multi-row aperture paint census.

A painted scanline is not a structural-wall role, canonical host, opening
frame, or construction quantity. No original source PDFs are bundled.
"""
from __future__ import annotations

from hashlib import sha256
from math import ceil, floor, isfinite
from pathlib import Path

import fitz
import numpy as np


def _source_horizontal_samples(image: np.ndarray, rect: fitz.Rect, *,
                               fixed_pt: float, first_pt: float,
                               last_pt: float, dark_max: int) -> dict:
    if (not isinstance(image, np.ndarray) or image.dtype != np.uint8 or
            image.ndim != 3 or image.shape[2] != 3 or
            not all(isfinite(x) for x in (fixed_pt, first_pt, last_pt)) or
            not isinstance(dark_max, int) or isinstance(dark_max, bool) or
            not 0 <= dark_max < 255 or rect.is_empty or
            not all(isfinite(x) for x in rect)):
        raise ValueError("opaque RGB source, finite geometry and valid policy required")
    h, w = image.shape[:2]
    if h < 1 or w < 1 or not (rect.width > 0 and rect.height > 0):
        raise ValueError("empty original source image")
    if not (rect.y0 <= fixed_pt <= rect.y1 and
            rect.x0 <= first_pt < last_pt <= rect.x1):
        return {"status": "ABSTAIN_SOURCE_IMAGE_PLACEMENT"}
    row = round((fixed_pt - rect.y0) * h / rect.height - .5)
    start = ceil((first_pt - rect.x0) * w / rect.width - .5)
    end = floor((last_pt - rect.x0) * w / rect.width - .5)
    if not (0 <= row < h and 0 <= start <= end < w):
        return {"status": "ABSTAIN_SOURCE_PIXEL_INTERVAL"}
    pixels = image[row, start:end + 1]
    return {"status": "SOURCE_AXIS_PAINT_OBSERVATION_ONLY",
            "dark_cells": int((np.max(pixels, axis=1) <= dark_max).sum()),
            "sampled_cells": len(pixels)}


def aperture_multiline_census(image: np.ndarray, image_rect: fitz.Rect, *,
                              left_band: tuple[float, float],
                              aperture: tuple[float, float],
                              right_band: tuple[float, float],
                              source_rows: tuple[float, ...],
                              dark_max: int = 100) -> dict:
    """Record every source row, fail closed on incomplete coverage, never promote."""
    bands = (left_band, aperture, right_band)
    if not isinstance(source_rows, tuple) or len(source_rows) < 2:
        raise ValueError("two or more original source rows required")
    if not all(isinstance(b, tuple) and len(b) == 2 for b in bands):
        raise ValueError("explicit three source x-intervals required")
    coords = [x for b in bands for x in b]
    if any(type(x) not in (int, float) or not isfinite(x) for x in coords):
        raise ValueError("finite numeric source coordinates required")
    if not (coords[0] < coords[1] <= coords[2] < coords[3] <=
            coords[4] < coords[5]):
        raise ValueError("ordered disjoint source bands required")
    if (any(type(y) not in (int, float) or not isfinite(y) for y in source_rows) or
            any(a >= b for a, b in zip(source_rows, source_rows[1:]))):
        raise ValueError("strictly increasing unique source rows required")
    # Different PDF y coordinates can sample one raster row. Reused pixels
    # are not independent original-source witnesses.
    if (isinstance(image, np.ndarray) and image.ndim == 3 and
            image.shape[0] > 0 and not image_rect.is_empty and
            all(isfinite(v) for v in image_rect)):
        raster_rows = [round((y - image_rect.y0) * image.shape[0] /
                             image_rect.height - .5) for y in source_rows]
        if len(set(raster_rows)) != len(raster_rows):
            raise ValueError("distinct source rows must resolve to distinct raster rows")
    observations = []
    for y in source_rows:
        entry = {"source_y_pt": y}
        for name, band in zip(("left", "aperture", "right"), bands):
            result = _source_horizontal_samples(
                image, image_rect, fixed_pt=y,
                first_pt=band[0], last_pt=band[1], dark_max=dark_max)
            if result["status"] != "SOURCE_AXIS_PAINT_OBSERVATION_ONLY":
                return {"status": "ABSTAIN_INCOMPLETE_SOURCE_IMAGE_COVERAGE",
                        "canonical_host": "ABSTAIN", "opening_area": "ABSTAIN"}
            entry[name] = {"dark_cells": result["dark_cells"],
                           "sampled_cells": result["sampled_cells"]}
        observations.append(entry)
    fractions = [x["aperture"]["dark_cells"] / x["aperture"]["sampled_cells"]
                 for x in observations]
    return {
        "status": "SOURCE_APERTURE_MULTILINE_PAINT_OBSERVATION_ONLY",
        "observations": observations,
        "aperture_min_dark_fraction": min(fractions),
        "aperture_max_dark_fraction": max(fractions),
        "single_scanline_wall_role_proven": False,
        "source_structural_role": "ABSTAIN",
        "canonical_host": "ABSTAIN",
        "whole_wall_frame": "ABSTAIN",
        "opening_height": "ABSTAIN",
        "opening_count": "ABSTAIN",
        "opening_area": "ABSTAIN",
        "new_firm_quantity": False,
    }


def original_pdf_multiline_census(pdf_path: Path, *, expected_sha256: str,
                                  page_1based: int, image_xref: int,
                                  expected_image_sha256: str,
                                  left_band: tuple[float, float],
                                  aperture: tuple[float, float],
                                  right_band: tuple[float, float],
                                  source_rows: tuple[float, ...]) -> dict:
    """Pin exact source bytes and uniquely placed original image parent."""
    data = Path(pdf_path).read_bytes()
    if sha256(data).hexdigest() != expected_sha256:
        raise ValueError("original PDF SHA mismatch")
    with fitz.open(stream=data, filetype="pdf") as doc:
        if not 1 <= page_1based <= len(doc):
            raise ValueError("original page out of range")
        page = doc[page_1based - 1]
        rects = page.get_image_rects(image_xref)
        if len(rects) != 1:
            raise ValueError("source image parent not uniquely placed")
        original_image = doc.extract_image(image_xref)["image"]
        image_sha = sha256(original_image).hexdigest()
        if image_sha != expected_image_sha256:
            raise ValueError("original source image SHA mismatch")
        pix = fitz.Pixmap(doc, image_xref)
        if pix.n != 3 or pix.alpha or pix.colorspace is None or pix.colorspace.n != 3:
            raise ValueError("original opaque RGB source required")
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)
        result = aperture_multiline_census(
            img, rects[0], left_band=left_band, aperture=aperture,
            right_band=right_band, source_rows=source_rows)
    return {"original_pdf_sha256": expected_sha256,
            "original_page_1based": page_1based,
            "source_image_xref": image_xref,
            "source_image_sha256": image_sha,
            **result}
