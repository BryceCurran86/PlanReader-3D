"""Source-closed export for promoted ceiling-lining review quantities.

Only quantities that already passed the explicit ceiling review-promotion boundary
may be sealed here. Raw shadow-only ceiling quantities are never accepted.

This module is benchmark-neutral. It does not discover ceiling geometry, choose
benchmark identities, read expected quantities, or score results.
"""
from __future__ import annotations

from typing import Sequence

from pb_ceiling_lining_review_promotion import CeilingLiningReviewCandidate
from pb_geometry_takeoff_model import AuthorityStatus
from pb_quantity_takeoff_adapter import existing_commercial_gate_results
from pb_source_closed_run_export import (
    SealedSourceClosedRun,
    SourceClosedRunConflictError,
    seal_source_closed_run,
)


def _validated_candidates(
    candidates: Sequence[CeilingLiningReviewCandidate],
) -> tuple[CeilingLiningReviewCandidate, ...]:
    out: list[CeilingLiningReviewCandidate] = []
    seen: set[str] = set()

    for candidate in candidates:
        if not isinstance(candidate, CeilingLiningReviewCandidate):
            raise TypeError(
                "candidates must contain only CeilingLiningReviewCandidate records"
            )
        quantity = candidate.promoted_quantity
        row = dict(candidate.review_row)

        if quantity.family != "ceiling_lining":
            raise SourceClosedRunConflictError(
                "ceiling sealed export received a non-ceiling quantity"
            )
        if quantity.abstained or quantity.value is None:
            raise SourceClosedRunConflictError(
                f"ceiling promoted quantity is unavailable: {quantity.quantity_id}"
            )
        if quantity.status != AuthorityStatus.REVIEW_REQUIRED.value:
            raise SourceClosedRunConflictError(
                f"ceiling quantity did not pass review-promotion boundary: {quantity.quantity_id}"
            )
        if quantity.metadata.get("source_owned_ceiling_promotion") is not True:
            raise SourceClosedRunConflictError(
                f"ceiling quantity lacks promotion provenance: {quantity.quantity_id}"
            )
        if quantity.metadata.get("shadow_only") is not False:
            raise SourceClosedRunConflictError(
                f"shadow-only ceiling quantity cannot be sealed: {quantity.quantity_id}"
            )
        if quantity.metadata.get("commercial_projection_allowed") is not True:
            raise SourceClosedRunConflictError(
                f"ceiling quantity is not review-projectable: {quantity.quantity_id}"
            )
        if row.get("quantity_id") != quantity.quantity_id:
            raise SourceClosedRunConflictError(
                f"ceiling review row quantity mismatch: {quantity.quantity_id}"
            )
        if row.get("origin") != "AI" or row.get("quantity_status") != "To review":
            raise SourceClosedRunConflictError(
                f"ceiling review row bypassed estimator review state: {quantity.quantity_id}"
            )

        gates = existing_commercial_gate_results(row)
        if any(result[0] for result in gates.values()):
            raise SourceClosedRunConflictError(
                f"unreviewed ceiling quantity is commercially authorised: {quantity.quantity_id}"
            )

        if candidate.source_trace.project_id != row.get("project_id"):
            raise SourceClosedRunConflictError(
                f"ceiling source trace project mismatch: {quantity.quantity_id}"
            )
        if candidate.source_trace.workspace_id != row.get("workspace_id"):
            raise SourceClosedRunConflictError(
                f"ceiling source trace workspace mismatch: {quantity.quantity_id}"
            )

        quantity_id = str(quantity.quantity_id).strip()
        if not quantity_id or quantity_id in seen:
            raise SourceClosedRunConflictError(
                f"duplicate or empty ceiling quantity id: {quantity_id}"
            )
        seen.add(quantity_id)
        out.append(candidate)

    if not out:
        raise SourceClosedRunConflictError(
            "no promoted ceiling review quantities are available to seal"
        )

    return tuple(sorted(out, key=lambda item: item.promoted_quantity.quantity_id))


def seal_live_ceiling_review_run(
    candidates: Sequence[CeilingLiningReviewCandidate],
    *,
    project_id: str,
) -> SealedSourceClosedRun:
    """Seal already-promoted ceiling review quantities with exact source traces."""
    validated = _validated_candidates(candidates)
    quantities = tuple(candidate.promoted_quantity for candidate in validated)
    traces = {
        candidate.promoted_quantity.quantity_id: candidate.source_trace
        for candidate in validated
    }
    return seal_source_closed_run(
        quantities,
        project_id=project_id,
        traces_by_quantity_id=traces,
    )


__all__ = ["seal_live_ceiling_review_run"]
