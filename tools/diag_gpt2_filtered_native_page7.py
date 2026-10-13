"""Original-source ONLY first-gate receipt for native lines removed before W2.

Diagnostic/hand-off, not permission to restore filtered drafting primitives as
structural walls. Emits exact native identities and coordinates rather than
source-word/name or nearest-edge guessed lineage.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

from pb_drawing_evidence_binding import DrawingViewType
from pb_filtered_native_primitive_receipts import filtered_native_primitive_receipts
from pb_physical_wall_candidate_authority import (
    _filter_repeated_non_physical_drafting_primitives,
)
from pb_vector_geometry_v130 import extract_native_page
from pb_viewport_segmentation import (
    segment_page_viewports,
    validate_non_overlapping_viewports,
)

SOURCE_PATH = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SOURCE_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
PAGE_INDEX = 6
ORIGINAL_NATIVE_IDS = ("d50057i0", "d50507i0", "d50048i0")


def collect_page7_filtered_native_receipt() -> dict[str, object]:
    payload = SOURCE_PATH.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    if sha != SOURCE_SHA:
        raise RuntimeError("original_maryborough_source_sha_conflict")
    pdf = fitz.open(stream=payload, filetype="pdf")
    try:
        if pdf.page_count != 31:
            raise RuntimeError("original_maryborough_page_universe_conflict")
        page = pdf.load_page(PAGE_INDEX)
        native = extract_native_page(page)
        views = tuple(segment_page_viewports(page, page_number=7))
        if not validate_non_overlapping_viewports(views):
            raise RuntimeError("source_viewport_overlap")
        floor = tuple(
            v for v in views
            if v.view_type == DrawingViewType.FLOOR_PLAN.value
            and v.status == "resolved"
            and v.bounding_box is not None
        )
        if len(floor) != 1:
            raise RuntimeError("source_floor_viewport_unavailable")
        x0, y0, x1, y1 = map(float, floor[0].bounding_box)

        # Explicit producer-owned original source-line containment only.
        # This is a strict diagnostic subset of the authenticated viewport,
        # not a replacement for the W4 producer's own source partition.
        original = tuple(
            row for row in native["segments"]
            if x0 <= row["x1"] <= x1 and x0 <= row["x2"] <= x1
            and y0 <= row["y1"] <= y1 and y0 <= row["y2"] <= y1
        )
        retained = _filter_repeated_non_physical_drafting_primitives(
            original, page_width=page.rect.width, page_height=page.rect.height
        )
        excluded = filtered_native_primitive_receipts(original, retained)
        excluded_by_id = {item.source_id: item for item in excluded}
        original_by_id = {}
        for row in original:
            key = row.get("id")
            if type(key) is not str or not key or key in original_by_id:
                raise RuntimeError("native_original_source_identity_collision")
            original_by_id[key] = row
        retained_ids = {row["id"] for row in retained}
        if len(retained_ids) != len(retained):
            raise RuntimeError("native_retained_source_identity_collision")
        if (not retained_ids <= set(original_by_id)
                or len(excluded_by_id) != len(excluded)):
            raise RuntimeError("native_filter_receipt_unavailable")

        targets = []
        for original_id in ORIGINAL_NATIVE_IDS:
            row = original_by_id.get(original_id)
            if row is None:
                raise RuntimeError("native_original_source_target_missing:" + original_id)
            if row.get("kind") != "line":
                raise RuntimeError("native_original_source_target_non_line:" + original_id)
            observed = excluded_by_id.get(original_id)
            status = (
                "EXCLUDED_NATIVE_CANDIDATE_ONLY" if observed is not None
                else "RETAINED_OR_OTHER_FILTER_NONCANDIDATE"
            )
            targets.append({
                "original_source_id": original_id,
                "source_path_index": row["path_index"],
                "exact_original_geometry": [
                    row["x1"], row["y1"], row["x2"], row["y2"]
                ],
                "original_stroke": row.get("stroke"),
                "original_width_pt": row.get("width"),
                "source_filter_disposition": status,
                "read_only_receipt_status": (
                    observed.status if observed is not None else None
                ),
                "physical_wall_proven": False,
                "two_sided_source_room_owner_proven": False,
                "new_firm_quantity_produced": False,
            })
        return {
            "source_sha256": sha,
            "original_page_number": 7,
            "authenticated_floor_viewport_id": floor[0].view_id,
            "source_native_original_viewport_segment_count": len(original),
            "source_filter_retained_segment_count": len(retained),
            "filtered_native_line_receipt_count": len(excluded),
            "targets": targets,
            "source_wall_role_authenticated_by_diagnostic": False,
            "source_room_geometry_published_by_diagnostic": False,
            "firm_quantity_published_by_diagnostic": False,
            "benchmark_accuracy_granted": False,
        }
    finally:
        pdf.close()


if __name__ == "__main__":
    print(json.dumps(collect_page7_filtered_native_receipt(), sort_keys=True))
