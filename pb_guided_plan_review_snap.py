"""Review-only magnetic targets from the canonical native preview.

No target authenticates wall ownership, an opening or a dimension. Full-page
display coordinates match the existing user correction editor exactly.
"""
from dataclasses import asdict
import hashlib
import io
import math
from pathlib import Path

import fitz
from PIL import Image

from pb_native_page_frame import native_page_frame

MAX_TARGETS = 2048
_PRODUCER = "pb_layered_wall_doorway_room_ring_shadow.build_layered_wall_doorway_room_rings"


def build_review_snap_targets(*, scope, pdf_path, image_bytes, report):
    if (
        not isinstance(report, dict)
        or report.get("source_sha256") != scope.source_sha256
        or report.get("page_index") != scope.pdf_page - 1
        or report.get("producer") != _PRODUCER
        or report.get("legacy_envelope_used") is not False
        or report.get("quantity_authorized") is not False
        or hashlib.sha256(image_bytes).hexdigest() != scope.image_sha256
    ):
        raise ValueError("Review snap preview provenance mismatch")
    data = Path(pdf_path).read_bytes()
    if hashlib.sha256(data).hexdigest() != scope.source_sha256:
        raise ValueError("Original PDF changed")
    with fitz.open(stream=data, filetype="pdf") as doc:
        if not 1 <= scope.pdf_page <= len(doc):
            raise ValueError("Review page unavailable")
        page = doc[scope.pdf_page - 1]
        frame = native_page_frame(page)
        if frame.rotation and (
            report.get("native_page_frame") != asdict(frame)
            or report.get("preview_png_orientation") != "displayed"
        ):
            raise ValueError("Review snap rotation provenance mismatch")
        zoom = min(1.2, 1800 / max(frame.display_width, frame.display_height))
        bounds = (page.rect * fitz.Matrix(zoom, zoom)).irect
        with Image.open(io.BytesIO(image_bytes)) as png:
            if png.format != "PNG" or png.size != (bounds.width, bounds.height):
                raise ValueError("Review snap image frame mismatch")
        network = report.get("exterior_source_wall_network") or {}
        raw = list(network.get("unjoined_native_wall_endpoints_pdf_pts") or [])
        raw.extend(hit.get("tip_pdf_pts") for hit in
                   network.get("source_endpoint_near_misses") or []
                   if isinstance(hit, dict))
        raw.extend(report.get("external_wall_path_points") or [])
        if len(raw) > MAX_TARGETS:
            raise ValueError("Too many source snap candidates; use manual placement")
        targets = set()
        for point in raw:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                continue
            x, y = point
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in (x, y)):
                continue
            if not (0 <= x <= frame.native_width and 0 <= y <= frame.native_height):
                continue
            if frame.rotation == 90:
                x, y = frame.native_height - y, x
            targets.add((round(100 * x * zoom / bounds.width, 8),
                         round(100 * y * zoom / bounds.height, 8)))
        return [{"x": x, "y": y} for x, y in sorted(targets)]
