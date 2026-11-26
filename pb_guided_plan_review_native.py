"""Convert a local review draft to source-page user evidence, not measurements.

Only the server's canonical full-page overlay (or exact original page render)
may be supplied by the Plan Mapper. This is not an API for trusting uploaded
overlay pixels or promoting a user annotation to automatic source evidence.
"""
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path

import fitz
from PIL import Image

from pb_guided_plan_review import (
    ReviewScope, editor_shapes, normalise_editor_shapes, normalise_answer,
)
from pb_native_page_frame import native_page_frame

_PRODUCER = "pb_layered_wall_doorway_room_ring_shadow.build_layered_wall_doorway_room_rings"
_GEOMETRY = ("topology", "room_faces", "opening_hosts", "floor_areas",
             "ceiling_areas", "net_wall_areas", "finishes", "costing", "model")
_METRIC = ("scale", "room_faces", "opening_dimensions", "floor_areas",
           "ceiling_areas", "net_wall_areas", "finishes", "costing", "model")
_STAGE_ORDER = ("topology", "scale", "room_faces", "opening_hosts",
                "opening_dimensions", "height", "exclusions", "floor_areas",
                "ceiling_areas", "net_wall_areas", "finishes", "costing", "model")


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _json_digest(value):
    return _digest(json.dumps(value, sort_keys=True, separators=(",", ":"),
                              allow_nan=False).encode("utf-8"))


def _affected_stages(shapes, answers):
    """Conservative per-page invalidation plan, not completed recalculation."""
    stages = set()
    for shape in shapes:
        category = shape["category"]
        if category == "dimension_witness":
            stages.update(_METRIC)
        elif category == "exclusion":
            stages.update(("exclusions", "floor_areas", "ceiling_areas",
                           "net_wall_areas", "finishes", "costing", "model"))
        else:
            stages.update(_GEOMETRY)
    for issue, answer in answers.items():
        if answer["decision"] != "correction_recorded":
            continue
        if issue == "scale":
            stages.update(_METRIC)
        elif issue == "height":
            stages.update(("height", "opening_dimensions", "net_wall_areas",
                           "finishes", "costing", "model"))
        elif issue == "finishes":
            stages.update(("finishes", "costing", "model"))
        elif issue == "exclusions":
            stages.update(("exclusions", "floor_areas", "ceiling_areas",
                           "net_wall_areas", "finishes", "costing", "model"))
        else:
            stages.update(_GEOMETRY)
    return [stage for stage in _STAGE_ORDER if stage in stages]


def build_native_review_packet(*, scope: ReviewScope, pdf_path, image_bytes,
                               saved, canonical_report=None):
    """Map saved image-percent marks to supported native PDF coordinates.

    The image receipt is exact-revision and full-page only. Native coordinates
    remain user-selected points, with pixel-scale precision, not traced faces,
    measured dimensions, uniquely hosted openings or source-confirmed walls.
    """
    if not isinstance(scope, ReviewScope):
        raise ValueError("Review scope required")
    if not isinstance(image_bytes, bytes) or _digest(image_bytes) != scope.image_sha256:
        raise ValueError("Review image changed")
    if type(saved.get("revision")) is not int or saved["revision"] < 1:
        raise ValueError("Save the review before preparing native corrections")
    shapes = normalise_editor_shapes(editor_shapes(saved["shapes"]))
    answers = {issue: normalise_answer(issue, **answer)
               for issue, answer in saved["answers"].items()}
    data = Path(pdf_path).read_bytes()
    if _digest(data) != scope.source_sha256:
        raise ValueError("Original PDF changed")
    with fitz.open(stream=data, filetype="pdf") as doc:
        if scope.pdf_page > len(doc):
            raise ValueError("Review page does not exist")
        page = doc[scope.pdf_page - 1]
        frame = native_page_frame(page)
        zoom = min(1.2, 1800 / max(frame.display_width, frame.display_height))
        expected = (page.rect * fitz.Matrix(zoom, zoom)).irect
        with Image.open(io.BytesIO(image_bytes)) as png:
            if png.format != "PNG" or png.size != (expected.width, expected.height):
                raise ValueError("Review image does not match the full displayed page frame")
        if canonical_report is None:
            rendered = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).tobytes("png")
            if _digest(rendered) != scope.image_sha256:
                raise ValueError("Review image is not the exact original page render")
            render_kind = "original_full_page"
        else:
            if (canonical_report.get("source_sha256") != scope.source_sha256
                    or canonical_report.get("page_index") != scope.pdf_page - 1
                    or canonical_report.get("producer") != _PRODUCER
                    or canonical_report.get("legacy_envelope_used") is not False
                    or canonical_report.get("quantity_authorized") is not False):
                raise ValueError("Canonical preview provenance mismatch")
            if frame.rotation and (
                    canonical_report.get("native_page_frame") != asdict(frame)
                    or canonical_report.get("preview_png_orientation") != "displayed"):
                raise ValueError("Canonical preview rotation receipt mismatch")
            render_kind = "canonical_full_page_preview"

        def native_point(point):
            # Image-edge rounding can add less than one raster pixel; clamp only
            # to the exact displayed page extent before inverse rotation.
            x = min(frame.display_width, point[0] * expected.width / (100 * zoom))
            y = min(frame.display_height, point[1] * expected.height / (100 * zoom))
            if frame.rotation == 90:
                return [y, frame.native_height - x]
            return [x, y]

        corrections = [
            {"correction_id": shape["id"], "category": shape["category"],
             "kind": shape["kind"],
             "native_points_pdf_pts": [native_point(p) for p in shape["points"]],
             "requires_candidate_binding": shape["category"] == "reject_candidate",
             "authority": "user_selected_geometry"}
            for shape in shapes
        ]
        packet = {
            "schema_version": 1,
            "scope": asdict(scope),
            "review_revision": saved["revision"],
            "coordinate_frame": asdict(frame),
            "image_render_kind": render_kind,
            "raster_zoom": zoom,
            "image_dimensions_px": [expected.width, expected.height],
            "corrections": corrections,
            "unbound_review_answers": answers,
            "affected_stage_candidates": _affected_stages(shapes, answers),
            "status": "USER_CORRECTIONS_PENDING_CONSUMER",
            "automatic_source_verified": False,
            "commercial_projection_allowed": False,
            "frozen_benchmark_allowed": False,
            "topology_recalculated": False,
        }
        packet["packet_sha256"] = _json_digest(packet)
        return packet
