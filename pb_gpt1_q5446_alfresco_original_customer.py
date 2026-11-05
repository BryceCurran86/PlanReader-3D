"""Q5446 original-source ALFRESCO architectural footprint -> customer row.

Two independent original measurements must agree: the printed source-owned
architectural area-schedule row, and the native outlined figured width/depth
of the *same named external bay*. This publishes only the scheduled alfresco
ground-floor footprint. It never claims net wall-face tiling, a ceiling, an
opening, a concrete thickness or estimator-approved commercial scope.
No evaluator item ID or reference quantity enters this production module.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
from pathlib import Path
from typing import Any

from pb_gpt1_q5446_alfresco_figure_authority import (
    OriginalAlfrescoFigureWitness, original_alfresco_figure_witness,
)
from pb_gpt1_q5446_original_area_schedule_shadow import SOURCE_SHA256
from pb_gpt1_q5446_source_declared_area_firm_handoff import (
    Q5446_PROJECT_ID, Q5446_DOCUMENT_ID, Q5446_ORIGINAL_REVISION_ID,
    issue_original_q5446_scheduled_area_handoff,
)
from pb_migration_contracts import QuantityEvidence, stable_contract_id
from pb_quantity_takeoff_adapter import (
    CommercialTakeoffSourceTrace, CommercialMeasurementAuthority,
    quantities_to_takeoff_output_rows,
)
from pb_source_closed_run_export import SealedSourceClosedRun, seal_source_closed_run
from pb_customer_output_verification import verify_sealed_customer_output


@dataclass(frozen=True)
class OriginalQ5446AlfrescoCustomerResult:
    status: str
    reason_codes: tuple[str, ...]
    quantity: QuantityEvidence | None = None
    trace: CommercialTakeoffSourceTrace | None = None
    sealed_run: SealedSourceClosedRun | None = None
    customer_rows: tuple[dict[str, Any], ...] = ()


def _blocked(code: str) -> OriginalQ5446AlfrescoCustomerResult:
    return OriginalQ5446AlfrescoCustomerResult("ABSTAIN", (code,))


def issue_original_q5446_alfresco_customer_area(
    original_pdf_path: str, *, workspace_id: int,
) -> OriginalQ5446AlfrescoCustomerResult:
    """Source-check architect's ALFRESCO footprint, then use existing adapters."""
    if type(original_pdf_path) is not str or not original_pdf_path.strip():
        return _blocked("source_path_unavailable")
    if type(workspace_id) is not int or workspace_id <= 0:
        return _blocked("authenticated_workspace_unavailable")

    # Existing source issuer rechecks original SHA and the complete printed
    # table; it does NOT itself permit commercial projection.
    source = issue_original_q5446_scheduled_area_handoff(
        original_pdf_path, workspace_id=workspace_id,
    )
    if (
        source.status != "SOURCE_FIRM_HANDOFF_ONLY"
        or len(source.quantities) != 5 or source.sealed_run is None
        or any(not r.lineage_ok or r.abstained for r in source.sealed_run.quantities)
    ):
        return _blocked("original_source_area_schedule_not_sealed")
    original = tuple(
        q for q in source.quantities
        if q.metadata.get("source_printed_category") == "architectural_ground_floor_alfresco"
    )
    if len(original) != 1:
        return _blocked("original_alfresco_schedule_owner_ambiguous")
    source_q = original[0]
    if (
        type(source_q) is not QuantityEvidence
        or source_q.family != "architectural_scheduled_area"
        or source_q.status != "firm"
        or source_q.abstained or source_q.blocking_reasons
        or source_q.metadata.get("source_sha256") != SOURCE_SHA256
        or source_q.metadata.get("quantity_handoff_only") is not True
        or source_q.metadata.get("commercial_projection_allowed") is not False
        or source_q.metadata.get("shadow_only") is not False
        or source_q.metadata.get("canonical_physical_floor_owner_authenticated") is not False
        or type(source_q.metadata.get("original_source_row_id")) is not str
    ):
        return _blocked("original_scheduled_area_source_permission_conflict")

    # Recheck exact bytes before reading the real plan. Keep bytes and all
    # original vector/geometry observation data private to this process.
    try:
        import fitz
        data = Path(original_pdf_path).read_bytes()
        if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
            return _blocked("source_sha_mismatch")
        with fitz.open(stream=data, filetype="pdf") as pdf:
            if len(pdf) != 10:
                return _blocked("original_plan_page_roster_incomplete")
            figure = original_alfresco_figure_witness(pdf[0].get_drawings())
    except (OSError, RuntimeError, ValueError, TypeError):
        return _blocked("original_plan_source_not_readable")
    if (
        type(figure) is not OriginalAlfrescoFigureWitness
        or figure.source_sha256 != SOURCE_SHA256
        or figure.status != "CANDIDATE"
        or figure.diagnostic_only is not True
    ):
        return _blocked("original_alfresco_figured_ink_or_scope_unproved")
    if Decimal(str(source_q.value)) != figure.area_m2:
        return _blocked("original_scheduled_and_figured_area_disagree")

    # The original schedule, native dimension lines and full source-native
    # ALFRESCO label together identify this architectural external footprint.
    # They do not measure an internal finished-face floor or tiled finish.
    physical_id = stable_contract_id(
        "q5446_original_alfresco_architectural_footprint",
        {"sha": SOURCE_SHA256, "source_schedule": source_q.quantity_id,
         "figured_source_paths": list(figure.source_vector_path_ids)},
        digest_chars=32,
    )
    source_paths = tuple(
        f"q5446_original_{SOURCE_SHA256[:20]}_p1_path_{i}"
        for i in figure.source_vector_path_ids
    )
    figures = tuple(
        f"q5446_original_{SOURCE_SHA256[:20]}_p1_path_{i}"
        for i in (6838, 10657)
    )
    evidence = tuple(dict.fromkeys((*source_q.evidence_ids, *source_paths)))
    quantity_id = stable_contract_id(
        "q5446_original_figured_alfresco_floor_area",
        {"source_sha": SOURCE_SHA256, "physical_id": physical_id,
         "area_source_qid": source_q.quantity_id, "figures": list(figures)},
        digest_chars=32,
    )
    quantity = QuantityEvidence(
        quantity_id=quantity_id, family="floor_area",
        semantic_key=f"floor_area:{physical_id}:architectural_alfresco",
        value=float(figure.area_m2), unit="m2",
        input_entity_ids=(physical_id,),
        formula="source_figured_alfresco_dimensions_corrob_architect_area",
        formula_version="1.0.0", evidence_ids=evidence,
        authority="documented_dimension", status="firm", confidence=1.0,
        abstained=False,
        metadata={
            "project_id": Q5446_PROJECT_ID, "document_id": Q5446_DOCUMENT_ID,
            "source_sha256": SOURCE_SHA256, "revision_id": Q5446_ORIGINAL_REVISION_ID,
            "workspace_id": workspace_id, "page_no": 1,
            "figured_dimension_ids": list(figures),
            "upstream_architect_area_quantity_id": source_q.quantity_id,
            "physical_scope": "original_external_architectural_alfresco_footprint",
            "net_internal_finished_face_authorized": False,
            "tiled_floor_finish_authorized": False,
            "commercial_projection_allowed": True, "quantity_handoff_only": False,
            "shadow_only": False, "inclusion_status": "INCLUSION",
            "section": "External", "element": "Alfresco architectural floor area",
            "location": "Alfresco", "substrate": "Unspecified",
            "finish_system": "Unspecified", "row_role": "floor_area",
        },
    )
    trace = CommercialTakeoffSourceTrace(
        workspace_id=workspace_id, project_id=Q5446_PROJECT_ID,
        document_id=Q5446_DOCUMENT_ID, source_sha256=SOURCE_SHA256,
        source_page="1", viewport_id="original_ground_floor_alfresco_figure",
        revision_id=Q5446_ORIGINAL_REVISION_ID,
        current_revision_id=Q5446_ORIGINAL_REVISION_ID,
        evidence_ids=evidence, canonical_entity_ids=(physical_id,),
        source_bbox=(799.68, 352.8, 1061.28, 661.8),
        metadata={"original_schedule_quantity_id": source_q.quantity_id,
                  "net_finish_area": False, "review_required": True},
    )
    try:
        sealed = seal_source_closed_run(
            (quantity,), project_id=Q5446_PROJECT_ID,
            traces_by_quantity_id={quantity.quantity_id: trace},
        )
        if len(sealed.quantities) != 1 or not sealed.quantities[0].lineage_ok:
            return _blocked("alfresco_source_closed_seal_failed")
        authority = CommercialMeasurementAuthority(
            method="figured_dimension", figured_dimension_ids=figures,
            metadata={"source": "original_figured_alfresco_plan"},
        )
        rows = tuple(quantities_to_takeoff_output_rows(
            (quantity,), traces_by_quantity_id={quantity.quantity_id: trace},
            authorities_by_quantity_id={quantity.quantity_id: authority},
        ))
        verify_sealed_customer_output(sealed, rows)
    except (ValueError, TypeError, RuntimeError):
        return _blocked("alfresco_sealed_customer_projection_conflict")
    if len(rows) != 1:
        return _blocked("alfresco_customer_quantity_missing")
    return OriginalQ5446AlfrescoCustomerResult(
        "FIRM_SOURCE_CUSTOMER_TO_REVIEW",
        ("original_source_architectural_alfresco_area_independently_figured",),
        quantity, trace, sealed, rows,
    )
