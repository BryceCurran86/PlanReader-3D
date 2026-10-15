"""Source-SHA checked original/proposed RCP viewport first-gate ledger.

Diagnostic only. Neither a title nor a derived sibling viewport proves an
original plan viewport or any material occurrence/metric quantity.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import fitz
from pb_drawing_evidence_binding import DrawingViewType
from pb_viewport_segmentation import (
    segment_page_viewports, is_authoritative_derived_viewport,
    validate_non_overlapping_viewports, calibrate_viewport_layout,
    extract_vector_frames, extract_view_title_anchors, _frame_candidates_for_title,
)

def _producer_token(value) -> str:
    """Preserve the producer's enum value instead of its Python enum name."""
    owned=getattr(value,"value",value)
    return owned if isinstance(owned,str) else ""


def _title_identity(label, anchor) -> bool:
    """Only compare explicitly matching native source title identities."""
    return (
        isinstance(label,str) and isinstance(anchor,str)
        and bool(label.strip()) and bool(anchor.strip())
        and " ".join(label.upper().split())==" ".join(anchor.upper().split())
    )


def _nearest_native_frames_to_title(title_bbox, frames, *, limit=4):
    """Rank original vector frames by source-native distance, never ownership.

    Exact native geometry only. No guessed offsets, title-to-frame binding,
    viewport construction, room finish attribution, or metric area authority.
    """
    import math
    try:
        t=tuple(float(v) for v in title_bbox)
    except (TypeError,ValueError,OverflowError):
        return []
    if len(t)!=4 or not all(math.isfinite(v) for v in t) or t[2]<=t[0] or t[3]<=t[1]:
        return []
    result=[]
    for raw in frames:
        try:
            box=tuple(float(v) for v in raw)
        except (TypeError,ValueError,OverflowError):
            continue
        if len(box)!=4 or not all(math.isfinite(v) for v in box) or box[2]<=box[0] or box[3]<=box[1]:
            continue
        dx=max(t[0]-box[2],box[0]-t[2],0.0)
        dy=max(t[1]-box[3],box[1]-t[3],0.0)
        distance=math.hypot(dx,dy)
        if not math.isfinite(distance):
            continue
        result.append({
            "frame_bbox_native_pdf_pts":list(box),
            "title_to_frame_native_distance_pdf_pts":round(distance,6),
            "original_vector_frame_not_title_owned":True,
        })
    return sorted(result,key=lambda row:(
        row["title_to_frame_native_distance_pdf_pts"],
        row["frame_bbox_native_pdf_pts"],
    ))[:limit]


def _frame_source_receipts(page, frame, calibration):
    """Keep *all* indexed native candidate owners for a detected frame.

    This uses the extractor's existing deduplication tolerance to associate
    source-native shapes for audit; proximity is NOT identity/role authority.
    """
    import math
    from pb_viewport_segmentation import (
        _closed_four_line_rect, _axis_aligned_quad_bbox,
    )
    tol = max(calibration.median_word_height_pt * 0.15, 0.75)
    dedup_eps = max(calibration.median_word_height_pt * 0.1, 0.25)
    result = []
    try:
        drawings = page.get_drawings() or ()
    except (AttributeError, RuntimeError, ValueError):
        return []
    for path_id, drawing in enumerate(drawings):
        items = drawing.get("items", ()) or ()
        candidates = []
        closed = _closed_four_line_rect(items, tol=tol)
        if closed is not None:
            candidates.append((closed, tuple(f"d{path_id}i{i}" for i in range(4)), "four_line_closed"))
        for item_id, item in enumerate(items):
            if not item or len(item) < 2:
                continue
            bbox = None
            if item[0] == "re":
                rect = item[1]
                bbox = (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))
            elif item[0] == "qu":
                bbox = _axis_aligned_quad_bbox(item[1], tol=tol)
            if bbox is not None:
                candidates.append((bbox, (f"d{path_id}i{item_id}",), str(item[0])))
        for candidate_bbox, source_ids, kind in candidates:
            try:
                box = tuple(float(v) for v in candidate_bbox)
                if (len(box) != 4 or not all(math.isfinite(v) for v in box)
                    or box[2] <= box[0] or box[3] <= box[1]):
                    continue
            except (TypeError, ValueError, OverflowError):
                continue
            if all(abs(box[i] - frame[i]) <= dedup_eps for i in range(4)):
                result.append({
                    "native_source_ids": list(source_ids),
                    "source_primitive_kind": kind,
                    "raw_native_bbox_pdf_pts": list(box),
                    "candidate_source_match_not_authority": True,
                })
    return sorted(result, key=lambda row: (
        tuple(row["native_source_ids"]), row["source_primitive_kind"],
        tuple(row["raw_native_bbox_pdf_pts"]),
    ))


def _frame_ownership_matrix(page, frames, anchors, calibration):
    """Expose native/display geometry, all title rivals and typed negatives."""
    from pb_viewport_segmentation import (
        _to_visual_bbox, _rejected_ownership_frame, _text_fragments,
    )
    fragments = _text_fragments(page)
    by_title = []
    all_candidates = []
    for idx, anchor in enumerate(anchors):
        candidates = _frame_candidates_for_title(
            page, anchor, frames, calibration, anchors=anchors,
        )
        all_candidates.append(set(candidates))
        by_title.append({
            "source_anchor_ordinal": idx,
            "reported_view_id": f"view_p9_{idx+1}",
            "native_title": str(anchor.text),
            "native_title_bbox_pdf_pts": list(anchor.bbox),
            "display_title_bbox_pdf_pts": list(_to_visual_bbox(page, anchor.bbox)),
            "native_direction": list(anchor.direction),
            "view_type": str(anchor.view_type),
            "geometric_frame_candidate_count": len(candidates),
            "no_source_role_or_viewport_granted": True,
        })
    frame_rows = []
    for idx, frame in enumerate(frames):
        rivals = []
        for owner_idx, anchor in enumerate(anchors):
            if frame in all_candidates[owner_idx]:
                rivals.append({
                    "source_anchor_ordinal": owner_idx,
                    "view_id": f"view_p9_{owner_idx+1}",
                    "native_title": str(anchor.text),
                    "view_type": str(anchor.view_type),
                    "production_frame_rejected_for_this_view_type": bool(
                        _rejected_ownership_frame(
                            page, frame, calibration, fragments,
                            view_type=anchor.view_type,
                        )
                    ),
                })
        frame_rows.append({
            "source_frame_ordinal": idx,
            "native_frame_bbox_pdf_pts": list(frame),
            "display_frame_bbox_pdf_pts": list(_to_visual_bbox(page, frame)),
            "candidate_native_source_receipts": _frame_source_receipts(
                page, frame, calibration,
            ),
            "candidate_title_rivals": rivals,
            "no_source_role_or_viewport_granted": True,
        })
    return {
        "source_titles": by_title,
        "source_frames": frame_rows,
        "diagnostic_only": True,
        "frame_candidate_matrix_grants_authority": False,
    }


PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SOURCE_SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"

def audit(source: bytes) -> dict:
    sha=hashlib.sha256(source).hexdigest()
    if sha!=SOURCE_SHA:
        raise ValueError("source_sha_mismatch")
    doc=fitz.open(stream=source,filetype="pdf")
    try:
        if len(doc)!=31:
            raise ValueError("source_page_universe_mismatch")
        page=doc[8]  # Authenticated source page number 9.
        views=segment_page_viewports(page,page_number=9)
        nonoverlap=validate_non_overlapping_viewports(views)
        calibration=calibrate_viewport_layout(page)
        title_anchors=extract_view_title_anchors(page)
        source_frames=extract_vector_frames(page,calibration)
        source_frame_ownership_matrix=_frame_ownership_matrix(
            page,source_frames,title_anchors,calibration,
        )
        title_frame_candidates={}
        for index,anchor in enumerate(title_anchors):
            view_id=f"view_p9_{index+1}"
            candidates=_frame_candidates_for_title(
                page,anchor,source_frames,calibration,anchors=title_anchors
            )
            title_frame_candidates[view_id]={
                "title":str(anchor.text),
                "title_bbox_pdf_pts":list(anchor.bbox),
                "title_native_direction":list(anchor.direction),
                "qualifying_candidate_frame_count":len(candidates),
                "qualifying_candidate_frames_pdf_pts":[list(box) for box in candidates],
                "candidate_geometry_grants_authority":False,
                "nearest_unowned_native_vector_frames":_nearest_native_frames_to_title(
                    anchor.bbox,source_frames,
                ),
                "nearest_frame_does_not_prove_viewport_boundary":True,
            }
        rows=[]
        for v in views:
            status=_producer_token(getattr(v,"status",None))
            typ=_producer_token(getattr(v,"view_type",None))
            rows.append({
                "view_id":str(v.view_id),
                "label":str(v.label),
                "view_type":typ,
                "status":status,
                "boundary_source":str(v.boundary_source),
                "bounding_box_pdf_pts":None if v.bounding_box is None else list(v.bounding_box),
                "authoritative_derived":bool(is_authoritative_derived_viewport(v)),
            })
        for row in rows:
            frame_data=title_frame_candidates.get(row["view_id"])
            if frame_data is None:
                row["title_frame_first_gate"] = "source_title_anchor_missing"
            elif not _title_identity(row["label"],frame_data["title"]):
                # An anchor's enumerated index cannot prove that it owns
                # this segmented viewport. Never borrow a sibling title.
                row["title_frame_first_gate"] = "source_title_anchor_identity_unverified"
            else:
                row["title_frame_first_gate"] = (
                    "no_source_title_owned_vector_frame"
                    if not frame_data["qualifying_candidate_frame_count"]
                    else "candidate_frame_requires_full_producer_ownership"
                )
            row["first_authority_gate"] = (
                "nonoverlapping_viewports_unproven" if not nonoverlap else
                "missing_source_viewport_boundary" if row["bounding_box_pdf_pts"] is None else
                "source_viewport_resolved" if row["status"].lower().split(".")[-1] == "resolved" else
                "source_derived_viewport_authenticated" if row["authoritative_derived"] else
                "derived_or_ambiguous_viewport_not_authenticated"
            )
        rcps=[row for row in rows if row["view_type"]==DrawingViewType.REFLECTED_CEILING_PLAN.value]
        authoritative=[row for row in rcps if
            nonoverlap
            and row["bounding_box_pdf_pts"] is not None
            and row["first_authority_gate"] in (
                "source_viewport_resolved",
                "source_derived_viewport_authenticated",
            )
        ]
        return {
            "source_sha256":sha, "source_page_number":9,
            "source_page_rotation_degrees":int(page.rotation),
            "native_frame_count":len(source_frames),
            "original_native_frame_ownership_matrix":source_frame_ownership_matrix,
            "title_frame_candidates":title_frame_candidates,
            "non_overlapping_source_viewports":bool(nonoverlap),
            "rcp_rows":rcps,"all_viewports":rows,
            "original_view_p9_2_first_gate":next((
                row["first_authority_gate"] for row in rows
                if row["view_id"] == "view_p9_2"
            ), "source_viewport_record_absent"),
            "authenticated_rcp_count":len(authoritative) if nonoverlap else 0,
            "original_rcp_view_p9_2_authenticated":bool(nonoverlap and any(row["view_id"]=="view_p9_2" for row in authoritative)),
            "material_occurrences_published":0,
            "metric_quantities_published":0,
            "diagnostic_only":True,
        }
    finally:
        doc.close()

if __name__=="__main__":
    print("GPT2_PAGE9_ORIGINAL_RCP_FIRST_GATES",json.dumps(audit(PDF.read_bytes()),sort_keys=True))
