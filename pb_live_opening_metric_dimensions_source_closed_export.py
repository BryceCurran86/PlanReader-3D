"""Signed original-source opening width and height measured in metres.

Never invert a figured area to guess a side or claim a source-derived opening
count. This is a source-closed engineering quantity, not direct customer
pricing/material approval. Its already-authenticated opening area is immutable.
"""
from __future__ import annotations

from collections import defaultdict

from pb_live_opening_area_quantity_publication import (
    publish_live_opening_area_quantities,
)
from pb_live_opening_metric_dimensions_quantity_publication import (
    publish_live_opening_dimension_quantities,
)
from pb_live_opening_source_closed_export import (
    build_live_opening_area_source_traces,
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


__all__ = ["seal_live_opening_dimension_run"]
