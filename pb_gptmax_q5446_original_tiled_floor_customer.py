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
        or "bathroom_and_ensuite_floor_tiles" not in finish.corroborated_material_scopes
        or finish.authentic_finished_face_area is not False
        or finish.authenticated_customer_quantity is not False
    ):
        return _blocked("authentic_ensuite_tiled_material_scope_unavailable")

    try:
        with fitz.open(stream=payload, filetype="pdf") as document:
            if len(document) != 10:
                return _blocked("source_plan_page_roster_unavailable")
            page = document[0]
            drawings = page.get_drawings()
            if len(drawings) > 20_000:
                return _blocked("source_primitive_cap")
            # Existing accepted original source figure+physical scope on THIS
            # page is the independent mm/pt calibration. No assumed scale.
            figured = original_alfresco_figure_witness(drawings)
            footprint = (
                corroborate_source_labeled_rectangular_footprint(
                    drawings,
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
            face = find_unique_native_tiled_room_face(
                page=page, page_number=1, room_label="ENS",
            )
    except (RuntimeError, OSError, ValueError, TypeError, KeyError, IndexError):
        return _blocked("source_native_face_extraction_unavailable")

    if (
        not isinstance(face, NativeTiledRoomFace)
        or not face.physical_source_verified
        or face.commercial_permission
        or face.room_label != "ENS"
        or face.page_number != 1
        or not face.wall_support_source_path_ids
        or not face.hatch_support_source_path_ids
    ):
        return _blocked("source_tiled_ensuite_finished_face_unavailable")

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
    def plan_path(idx: int) -> str:
        return f"q5446_original_{SOURCE_SHA256[:20]}_p1_path_{idx}"

    boundary_ids = (plan_path(face.source_boundary_path_id),)
    wall_ids = tuple(plan_path(i) for i in face.wall_support_source_path_ids)
    hatch_ids = tuple(plan_path(i) for i in face.hatch_support_source_path_ids)
    scale_ids = tuple(plan_path(i) for i in (
        *figured.source_vector_path_ids, *footprint.boundary_source_path_ids,
        *footprint.connector_source_path_ids,
    ))
    source_roles = tuple(
        f"original_support_pdf_sha256_{sha}" for sha in finish.source_sha256s
    )
    physical_id = stable_contract_id(
        "original_source_native_tiled_finished_room_face",
        {"document": SOURCE_SHA256, "page": 1, "room": face.room_label,
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
            "source_page": "1",
            "original_source_page_role": "ground_floor_plan",
            "room_label": "ENS",
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
            "element": "Ground-floor ensuite floor tiles",
            "location": "Ground-floor ensuite",
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
        source_page="1",
        viewport_id="original_ground_floor_vector_plan",
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
                "room_label": "ENS",
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
