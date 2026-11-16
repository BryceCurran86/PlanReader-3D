"""Read-only coloured review overlay for unverified original PDF enclosures.

Displays source-backed *candidate* polygons only. Does not modify original PDF,
create physical room authority, or produce wall/floor/customer quantities.
"""
from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
import math
from typing import Any

import fitz
from PIL import Image, ImageDraw

_CANDIDATES = {"unverified_enclosed_candidate", "interior_enclosed_room"}
_PALETTE = (
    (211, 56, 67), (18, 126, 157), (168, 99, 29),
    (113, 78, 177), (25, 139, 78), (220, 104, 30),
)


def render_unverified_enclosures(
    page: fitz.Page, report: Mapping[str, Any],
) -> bytes | None:
    """Render plan + distinct coloured *unverified* polygons, never billable."""
    if page.rotation != 0:
        return None  # Rotated pages require a separately proven transform.
    rows = tuple(
        rec for rec in (report.get("regions") or ())
        if isinstance(rec, Mapping)
        and rec.get("kind") in _CANDIDATES
        and rec.get("status") in ("candidate", "abstained")
        and not rec.get("measurement_authorized", False)
        and rec.get("bounding_native_path_ids")
    )
    if not rows:
        return None
    rect = page.rect
    if rect.width <= 0 or rect.height <= 0:
        return None
    scale = min(1.5, 1800.0 / max(float(rect.width), float(rect.height)))
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    drawer = ImageDraw.Draw(overlay)
    drawn = 0
    for rec in rows:
        pts = []
        for pair in rec.get("polygon_pdf_pts") or ():
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                pts = []
                break
            try:
                x, y = float(pair[0]), float(pair[1])
            except (TypeError, ValueError):
                pts = []
                break
            if not (math.isfinite(x) and math.isfinite(y)):
                pts = []
                break
            pts.append(((x - rect.x0) * scale, (y - rect.y0) * scale))
        if len(pts) < 3:
            continue
        color = _PALETTE[drawn % len(_PALETTE)]
        drawer.polygon(pts, fill=(*color, 48))
        drawer.line(pts + [pts[0]], fill=(*color, 245), width=max(2, round(2 * scale)))
        drawn += 1
    if not drawn:
        return None
    result = Image.alpha_composite(image, overlay).convert("RGB")
    buffer = BytesIO()
    result.save(buffer, format="PNG")
    return buffer.getvalue()
