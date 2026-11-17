"""Fail-closed original Q5446 family append: independently issued ALFRESCO +
one real tiled finished-floor area, using existing source seals and customers.

This is a bounded original-app, explicit opt-in customer integration. It does
NOT claim that all six original-source roles executed or that the frozen score
was updated. Separate supporting original PDFs grant material scope, not metric.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pb_gpt1_q5446_alfresco_original_customer import (
    OriginalQ5446AlfrescoCustomerResult,
    issue_original_q5446_alfresco_customer_area,
)
from pb_gptmax_q5446_original_tiled_floor_customer import (
    OriginalQ5446TiledFloorCustomerResult,
    issue_original_q5446_first_ensuite_tiled_floor,
    issue_original_q5446_ground_ensuite_tiled_floor,
    issue_original_q5446_ground_laundry_tiled_floor,
)
from pb_gpt1_q5446_source_declared_area_firm_handoff import (
    Q5446_PROJECT_ID, Q5446_DOCUMENT_ID,
)
from pb_gpt1_q5446_original_area_schedule_shadow import SOURCE_SHA256
from pb_source_closed_run_export import (
    SealedSourceClosedRun, SourceClosedRunConflictError, combine_source_closed_runs,
)
from pb_customer_output_verification import verify_sealed_customer_output
from pb_migration_contracts import QuantityEvidence


@dataclass(frozen=True)
class Q5446TwoFamilyCustomerResult:
    status: str
    reason_codes: tuple[str, ...]
    source_role_coverage_verified: bool = False
    original_alfresco: OriginalQ5446AlfrescoCustomerResult | None = None
    original_tiled_room: OriginalQ5446TiledFloorCustomerResult | None = None
    combined_sealed_run: SealedSourceClosedRun | None = None
    customer_rows: tuple[dict[str, Any], ...] = ()


def _blocked(code: str) -> Q5446TwoFamilyCustomerResult:
    return Q5446TwoFamilyCustomerResult("ABSTAIN", (code,))


def issue_original_q5446_alfresco_plus_ensuite_customer(
    original_plan: str | Path,
    original_inclusions: str | Path,
    original_sales_advice: str | Path,
    *,
    workspace_id: int = 1,
) -> Q5446TwoFamilyCustomerResult:
    """Bind two *separately* source-closed original-app families.

    Does not use project/reference IDs or expected areas to set measurements.
    Current untouched ALFRESCO issuer remains independently consumable if the
    tile family abstains. A failed second role cannot replace its original seal.
    """
    if type(workspace_id) is not int or workspace_id <= 0:
        return _blocked("authenticated_workspace_unavailable")
    if not isinstance(original_plan, (str, Path)):
        return _blocked("original_plan_path_unavailable")

    previous = issue_original_q5446_alfresco_customer_area(
        str(original_plan), workspace_id=workspace_id,
    )
    if (
        not isinstance(previous, OriginalQ5446AlfrescoCustomerResult)
        or previous.status != "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
        or not isinstance(previous.quantity, QuantityEvidence)
        or previous.quantity.family != "floor_area"
        or previous.quantity.abstained
        or previous.trace is None
        or previous.sealed_run is None
        or len(previous.sealed_run.quantities) != 1
        or len(previous.customer_rows) != 1
        or previous.trace.source_sha256 != SOURCE_SHA256
        or previous.trace.project_id != Q5446_PROJECT_ID
        or previous.trace.document_id != Q5446_DOCUMENT_ID
    ):
        return _blocked("original_alfresco_signed_customer_retention_unavailable")

    candidate = issue_original_q5446_ground_ensuite_tiled_floor(
        original_plan, original_inclusions, original_sales_advice,
        workspace_id=workspace_id,
    )
    if (
        not isinstance(candidate, OriginalQ5446TiledFloorCustomerResult)
        or candidate.status != "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
        or not isinstance(candidate.quantity, QuantityEvidence)
        or candidate.quantity.family != "floor_finish_area"
        or candidate.quantity.abstained
        or candidate.trace is None
        or candidate.sealed_run is None
        or len(candidate.sealed_run.quantities) != 1
        or len(candidate.customer_rows) != 1
        or candidate.trace.source_sha256 != SOURCE_SHA256
        or candidate.trace.project_id != Q5446_PROJECT_ID
        or candidate.trace.document_id != Q5446_DOCUMENT_ID
        or candidate.quantity.metadata.get("tiled_floor_finish_authorized") is not True
        or candidate.quantity.metadata.get("net_internal_finished_face_authorized") is not True
        or candidate.quantity.quantity_id == previous.quantity.quantity_id
        or set(candidate.quantity.input_entity_ids).intersection(
            previous.quantity.input_entity_ids
        )
    ):
        return _blocked("original_ensuite_signed_customer_retention_unavailable")

    try:
        original_bodies = tuple(record.to_dict() for record in previous.sealed_run.quantities)
        verified_prior = verify_sealed_customer_output(
            previous.sealed_run, previous.customer_rows,
        )
        verified_tile = verify_sealed_customer_output(
            candidate.sealed_run, candidate.customer_rows,
        )
        if verified_prior.customer_row_count != 1 or verified_tile.customer_row_count != 1:
            return _blocked("original_family_customer_source_bijection_unavailable")

        combined = combine_source_closed_runs(
            (previous.sealed_run, candidate.sealed_run),
            project_id=Q5446_PROJECT_ID,
        )
        rows = (*previous.customer_rows, *candidate.customer_rows)
        verified = verify_sealed_customer_output(combined, rows)
        required_ids = {
            previous.quantity.quantity_id, candidate.quantity.quantity_id,
        }
        if (
            len(combined.quantities) != 2
            or verified.customer_row_count != 2
            or set(verified.verified_quantity_ids) != required_ids
            or tuple(record.to_dict() for record in combined.quantities
                     if record.quantity_id == previous.quantity.quantity_id)
               != original_bodies
            or rows[0] != previous.customer_rows[0]
            or set(combined.source_sha256s) != {SOURCE_SHA256}
            or len(combined.revision_ids) != 1
            or not all(record.lineage_ok and not record.abstained
                       for record in combined.quantities)
        ):
            return _blocked("combined_original_family_retention_unavailable")
    except (ValueError, RuntimeError, TypeError, KeyError, SourceClosedRunConflictError):
        return _blocked("combined_original_family_seal_or_customer_conflict")

    return Q5446TwoFamilyCustomerResult(
        status="TWO_INDEPENDENT_SOURCE_FAMILIES_CUSTOMER_VERIFIED",
        reason_codes=("original_alfresco_and_ensuite_distinct_physical_owners",),
        source_role_coverage_verified=False,
        original_alfresco=previous,
        original_tiled_room=candidate,
        combined_sealed_run=combined,
        customer_rows=rows,
    )


@dataclass(frozen=True)
class Q5446MultiRoomTiledCustomerResult:
    status: str
    reason_codes: tuple[str, ...]
    source_role_coverage_verified: bool = False
    original_alfresco: OriginalQ5446AlfrescoCustomerResult | None = None
    tiled_rooms: tuple[OriginalQ5446TiledFloorCustomerResult, ...] = ()
    combined_sealed_run: SealedSourceClosedRun | None = None
    customer_rows: tuple[dict[str, Any], ...] = ()


def issue_original_q5446_alfresco_plus_tiled_floors_customer(
    original_plan: str | Path,
    original_inclusions: str | Path,
    original_sales_advice: str | Path,
    *,
    workspace_id: int = 1,
) -> Q5446MultiRoomTiledCustomerResult:
    """Combine independently source-closed Q5446 ALFRESCO + 3 verified tiled floor rooms."""
    if type(workspace_id) is not int or workspace_id <= 0:
        return Q5446MultiRoomTiledCustomerResult("ABSTAIN", ("authenticated_workspace_unavailable",))
    if not isinstance(original_plan, (str, Path)):
        return Q5446MultiRoomTiledCustomerResult("ABSTAIN", ("original_plan_path_unavailable",))

    alf = issue_original_q5446_alfresco_customer_area(
        str(original_plan), workspace_id=workspace_id,
    )
    if (
        not isinstance(alf, OriginalQ5446AlfrescoCustomerResult)
        or alf.status != "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
        or not isinstance(alf.quantity, QuantityEvidence)
        or alf.quantity.abstained
        or alf.quantity.family != "floor_area"
        or alf.trace is None
        or alf.trace.source_sha256 != SOURCE_SHA256
        or alf.trace.project_id != Q5446_PROJECT_ID
        or alf.trace.document_id != Q5446_DOCUMENT_ID
        or alf.sealed_run is None
        or len(alf.sealed_run.quantities) != 1
        or len(alf.customer_rows) != 1
    ):
        return Q5446MultiRoomTiledCustomerResult("ABSTAIN", ("original_alfresco_signed_customer_retention_unavailable",))

    ens1 = issue_original_q5446_ground_ensuite_tiled_floor(
        original_plan, original_inclusions, original_sales_advice, workspace_id=workspace_id,
    )
    ldry1 = issue_original_q5446_ground_laundry_tiled_floor(
        original_plan, original_inclusions, original_sales_advice, workspace_id=workspace_id,
    )
    ens2 = issue_original_q5446_first_ensuite_tiled_floor(
        original_plan, original_inclusions, original_sales_advice, workspace_id=workspace_id,
    )
    tiled = (ens1, ldry1, ens2)
    seen_qids = {alf.quantity.quantity_id}
    seen_entities = set(alf.quantity.input_entity_ids)
    for item in tiled:
        if (
            not isinstance(item, OriginalQ5446TiledFloorCustomerResult)
            or item.status != "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
            or not isinstance(item.quantity, QuantityEvidence)
            or item.quantity.abstained
            or item.quantity.family != "floor_finish_area"
            or item.trace is None
            or item.trace.source_sha256 != SOURCE_SHA256
            or item.trace.project_id != Q5446_PROJECT_ID
            or item.trace.document_id != Q5446_DOCUMENT_ID
            or item.sealed_run is None
            or len(item.sealed_run.quantities) != 1
            or len(item.customer_rows) != 1
            or item.quantity.metadata.get("tiled_floor_finish_authorized") is not True
            or item.quantity.metadata.get("net_internal_finished_face_authorized") is not True
            or item.quantity.quantity_id in seen_qids
            or not item.quantity.input_entity_ids
            or seen_entities.intersection(item.quantity.input_entity_ids)
        ):
            return Q5446MultiRoomTiledCustomerResult("ABSTAIN", ("original_tiled_floor_signed_customer_retention_unavailable",))
        seen_qids.add(item.quantity.quantity_id)
        seen_entities.update(item.quantity.input_entity_ids)

    try:
        constituents = (alf, *tiled)
        source_bodies = {
            item.quantity.quantity_id: tuple(rec.to_dict() for rec in item.sealed_run.quantities)
            for item in constituents
        }
        for item in constituents:
            single_verified = verify_sealed_customer_output(item.sealed_run, item.customer_rows)
            if (
                single_verified.customer_row_count != 1
                or set(single_verified.verified_quantity_ids) != {item.quantity.quantity_id}
            ):
                return Q5446MultiRoomTiledCustomerResult("ABSTAIN", ("original_family_customer_source_bijection_unavailable",))
        combined = combine_source_closed_runs(
            tuple(item.sealed_run for item in constituents),
            project_id=Q5446_PROJECT_ID,
        )
        rows = tuple(row for item in constituents for row in item.customer_rows)
        verified = verify_sealed_customer_output(combined, rows)
        combined_ids = {rec.quantity_id for rec in combined.quantities}
        if (
            len(combined.quantities) != 4
            or verified.customer_row_count != 4
            or set(verified.verified_quantity_ids) != seen_qids
            or len(combined_ids) != 4
            or any(
                tuple(rec.to_dict() for rec in combined.quantities if rec.quantity_id == qid) != originals
                for qid, originals in source_bodies.items()
            )
            or rows != tuple(row for item in constituents for row in item.customer_rows)
            or set(combined.source_sha256s) != {SOURCE_SHA256}
            or len(combined.revision_ids) != 1
            or not all(rec.lineage_ok and not rec.abstained for rec in combined.quantities)
        ):
            return Q5446MultiRoomTiledCustomerResult("ABSTAIN", ("combined_original_family_retention_unavailable",))
    except (ValueError, RuntimeError, TypeError, KeyError, SourceClosedRunConflictError):
        return Q5446MultiRoomTiledCustomerResult("ABSTAIN", ("combined_original_family_seal_or_customer_conflict",))

    return Q5446MultiRoomTiledCustomerResult(
        status="MULTI_ROOM_SOURCE_FAMILIES_CUSTOMER_VERIFIED",
        reason_codes=("original_alfresco_and_three_tiled_rooms_distinct_physical_owners",),
        source_role_coverage_verified=False,
        original_alfresco=alf,
        tiled_rooms=tiled,
        combined_sealed_run=combined,
        customer_rows=rows,
    )
