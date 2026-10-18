"""Default-off proof of raster image roots on both sides of a drawing tile seam.

This is source-pixel lineage only, never structural wall/host/frame/metric authority.
It does not change the raster primitive cap, candidate graphs, or live takeoff.
"""
from __future__ import annotations

from hashlib import sha256
import math
from typing import Any

import fitz

SOURCE_ONLY = "SOURCE_PIXELS_VERIFIED_SHADOW"
ABSTAIN = "ABSTAIN"


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite real")
    return float(value)


def _abstain(digest: str, page_no: int, reason: str) -> dict[str, Any]:
    return {"status": ABSTAIN, "source_sha256": digest, "page_no": page_no,
            "reason_codes": [reason], "image_roots": [],
            "structural_host_granted": False, "whole_wall_frame_granted": False,
            "opening_count_granted": False, "quantity_granted": False}


def prove_tile_seam_source_pixels(
    pdf_bytes: bytes, *, expected_sha256: str, page_no: int,
    seam_x: float, source_y: float, flank_offset_pt: float = 4.0,
    dpi: int = 300,
) -> dict[str, Any]:
    """Corroborate two independently rooted source image pixels with the page raster.

    Sample points and the seam are explicit source-coordinate inputs, not found by
    label proximity. Exactly one image placement must own each pixel, with distinct
    xrefs and abutting source rectangles. No source wall/host interpretation is made.
    """
    if type(pdf_bytes) is not bytes or not pdf_bytes:
        raise ValueError("immutable original PDF bytes required")
    digest = sha256(pdf_bytes).hexdigest()
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64 or digest != expected_sha256:
        raise ValueError("original source SHA-256 mismatch")
    if type(page_no) is not int or page_no <= 0:
        raise ValueError("positive one-based page number required")
    seam_x = _number(seam_x, "seam_x")
    source_y = _number(source_y, "source_y")
    offset = _number(flank_offset_pt, "flank_offset_pt")
    if not 0 < offset <= 20:
        raise ValueError("flank_offset_pt must be positive and bounded")
    if type(dpi) is not int or not 72 <= dpi <= 450:
        raise ValueError("dpi must be a bounded explicit integer")
    xs = (seam_x - offset, seam_x + offset)
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        if page_no > len(document):
            return _abstain(digest, page_no, "source_page_unavailable")
        page = document[page_no - 1]
        if page.rotation != 0 or not all(page.rect.contains(fitz.Point(x, source_y)) for x in xs):
            return _abstain(digest, page_no, "unresolved_source_page_frame")
        owners: list[list[tuple[int, int, fitz.Rect]]] = [[], []]
        seen = set()
        for item in page.get_images(full=True):
            xref, smask = int(item[0]), int(item[1])
            for rect in page.get_image_rects(xref):
                key = (xref, tuple(float(v) for v in rect))
                if key in seen:
                    continue
                seen.add(key)
                for i, x in enumerate(xs):
                    if rect.contains(fitz.Point(x, source_y)):
                        owners[i].append((xref, smask, rect))
        if any(len(o) != 1 for o in owners):
            return _abstain(digest, page_no, "source_tile_membership_not_unique")
        (left_xref, left_mask, left_rect), (right_xref, right_mask, right_rect) = owners[0][0], owners[1][0]
        if (left_xref == right_xref or left_mask or right_mask
            or abs(left_rect.x1 - seam_x) > 0.03 or abs(right_rect.x0 - seam_x) > 0.03
            or abs(left_rect.x1 - right_rect.x0) > 0.03):
            return _abstain(digest, page_no, "distinct_abutting_unmasked_image_roots_unproven")
        scale = dpi / 72.0
        clip = fitz.Rect(xs[0] - 1, source_y - 1, xs[1] + 1, source_y + 1)
        composite = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
        roots = []
        for x, (xref, _smask, rect) in zip(xs, (owners[0][0], owners[1][0])):
            image = fitz.Pixmap(document, xref)
            if image.n != 3 or image.width < 1 or image.height < 1:
                return _abstain(digest, page_no, "source_tile_pixel_format_unsupported")
            px = min(image.width - 1, max(0, int((x - rect.x0) / rect.width * image.width)))
            py = min(image.height - 1, max(0, int((source_y - rect.y0) / rect.height * image.height)))
            source_rgb = tuple(image.pixel(px, py)[:3])
            cx = int(x * scale) - composite.x
            cy = int(source_y * scale) - composite.y
            if not (0 <= cx < composite.width and 0 <= cy < composite.height):
                return _abstain(digest, page_no, "source_render_sample_outside_clip")
            rendered_rgb = tuple(composite.pixel(cx, cy)[:3])
            if max(source_rgb) > 64 or max(rendered_rgb) > 64 or any(abs(a - b) > 12 for a, b in zip(source_rgb, rendered_rgb)):
                return _abstain(digest, page_no, "source_ink_or_render_corroboration_failed")
            roots.append({"xref": xref, "image_sha256": sha256(document.extract_image(xref)["image"]).hexdigest(),
                          "placement": [round(float(v), 6) for v in rect],
                          "sample_pt": [x, source_y], "source_rgb": list(source_rgb),
                          "rendered_rgb": list(rendered_rgb)})
        return {"status": SOURCE_ONLY, "source_sha256": digest, "page_no": page_no,
                "reason_codes": [], "image_roots": roots,
                "structural_host_granted": False, "whole_wall_frame_granted": False,
                "opening_count_granted": False, "quantity_granted": False}
