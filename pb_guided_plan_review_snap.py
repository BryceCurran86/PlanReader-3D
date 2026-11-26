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


def _display_points(*, scope, pdf_path, image_bytes, report, raw):
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
        if len(raw) > MAX_TARGETS:
            raise ValueError("Too many source snap candidates; use manual placement")
        targets = []
        for point in raw:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                targets.append(None)
                continue
            x, y = point
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in (x, y)):
                targets.append(None)
                continue
            if not (0 <= x <= frame.native_width and 0 <= y <= frame.native_height):
                targets.append(None)
                continue
            if frame.rotation == 90:
                x, y = frame.native_height - y, x
            targets.append((round(100 * x * zoom / bounds.width, 8),
                            round(100 * y * zoom / bounds.height, 8)))
        return targets


def build_review_snap_targets(*, scope, pdf_path, image_bytes, report):
    if not isinstance(report, dict):
        raise ValueError("Review snap preview provenance mismatch")
    network = report.get("exterior_source_wall_network") or {}
    raw = list(network.get("unjoined_native_wall_endpoints_pdf_pts") or [])
    raw.extend(hit.get("tip_pdf_pts") for hit in
               network.get("source_endpoint_near_misses") or []
               if isinstance(hit, dict))
    raw.extend(report.get("external_wall_path_points") or [])
    points = _display_points(scope=scope, pdf_path=pdf_path, image_bytes=image_bytes,
                             report=report, raw=raw)
    return [{"x": x, "y": y} for x, y in sorted({p for p in points if p is not None})]


def build_review_issue_targets(*, scope, pdf_path, image_bytes, report):
    """Locate only residual post-aperture review candidates, not raw gaps.

    The canonical audit can already explain a raw wall tip as an opening,
    internal wall, joinery or a covered terminal. These must not be presented
    as a missing-wall instruction. An empty list is not a closure certificate.
    """
    labels = {
        "unmatched_raw_wall_ink_terminal_needs_post_opening_review":
            "Unmatched wall endpoint",
        "ambiguous_competing_hosted_apertures": "Ambiguous opening ownership",
        "ambiguous_competing_source_roles": "Ambiguous wall / source role",
    }
    if not isinstance(report, dict):
        raise ValueError("Review issue preview provenance mismatch")
    audit = report.get("source_wall_endpoint_aperture_review") or {}
    reviews = [item for item in (audit.get("endpoint_reviews") or [])
               if isinstance(item, dict) and item.get("status") in labels]
    points = _display_points(
        scope=scope, pdf_path=pdf_path, image_bytes=image_bytes, report=report,
        raw=[item.get("endpoint_pdf_pts") for item in reviews],
    )
    candidates = {(item["status"], *point)
                  for item, point in zip(reviews, points) if point is not None}
    result = []
    for status, x, y in sorted(candidates):
        identity = hashlib.sha256(
            f"{scope.key}:{status}:{x}:{y}".encode("utf-8")
        ).hexdigest()
        result.append({"id": identity, "label": labels[status],
                       "x": x, "y": y})
    return result
