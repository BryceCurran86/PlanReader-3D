"""Benchmark-neutral source-closed export for live physical opening areas.

This module bridges the already-authenticated live opening composition into the
existing source-closed run exporter. It does not discover openings, perform
benchmark identity mapping, read expected quantities, or weaken commercial
trace requirements.

Every sealed quantity is traced to the exact canonical physical opening,
document/revision/hash, owned viewport, source page and complete evidence set.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from pb_live_opening_area_quantity_publication import (
    publish_live_opening_area_quantities,
)
from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject,
    LivePhysicalOpeningVoidComposition,
)
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import (
    SealedSourceClosedRun,
    SourceClosedRunConflictError,
    seal_source_closed_run,
)


def _opening_by_identity(
    composition: LivePhysicalOpeningVoidComposition,
) -> Mapping[str, LiveCanonicalOpeningObject]:
    by_id: dict[str, LiveCanonicalOpeningObject] = {}
    for opening in composition.canonical_openings:
        if type(opening) is not LiveCanonicalOpeningObject:
            raise TypeError(
                "canonical_openings must contain LiveCanonicalOpeningObject"
            )
        canonical_id = str(opening.canonical_opening_id or "").strip()
        if not canonical_id:
            raise SourceClosedRunConflictError(
                "canonical opening identity must be non-empty"
            )
        if canonical_id in by_id:
            raise SourceClosedRunConflictError(
                f"duplicate canonical opening identity: {canonical_id}"
            )
        by_id[canonical_id] = opening
    return MappingProxyType(by_id)


def build_live_opening_area_source_traces(
    composition: LivePhysicalOpeningVoidComposition,
    *,
    workspace_id: int,
    project_id: str,
) -> Mapping[str, CommercialTakeoffSourceTrace]:
    """Build exact source traces for quantities publishable from a composition."""

    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError(
            "composition must be LivePhysicalOpeningVoidComposition"
        )

    quantities = publish_live_opening_area_quantities(composition)
    openings = _opening_by_identity(composition)
    traces: dict[str, CommercialTakeoffSourceTrace] = {}

    for quantity in quantities:
        if len(quantity.input_entity_ids) != 1:
            raise SourceClosedRunConflictError(
                "opening area quantity must reference exactly one canonical opening"
            )
        canonical_id = str(quantity.input_entity_ids[0])
        opening = openings.get(canonical_id)
        if opening is None:
            raise SourceClosedRunConflictError(
                f"opening area quantity references unknown identity: {canonical_id}"
            )
        if opening.physical_opening_id != canonical_id:
            raise SourceClosedRunConflictError(
                f"canonical/physical opening identity mismatch: {canonical_id}"
            )

        viewport_id = str(opening.viewport_id or "").strip()
        if not viewport_id:
            raise SourceClosedRunConflictError(
                f"opening area quantity lacks owned viewport: {canonical_id}"
            )
        evidence_ids = tuple(
            dict.fromkeys(
                str(value).strip()
                for value in opening.evidence_ids
                if str(value).strip()
            )
        )
        missing_evidence = set(quantity.evidence_ids) - set(evidence_ids)
        if missing_evidence:
            raise SourceClosedRunConflictError(
                "canonical opening trace does not cover quantity evidence: "
                + ", ".join(sorted(missing_evidence))
            )

        trace = CommercialTakeoffSourceTrace(
            workspace_id=workspace_id,
            project_id=project_id,
            document_id=opening.document_id,
            source_sha256=opening.source_sha256,
            source_page=opening.page_id,
            viewport_id=viewport_id,
            revision_id=opening.revision_id,
            current_revision_id=opening.revision_id,
            evidence_ids=evidence_ids,
            canonical_entity_ids=(canonical_id,),
            metadata={
                "family": quantity.family,
                "opening_kind": opening.opening_kind,
                "area_basis": opening.area_basis,
                "host_wall_id": opening.host_wall_id,
            },
        )
        if quantity.quantity_id in traces:
            raise SourceClosedRunConflictError(
                f"duplicate opening quantity id: {quantity.quantity_id}"
            )
        traces[quantity.quantity_id] = trace

    return MappingProxyType(traces)


def seal_live_opening_area_run(
    composition: LivePhysicalOpeningVoidComposition,
    *,
    workspace_id: int,
    project_id: str,
) -> SealedSourceClosedRun:
    """Seal all currently corroborated opening-area quantities.

    The returned run remains benchmark-neutral. Frozen identity mapping and V2
    reconciliation happen only after this function has returned the sealed run.
    """

    quantities = publish_live_opening_area_quantities(composition)
    traces = build_live_opening_area_source_traces(
        composition,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    return seal_source_closed_run(
        quantities,
        project_id=project_id,
        traces_by_quantity_id=traces,
    )


__all__ = [
    "build_live_opening_area_source_traces",
    "seal_live_opening_area_run",
]
