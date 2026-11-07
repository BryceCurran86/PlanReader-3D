"""Maryborough original-source OFFICE & FOOD PREP floor area -> customer rows.

Backwards-compatible wrapper delegating to pb_maryborough_customer_authority.
"""
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
    """Validate source drawing ink on Page 11 and Page 7, then seal customer rows."""
    res = issue_all_original_maryborough_customer_quantities(pdf_path, workspace_id=workspace_id)
    if res.status != "FIRM_SOURCE_CUSTOMER_TO_REVIEW":
        return res
    floor_quantities = tuple(
        q for q in res.quantities if q.input_entity_ids[0] in (OFFICE_PHYSICAL_FLOOR_ID, FOOD_PREP_PHYSICAL_FLOOR_ID)
    )
    floor_rows = tuple(
        r
        for r in res.customer_rows
        if any(
            cid in (OFFICE_PHYSICAL_FLOOR_ID, FOOD_PREP_PHYSICAL_FLOOR_ID)
            for cid in r.get("canonical_entity_ids", ())
        )
    )
    return OriginalMaryboroughFloorCustomerResult(
        status=res.status,
        reason_codes=res.reason_codes,
        quantities=floor_quantities,
        traces=res.traces,
        sealed_run=res.sealed_run,
        customer_rows=floor_rows,
        identity_map_bindings=res.identity_map_bindings,
    )
