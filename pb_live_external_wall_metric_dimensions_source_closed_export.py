"""Authenticated original physical external-wall length and height in metres.

An external wall's net m2 is independently sourced by physical gross wall
polygon minus the COMPLETE physical opening void union. This module reuses
that authenticated source, not labels, proximity or guessed material faces.
"""
from __future__ import annotations

import math

from pb_live_external_wall_surface_area_quantity_publication import (
    publish_live_per_wall_surface_area_quantities,
)
from pb_live_external_physical_net_wall_publication import (
    LiveExternalPhysicalNetWallPublication,
)
from pb_migration_contracts import QuantityEvidence, stable_contract_id
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import (
    SealedSourceClosedRun, SourceClosedRunConflictError,
    seal_source_closed_run,
)


def _original_wall_linear_quantities(
    publication: LiveExternalPhysicalNetWallPublication,
) -> tuple[QuantityEvidence, ...]:
    if type(publication) is not LiveExternalPhysicalNetWallPublication:
        raise TypeError("publication must be original external physical wall")
    net = publish_live_per_wall_surface_area_quantities(publication)
    if not net:
        return ()
    area_by_wall = {q.input_entity_ids[0]: q for q in net}
    if len(area_by_wall) != len(publication.canonical_walls):
        return ()
    result = []
    for wall in publication.canonical_walls:
        source_area = area_by_wall.get(wall.physical_wall_id)
        if source_area is None:
            return ()
        axes = (wall.length_m, wall.height_m)
        if any(type(axis) not in (int, float) for axis in axes):
            return ()
        try:
            length, height = map(float, axes)
            gross = float(wall.gross_area_m2)
        except (ValueError, TypeError, OverflowError):
            return ()
        # Keep each axis independently source-bound to the same verified
        # whole-wall rectangle, not a selected unrelated smaller wall.
        if (
            not all(math.isfinite(v) and v > 0.0 for v in (length, height, gross))
            or not math.isfinite(length * height)
            or not math.isclose(length * height, gross, rel_tol=0.0, abs_tol=0.000002)
        ):
            return ()
        for axis, measured in (("wall_length", length), ("wall_height", height)):
            metres = round(measured, 6)
            if metres <= 0 or not math.isclose(metres, measured, rel_tol=0, abs_tol=1e-6):
                return ()
            result.append(QuantityEvidence(
                quantity_id=stable_contract_id("source_external_wall_linear_m", {
                    "wall_net_area_quantity_id": source_area.quantity_id,
                    "original_wall_id": wall.physical_wall_id,
                    "axis": axis,
                    "value_m": metres,
                    "gross_geometry_record_id": wall.gross_geometry_record_id,
                }),
                family=axis,
                semantic_key=f"{axis}:{wall.physical_wall_id}",
                value=metres,
                unit="lm",
                input_entity_ids=(wall.physical_wall_id,),
                formula=f"original_source_owned_{axis}_metres",
                formula_version="1.0.0",
                evidence_ids=source_area.evidence_ids,
                authority="original_external_wall_source_metric_geometry",
                status="corroborated",
                confidence=source_area.confidence,
                abstained=False,
                blocking_reasons=(),
                reason_codes=("original_physical_wall_linear_dimension_resolved",),
                metadata={
                    "document_id": wall.document_id,
                    "source_sha256":wall.source_sha256.lower(),
                    "revision_id":wall.revision_id,
                    "snapshot_id":wall.snapshot_id,
                    "page_no":wall.page_id,
                    "viewport_id":wall.plan_members[0].viewport_id,
                    "canonical_wall_id":wall.canonical_wall_id,
                    "physical_wall_id":wall.physical_wall_id,
                    "gross_geometry_record_id":wall.gross_geometry_record_id,
                    "source_net_area_quantity_id":source_area.quantity_id,
                    "source_verified_gross_area_m2":gross,
                    "material_finish_authority":"unavailable",
                    "commercial_projection_allowed":False,
                    "quantity_handoff_only":True,
                    "wall_face_multiplier_allowed":False,
                },
            ))
    return tuple(sorted(result,key=lambda q:q.quantity_id))


def publish_live_per_wall_linear_quantities(
    publication: LiveExternalPhysicalNetWallPublication,
) -> tuple[QuantityEvidence, ...]:
    """Publish original physical wall lengths/heights without finish authority."""
    return _original_wall_linear_quantities(publication)


def seal_live_per_wall_linear_run(
    publication: LiveExternalPhysicalNetWallPublication,
    *,
    workspace_id: int,
    project_id: str,
) -> SealedSourceClosedRun:
    """Seal real length/height after exact original wall area source reproof."""
    quantities = publish_live_per_wall_linear_quantities(publication)
    if not quantities:
        raise SourceClosedRunConflictError("no original source-complete wall length/height")
    wall_map = {w.physical_wall_id:w for w in publication.canonical_walls}
    traces = {}
    for q in quantities:
        original = wall_map[q.input_entity_ids[0]]
        traces[q.quantity_id] = CommercialTakeoffSourceTrace(
            workspace_id=workspace_id,project_id=project_id,
            document_id=original.document_id,
            source_sha256=original.source_sha256,
            source_page=original.page_id,
            viewport_id=original.plan_members[0].viewport_id,
            revision_id=original.revision_id,
            current_revision_id=original.revision_id,
            evidence_ids=q.evidence_ids,
            canonical_entity_ids=(original.physical_wall_id,),
            metadata={
                "source_net_area_quantity_id":q.metadata["source_net_area_quantity_id"],
                "commercial_finish_permission":False,
            },
        )
    sealed = seal_source_closed_run(
        quantities,project_id=project_id,traces_by_quantity_id=traces,
    )
    if len(sealed.quantities)!=len(quantities) or any(
        not row.lineage_ok or row.abstained for row in sealed.quantities
    ):
        raise SourceClosedRunConflictError("external wall linear source trace unsealed")
    return sealed


__all__ = [
    "publish_live_per_wall_linear_quantities",
    "seal_live_per_wall_linear_run",
]
