"""Fail-closed compatibility wrapper for the quarantined floor subset."""
from __future__ import annotations

from pathlib import Path

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
    """Return no subset until its own source-owned authority and seal exist."""
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
    # Never return two selected rows with an unrelated larger source seal.
    # A future upstream implementation cannot silently re-enable this subset.
    return OriginalMaryboroughFloorCustomerResult(
        "ABSTAIN", ("source_owned_floor_subset_authority_unavailable",),
    )
