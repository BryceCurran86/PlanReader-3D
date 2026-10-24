"""Original-document Q5446 architect-declared floor-plan area handoff.

The source schedule explicitly prints areas for five distinct architectural
categories. This handoff is *not* a net floor area, tiled area, material
measurement, or benchmark-target inference. It makes source-issued, FIRM,
quantity-handoff-only scheduled-area records from a privately authenticated
original document, with no customer projection until an independent physical
scope/measurement-family release is performed.

No source values are estimated from pixels or reconstructed wall geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pb_gpt1_q5446_original_area_schedule_shadow import (
    OriginalAreaScheduleCandidate,
    Q5446SourceAreaScheduleShadow,
    ORIGINAL_ROW_Y_BOUNDS,
    PRINTED_ORIGINAL_ROWS,
    SOURCE_SHA256,
    inspect_original_q5446_printed_area_schedule,
)
from pb_migration_contracts import QuantityEvidence, stable_contract_id
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import (
    SealedSourceClosedRun, SourceClosedRunExportError, seal_source_closed_run,
)

Q5446_PROJECT_ID = "au_qld_q5446_armstrong32_harlequin"
Q5446_DOCUMENT_ID = "q5446_standard_plans_original"
Q5446_ORIGINAL_REVISION_ID = "q5446_sha_" + SOURCE_SHA256[:20]
Q5446_SOURCE_VIEWPORT_ID = "original_page1_printed_areas_schedule"

# These source-plan associations document the ARCHITECT'S PRINTED schedule,
# not a canonical physical room or independently authenticated wall-face ring.
# A consumer must not assume these names prove a unique physical surface.
_PLAN_OWNERS = {
    "ground_floor": ("architectural_ground_floor_level", "2.1", 1),
    "first_floor": ("architectural_first_floor_level", "2.2", 2),
    "porch": ("architectural_ground_floor_porch", "2.1", 1),
    "garage": ("architectural_ground_floor_garage", "2.1", 1),
    "alfresco": ("architectural_ground_floor_alfresco", "2.1", 1),
}


@dataclass(frozen=True)
class OriginalQ5446ArchitecturalAreaHandoff:
    """Source-only FIRM records and the unchanged normal V1 sealed lineage.

    No customer quantity rows and no frozen evaluation results are emitted.
    """
    status: str
    reason_codes: tuple[str, ...]
    quantities: tuple[QuantityEvidence, ...]
    traces: tuple[CommercialTakeoffSourceTrace, ...]
    sealed_run: SealedSourceClosedRun | None = None
    customer_projection_allowed: bool = False


def _blocked(reason: str) -> OriginalQ5446ArchitecturalAreaHandoff:
    return OriginalQ5446ArchitecturalAreaHandoff(
        status="ABSTAIN", reason_codes=(reason,), quantities=(), traces=(),
    )


def _typed_owner(value: object) -> bool:
    return type(value) is str and bool(value) and value == value.strip()


def _issued_row(
    row: OriginalAreaScheduleCandidate, *,
    key: str,
    workspace_id: int,
) -> tuple[QuantityEvidence, CommercialTakeoffSourceTrace]:
    scheduled_category, sheet_number, physical_plan_page = _PLAN_OWNERS[key]
    expected_row = next(
        (i for i, record in enumerate(PRINTED_ORIGINAL_ROWS, 1)
         if record[0] == key),
        None,
    )
    if (
        expected_row is None or row.table_row_number != expected_row
        or row.is_rollup
        or row.printed_area_m2 != PRINTED_ORIGINAL_ROWS[expected_row - 1][2]
        or row.printed_label != PRINTED_ORIGINAL_ROWS[expected_row - 1][1]
    ):
        raise ValueError("original schedule source row is not the intended component")
    # Evidence entity is the ORIGINAL PRINTED SOURCE ROW, not an invented
    # canonical floor polygon. Physical wall/finish owner remains unresolved.
    source_entity = f"q5446_original_source_schedule_{row.original_row_id}"
    # A label-only row is NOT a source-verified numeric area. Both source
    # vectors are independently mandatory; a populated label family may
    # never hide a missing numeric glyph path family in their combined tuple.
    if (
        not row.original_numeric_vector_path_ids
        or not row.original_label_vector_path_ids
    ):
        raise ValueError("original source vector-path families unavailable")
    # Pinned original page-1 native stroke paths; each witness must be
    # individually source-unique, typed and bound to the SHA-verified PDF.
    # Both original numeric glyphs and printed category-label strokes must
    # be present. A populated label alone cannot prove an area value, and
    # numeric glyphs alone cannot prove the source schedule row's category.
    if not row.original_numeric_vector_path_ids or not row.original_label_vector_path_ids:
        raise ValueError("original source vector-path identities unavailable")
    paths = (
        *row.original_numeric_vector_path_ids,
        *row.original_label_vector_path_ids,
    )
    if any(type(p) is not int or p < 0 for p in paths):
        raise ValueError("original source vector-path identities unavailable")
    if len(set(paths)) != len(paths):
        raise ValueError("original source vector-path identities duplicate")
    receipts = tuple(
        f"q5446_original_{SOURCE_SHA256[:20]}_p1_path_{path}"
        for path in paths
    )
    receipts += (f"q5446_original_p1_area_table_row_{row.table_row_number}",)

    value = row.printed_area_m2
    if (
        type(value) is not Decimal
        or value <= Decimal("0")
        or value.as_tuple().exponent != -2
    ):
        raise ValueError("exact original source scheduled m2 is unavailable")
    quantity_id = stable_contract_id(
        "q5446_original_scheduled_area",
        {
            "sha256": SOURCE_SHA256,
            "source_area_category": scheduled_category,
            "row": row.original_row_id,
            "original_numeric_paths": row.original_numeric_vector_path_ids,
        },
        digest_chars=32,
    )
    quantity = QuantityEvidence(
        quantity_id=quantity_id,
        family="architectural_scheduled_area",
        semantic_key=f"architectural_scheduled_area:{source_entity}",
        value=float(value),
        unit="m2",
        input_entity_ids=(source_entity,),
        formula="original_printed_architectural_area_schedule",
        formula_version="1.0.0",
        evidence_ids=receipts,
        authority="original_pdf_explicit_architectural_area_schedule",
        status="firm",
        confidence=1.0,
        abstained=False,
        metadata={
            "project_id": Q5446_PROJECT_ID,
            "document_id": Q5446_DOCUMENT_ID,
            "source_sha256": SOURCE_SHA256,
            "revision_id": Q5446_ORIGINAL_REVISION_ID,
            "workspace_id": workspace_id,
            "source_page": 1,
            "owner_original_plan_page": physical_plan_page,
            "owner_original_sheet_number": sheet_number,
            "original_source_row_id": row.original_row_id,
            "original_source_printed_label": row.printed_label,
            "source_printed_value_m2": str(value),
            "source_printed_category": scheduled_category,
            "canonical_physical_floor_owner_authenticated": False,
            "source_printed_area_semantics": (
                "architectural_area_schedule_not_net_wall_face_or_finish"
            ),
            "numeric_vector_glyphs_original": True,
            "original_area_row_label_strokes": True,
            "commercial_projection_allowed": False,
            "quantity_handoff_only": True,
            "shadow_only": False,
            "source_scope_requires_independent_customer_mapping": True,
        },
    )
    lo, hi = ORIGINAL_ROW_Y_BOUNDS[row.table_row_number - 1]
    trace = CommercialTakeoffSourceTrace(
        workspace_id=workspace_id,
        project_id=Q5446_PROJECT_ID,
        document_id=Q5446_DOCUMENT_ID,
        source_sha256=SOURCE_SHA256,
        source_page="1",
        viewport_id=Q5446_SOURCE_VIEWPORT_ID,
        revision_id=Q5446_ORIGINAL_REVISION_ID,
        current_revision_id=Q5446_ORIGINAL_REVISION_ID,
        evidence_ids=receipts,
        canonical_entity_ids=(source_entity,),
        source_bbox=(979.32, lo, 1147.44, hi),
        metadata={
            "source_role": "architectural_area_schedule",
            "not_net_floor_finish": True,
            "not_customer_release": True,
            "original_area_row_number": row.table_row_number,
            "owner_original_plan_page": physical_plan_page,
        },
    )
    return quantity, trace


def issue_original_q5446_scheduled_area_handoff(
    original_pdf_path: str, *, workspace_id: int,
) -> OriginalQ5446ArchitecturalAreaHandoff:
    """Re-open the exact owner-original PDF, then issue just five source areas.

    Original schedule subtotal and total are reference rollups, not two
    further physical entities. A later customer and frozen-V2 adapter MUST
    establish compatible quantity family and original physical owner first.
    """
    if type(workspace_id) is not int or workspace_id <= 0:
        return _blocked("workspace_identity_unavailable")
    if not _typed_owner(original_pdf_path):
        return _blocked("original_source_path_unavailable")
    report = inspect_original_q5446_printed_area_schedule(original_pdf_path)
    if (
        type(report) is not Q5446SourceAreaScheduleShadow
        or report.status != "CANDIDATE"
        or report.actual_source_sha256 != SOURCE_SHA256
        or report.diagnostic_only is not True
        or len(report.rows) != 7
        or report.printed_floor_subtotal_delta_m2 != Decimal("0.01")
        or report.printed_total_rollup_delta_m2 != Decimal("0.00")
    ):
        return _blocked(
            "original_source_schedule_unverified_or_ambiguous"
        )
    by_key: dict[str, OriginalAreaScheduleCandidate] = {}
    for row in report.rows:
        if (
            type(row) is not OriginalAreaScheduleCandidate
            or row.original_source_sha256 != SOURCE_SHA256
            or row.status != "CANDIDATE"
            or row.customer_projection_allowed is not False
            or row.glyph_correspondence_authenticated is not True
            or row.label_stroke_presence_verified is not True
            or row.physical_surface_owner_authenticated is not False
            or type(row.original_row_id) is not str
            or type(row.table_row_number) is not int
            or not 1 <= row.table_row_number <= 7
        ):
            return _blocked("original_area_row_untrusted")
        key = row.original_row_id.split("_row_" + str(row.table_row_number) + "_")[-1]
        if key in by_key:
            return _blocked("original_area_source_duplicate_row")
        by_key[key] = row
    if set(by_key) != set(_PLAN_OWNERS) | {"subtotal", "total"}:
        return _blocked("original_area_row_universe_incomplete")
    if not by_key["subtotal"].is_rollup or not by_key["total"].is_rollup:
        return _blocked("original_source_rollup_role_inconsistent")
    if any(by_key[key].is_rollup for key in _PLAN_OWNERS):
        return _blocked("original_physical_area_claim_is_rollup")
    if any(
        row.original_row_id != f"q5446_source_p1_area_schedule_row_{i}_{key}"
        or row.table_row_number != i
        for i, (key, row) in enumerate(
            [
                ("ground_floor", by_key["ground_floor"]),
                ("first_floor", by_key["first_floor"]),
                ("subtotal", by_key["subtotal"]),
                ("porch", by_key["porch"]),
                ("garage", by_key["garage"]),
                ("alfresco", by_key["alfresco"]),
                ("total", by_key["total"]),
            ],
            1,
        )
    ):
        return _blocked("original_source_area_row_order_inconsistent")

    try:
        pairs = tuple(
            _issued_row(by_key[key], key=key, workspace_id=workspace_id)
            for key in _PLAN_OWNERS
        )
        quantities = tuple(pair[0] for pair in pairs)
        traces = tuple(pair[1] for pair in pairs)
        # Firm SOURCE-DECLARED quantities only. Customer release remains
        # explicitly false until independent measurement-family mapping.
        sealed_run = seal_source_closed_run(
            quantities,
            project_id=Q5446_PROJECT_ID,
            traces_by_quantity_id={
                quantity.quantity_id: trace
                for quantity, trace in pairs
            },
        )
        if (
            len(sealed_run.quantities) != len(quantities)
            or not all(row.lineage_ok and not row.abstained for row in sealed_run.quantities)
        ):
            return _blocked("original_scheduled_area_seal_lineage_unavailable")
    except (ValueError, TypeError, OverflowError, SourceClosedRunExportError):
        return _blocked("original_scheduled_area_issuer_conflict")

    return OriginalQ5446ArchitecturalAreaHandoff(
        status="SOURCE_FIRM_HANDOFF_ONLY",
        reason_codes=(
            "original_document_and_numeric_vector_schedule_authenticated",
            "architectural_source_declared_area_not_net_floor_finish",
            "customer_and_frozen_family_mapping_not_authorized",
        ),
        quantities=quantities,
        traces=traces,
        sealed_run=sealed_run,
    )
