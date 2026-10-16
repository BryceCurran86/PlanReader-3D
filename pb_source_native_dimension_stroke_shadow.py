"""Read-only native text-to-vector dimension-line nomination.

This module does not mint figured-dimension authority or any measurement.
A source word can nominate a neighbouring physical stroke, but the drawing's
scale, dimension arrow/witness completion, material, target room and
cross-sheet correspondence are independently gated elsewhere.

Never use this as a value or physical registration producer. It retains
all rival native paths rather than electing the nearest, longest or scaled
line. Source path addresses are original PyMuPDF drawing/item positions.
"""
from __future__ import annotations

import math
import re
from typing import Any

# Lexical format is only a nomination, not a verified dimension number.
_PLAIN_FIGURE = re.compile(r"^[1-9][0-9]{2,5}$", re.ASCII)


def _rect(raw: Any) -> tuple[float, float, float, float] | None:
    try:
        if isinstance(raw, (str, bytes)):
            return None
        result = tuple(float(value) for value in raw)
    except (TypeError, ValueError, OverflowError):
        return None
    if (len(result) != 4 or not all(math.isfinite(x) for x in result)
            or result[2] <= result[0] or result[3] <= result[1]):
        return None
    return result


def _black_opaque_strokes(page: Any):
    """Enumerate producer-native *line objects*; retain original lineage."""
    for path_index, drawing in enumerate(page.get_drawings()):
        if drawing.get("type") not in ("s", "fs"):
            continue
        color = drawing.get("color")
        try:
            stroke = tuple(float(x) for x in color)
            width = float(drawing.get("width", 0))
            opacity = float(drawing.get("stroke_opacity", 1))
        except (TypeError, ValueError, OverflowError):
            continue
        if (len(stroke) != 3 or any(not math.isfinite(x) for x in stroke)
                or stroke != (0.0, 0.0, 0.0) or width <= 0
                or not math.isfinite(width) or opacity != 1.0):
            continue
        for item_index, item in enumerate(drawing.get("items", ())):
            if not item or item[0] != "l":
                continue
            try:
                a, b = item[1:3]
                x0, y0, x1, y1 = map(float, (a.x, a.y, b.x, b.y))
            except (TypeError, ValueError, IndexError, AttributeError, OverflowError):
                continue
            if not all(math.isfinite(v) for v in (x0,y0,x1,y1)):
                continue
            if abs(x0 - x1) <= 1e-5 and abs(y0 - y1) > 0.1:
                axis, length = "native_y", abs(y1 - y0)
            elif abs(y0 - y1) <= 1e-5 and abs(x0 - x1) > 0.1:
                axis, length = "native_x", abs(x1 - x0)
            else:
                continue
            yield {
                "source_primitive_id": f"d{path_index}i{item_index}",
                "source_path_index": path_index,
                "source_path_item_index": item_index,
                "native_segment_pdf_pts": [x0,y0,x1,y1],
                "line_axis": axis,
                "native_segment_length_pdf_pts": length,
                "native_stroke_width_pdf_pts": width,
                "printed_dimension_line_candidate_only": True,
                "printed_dimension_witness_complete": False,
                "source_physical_room_owner_proven": False,
            }


def nominate_printed_native_dimension_strokes(page: Any, native_word: Any):
    """Return all source-native black straight segments near one printed word.

    Satisfying this *geometric candidate* test is not source proof of an
    actual dimension annotation or its witness endpoints. Locality is used
    only to nominate source data for a human/producer to verify: it NEVER
    elects a semantic role, derives scale or binds the measurement to a room.
    """
    if len(native_word) < 8:
        return []
    word = str(native_word[4]).strip()
    if _PLAIN_FIGURE.fullmatch(word) is None:
        return []
    box = _rect(native_word[:4])
    if box is None:
        return []
    cx, cy = (box[0]+box[2])/2, (box[1]+box[3])/2
    transverse_extent = max(box[2]-box[0], box[3]-box[1])
    rows = []
    for item in _black_opaque_strokes(page):
        x0,y0,x1,y1 = item["native_segment_pdf_pts"]
        axis = item["line_axis"]
        if item["native_segment_length_pdf_pts"] < 2.0 * transverse_extent:
            continue
        if axis == "native_y":
            distance = abs(x0-cx)
            within_span = min(y0,y1) <= cy <= max(y0,y1)
        else:
            distance = abs(y0-cy)
            within_span = min(x0,x1) <= cx <= max(x0,x1)
        if distance > transverse_extent or not within_span:
            continue
        rows.append({
            "source_word_page_bbox_pdf_pts": list(box),
            "original_word_lineage": list(native_word[5:8]),
            "original_printed_word": word,
            "word_candidate_not_authenticated_dimension": True,
            "transverse_separation_pdf_pts": distance,
            **item,
        })
    return sorted(rows, key=lambda x: (
        x["source_path_index"], x["source_path_item_index"],
        x["native_segment_pdf_pts"],
    ))


def trace_native_endpoint_tick_candidates_shadow(page: Any, dimension_candidate: dict):
    """Preserve *original* native perpendicular tick sources at both ends.

    The same physical ink endpoint with a short perpendicular black stroke
    corroborates the printed dimension-*annotation* source lineage only.
    It cannot identify a particular structural wall face, room or other
    PDF sheet, and it cannot certify the figured dimension value.
    """
    segment = _rect((
        min(dimension_candidate["native_segment_pdf_pts"][0],
            dimension_candidate["native_segment_pdf_pts"][2]),
        min(dimension_candidate["native_segment_pdf_pts"][1],
            dimension_candidate["native_segment_pdf_pts"][3]),
        max(dimension_candidate["native_segment_pdf_pts"][0],
            dimension_candidate["native_segment_pdf_pts"][2]),
        max(dimension_candidate["native_segment_pdf_pts"][1],
            dimension_candidate["native_segment_pdf_pts"][3]),
    ))
    # Axis-aligned segments have a zero-width rectangle. Use the exact
    # finite source endpoints from the candidate; don't normalize an
    # annotation stroke into a synthetic rectangle.
    del segment
    vals = dimension_candidate.get("native_segment_pdf_pts", ())
    if len(vals) != 4 or not all(
        isinstance(x, (int, float)) and math.isfinite(x) for x in vals
    ):
        return []
    x0, y0, x1, y1 = (float(v) for v in vals)
    axis = dimension_candidate.get("line_axis")
    if axis not in ("native_x", "native_y"):
        return []
    responses = []
    for endpoint in ((x0, y0), (x1, y1)):
        hits = []
        for tick in _black_opaque_strokes(page):
            if tick["source_primitive_id"] == dimension_candidate.get("source_primitive_id"):
                continue
            t = tick["native_segment_pdf_pts"]
            opposite_axis = "native_x" if axis == "native_y" else "native_y"
            if tick["line_axis"] != opposite_axis:
                continue
            if tick["native_segment_length_pdf_pts"] < 7:
                continue
            # Strict source intersection only (0.001 pt tolerance to absorb
            # native finite precision), not nearest drawing or label matching.
            if axis == "native_y":
                agrees = (
                    abs(t[1] - endpoint[1]) <= .001
                    and min(t[0], t[2]) - .001 <= endpoint[0]
                    <= max(t[0], t[2]) + .001
                )
            else:
                agrees = (
                    abs(t[0] - endpoint[0]) <= .001
                    and min(t[1], t[3]) - .001 <= endpoint[1]
                    <= max(t[1], t[3]) + .001
                )
            if agrees:
                hits.append({
                    "native_source_endpoint_pdf_pts": list(endpoint),
                    "source_dimension_line_candidate_id":
                        dimension_candidate.get("source_primitive_id"),
                    "source_tick_candidate_not_structural_wall_face": True,
                    **tick,
                })
        responses.append({
            "native_endpoint_pdf_pts": list(endpoint),
            "all_native_perpendicular_tick_candidates": sorted(
                hits, key=lambda item: (item["source_path_index"],
                                        item["source_path_item_index"])
            ),
            "source_endpoint_is_physical_wall_face_proven": False,
        })
    return responses


__all__ = [
    "nominate_printed_native_dimension_strokes",
    "trace_native_endpoint_tick_candidates_shadow",
]
