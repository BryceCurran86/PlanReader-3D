"""Combine source-closed floor measurement and finish output.

This adapter is benchmark-neutral. It preserves every genuine commercial
floor-area row and every genuine floor-finish-area row, composes their signed
source runs, and verifies the complete customer-row bijection. It never
suppresses one family because another family owns the same physical floor.
"""
from __future__ import annotations

from typing import Any

from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_floor_area_customer_projection import (
    project_live_floor_area_customer_rows,
)
from pb_live_floor_area_source_closed_export import seal_live_floor_area_run
from pb_live_floor_finish_area_source_closed_export import (
    seal_live_floor_finish_area_run,
)
from pb_live_floor_finish_customer_projection import (
    project_live_floor_finish_customer_rows,
)
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_source_closed_run_export import (
    SealedSourceClosedRun,
    SourceClosedRunConflictError,
    combine_source_closed_runs,
)


def _quantity_id(row: dict[str, Any]) -> str:
    value = row.get("quantity_id")
    if type(value) is not str or not value or value != value.strip():
        raise SourceClosedRunConflictError(
            "floor-family customer row has invalid quantity_id"
        )
    return value


def project_live_floor_family_customer_output(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> tuple[SealedSourceClosedRun, tuple[dict[str, Any], ...]]:
    """Project and verify all commercial floor families without supersedence."""
    if type(claim) is not LivePhysicalNetWallClaim:
        raise TypeError("claim must be LivePhysicalNetWallClaim")
    if type(workspace_id) is not int or workspace_id <= 0:
        raise ValueError("workspace_id must be an authenticated positive integer")
    if type(project_id) is not str or not project_id or project_id != project_id.strip():
        raise ValueError("project_id must be a non-empty canonical string")

    floor_rows = tuple(
        project_live_floor_area_customer_rows(
            claim,
            workspace_id=workspace_id,
            project_id=project_id,
        )
    )
    finish_rows = tuple(
        project_live_floor_finish_customer_rows(
            claim,
            workspace_id=workspace_id,
            project_id=project_id,
        )
    )

    runs: list[SealedSourceClosedRun] = []
    if floor_rows:
        runs.append(
            seal_live_floor_area_run(
                claim,
                workspace_id=workspace_id,
                project_id=project_id,
            )
        )
    if finish_rows:
        runs.append(
            seal_live_floor_finish_area_run(
                claim,
                workspace_id=workspace_id,
                project_id=project_id,
            )
        )
    if not runs:
        raise SourceClosedRunConflictError(
            "no source-closed floor-family customer quantities are available"
        )

    rows = floor_rows + finish_rows
    quantity_ids = tuple(_quantity_id(row) for row in rows)
    if len(quantity_ids) != len(set(quantity_ids)):
        raise SourceClosedRunConflictError(
            "floor-family customer quantity IDs are not unique"
        )

    combined = combine_source_closed_runs(
        tuple(runs),
        project_id=project_id,
    )
    if len(combined.quantities) != len(rows):
        raise SourceClosedRunConflictError(
            "combined floor-family sealed/customer cardinality mismatch"
        )
    if {quantity.quantity_id for quantity in combined.quantities} != set(quantity_ids):
        raise SourceClosedRunConflictError(
            "combined floor-family sealed/customer identity mismatch"
        )

    verify_sealed_customer_output(combined, rows)
    return combined, rows


__all__ = ["project_live_floor_family_customer_output"]
