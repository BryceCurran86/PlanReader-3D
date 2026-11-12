"""Source-native RCP callout to candidate ceiling-zone geometry.

A text bubble is NOT automatically its enclosing finished ceiling plane. The
original PDF's recorded rectangles provide auditable geometric candidates,
not commercial zone boundaries. A cross-sheet room association is separately
reviewed, with neither physical authority nor customer quantity implied.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence
import math

from .engine import NativePage, NativeRectangle, SourceConflict
from .height_evidence import rcp_material_height_callouts, validate_height_receipt

# Rectangles are PDF native drawings, not a guessed alignment transform.
_RECT_FUZZ_PT = 0.35
# A second almost identical containing rectangle may be a different
# overlapping element. Never arbitrarily prefer the marginally smaller one.
_MIN_RELATIVE_SIZE_SEPARATION = 0.10


def _is_source_stroked_outline(rectangle: NativeRectangle) -> bool:
    """Reject fill-only shapes, invisible white outlines and unknown paint.

    A native PDF rectangle operation is not necessarily drawn as a border.
    Its coordinates may only paint a white masking/background fill. It is
    NOT a ceiling border without its own visibly stroked perimeter.
    Even a stroked rectangle is only a zone CANDIDATE, never physical proof.
    """
    if rectangle.stroke_present is not True:
        return False
    rgb = rectangle.stroke_color
    if (
        rgb is None or len(rgb) not in (1, 3, 4)
        or not all(math.isfinite(v) and 0 <= v <= 1 for v in rgb)
    ):
        return False
    # Near-white stroke on the white PDF background is not a drawn border.
    if min(rgb) >= .95:
        return False
    return (
        rectangle.stroke_width is not None
        and math.isfinite(rectangle.stroke_width)
        and rectangle.stroke_width > 0
    )


def _is_white_layout_fill(rectangle: NativeRectangle) -> bool:
    """PDF white mask: useful layout SEED, not its own drawn boundary."""
    rgb = rectangle.fill_color
    return (
        rectangle.stroke_present is False
        and rgb is not None
        and len(rgb) in (1, 3, 4)
        and all(math.isfinite(v) and .95 <= v <= 1 for v in rgb)
    )


def _native_rect_area(rectangle: NativeRectangle) -> float:
    x0, y0, x1, y1 = rectangle.bbox
    return (x1 - x0) * (y1 - y0)


def _encloses(rectangle: NativeRectangle, bounds: Sequence[float]) -> bool:
    x0, y0, x1, y1 = rectangle.bbox
    a, b, c, d = bounds
    return (
        x0 + _RECT_FUZZ_PT <= a and y0 + _RECT_FUZZ_PT <= b
        and x1 - _RECT_FUZZ_PT >= c and y1 - _RECT_FUZZ_PT >= d
    )


def _combined_word_bounds(page_words: Mapping[str, Any], claim: Mapping[str, Any]) -> tuple[float, float, float, float]:
    height = page_words.get(claim["height_word_ref"])
    material = page_words.get(claim["material_word_ref"])
    if height is None or material is None:
        raise SourceConflict("rcp_height_material_original_word_missing")
    a, b = height.bbox, material.bbox
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


def propose_rcp_source_zone_rectangles(
    page: NativePage, *, viewport_pdf_pts: Sequence[float] | None = None,
    include_fill_masks_as_layout_hints: bool = False,
) -> dict[str, Any]:
    """Associate each original height/material pair with an original rectangle.

    Only original visibly STROKED rectangular perimeters qualify; PDF
    fill-only white mask rectangles cannot be interpreted as drawn walls.
    Unique smallest rect is allowed only if the next containing source
    rectangle is at least 10% larger. Large plan-wide rectangles and close
    nested duplicates stay unmatched. Multiple same-value bubbles within
    one accepted rectangle consolidate, conflicting values abstain.
    This never authorizes a ceiling area or wall height.
    """
    receipts = rcp_material_height_callouts(page, viewport_pdf_pts=viewport_pdf_pts)
    words = {word.ref: word for word in page.words}
    if len(words) != len(page.words):
        raise SourceConflict("duplicate_source_word_ref")

    # Prevent one source rectangle reused as many independent commercial zones.
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rectangle_lookup = {rect.ref: rect for rect in page.rectangles}
    if len(rectangle_lookup) != len(page.rectangles):
        raise SourceConflict("duplicate_source_rectangle_ref")
    abstentions: list[dict[str, str]] = []
    for receipt in receipts:
        box = _combined_word_bounds(words, receipt)
        containing = sorted(
            (rect for rect in page.rectangles
             if rect.clip_known
             and (_is_source_stroked_outline(rect) or (
                 include_fill_masks_as_layout_hints and _is_white_layout_fill(rect)
             ))
             and _encloses(rect, box) and _native_rect_area(rect) > 0),
            key=lambda rect: (_native_rect_area(rect), rect.ref),
        )
        if not containing:
            abstentions.append({
                "height_word_ref": receipt["height_word_ref"],
                "reason_code": "no_source_zone_rectangle_around_rcp_callout",
            })
            continue
        best = containing[0]
        if len(containing) == 1:
            # A sole box can be the whole sheet/legend. It is not evidence
            # that this one text bubble identifies one physical ceiling zone.
            abstentions.append({
                "height_word_ref": receipt["height_word_ref"],
                "reason_code": "rcp_only_one_unresolved_containing_rectangle",
            })
            continue
        if _native_rect_area(containing[1]) < (
            _native_rect_area(best) * (1 + _MIN_RELATIVE_SIZE_SEPARATION)
        ):
            abstentions.append({
                "height_word_ref": receipt["height_word_ref"],
                "reason_code": "rcp_overlapping_rectangles_ambiguous",
            })
            continue
        grouped[best.ref].append(receipt)

    candidates: list[dict[str, Any]] = []
    for rect_ref, group in sorted(grouped.items()):
        height_material = {
            (receipt["height_mm"], receipt["material_code_candidate"])
            for receipt in group
        }
        if len(height_material) != 1:
            abstentions.extend({
                "height_word_ref": receipt["height_word_ref"],
                "reason_code": "rcp_conflicting_bubbles_in_candidate_zone",
            } for receipt in group)
            continue
        rect = rectangle_lookup[rect_ref]
        height_mm, material_code = next(iter(height_material))
        candidates.append({
            "source_sha256": page.source_sha256,
            "page_index": page.page_index,
            "source_rectangle_ref": rect.ref,
            "source_rectangle_bbox_pdf_pts": list(rect.bbox),
            "height_mm": height_mm,
            "material_code_candidate": material_code,
            "height_word_refs": sorted(receipt["height_word_ref"] for receipt in group),
            "material_word_refs": sorted(receipt["material_word_ref"] for receipt in group),
            "callout_receipts": group,
            "candidate_scope": (
                "WHITE_FILL_LAYOUT_SEED_NOT_A_DRAWN_CEILING_BOUNDARY"
                if _is_white_layout_fill(rect)
                else "SOURCE_STROKED_RECTANGLE_STILL_NEEDS_PHYSICAL_VERIFICATION"
            ),
            "source_stroke_outline_visible": _is_source_stroked_outline(rect),
            "source_white_fill_layout_mask": _is_white_layout_fill(rect),
            "ceiling_zone_authenticated": False,
            "room_correspondence_authenticated": False,
            "commercial_publishable": False,
            "benchmark_credit": False,
        })
    return {
        "source_sha256": page.source_sha256,
        "page_index": page.page_index,
        "source_height_material_pairs": len(receipts),
        "source_zone_rectangle_candidates": candidates,
        "unresolved_callouts": abstentions,
        "physical_ceiling_zone_authenticated": False,
        "commercial_publishable": False,
        "benchmark_credit": False,
        "official_score": None,
    }


def associate_reviewed_rcp_zone_with_plan_face(
    plan_page: NativePage,
    rcp_page: NativePage,
    *,
    source_rectangle_ref: str,
    height_word_ref: str,
    item_id: str,
    plan_face_segment_ref: str,
    plan_room_label_word_ref: str,
    cross_sheet_correspondence_reviewed: bool,
) -> dict[str, Any]:
    """Record explicit review of a ceiling-zone ? plan-face relation.

    An exact source native segment and label are required on the plan. A
    source-native rectangle and original source height are required on RCP.
    This reviewer relation does not claim ceiling height globally; 2700 FFL/FCL
    from a building section is a separate route and must not be silently
    substituted for an RCP's local callout.
    """
    if plan_page.source_sha256 != rcp_page.source_sha256:
        raise SourceConflict("cross_sheet_height_source_sha_mismatch")
    if plan_page.page_index == rcp_page.page_index:
        raise SourceConflict("cross_sheet_height_pages_not_distinct")
    if cross_sheet_correspondence_reviewed is not True:
        raise SourceConflict("cross_sheet_room_zone_correspondence_not_reviewed")
    if type(item_id) is not str or not item_id.strip() or item_id != item_id.strip():
        raise SourceConflict("height_scope_item_id_invalid")
    face = next((s for s in plan_page.segments if s.ref == plan_face_segment_ref), None)
    if face is None or face.kind not in ("line", "rect_edge"):
        raise SourceConflict("plan_face_source_segment_invalid")
    if not math.isfinite(face.x1 + face.x2 + face.y1 + face.y2):
        raise SourceConflict("plan_face_source_geometry_invalid")
    if math.hypot(face.x2 - face.x1, face.y2 - face.y1) < 8:
        raise SourceConflict("plan_face_source_segment_too_short")
    label = next((w for w in plan_page.words if w.ref == plan_room_label_word_ref), None)
    if label is None or not label.text.strip():
        raise SourceConflict("plan_room_label_original_word_missing")
    zone = propose_rcp_source_zone_rectangles(rcp_page)
    candidates = [
        c for c in zone["source_zone_rectangle_candidates"]
        if c["source_rectangle_ref"] == source_rectangle_ref
        and height_word_ref in c["height_word_refs"]
    ]
    if len(candidates) != 1:
        raise SourceConflict("rcp_height_zone_geometry_not_uniquely_owned")
    candidate = candidates[0]
    original_receipt = next(
        r for r in candidate["callout_receipts"]
        if r["height_word_ref"] == height_word_ref
    )
    verified = validate_height_receipt(rcp_page, original_receipt)
    if verified["height_mm"] != candidate["height_mm"]:
        raise SourceConflict("rcp_height_zone_value_mismatch")
    return {
        "source_sha256": rcp_page.source_sha256,
        "plan_page_index": plan_page.page_index,
        "rcp_page_index": rcp_page.page_index,
        "item_id": item_id,
        "plan_face_segment_ref": face.ref,
        "plan_room_label_word_ref": label.ref,
        "plan_room_label_text": label.text,
        "rcp_source_rectangle_ref": source_rectangle_ref,
        "rcp_height_word_ref": verified["height_word_ref"],
        "rcp_material_word_ref": verified["material_word_ref"],
        "height_mm": verified["height_mm"],
        "ceiling_material_code_candidate": verified["material_code_candidate"],
        "cross_sheet_correspondence_reviewed": True,
        "physical_wall_role_authenticated": False,
        "physical_ceiling_zone_authenticated": False,
        "wall_finish_to_fcl_authenticated": False,
        "commercial_publishable": False,
        "benchmark_credit": False,
        "official_score": None,
        "status": "REVIEWED_CROSS_SHEET_HEIGHT_LINK_SHADOW",
    }
