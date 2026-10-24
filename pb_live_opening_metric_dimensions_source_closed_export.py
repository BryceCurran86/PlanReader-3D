"""Signed original-source opening width and height measured in metres.

Never invert a figured area to guess a side or claim a source-derived opening
count. This is a source-closed engineering quantity, not direct customer
pricing/material approval. Its already-authenticated opening area is immutable.
"""
from __future__ import annotations

from collections import defaultdict
import math

from pb_live_opening_metric_dimensions_quantity_publication import (
    _measurement_axes,
    OPENING_SOURCE_DIMENSION_AUTHORITY,
)
from pb_migration_contracts import stable_contract_id

from pb_live_opening_area_quantity_publication import (
    publish_live_opening_area_quantities,
)
from pb_live_opening_metric_dimensions_quantity_publication import (
    publish_live_opening_dimension_quantities,
)
from pb_live_opening_source_closed_export import (
    build_live_opening_area_source_traces,
    build_live_opening_area_claim_source_traces,
)
from pb_live_physical_opening_void_composition import (
    LivePhysicalOpeningVoidComposition,
)
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import (
    SealedSourceClosedRun, SourceClosedRunConflictError,
    seal_source_closed_run,
)


def seal_live_opening_dimension_run(
    composition: LivePhysicalOpeningVoidComposition,
    *,
    workspace_id: int,
    project_id: str,
) -> SealedSourceClosedRun:
    """Seal width/height in lm only after exact original area/source reproof.

    Both metric axes must be admitted for each contributing physical opening.
    Foreign area receipts, wrong source snapshots and copied source quantities
    are rejected by the original opening-area trace verifier first.
    """
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("composition must be original source opening composition")
    area_traces = build_live_opening_area_source_traces(
        composition, workspace_id=workspace_id, project_id=project_id,
    )
    area_by_id = {
        q.quantity_id: q for q in publish_live_opening_area_quantities(composition)
        if not q.abstained and q.status == "corroborated"
    }
    axes = publish_live_opening_dimension_quantities(composition)
    canonical = {opening.physical_opening_id: opening
                 for opening in composition.canonical_openings}
    if len(canonical) != len(composition.canonical_openings):
        raise SourceClosedRunConflictError("duplicate original physical opening identity")
    traces = {}
    groups = defaultdict(set)
    for quantity in axes:
        if (
            quantity.family not in {"opening_width", "opening_height"}
            or quantity.unit != "lm"
            or quantity.status != "corroborated"
            or quantity.abstained
            or len(quantity.input_entity_ids) != 1
            or quantity.metadata.get("commercial_projection_allowed") is not False
            or quantity.metadata.get("quantity_handoff_only") is not True
        ):
            raise SourceClosedRunConflictError("unqualified original metric opening axis")
        physical_id = quantity.input_entity_ids[0]
        opening = canonical.get(physical_id)
        area_id = quantity.metadata.get("source_area_quantity_id")
        area = area_by_id.get(area_id)
        parent = area_traces.get(area_id)
        if (
            opening is None or area is None or parent is None
            or opening.physical_opening_id != opening.canonical_opening_id
            or area.input_entity_ids != (physical_id,)
            or parent.canonical_entity_ids != (physical_id,)
            or not set(quantity.evidence_ids).issubset(set(opening.evidence_ids))
            or quantity.metadata.get("document_id") != parent.document_id
            or quantity.metadata.get("source_sha256", "").lower() != parent.source_sha256
            or quantity.metadata.get("revision_id") != parent.revision_id
            or quantity.metadata.get("page_no") != parent.source_page
            or quantity.metadata.get("viewport_id") != parent.viewport_id
            or quantity.metadata.get("physical_opening_id") != physical_id
            or quantity.quantity_id in traces
            or quantity.family in groups[physical_id]
        ):
            raise SourceClosedRunConflictError("opening metric axis lacks exact original area owner")
        groups[physical_id].add(quantity.family)
        traces[quantity.quantity_id] = CommercialTakeoffSourceTrace(
            workspace_id=workspace_id,
            project_id=project_id,
            document_id=parent.document_id,
            source_sha256=parent.source_sha256,
            source_page=parent.source_page,
            viewport_id=parent.viewport_id,
            revision_id=parent.revision_id,
            current_revision_id=parent.revision_id,
            evidence_ids=tuple(sorted(quantity.evidence_ids)),
            canonical_entity_ids=(physical_id,),
            metadata={
                "original_opening_area_quantity_id": area_id,
                "source_metric_axis": quantity.family,
                "commercial_projection_allowed": False,
            },
        )
    for physical_id, families in groups.items():
        if families != {"opening_width", "opening_height"}:
            raise SourceClosedRunConflictError(
                f"incomplete original opening metric axis pair: {physical_id}"
            )
    result = seal_source_closed_run(
        axes, project_id=project_id, traces_by_quantity_id=traces,
    )
    if any(not row.lineage_ok for row in result.quantities):
        raise SourceClosedRunConflictError("opening axis source handoff lineage incomplete")
    return result


def seal_live_opening_dimension_claim_run(
    claim,
    *,
    workspace_id: int,
    project_id: str,
) -> SealedSourceClosedRun:
    """Reprove project-claim metric axes against their original area issuer.

    The final source claim owns canonical openings, signed area evidence and
    independently figured/frame-qualified axis evidence. Never retain an
    entire heavyweight physical-void composer just to seal these lengths.
    """
    from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim

    if type(claim) is not LivePhysicalNetWallClaim:
        raise TypeError("claim must be one original live physical wall claim")
    area_traces = build_live_opening_area_claim_source_traces(
        claim, workspace_id=workspace_id, project_id=project_id,
    )
    areas_by_id = {
        q.quantity_id: q for q in claim.opening_quantity_evidence
        if not q.abstained and q.status == "corroborated"
    }
    area_by_opening = {
        q.input_entity_ids[0]: q for q in areas_by_id.values()
        if len(q.input_entity_ids) == 1
    }
    openings = {}
    original_scope = None
    for opening in claim.canonical_openings:
        physical_id = opening.physical_opening_id
        if physical_id in openings:
            raise SourceClosedRunConflictError("duplicate physical opening in source claim")
        openings[physical_id] = opening
        scope = (
            opening.document_id, opening.source_sha256.lower(),
            opening.revision_id, opening.snapshot_id,
        )
        if original_scope is None:
            original_scope = scope
        elif original_scope != scope:
            raise SourceClosedRunConflictError("foreign original opening snapshot in claim")

    expected = {}
    for physical_id, opening in openings.items():
        original_area = area_by_opening.get(physical_id)
        if original_area is None:
            continue
        resolved = _measurement_axes(opening)
        if resolved is None:
            continue
        width, height, axis_receipts = resolved
        area = float(original_area.value)
        tolerance = (
            0.0050001 if opening.area_basis == "figured_opening_label"
            else 1e-6
        )
        if (
            not math.isfinite(width * height)
            or not math.isclose(area, width * height, rel_tol=0.0,
                                abs_tol=tolerance)
        ):
            continue
        if original_area.quantity_id not in area_traces:
            raise SourceClosedRunConflictError("measured axis lacks original source area")
        for family, measured in (("opening_width", width), ("opening_height", height)):
            amount = round(measured, 6)
            if amount <= 0 or not math.isclose(amount, measured, rel_tol=0, abs_tol=1e-6):
                raise SourceClosedRunConflictError("imprecise original metric axis")
            key = (physical_id, family)
            expected[key] = (
                stable_contract_id("opening_metric_axis", {
                    "opening_area_quantity_id": original_area.quantity_id,
                    "physical_opening_id": physical_id,
                    "axis": family.split("_")[1],
                    "value_m": amount,
                    "original_receipts": axis_receipts,
                }),
                amount, original_area, axis_receipts, opening,
            )
    actual = tuple(claim.opening_dimension_quantity_evidence)
    found = {}
    traces = {}
    for q in actual:
        if len(q.input_entity_ids) != 1:
            raise SourceClosedRunConflictError("opening axis lacks unique physical owner")
        physical_id = q.input_entity_ids[0]
        key = (physical_id, q.family)
        candidate = expected.get(key)
        if candidate is None or key in found:
            raise SourceClosedRunConflictError("unknown or duplicate original axis quantity")
        expected_id, amount, area, receipts, opening = candidate
        parent = area_traces.get(area.quantity_id)
        source_evidence = tuple(sorted(set((*area.evidence_ids, *receipts))))
        axis_name = q.family.split("_")[1]
        expected_formula = (
            "original_schedule_outer_frame_dimension_mm / 1000"
            if opening.area_basis == "authenticated_frame_schedule"
            else f"original_source_owned_{axis_name}_metres"
        )
        original_meta = {
            "document_id": opening.document_id,
            "revision_id": opening.revision_id,
            "source_sha256": opening.source_sha256,
            "snapshot_id": opening.snapshot_id,
            "page_no": opening.page_id,
            "viewport_id": opening.viewport_id,
            "canonical_opening_id": opening.canonical_opening_id,
            "physical_opening_id": opening.physical_opening_id,
            "opening_kind": opening.opening_kind,
            "host_wall_id": opening.host_wall_id,
            "area_basis": opening.area_basis,
            "source_area_quantity_id": area.quantity_id,
            "source_axis_record_ids": receipts,
            "material_finish_authority": "unavailable",
            "commercial_projection_allowed": False,
            "quantity_handoff_only": True,
            "do_not_infer_opening_count": True,
        }
        if (
            q.quantity_id != expected_id or q.value != amount
            or q.semantic_key != f"{q.family}:{physical_id}"
            or q.unit != "lm"
            or q.formula != expected_formula
            or q.formula_version != "1.0.0"
            or q.evidence_ids != source_evidence
            or q.authority != OPENING_SOURCE_DIMENSION_AUTHORITY
            or q.status != "corroborated" or q.confidence != 1.0
            or q.abstained or q.blocking_reasons
            or q.reason_codes != ("original_metric_opening_axis_resolved",)
            or dict(q.metadata) != original_meta
            or parent is None
        ):
            raise SourceClosedRunConflictError("replayed opening metric axis differs from original")
        found[key] = q
        traces[q.quantity_id] = CommercialTakeoffSourceTrace(
            workspace_id=workspace_id, project_id=project_id,
            document_id=parent.document_id,
            source_sha256=parent.source_sha256,
            source_page=parent.source_page,
            viewport_id=parent.viewport_id,
            revision_id=parent.revision_id,
            current_revision_id=parent.revision_id,
            evidence_ids=source_evidence,
            canonical_entity_ids=(physical_id,),
            metadata={
                "source_area_quantity_id": area.quantity_id,
                "commercial_projection_allowed": False,
            },
        )
    # A source-owned complete opening emits BOTH independent physical axes.
    # A missing sibling is not a valid half-published physical dimension pair.
    if set(found) != set(expected):
        raise SourceClosedRunConflictError("original opening source axis universe incomplete")
    sealed = seal_source_closed_run(
        actual, project_id=project_id, traces_by_quantity_id=traces,
    )
    if any(not row.lineage_ok for row in sealed.quantities):
        raise SourceClosedRunConflictError("opening axis claim lineage cannot seal")
    return sealed


__all__ = ["seal_live_opening_dimension_run", "seal_live_opening_dimension_claim_run"]
