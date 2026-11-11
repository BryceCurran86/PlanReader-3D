"""Conservative review suggestions from native closed shapes and printed words.

Never promotes a proposed rectangle to an internal wall-face, publishes a
quantity, or silently chooses between equally plausible dimensions.
"""
from __future__ import annotations
from decimal import Decimal
import math
import re
from typing import Any

from .engine import NativePage, _figured_mm, _inside, SourceConflict


def suggest_room_bindings(page: NativePage) -> dict[str, Any]:
    proposals: list[dict[str, Any]] = []
    abstentions: list[dict[str, str]] = []
    words = page.words
    for rect in page.rectangles:
        x0, y0, x1, y1 = rect.bbox
        if x1 <= x0 or y1 <= y0 or not all(math.isfinite(v) for v in rect.bbox):
            continue
        in_box = [w for w in words if _inside(w.bbox, rect.bbox)]
        finishes = [w for w in in_box if re.fullmatch(r"FT\d{1,3}", w.text.strip(), re.I)]
        labels = [w for w in in_box if re.fullmatch(r"[A-Za-z][A-Za-z.]{1,30}", w.text.strip())]
        if not finishes:
            continue
        reason = ""
        if len(finishes) != 1 or len(labels) != 1:
            reason = "non_unique_room_label_or_floor_finish_code"
        horizontal, vertical = [], []
        for w in words:
            if w.ref in {finish.ref for finish in finishes}:
                continue
            try:
                mm = _figured_mm(w)
            except SourceConflict:
                continue
            cx = (w.bbox[0] + w.bbox[2]) / 2
            cy = (w.bbox[1] + w.bbox[3]) / 2
            if x0 <= cx <= x1 and (abs(cy - y0) <= 32 or abs(cy - y1) <= 32):
                horizontal.append(w)
            if y0 <= cy <= y1 and (abs(cx - x0) <= 32 or abs(cx - x1) <= 32):
                vertical.append(w)
        if not reason and (len(horizontal) != 1 or len(vertical) != 1):
            reason = "figured_axis_ambiguous_or_missing"
        if reason:
            abstentions.append({"rectangle_ref": rect.ref, "reason_code": reason})
            continue
        if horizontal[0].ref == vertical[0].ref:
            abstentions.append({"rectangle_ref": rect.ref, "reason_code": "figured_axes_not_independent"})
            continue
        figures = _figured_mm(horizontal[0]) / _figured_mm(vertical[0])
        shape = Decimal(str((x1 - x0) / (y1 - y0)))
        if abs(shape / figures - 1) > Decimal("0.05"):
            abstentions.append({"rectangle_ref": rect.ref, "reason_code": "figured_axes_do_not_match_native_face_shape"})
            continue
        proposals.append({
            "room_id": f"native-{rect.ref}",
            "rectangle_ref": rect.ref,
            "boundary_basis": "REVIEW_REQUIRED",
            "width_word_ref": horizontal[0].ref,
            "height_word_ref": vertical[0].ref,
            "room_label_word_ref": labels[0].ref,
            "finish_word_ref": finishes[0].ref,
        })
    return {
        "schema_version": "0.1.0",
        "source_sha256": page.source_sha256,
        "page_index": page.page_index,
        "rooms": proposals,
        "abstentions": abstentions,
        "human_internal_finished_face_review_required": True,
    }
