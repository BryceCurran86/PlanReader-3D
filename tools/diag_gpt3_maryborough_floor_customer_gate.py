"""Read-only source-sealed floor-area to customer-review receipt diagnostic.

Consumes real LivePhysicalNetWallClaim. Does not infer source geometry, metric
scale, missing material semantics, universe completeness or benchmark scores.
The diagnostic workspace ID does NOT authorize estimator/customer approval.
"""
from __future__ import annotations

from pb_customer_output_verification import (
    CustomerOutputVerificationError,
    verify_sealed_customer_output,
)
from pb_live_floor_area_customer_projection import (
    project_live_floor_area_customer_rows,
)
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_live_floor_area_source_closed_export import seal_live_floor_area_run
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_quantity_takeoff_adapter import CommercialTakeoffProjectionError
from pb_source_closed_run_export import SourceClosedRunExportError


def inspect_floor_customer_handoff(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int = 1,
    project_id: str = "source-only-floor-area-diagnostic",
) -> dict:
    """Prove exact source quantity→sealed quantity→AI review row bijection."""
    if type(claim) is not LivePhysicalNetWallClaim:
        raise TypeError("claim must be a real LivePhysicalNetWallClaim")
    published = publish_live_floor_area_quantities(claim)
    expected_ids = tuple(sorted(q.quantity_id for q in published))
    result = {
        "published_floor_area_quantity_ids": list(expected_ids),
        "sealed_floor_area_quantity_ids": [],
        "customer_verified_floor_area_quantity_ids": [],
        "customer_review_row_count": 0,
        "customer_projection_failure_type": None,
        "diagnostic_workspace_not_customer_approved": True,
        "commercial_estimator_approved": False,
        "benchmark_accuracy": None,
    }
    if not expected_ids:
        return result
    try:
        sealed = seal_live_floor_area_run(
            claim, workspace_id=workspace_id, project_id=project_id
        )
        if sealed.project_id != project_id:
            raise SourceClosedRunExportError("source seal project identity mismatch")
        sealed_ids = tuple(sorted(q.quantity_id for q in sealed.quantities))
        result["sealed_floor_area_quantity_ids"] = list(sealed_ids)
        if sealed_ids != expected_ids or not all(
            q.lineage_ok and not q.abstained for q in sealed.quantities
        ):
            raise SourceClosedRunExportError("source seal quantities or lineage differ")
        rows = project_live_floor_area_customer_rows(
            claim, workspace_id=workspace_id, project_id=project_id
        )
        verified = verify_sealed_customer_output(sealed, rows)
        verified_ids = tuple(sorted(verified.verified_quantity_ids))
        if (
            verified_ids != expected_ids
            or verified.valid_quantity_count != len(expected_ids)
            or verified.customer_row_count != len(expected_ids)
            or any(
                item.get("quantity_status") != "To review"
                or item.get("origin") != "AI"
                or item.get("row_role") != "floor_area"
                for item in rows
            )
        ):
            raise CustomerOutputVerificationError(
                "source floor/customer draft row parity or review state differs"
            )
        result["customer_review_row_count"] = len(rows)
        result["customer_verified_floor_area_quantity_ids"] = list(verified_ids)
    except (
        SourceClosedRunExportError,
        CommercialTakeoffProjectionError,
        CustomerOutputVerificationError,
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:
        result["customer_projection_failure_type"] = type(exc).__name__
    return result
