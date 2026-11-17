"""Compose four INDEPENDENT source-owned 3Laurel finish issuers into one sealed customer result.

No measured area is inferred from candidate room polygons or door labels.
Reject missing, conflicting or mutated inputs. This is source-authorised only
for the 22 existing independently dimensioned finish items, not other rooms.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pb_three_laurel_vinyl_floor_customer import (
    issue_original_three_laurel_vinyl_floor_customer_quantities,
)
from pb_three_laurel_wet_area_floor_customer import (
    issue_original_three_laurel_wet_area_floor_customer_quantities,
)
from pb_three_laurel_wall_tile_customer import (
    issue_original_three_laurel_wall_tile_customer_quantities,
)
from pb_three_laurel_ceiling_customer import (
    issue_original_three_laurel_ceiling_customer_quantities,
)
from pb_source_closed_run_export import (
    SealedSourceClosedRun, combine_source_closed_runs,
    SourceClosedRunConflictError,
)
from pb_customer_output_verification import verify_sealed_customer_output

SOURCE_SHA = "014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e"
PROJECT = "au_qld_3laurel"
_EXPECTED_FAMILIES = (
    ("floor_finish_area", 3),
    ("floor_finish_area", 4),
    ("wall_finish_area", 8),
    ("ceiling_lining", 7),
)


@dataclass(frozen=True)
class ThreeLaurelCombinedSourceCustomerResult:
    status: str
    reason_codes: tuple[str, ...]
    sealed_run: SealedSourceClosedRun | None = None
    customer_rows: tuple[dict[str, Any], ...] = ()
    family_counts: tuple[int, int, int, int] = (0, 0, 0, 0)
    all_rooms_physically_authenticated: bool = False
    frozen_benchmark_score_authorized: bool = False


def _blocked(reason: str) -> ThreeLaurelCombinedSourceCustomerResult:
    return ThreeLaurelCombinedSourceCustomerResult("ABSTAIN", (reason,))


def issue_original_three_laurel_22_finish_customer_rows(
    original_pdf: str | Path, *, workspace_id: int = 1,
) -> ThreeLaurelCombinedSourceCustomerResult:
    """Source-seal all four existing quantities, without rescoring candidate rooms."""
    if type(workspace_id) is not int or workspace_id <= 0:
        return _blocked("authenticated_workspace_unavailable")
    try:
        path = Path(original_pdf)
        if path.is_symlink() or not path.is_file():
            return _blocked("original_source_path_unavailable")
        if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCE_SHA:
            return _blocked("original_source_hash_mismatch")
    except (OSError, TypeError, ValueError):
        return _blocked("original_source_path_unavailable")

    issuers = (
        issue_original_three_laurel_vinyl_floor_customer_quantities,
        issue_original_three_laurel_wet_area_floor_customer_quantities,
        issue_original_three_laurel_wall_tile_customer_quantities,
        issue_original_three_laurel_ceiling_customer_quantities,
    )
    parts = tuple(f(path, workspace_id=workspace_id) for f in issuers)
    original_bodies = {}
    seen_entities = set()
    source_runs = []
    all_rows = []
    for part, (family, count) in zip(parts, _EXPECTED_FAMILIES):
        if (
            part.status != "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
            or part.sealed_run is None
            or len(part.quantities) != count
            or len(part.sealed_run.quantities) != count
            or len(part.customer_rows) != count
        ):
            return _blocked("independently_dimensioned_finish_family_unavailable")
        for q in part.quantities:
            if (
                q.abstained or q.family != family
                or q.metadata.get("source_sha256") != SOURCE_SHA
                or q.metadata.get("project_id") != PROJECT
                or q.metadata.get("workspace_id") != workspace_id
                or q.metadata.get("takeoff_eligible") is not True
                or q.metadata.get("commercial_projection_allowed") is not True
                or not q.input_entity_ids
                or set(q.input_entity_ids) & seen_entities
                or q.quantity_id in original_bodies
            ):
                return _blocked("source_quantity_identity_or_finish_conflict")
            seen_entities.update(q.input_entity_ids)
        records = tuple(r.to_dict() for r in part.sealed_run.quantities)
        record_by_id = {r.quantity_id: r.to_dict() for r in part.sealed_run.quantities}
        if len(record_by_id) != count or len(records) != count:
            return _blocked("source_family_seal_conflict")
        original_bodies.update(record_by_id)
        try:
            verified = verify_sealed_customer_output(
                part.sealed_run, part.customer_rows,
            )
            if (
                verified.customer_row_count != count
                or set(verified.verified_quantity_ids) != set(record_by_id)
                or set(part.sealed_run.source_sha256s) != {SOURCE_SHA}
                or len(part.sealed_run.revision_ids) != 1
            ):
                return _blocked("original_family_customer_lineage_unavailable")
        except (ValueError, RuntimeError, TypeError, KeyError):
            return _blocked("original_family_customer_lineage_unavailable")
        source_runs.append(part.sealed_run)
        all_rows.extend(part.customer_rows)

    try:
        combined = combine_source_closed_runs(
            tuple(source_runs), project_id=PROJECT,
        )
        rows = tuple(all_rows)
        checked = verify_sealed_customer_output(combined, rows)
        recovered = {r.quantity_id: r.to_dict() for r in combined.quantities}
        if (
            len(recovered) != 22 or len(combined.quantities) != 22
            or checked.customer_row_count != 22
            or set(checked.verified_quantity_ids) != set(original_bodies)
            or recovered != original_bodies
            or len(rows) != 22
            or set(combined.source_sha256s) != {SOURCE_SHA}
            or len(combined.revision_ids) != 1
            or not all(r.lineage_ok and not r.abstained for r in combined.quantities)
        ):
            return _blocked("combined_finish_receipt_retention_unavailable")
    except (ValueError, RuntimeError, TypeError, KeyError,
            SourceClosedRunConflictError):
        return _blocked("combined_finish_customer_seal_conflict")

    return ThreeLaurelCombinedSourceCustomerResult(
        status="FIRM_SOURCE_CUSTOMER_TO_REVIEW",
        reason_codes=("22_independently_dimensioned_finish_rows_preserved",),
        sealed_run=combined,
        customer_rows=rows,
        family_counts=(3, 4, 8, 7),
        all_rooms_physically_authenticated=False,
        frozen_benchmark_score_authorized=False,
    )
