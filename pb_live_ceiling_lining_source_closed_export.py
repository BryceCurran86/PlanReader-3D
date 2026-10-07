"""Source-closed export for cross-view canonical ceiling-lining quantities.

Consumes only typed ceiling_lining_quantity_evidence already published by the
live integration. This module does not extract, bind, measure, infer a finish,
read benchmark truth, or create a new quantity.
"""
from __future__ import annotations

import math
from types import MappingProxyType
from typing import Mapping

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
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


def build_live_ceiling_lining_source_traces(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> Mapping[str, CommercialTakeoffSourceTrace]:
    if type(claim) is not LivePhysicalNetWallClaim:
        raise TypeError("claim must be LivePhysicalNetWallClaim")

    rooms_by_canonical_id = {}
    rooms_by_physical_id = {}
    for room in claim.canonical_rooms:
        canonical_id = _clean(room.canonical_room_id)
        physical_id = _clean(room.physical_room_id)
        if not canonical_id or not physical_id:
            continue
        if canonical_id in rooms_by_canonical_id:
            raise SourceClosedRunConflictError(
                f"duplicate canonical room identity: {canonical_id}"
            )
        if physical_id in rooms_by_physical_id:
            raise SourceClosedRunConflictError(
                f"duplicate physical room identity: {physical_id}"
            )
        rooms_by_canonical_id[canonical_id] = room
        rooms_by_physical_id[physical_id] = room

    traces: dict[str, CommercialTakeoffSourceTrace] = {}
    for quantity in claim.ceiling_lining_quantity_evidence:
        if not isinstance(quantity, QuantityEvidence):
            raise TypeError(
                "ceiling_lining_quantity_evidence must contain QuantityEvidence"
            )
        if quantity.family != "ceiling_lining":
            raise SourceClosedRunConflictError(
                f"non-ceiling quantity reached ceiling exporter: {quantity.quantity_id}"
            )
        if quantity.abstained or quantity.value is None:
            continue
        if len(quantity.input_entity_ids) != 1:
            raise SourceClosedRunConflictError(
                f"ceiling quantity must own one canonical ceiling identity: "
                f"{quantity.quantity_id}"
            )
        if (
            _clean(quantity.status) != AuthorityStatus.FIRM.value
            or _clean(quantity.authority)
            != MeasurementAuthorityType.DOCUMENTED_DIMENSION.value
        ):
            raise SourceClosedRunConflictError(
                f"ceiling quantity is not firm documented authority: "
                f"{quantity.quantity_id}"
            )

        metadata = (
            quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
        )
        canonical_ceiling_id = _clean(quantity.input_entity_ids[0])
        if _clean(metadata.get("canonical_ceiling_id")) != canonical_ceiling_id:
            raise SourceClosedRunConflictError(
                f"ceiling quantity canonical identity mismatch: "
                f"{quantity.quantity_id}"
            )
        if (
            _clean(metadata.get("physical_ceiling_surface_id"))
            != canonical_ceiling_id
        ):
            raise SourceClosedRunConflictError(
                f"ceiling quantity physical identity mismatch: "
                f"{quantity.quantity_id}"
            )
        canonical_room_id = _clean(metadata.get("canonical_room_id"))
        physical_room_id = _clean(metadata.get("physical_room_id"))
        room = rooms_by_canonical_id.get(canonical_room_id)
        if (
            room is None
            or rooms_by_physical_id.get(physical_room_id) is not room
            or _clean(room.source_room_face_record_id)
            != _clean(metadata.get("source_room_face_record_id"))
        ):
            raise SourceClosedRunConflictError(
                f"ceiling quantity references unknown room identity: "
                f"{quantity.quantity_id}"
            )
        if (
            _clean(metadata.get("source_sha256")).lower()
            != _clean(room.source_sha256).lower()
            or _clean(metadata.get("revision_id")) != _clean(room.revision_id)
            or _clean(metadata.get("page_no")) != _clean(room.page_id)
        ):
            raise SourceClosedRunConflictError(
                f"ceiling quantity source lineage mismatch: "
                f"{quantity.quantity_id}"
            )
        viewport_id = _clean(metadata.get("viewport_id")) or _clean(
            room.viewport_id
        )
        if not viewport_id:
            raise SourceClosedRunConflictError(
                f"ceiling quantity lacks owned room viewport: "
                f"{quantity.quantity_id}"
            )
        if _clean(room.viewport_id) and _clean(room.viewport_id) != viewport_id:
            raise SourceClosedRunConflictError(
                f"ceiling quantity room viewport mismatch: "
                f"{quantity.quantity_id}"
            )
        if _clean(metadata.get("row_role")) != "ceiling_area":
            raise SourceClosedRunConflictError(
                f"ceiling quantity row role mismatch: {quantity.quantity_id}"
            )

        try:
            value = float(quantity.value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise SourceClosedRunConflictError(
                f"ceiling quantity is not metric: {quantity.quantity_id}"
            ) from exc
        if not math.isfinite(value) or value <= 0.0:
            raise SourceClosedRunConflictError(
                f"ceiling quantity must be positive: {quantity.quantity_id}"
            )

        points = tuple(room.polygon_pdf_pts or ())
        source_bbox = None
        if points:
            try:
                xs = tuple(float(point[0]) for point in points)
                ys = tuple(float(point[1]) for point in points)
            except (TypeError, ValueError, IndexError) as exc:
                raise SourceClosedRunConflictError(
                    f"ceiling source room polygon is invalid: "
                    f"{quantity.quantity_id}"
                ) from exc
            if xs and ys:
                source_bbox = (min(xs), min(ys), max(xs), max(ys))

        evidence_ids = tuple(
            dict.fromkeys(
                _clean(value)
                for value in quantity.evidence_ids
                if _clean(value)
            )
        )
        if not evidence_ids:
            raise SourceClosedRunConflictError(
                f"ceiling quantity lacks evidence trace: {quantity.quantity_id}"
            )

        trace = CommercialTakeoffSourceTrace(
            workspace_id=int(workspace_id),
            project_id=str(project_id),
            document_id=room.document_id,
            source_sha256=room.source_sha256,
            source_page=str(room.page_id),
            viewport_id=viewport_id,
            revision_id=room.revision_id,
            current_revision_id=room.revision_id,
            evidence_ids=evidence_ids,
            canonical_entity_ids=tuple(
                dict.fromkeys(
                    (
                        canonical_ceiling_id,
                        canonical_room_id,
                        physical_room_id,
                    )
                )
            ),
            source_bbox=source_bbox,
            metadata={
                "family": "ceiling_lining",
                "canonical_ceiling_id": canonical_ceiling_id,
                "physical_ceiling_surface_id": canonical_ceiling_id,
                "canonical_room_id": canonical_room_id,
                "physical_room_id": physical_room_id,
                "source_room_face_record_id": room.source_room_face_record_id,
                "support_page_id": metadata.get("support_page_id"),
                "support_viewport_id": metadata.get("support_viewport_id"),
                "finish_code": metadata.get("finish_code"),
                "semantic_finish": metadata.get("semantic_finish"),
            },
        )
        if quantity.quantity_id in traces:
            raise SourceClosedRunConflictError(
                f"duplicate ceiling quantity id: {quantity.quantity_id}"
            )
        traces[quantity.quantity_id] = trace

    return MappingProxyType(traces)


def seal_live_ceiling_lining_run(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> SealedSourceClosedRun:
    quantities = tuple(
        quantity
        for quantity in claim.ceiling_lining_quantity_evidence
        if not quantity.abstained and quantity.value is not None
    )
    traces = build_live_ceiling_lining_source_traces(
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
    "build_live_ceiling_lining_source_traces",
    "seal_live_ceiling_lining_run",
]
