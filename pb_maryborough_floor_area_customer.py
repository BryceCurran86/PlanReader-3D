"""Fail-closed compatibility wrapper for the quarantined floor subset."""
from __future__ import annotations

from pathlib import Path

from pb_customer_output_verification import verify_sealed_customer_output
from pb_migration_contracts import QuantityEvidence
from pb_source_closed_run_export import seal_source_closed_run
from pb_maryborough_customer_authority import (
    FOOD_PREP_PHYSICAL_FLOOR_ID,
    FOOD_PREP_PHYSICAL_ROOM_ID,
    MARYBOROUGH_DOCUMENT_ID,
    MARYBOROUGH_PROJECT_ID,
    MARYBOROUGH_REVISION_ID,
    MARYBOROUGH_SOURCE_SHA256,
    OFFICE_PHYSICAL_FLOOR_ID,
    OFFICE_PHYSICAL_ROOM_ID,
    issue_all_original_maryborough_customer_quantities,
)
from pb_maryborough_customer_authority import (
    MaryboroughCustomerResult as OriginalMaryboroughFloorCustomerResult,
)

__all__ = [
    "FOOD_PREP_PHYSICAL_FLOOR_ID",
    "FOOD_PREP_PHYSICAL_ROOM_ID",
    "MARYBOROUGH_DOCUMENT_ID",
    "MARYBOROUGH_PROJECT_ID",
    "MARYBOROUGH_REVISION_ID",
    "MARYBOROUGH_SOURCE_SHA256",
    "OFFICE_PHYSICAL_FLOOR_ID",
    "OFFICE_PHYSICAL_ROOM_ID",
    "OriginalMaryboroughFloorCustomerResult",
    "issue_original_maryborough_floor_customer_areas",
]


def issue_original_maryborough_floor_customer_areas(
    pdf_path: str | Path,
    *,
    workspace_id: int = 1,
) -> OriginalMaryboroughFloorCustomerResult:
    """Return authentic floor subset with dedicated 1-to-1 sealed run."""
    if type(workspace_id) is not int or workspace_id <= 0:
        return OriginalMaryboroughFloorCustomerResult(
            "ABSTAIN", ("authenticated_workspace_unavailable",),
        )
    result = issue_all_original_maryborough_customer_quantities(
        pdf_path, workspace_id=workspace_id,
    )
    if (
        result.status == "ABSTAIN"
        and not result.quantities
        and not result.traces
        and result.sealed_run is None
        and not result.customer_rows
        and not result.identity_map_bindings
    ):
        return result

    # When upstream resolves genuine source quantities, filter and seal the authentic floor subset.
    # Reject unexpected or unverified upstream rows to maintain fail-closed quarantine.
    if (
        result.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
        and result.reason_codes == ("source_owned_physical_quantity_resolved",)
        and result.quantities
        and result.traces
        and result.customer_rows
    ):
        floor_quantities = tuple(
            q for q in result.quantities
            if isinstance(q, QuantityEvidence)
            and q.family == "floor_finish_area"
            and not q.abstained
            and q.value is not None
            and OFFICE_PHYSICAL_FLOOR_ID in q.input_entity_ids
        )
        if floor_quantities and len(floor_quantities) == len(result.quantities):
            # The entire result is the authenticated floor finish quantity and seal
            return result
        if floor_quantities:
            traces_by_qid = {
                tr.evidence_ids[0]: tr
                for tr in result.traces
                if hasattr(tr, "evidence_ids") and tr.evidence_ids
            }
            floor_rows = tuple(
                r for r in result.customer_rows
                if isinstance(r, dict) and r.get("quantity_id") in {q.quantity_id for q in floor_quantities}
            )
            sealed_subset = seal_source_closed_run(
                floor_quantities,
                project_id=MARYBOROUGH_PROJECT_ID,
                traces_by_quantity_id=traces_by_qid,
            )
            verify_sealed_customer_output(sealed_subset, floor_rows)
            return OriginalMaryboroughFloorCustomerResult(
                status="FIRM_SOURCE_CUSTOMER_TO_REVIEW",
                reason_codes=("source_owned_physical_quantity_resolved",),
                quantities=floor_quantities,
                traces=result.traces,
                sealed_run=sealed_subset,
                customer_rows=floor_rows,
                identity_map_bindings=(),
            )

    # Never return two selected rows with an unrelated larger source seal.
    # An unverified upstream implementation cannot silently re-enable this subset.
    return OriginalMaryboroughFloorCustomerResult(
        "ABSTAIN", ("source_owned_floor_subset_authority_unavailable",),
    )
