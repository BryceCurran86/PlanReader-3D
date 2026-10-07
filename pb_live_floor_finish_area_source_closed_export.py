"""Source-closed export for authenticated canonical floor-finish quantities.

Consumes only FIRM floor_finish_area QuantityEvidence already produced by
CrossViewFloorFinishProducer and retained on the same canonical floor. This
module does not infer finishes, dimensions, room identity, or benchmark mappings.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType

from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceObject
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import (
    SealedSourceClosedRun,
    SourceClosedRunConflictError,
    seal_source_closed_run,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def build_live_floor_finish_area_source_traces(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> Mapping[str, CommercialTakeoffSourceTrace]:
    """Build exact source traces for already-authenticated floor finishes."""
    if type(claim) is not LivePhysicalNetWallClaim:
        raise TypeError("claim must be LivePhysicalNetWallClaim")

    floors_by_id: dict[str, LiveCanonicalFloorSurfaceObject] = {}
    for floor in claim.canonical_floors:
        if type(floor) is not LiveCanonicalFloorSurfaceObject:
            raise TypeError(
                "canonical_floors must contain LiveCanonicalFloorSurfaceObject"
            )
        floor_id = _clean(floor.canonical_floor_id)
        if not floor_id:
            continue
        if floor_id in floors_by_id:
            raise SourceClosedRunConflictError(
                f"duplicate canonical floor identity: {floor_id}"
            )
        floors_by_id[floor_id] = floor

    traces: dict[str, CommercialTakeoffSourceTrace] = {}
    for quantity in claim.floor_finish_quantity_evidence:
        if not isinstance(quantity, QuantityEvidence):
            raise TypeError(
                "floor_finish_quantity_evidence must contain QuantityEvidence"
            )
        if quantity.family != "floor_finish_area":
            raise SourceClosedRunConflictError(
                f"non-floor-finish quantity reached exporter: {quantity.quantity_id}"
            )
        if quantity.abstained or quantity.value is None:
            continue
        if len(quantity.input_entity_ids) != 1:
            raise SourceClosedRunConflictError(
                "floor-finish quantity must own exactly one canonical floor: "
                f"{quantity.quantity_id}"
            )

        floor_id = _clean(quantity.input_entity_ids[0])
        floor = floors_by_id.get(floor_id)
        if floor is None:
            raise SourceClosedRunConflictError(
                f"floor-finish quantity references unknown canonical floor: {floor_id}"
            )
        if not floor.physical_floor_surface_identity_resolved:
            raise SourceClosedRunConflictError(
                f"physical floor identity is unresolved: {floor_id}"
            )
        if not _clean(floor.physical_floor_surface_id):
            raise SourceClosedRunConflictError(
                f"physical floor identity is missing: {floor_id}"
            )

        try:
            qvalue = float(quantity.value)
            floor_value = float(floor.metric_area_m2)
        except (TypeError, ValueError, OverflowError) as exc:
            raise SourceClosedRunConflictError(
                f"floor-finish quantity is not metric: {quantity.quantity_id}"
            ) from exc
        if (
            not math.isfinite(qvalue)
            or qvalue <= 0.0
            or not math.isfinite(floor_value)
            or abs(qvalue - floor_value) > 1e-9
        ):
            raise SourceClosedRunConflictError(
                "floor-finish quantity value disagrees with canonical floor: "
                f"{quantity.quantity_id}"
            )

        metadata = (
            quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
        )
        if _clean(metadata.get("canonical_floor_id")) != floor_id:
            raise SourceClosedRunConflictError(
                "floor-finish canonical identity metadata mismatch: "
                f"{quantity.quantity_id}"
            )
        if _clean(metadata.get("physical_floor_surface_id")) != _clean(
            floor.physical_floor_surface_id
        ):
            raise SourceClosedRunConflictError(
                "floor-finish physical identity metadata mismatch: "
                f"{quantity.quantity_id}"
            )
        if _clean(metadata.get("source_sha256")).lower() != _clean(
            floor.source_sha256
        ).lower():
            raise SourceClosedRunConflictError(
                f"floor-finish source SHA mismatch: {quantity.quantity_id}"
            )
        if _clean(metadata.get("revision_id")) != _clean(floor.revision_id):
            raise SourceClosedRunConflictError(
                f"floor-finish revision mismatch: {quantity.quantity_id}"
            )

        semantic_finish = _clean(metadata.get("semantic_finish")).lower()
        if (
            not _clean(metadata.get("support_snapshot_id"))
            or not semantic_finish
            or _clean(floor.finish_descriptor).lower() != semantic_finish
        ):
            raise SourceClosedRunConflictError(
                "floor-finish semantic mismatch with canonical floor: "
                f"{quantity.quantity_id}"
            )

        viewport_id = _clean(metadata.get("viewport_id"))
        if not viewport_id:
            raise SourceClosedRunConflictError(
                f"floor-finish quantity lacks owned viewport: {quantity.quantity_id}"
            )
        if _clean(floor.viewport_id) and _clean(floor.viewport_id) != viewport_id:
            raise SourceClosedRunConflictError(
                f"floor-finish viewport mismatch: {quantity.quantity_id}"
            )

        floor_evidence = {
            _clean(value) for value in floor.evidence_ids if _clean(value)
        }
        if not set(quantity.evidence_ids).issubset(floor_evidence):
            raise SourceClosedRunConflictError(
                "floor-finish source trace does not cover quantity evidence: "
                f"{quantity.quantity_id}"
            )

        points = tuple(floor.polygon_pdf_pts or ())
        source_bbox = None
        if points:
            try:
                xs = tuple(float(point[0]) for point in points)
                ys = tuple(float(point[1]) for point in points)
            except (TypeError, ValueError, IndexError) as exc:
                raise SourceClosedRunConflictError(
                    f"floor source polygon is invalid: {quantity.quantity_id}"
                ) from exc
            if xs and ys:
                source_bbox = (min(xs), min(ys), max(xs), max(ys))

        trace = CommercialTakeoffSourceTrace(
            workspace_id=int(workspace_id),
            project_id=str(project_id),
            document_id=floor.document_id,
            source_sha256=floor.source_sha256,
            source_page=str(floor.page_id),
            viewport_id=viewport_id,
            revision_id=floor.revision_id,
            current_revision_id=floor.revision_id,
            evidence_ids=tuple(sorted(floor_evidence)),
            canonical_entity_ids=tuple(
                dict.fromkeys(
                    value
                    for value in (
                        floor_id,
                        _clean(floor.physical_floor_surface_id),
                        _clean(floor.room_entity_id),
                    )
                    if value
                )
            ),
            source_bbox=source_bbox,
            metadata={
                "family": "floor_finish_area",
                "canonical_floor_id": floor_id,
                "physical_floor_surface_id": floor.physical_floor_surface_id,
                "room_entity_id": floor.room_entity_id,
                "source_room_face_record_id": floor.source_room_face_record_id,
                "finish_code": metadata.get("finish_code"),
                "semantic_finish": semantic_finish,
                "support_snapshot_id": metadata.get("support_snapshot_id"),
                "finish_definition_record_id": metadata.get(
                    "finish_definition_record_id"
                ),
                "finish_occurrence_record_id": metadata.get(
                    "finish_occurrence_record_id"
                ),
                "source_dimension_page_id": metadata.get(
                    "source_dimension_page_id"
                ),
            },
        )
        if quantity.quantity_id in traces:
            raise SourceClosedRunConflictError(
                f"duplicate floor-finish quantity id: {quantity.quantity_id}"
            )
        traces[quantity.quantity_id] = trace

    return MappingProxyType(traces)


def seal_live_floor_finish_area_run(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> SealedSourceClosedRun:
    """Seal already-FIRM canonical floor-finish area quantities."""
    quantities = tuple(
        quantity
        for quantity in claim.floor_finish_quantity_evidence
        if isinstance(quantity, QuantityEvidence)
        and not quantity.abstained
        and quantity.value is not None
    )
    traces = build_live_floor_finish_area_source_traces(
        claim,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    return seal_source_closed_run(
        quantities,
        project_id=project_id,
        traces_by_quantity_id=traces,
    )


__all__ = [
    "build_live_floor_finish_area_source_traces",
    "seal_live_floor_finish_area_run",
]
