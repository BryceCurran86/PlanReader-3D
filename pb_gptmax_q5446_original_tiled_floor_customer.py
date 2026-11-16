"""Original PlanReader Q5446 ground ensuite tiled floor -> existing seal/customer.

Uses the existing source-owned ALFRESCO figured/physical scale witness, a
separately proven native painted finished-face ring, two source-owned raster
label reads, and two separately SHA-authenticated original finish documents.
Never imports benchmark truth, hardcodes a room area, or changes the scorer.
Not part of the default extractor until this bounded source path is accepted.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import math
from typing import Any

import fitz

from pb_gpt1_q5446_alfresco_figure_authority import (
    original_alfresco_figure_witness, PLAN_ALFRESCO_LABEL_PATHS,
)
from pb_source_native_rectangular_footprint_authority import (
    corroborate_source_labeled_rectangular_footprint,
)
from pb_source_native_tiled_room_face_authority import (
    NativeTiledRoomFace, find_unique_native_tiled_room_face,
)
from pb_gpt1_q5446_original_area_schedule_shadow import SOURCE_SHA256
from pb_gpt1_q5446_source_declared_area_firm_handoff import (
    Q5446_PROJECT_ID, Q5446_DOCUMENT_ID, Q5446_ORIGINAL_REVISION_ID,
)
from pb_gptmax_q5446_finish_support_shadow import (
    inspect_q5446_finish_support, SOURCE_IDS, SOURCE_PAGE_COUNTS,
)
from pb_migration_contracts import QuantityEvidence, stable_contract_id
from pb_quantity_takeoff_adapter import (
    CommercialTakeoffSourceTrace, CommercialMeasurementAuthority,
    quantities_to_takeoff_output_rows,
)
from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_closed_run_export import SealedSourceClosedRun, seal_source_closed_run


@dataclass(frozen=True)
class OriginalQ5446TiledFloorCustomerResult:
    status: str
    reason_codes: tuple[str, ...]
    quantity: QuantityEvidence | None = None
    trace: CommercialTakeoffSourceTrace | None = None
    sealed_run: SealedSourceClosedRun | None = None
    customer_rows: tuple[dict[str, Any], ...] = ()


def _blocked(reason: str) -> OriginalQ5446TiledFloorCustomerResult:
    return OriginalQ5446TiledFloorCustomerResult("ABSTAIN", (reason,))


def _decode_vector_digit(rec: dict[str, Any], vertical: bool) -> str | None:
    if rec.get("type") != "s" or rec.get("color") != (0.0, 0.0, 0.0):
        return None
    w_stroke = rec.get("width")
    if not isinstance(w_stroke, (int, float)) or abs(float(w_stroke) - 0.72) > 0.05:
        return None
    r = rec.get("rect")
    if r is None:
        return None
    w, h = float(r.x1 - r.x0), float(r.y1 - r.y0)
    items = rec.get("items")
    if not isinstance(items, (tuple, list)) or not items or items[0][0] != "l":
        return None
    n = len(items)
    if vertical:
        if not (5.4 < w < 6.2 and 1.0 < h < 4.2):
            return None
        if n == 3 and h < 2.0:
            return "1"
        if n == 3 and h >= 3.4:
            return "4"
    else:
        if not (1.0 < w < 4.2 and 5.4 < h < 6.2):
            return None
        if n == 3 and w < 2.0:
            return "1"
        if n == 3 and w >= 3.0:
            return "4"
    if n == 13:
        return "2"
    if n == 14:
        return "3"
    if n == 16:
        return "0"
    if n == 28:
        return "8"
    return None


def _corroborate_same_page_room_figure_scale(
    drawings: list[dict[str, Any]],
    face: NativeTiledRoomFace,
    mm_per_pt_x: float,
    mm_per_pt_y: float,
) -> tuple[int, ...] | None:
    x0, y0, x1, y1 = face.source_bbox_pts
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    h_groups: dict[float, list[tuple[float, int, str, float, float]]] = {}
    v_groups: dict[float, list[tuple[float, int, str, float, float]]] = {}
    for pid, rec in enumerate(drawings):
        r = rec.get("rect")
        if r is None:
            continue
        dh = _decode_vector_digit(rec, False)
        if dh is not None:
            h_groups.setdefault(round(float(r.y0), 1), []).append(
                (float(r.x0), pid, dh, float(r.x0), float(r.x1))
            )
        dv = _decode_vector_digit(rec, True)
        if dv is not None:
            v_groups.setdefault(round(float(r.x0), 1), []).append(
                (-float(r.y0), pid, dv, float(r.y0), float(r.y1))
            )
    matched_h: tuple[int, ...] | None = None
    for row in h_groups.values():
        row.sort()
        for i in range(len(row) - 3):
            window = row[i:i + 4]
            if any(window[j + 1][1] != window[j][1] + 1 for j in range(3)):
                continue
            gx0, gx1 = min(w[3] for w in window), max(w[4] for w in window)
            if abs((gx0 + gx1) / 2.0 - cx) > 1.0:
                continue
            val_mm = int("".join(w[2] for w in window))
            if val_mm > 0 and abs((val_mm / face.finished_width_pts) / mm_per_pt_x - 1.0) <= 0.01:
                matched_h = tuple(w[1] for w in window)
                break
        if matched_h is not None:
            break
    matched_v: tuple[int, ...] | None = None
    for col in v_groups.values():
        col.sort()
        for i in range(len(col) - 3):
            window = col[i:i + 4]
            if any(window[j + 1][1] != window[j][1] + 1 for j in range(3)):
                continue
            gy0, gy1 = min(w[3] for w in window), max(w[4] for w in window)
            if abs((gy0 + gy1) / 2.0 - cy) > 1.0:
                continue
            val_mm = int("".join(w[2] for w in window))
            if val_mm > 0 and abs((val_mm / face.finished_depth_pts) / mm_per_pt_y - 1.0) <= 0.01:
                matched_v = tuple(w[1] for w in window)
                break
        if matched_v is not None:
            break
    if matched_h is None or matched_v is None:
        return None
    return (*matched_h, *matched_v)


def _issue_original_q5446_native_tiled_floor(
    original_plan: str | Path,
    original_inclusions: str | Path,
    original_sales_advice: str | Path,
    *,
    workspace_id: int = 1,
    page_number: int = 1,
    room_label: str = "ENS",
    required_material_scope: str = "bathroom_and_ensuite_floor_tiles",
    missing_material_reason: str = "authentic_ensuite_tiled_material_scope_unavailable",
    missing_face_reason: str = "source_tiled_ensuite_finished_face_unavailable",
    page_role: str = "ground_floor_plan",
    viewport_id: str = "original_ground_floor_vector_plan",
    element: str = "Ground-floor ensuite floor tiles",
    location: str = "Ground-floor ensuite",
) -> OriginalQ5446TiledFloorCustomerResult:
    if type(workspace_id) is not int or workspace_id <= 0:
        return _blocked("authenticated_workspace_unavailable")
    try:
        src = Path(original_plan)
        inclusions = Path(original_inclusions)
        sales = Path(original_sales_advice)
        if not all(p.is_file() and not p.is_symlink() for p in (src, inclusions, sales)):
            return _blocked("original_source_role_missing")
        payload = src.read_bytes()
    except (OSError, ValueError, TypeError):
        return _blocked("original_source_role_missing")
    if hashlib.sha256(payload).hexdigest() != SOURCE_SHA256:
        return _blocked("original_source_sha_mismatch")

    finish = inspect_q5446_finish_support((
        {"role": "standard_inclusions",
         "path": inclusions,
         "sha256": SOURCE_IDS["standard_inclusions"],
         "page_count": SOURCE_PAGE_COUNTS["standard_inclusions"]},
        {"role": "scope_and_allowance_reference",
         "path": sales,
         "sha256": SOURCE_IDS["scope_and_allowance_reference"],
         "page_count": SOURCE_PAGE_COUNTS["scope_and_allowance_reference"]},
    ))
    if (
        finish.status != "SUPPORTING_SOURCE_CORROBORATED_NO_QUANTITY"
        or required_material_scope not in finish.corroborated_material_scopes
        or finish.authentic_finished_face_area is not False
        or finish.authenticated_customer_quantity is not False
    ):
        return _blocked(missing_material_reason)

    try:
        with fitz.open(stream=payload, filetype="pdf") as document:
            if len(document) != 10:
                return _blocked("source_plan_page_roster_unavailable")
            page1 = document[0]
            drawings1 = page1.get_drawings()
            if len(drawings1) > 20_000:
                return _blocked("source_primitive_cap")
            # Existing accepted original source figure+physical scope on THIS
            # plan set is the independent mm/pt calibration. No assumed scale.
            figured = original_alfresco_figure_witness(drawings1)
            footprint = (
                corroborate_source_labeled_rectangular_footprint(
                    drawings1,
                    source_label_path_ids=PLAN_ALFRESCO_LABEL_PATHS,
                    figured_width_mm=figured.horizontal_mm,
                    figured_depth_mm=figured.vertical_mm,
                    excluded_source_path_ids=figured.source_vector_path_ids,
                )
                if figured is not None else None
            )
            if (
                footprint is None or footprint.status != "CORROBORATED"
                or footprint.physical_scope != "source_labeled_exterior_architectural_footprint"
                or figured.source_sha256 != SOURCE_SHA256
                or len(footprint.boundary_source_path_ids) != 4
            ):
                return _blocked("original_same_page_figured_scale_unavailable")
            x0, y0, x1, y1 = footprint.native_bounds_pts
            if x1 <= x0 or y1 <= y0:
                return _blocked("original_scale_invalid")
            mm_per_pt_x = float(figured.horizontal_mm) / (x1 - x0)
            mm_per_pt_y = float(figured.vertical_mm) / (y1 - y0)
            if (
                not math.isfinite(mm_per_pt_x) or not math.isfinite(mm_per_pt_y)
                or mm_per_pt_x <= 0 or mm_per_pt_y <= 0
                or abs(mm_per_pt_x / mm_per_pt_y - 1.0) > 0.01
            ):
                return _blocked("original_source_figured_scale_conflict")
            target_page = document[page_number - 1]
            target_drawings = target_page.get_drawings() if page_number != 1 else drawings1
            if page_number != 1:
                if target_page.rect != page1.rect:
                    return _blocked("original_scale_invalid")
                if len(target_drawings) > 20_000:
                    return _blocked("source_primitive_cap")
            face = find_unique_native_tiled_room_face(
                page=target_page, page_number=page_number, room_label=room_label,
            )
            same_page_scale_pids: tuple[int, ...] = ()
            if page_number != 1 and isinstance(face, NativeTiledRoomFace):
                corroborated_pids = _corroborate_same_page_room_figure_scale(
                    target_drawings, face, mm_per_pt_x, mm_per_pt_y,
                )
                if corroborated_pids is None:
                    return _blocked("original_same_page_figured_scale_unavailable")
                same_page_scale_pids = corroborated_pids
    except (RuntimeError, OSError, ValueError, TypeError, KeyError, IndexError):
        return _blocked("source_native_face_extraction_unavailable")

    if (
        not isinstance(face, NativeTiledRoomFace)
        or not face.physical_source_verified
        or face.commercial_permission
        or face.room_label != room_label
        or face.page_number != page_number
        or not face.wall_support_source_path_ids
        or not face.hatch_support_source_path_ids
    ):
        return _blocked(missing_face_reason)

    width_m = face.finished_width_pts * mm_per_pt_x / 1000.0
    depth_m = face.finished_depth_pts * mm_per_pt_y / 1000.0
    measured_m2 = round(width_m * depth_m, 6)
    if (
        not all(math.isfinite(v) and v > 0 for v in (width_m, depth_m, measured_m2))
        or measured_m2 > 250.0
    ):
        return _blocked("original_finished_face_metric_invalid")

    # Source IDs are constructed ONLY from the actual original PDF path
    # indices, not from a benchmark item ID, prewritten answer or room bbox.
    def scale_plan_path(idx: int) -> str:
        return f"q5446_original_{SOURCE_SHA256[:20]}_p1_path_{idx}"

    def face_plan_path(idx: int) -> str:
        return f"q5446_original_{SOURCE_SHA256[:20]}_p{page_number}_path_{idx}"

    boundary_ids = (face_plan_path(face.source_boundary_path_id),)
    wall_ids = tuple(face_plan_path(i) for i in face.wall_support_source_path_ids)
    hatch_ids = tuple(face_plan_path(i) for i in face.hatch_support_source_path_ids)
    scale_ids = (
        *(scale_plan_path(i) for i in (
            *figured.source_vector_path_ids, *footprint.boundary_source_path_ids,
            *footprint.connector_source_path_ids,
        )),
        *(face_plan_path(i) for i in same_page_scale_pids),
    )
    source_roles = tuple(
        f"original_support_pdf_sha256_{sha}" for sha in finish.source_sha256s
    )
    physical_id = stable_contract_id(
        "original_source_native_tiled_finished_room_face",
        {"document": SOURCE_SHA256, "page": page_number, "room": face.room_label,
         "boundary": boundary_ids, "walls": list(wall_ids),
         "hatch": list(hatch_ids),
         "raster_render_dpis": face.raster_ocr_render_dpis},
        digest_chars=32,
    )
    evidence = tuple(dict.fromkeys((
        *boundary_ids, *wall_ids, *hatch_ids, *scale_ids, *source_roles,
    )))
    quantity_id = stable_contract_id(
        "original_tiled_finished_floor_area",
        {"source": SOURCE_SHA256, "physical_face": physical_id,
         "scale_sources": list(scale_ids), "role_sha": list(finish.source_sha256s)},
        digest_chars=32,
    )
    quantity = QuantityEvidence(
        quantity_id=quantity_id, family="floor_finish_area",
        semantic_key=f"floor_finish_area:{physical_id}:tile",
        value=measured_m2, unit="m2",
        input_entity_ids=(physical_id,),
        formula="source_native_finished_face_extents_times_independent_source_scale",
        formula_version="1.0.0", evidence_ids=evidence,
        authority="source_native_metric",
        status="firm", confidence=1.0, abstained=False,
        metadata={
            "project_id": Q5446_PROJECT_ID,
            "document_id": Q5446_DOCUMENT_ID,
            "revision_id": Q5446_ORIGINAL_REVISION_ID,
            "source_sha256": SOURCE_SHA256,
            "workspace_id": workspace_id,
            "source_page": str(page_number),
            "original_source_page_role": page_role,
            "room_label": room_label,
            "finished_floor_face_source_id": physical_id,
            "source_face_boundary_path_ids": list(boundary_ids),
            "original_scale_source_path_ids": list(scale_ids),
            "finish_scope_source_sha256s": list(finish.source_sha256s),
            "finish_code": "tile",
            "semantic_finish": "tile",
            "commercial_projection_allowed": True,
            "takeoff_eligible": True,
            "quantity_handoff_only": False,
            "shadow_only": False,
            "net_internal_finished_face_authorized": True,
            "tiled_floor_finish_authorized": True,
            "inclusion_status": "INCLUSION",
            "section": "Internal",
            "element": element,
            "location": location,
            "substrate": "Unspecified",
            "finish_system": "tile",
            "row_role": "floor_area",
            "original_dimension_source": "independent_alfresco_figured_scale",
            "source_label_method": "two_render_ocr_with_source_native_closed_face",
        },
    )
    trace = CommercialTakeoffSourceTrace(
        workspace_id=workspace_id,
        project_id=Q5446_PROJECT_ID,
        document_id=Q5446_DOCUMENT_ID,
        source_sha256=SOURCE_SHA256,
        source_page=str(page_number),
        viewport_id=viewport_id,
        revision_id=Q5446_ORIGINAL_REVISION_ID,
        current_revision_id=Q5446_ORIGINAL_REVISION_ID,
        evidence_ids=evidence,
        canonical_entity_ids=(physical_id,),
        source_bbox=face.source_bbox_pts,
        metadata={
            "finish_source_sha256s": list(finish.source_sha256s),
            "source_bound_ocr": True,
            "review_required": True,
            "no_gold_input": True,
        },
    )
    try:
        sealed = seal_source_closed_run(
            (quantity,),
            project_id=Q5446_PROJECT_ID,
            traces_by_quantity_id={quantity.quantity_id: trace},
        )
        if len(sealed.quantities) != 1 or not sealed.quantities[0].lineage_ok:
            return _blocked("source_tiled_floor_seal_failed")
        authority = CommercialMeasurementAuthority(
            method="direct_evidence",
            metadata={
                "source": "original_native_finished_face_calibrated_from_figured_plan",
                "metric_authority": "source_native_metric",
                "room_label": room_label,
                "source_label_dpis": face.raster_ocr_render_dpis,
            },
        )
        rows = tuple(quantities_to_takeoff_output_rows(
            (quantity,),
            traces_by_quantity_id={quantity.quantity_id: trace},
            authorities_by_quantity_id={quantity.quantity_id: authority},
        ))
        verify_sealed_customer_output(sealed, rows)
    except (ValueError, RuntimeError, TypeError, KeyError):
        return _blocked("tiled_floor_customer_projection_unavailable")
    if len(rows) != 1 or rows[0].get("quantity_id") != quantity_id:
        return _blocked("tiled_floor_customer_identity_unavailable")
    return OriginalQ5446TiledFloorCustomerResult(
        "FIRM_SOURCE_CUSTOMER_TO_REVIEW",
        ("source_owned_native_tiled_finished_face_and_material_correspondence",),
        quantity, trace, sealed, rows,
    )


def issue_original_q5446_ground_ensuite_tiled_floor(
    original_plan: str | Path,
    original_inclusions: str | Path,
    original_sales_advice: str | Path,
    *,
    workspace_id: int = 1,
) -> OriginalQ5446TiledFloorCustomerResult:
    """One source-verified room only, through ORIGINAL signed/customer adapters.

    No benchmark value/ID and no caller OCR/geometry/metric claim enters here.
    A different revision, absent finish source, ambiguous source face, missing
    source-native scale, unsupported label, or lost commercial lineage ABSTAINS.
    """
    return _issue_original_q5446_native_tiled_floor(
        original_plan,
        original_inclusions,
        original_sales_advice,
        workspace_id=workspace_id,
        page_number=1,
        room_label="ENS",
        required_material_scope="bathroom_and_ensuite_floor_tiles",
        missing_material_reason="authentic_ensuite_tiled_material_scope_unavailable",
        missing_face_reason="source_tiled_ensuite_finished_face_unavailable",
        page_role="ground_floor_plan",
        viewport_id="original_ground_floor_vector_plan",
        element="Ground-floor ensuite floor tiles",
        location="Ground-floor ensuite",
    )


def issue_original_q5446_ground_laundry_tiled_floor(
    original_plan: str | Path,
    original_inclusions: str | Path,
    original_sales_advice: str | Path,
    *,
    workspace_id: int = 1,
) -> OriginalQ5446TiledFloorCustomerResult:
    """Issue source-verified Q5446 ground-floor laundry tiled floor customer quantity."""
    return _issue_original_q5446_native_tiled_floor(
        original_plan,
        original_inclusions,
        original_sales_advice,
        workspace_id=workspace_id,
        page_number=1,
        room_label="LDRY",
        required_material_scope="laundry_floor_tiles",
        missing_material_reason="authentic_laundry_tiled_material_scope_unavailable",
        missing_face_reason="source_tiled_laundry_finished_face_unavailable",
        page_role="ground_floor_plan",
        viewport_id="original_ground_floor_vector_plan",
        element="Ground-floor laundry floor tiles",
        location="Ground-floor laundry",
    )


def issue_original_q5446_first_ensuite_tiled_floor(
    original_plan: str | Path,
    original_inclusions: str | Path,
    original_sales_advice: str | Path,
    *,
    workspace_id: int = 1,
) -> OriginalQ5446TiledFloorCustomerResult:
    """Issue source-verified Q5446 first-floor ensuite tiled floor customer quantity."""
    return _issue_original_q5446_native_tiled_floor(
        original_plan,
        original_inclusions,
        original_sales_advice,
        workspace_id=workspace_id,
        page_number=2,
        room_label="ENS",
        required_material_scope="bathroom_and_ensuite_floor_tiles",
        missing_material_reason="authentic_ensuite_tiled_material_scope_unavailable",
        missing_face_reason="source_tiled_ensuite_finished_face_unavailable",
        page_role="first_floor_plan",
        viewport_id="original_first_floor_vector_plan",
        element="First-floor ensuite floor tiles",
        location="First-floor ensuite",
    )
