"""Source-closed horizontal raster-tile seam proof for elevation graphics.

Producer-observed image placements and sampled *original* pixels are only
pixel-lineage evidence. This never binds an elevation to a plan, resolves an
opening kind, grants a host, or publishes a quantity.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any

import fitz

from pb_gptmax_raster_tile_seam_shadow import (
    ABSTAIN, SOURCE_ONLY, _abstain, _canonical_source_image_placement,
    _number,
)


def prove_horizontal_tile_seam_source_pixels(
    pdf_bytes: bytes, *, expected_sha256: str, page_no: int,
    source_x: float, seam_y: float, flank_offset_pt: float = 4.0,
    dpi: int = 300,
) -> dict[str, Any]:
    """Verify independent original dark image roots above/below a source seam.

    Image placement is unrotated/unmirrored; exactly one placed image owns each
    probe point. Two source-image payloads and the rendered PDF independently
    agree on the dark pixels. The paired points do NOT prove a continuous
    structural stroke between them or a physical elevation-to-floor identity.
    """
    if type(pdf_bytes) is not bytes or not pdf_bytes:
        raise ValueError("immutable original PDF bytes required")
    digest = sha256(pdf_bytes).hexdigest()
    if (not isinstance(expected_sha256, str)
            or len(expected_sha256) != 64 or digest != expected_sha256):
        raise ValueError("original source SHA-256 mismatch")
    if type(page_no) is not int or page_no < 1:
        raise ValueError("positive one-based page number required")
    source_x = _number(source_x, "source_x")
    seam_y = _number(seam_y, "seam_y")
    offset = _number(flank_offset_pt, "flank_offset_pt")
    if not 0 < offset <= 20:
        raise ValueError("flank_offset_pt must be positive and bounded")
    if type(dpi) is not int or not 72 <= dpi <= 450:
        raise ValueError("dpi must be a bounded explicit integer")
    ys = (seam_y - offset, seam_y + offset)
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        if page_no > len(document):
            return _abstain(digest, page_no, "source_page_unavailable")
        page = document[page_no - 1]
        if page.rotation != 0 or not all(
            page.rect.contains(fitz.Point(source_x, y)) for y in ys
        ):
            return _abstain(digest, page_no, "unresolved_source_page_frame")
        owners: list[list[tuple[int, int, fitz.Rect, bool]]] = [[], []]
        seen = set()
        for image in page.get_images(full=True):
            xref, smask = int(image[0]), int(image[1])
            for rect, matrix in page.get_image_rects(xref, transform=True):
                key = (xref, tuple(float(v) for v in rect),
                       tuple(float(v) for v in matrix))
                if key in seen:
                    continue
                seen.add(key)
                supported = _canonical_source_image_placement(rect, matrix)
                for index, y in enumerate(ys):
                    if rect.contains(fitz.Point(source_x, y)):
                        owners[index].append((xref, smask, rect, supported))
        if any(len(found) != 1 for found in owners):
            return _abstain(digest, page_no, "source_tile_membership_not_unique")
        top, bottom = owners[0][0], owners[1][0]
        tx, tm, tr, tok = top
        bx, bm, br, bok = bottom
        if not (tok and bok):
            return _abstain(digest, page_no, "source_tile_image_transform_unsupported")
        if (tx == bx or tm or bm
            or abs(tr.y1 - seam_y) > .03
            or abs(br.y0 - seam_y) > .03
            or abs(tr.y1 - br.y0) > .03):
            return _abstain(digest, page_no, "distinct_abutting_unmasked_image_roots_unproven")
        scale = dpi / 72.0
        composite = page.get_pixmap(
            matrix=fitz.Matrix(scale, scale),
            clip=fitz.Rect(source_x - 1, ys[0] - 1,
                           source_x + 1, ys[1] + 1),
            alpha=False,
        )
        roots = []
        for y, (xref, _smask, rect, _ok) in zip(ys, (top, bottom)):
            original = fitz.Pixmap(document, xref)
            if original.n != 3 or original.width < 1 or original.height < 1:
                return _abstain(digest, page_no, "source_tile_pixel_format_unsupported")
            px = min(original.width - 1, max(0, int(
                (source_x - rect.x0) / rect.width * original.width)))
            py = min(original.height - 1, max(0, int(
                (y - rect.y0) / rect.height * original.height)))
            source_rgb = tuple(original.pixel(px, py)[:3])
            cx = int(source_x * scale) - composite.x
            cy = int(y * scale) - composite.y
            if not (0 <= cx < composite.width and 0 <= cy < composite.height):
                return _abstain(digest, page_no, "source_render_sample_outside_clip")
            rendered_rgb = tuple(composite.pixel(cx, cy)[:3])
            if (max(source_rgb) > 64 or max(rendered_rgb) > 64
                    or any(abs(a - b) > 12 for a, b in zip(source_rgb, rendered_rgb))):
                return _abstain(digest, page_no, "source_ink_or_render_corroboration_failed")
            roots.append({
                "xref": xref,
                "image_sha256": sha256(document.extract_image(xref)["image"]).hexdigest(),
                "placement": [round(float(v), 6) for v in rect],
                "sample_pt": [source_x, y],
                "source_rgb": list(source_rgb),
                "rendered_rgb": list(rendered_rgb),
            })
        return {
            "status": SOURCE_ONLY,
            "source_sha256": digest,
            "page_no": page_no,
            "reason_codes": [],
            "image_roots": roots,
            "structural_host_granted": False,
            "whole_wall_frame_granted": False,
            "opening_count_granted": False,
            "quantity_granted": False,
            "elevation_plan_identity_granted": False,
            "opening_kind_granted": False,
        }
