"""Fail-closed room-area QuantityEvidence -> commercial takeoff projection.

This bridge owns no extraction, geometry, room matching by proximity, project
identity inference, or commercial approval. It composes already source-owned
room-area quantities with the exact canonical floor/room that carries the same
quantity identity, then delegates source-trace and measurement authority to the
canonical M5 binders.

Returned rows remain unreviewed ("To review") and therefore stay behind the
existing estimator/commercial/JobHub publication gates.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceObject
from pb_live_canonical_room_composition import LiveCanonicalRoomObject
from pb_migration_contracts import QuantityEvidence, stable_contract_id
from pb_migration_measurement_authority_binder import (
    MeasurementAuthorityBindingError,
    bind_commercial_measurement_authority,
)
from pb_migration_provider_envelope import ProviderContext
from pb_migration_source_trace_binder import (
    SourceTraceBindingError,
    bind_commercial_source_trace,
)
from pb_quantity_takeoff_adapter import (
    CommercialTakeoffProjectionError,
    quantity_evidence_to_takeoff_output_row,
)


ROOM_AREA_CUSTOMER_BRIDGE_VERSION = "1.0.0"


@dataclass(frozen=True)
class RoomAreaCustomerBridgeResult:
    rows: tuple[dict[str, Any], ...]
    projected_quantity_ids: tuple[str, ...]
    blocked: tuple[tuple[str, tuple[str, ...]], ...]
    schema_version: str = ROOM_AREA_CUSTOMER_BRIDGE_VERSION


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _blocking_entry(
    blocked: dict[str, set[str]],
    quantity_id: str,
    reason: str,
) -> None:
    blocked.setdefault(str(quantity_id or "<missing>"), set()).add(str(reason))


def _positive_workspace_id(value: int) -> int:
    if isinstance(value, bool):
        raise ValueError("workspace_id must be a positive integer")
    workspace_id = int(value)
    if workspace_id <= 0:
        raise ValueError("workspace_id must be a positive integer")
    return workspace_id


def project_room_area_customer_rows(
    *,
    quantities: Sequence[QuantityEvidence],
    floors: Sequence[LiveCanonicalFloorSurfaceObject],
    rooms: Sequence[LiveCanonicalRoomObject],
    workspace_id: int,
    project_id: str,
) -> RoomAreaCustomerBridgeResult:
    """Project only identity-proven room areas through the canonical M5 adapters."""

    workspace_record_id = _positive_workspace_id(workspace_id)
    trusted_project_id = str(project_id or "").strip()
    if not trusted_project_id:
        raise ValueError("project_id must be supplied by orchestration")

    if any(type(item) is not QuantityEvidence for item in quantities):
        raise TypeError("quantities must contain exact QuantityEvidence records")
    if any(type(item) is not LiveCanonicalFloorSurfaceObject for item in floors):
        raise TypeError("floors must contain exact LiveCanonicalFloorSurfaceObject records")
    if any(type(item) is not LiveCanonicalRoomObject for item in rooms):
        raise TypeError("rooms must contain exact LiveCanonicalRoomObject records")

    floors_by_quantity: dict[str, list[LiveCanonicalFloorSurfaceObject]] = {}
    for floor in floors:
        quantity_id = str(floor.metric_area_quantity_id or "").strip()
        if quantity_id:
            floors_by_quantity.setdefault(quantity_id, []).append(floor)

    rooms_by_id: dict[str, list[LiveCanonicalRoomObject]] = {}
    for room in rooms:
        room_id = str(room.canonical_room_id or "").strip()
        if room_id:
            rooms_by_id.setdefault(room_id, []).append(room)

    semantic_counts: dict[str, int] = {}
    for quantity in quantities:
        if not quantity.abstained:
            semantic_counts[str(quantity.semantic_key or "")] = (
                semantic_counts.get(str(quantity.semantic_key or ""), 0) + 1
            )

    blocked: dict[str, set[str]] = {}
    rows: list[dict[str, Any]] = []
    projected_ids: list[str] = []

    for quantity in sorted(quantities, key=lambda item: str(item.quantity_id)):
        quantity_id = str(quantity.quantity_id or "").strip()
        reasons: list[str] = []

        if (
            quantity.abstained
            or quantity.value is None
            or str(quantity.family or "") != "room_area"
            or str(quantity.status or "").strip().lower() != AuthorityStatus.FIRM.value
            or str(quantity.authority or "") != MeasurementAuthorityType.DOCUMENTED_DIMENSION.value
            or str(quantity.unit or "").strip().lower() not in {"m2", "m²"}
        ):
            reasons.append("room_area_quantity_not_firm_documented")
        try:
            numeric_value = float(quantity.value) if quantity.value is not None else float("nan")
        except (TypeError, ValueError, OverflowError):
            numeric_value = float("nan")
        if not math.isfinite(numeric_value) or numeric_value <= 0.0:
            reasons.append("room_area_quantity_invalid")

        if semantic_counts.get(str(quantity.semantic_key or ""), 0) != 1:
            reasons.append("room_area_semantic_claim_not_unique")

        matching_floors = floors_by_quantity.get(quantity_id, ())
        if len(matching_floors) != 1:
            reasons.append("canonical_floor_quantity_link_not_unique")
            floor = None
        else:
            floor = matching_floors[0]

        room = None
        if floor is not None:
            matching_rooms = rooms_by_id.get(str(floor.room_entity_id or "").strip(), ())
            if len(matching_rooms) != 1:
                reasons.append("canonical_room_floor_link_not_unique")
            else:
                room = matching_rooms[0]

        metadata = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
        figured_ids = tuple(
            sorted(
                {
                    str(value).strip()
                    for value in (metadata.get("figured_dimension_ids") or ())
                    if str(value).strip()
                }
            )
        )
        if len(figured_ids) != 2:
            reasons.append("room_area_requires_two_figured_dimension_ids")

        for key in ("section", "element", "location", "substrate", "row_role"):
            if not str(metadata.get(key) or "").strip():
                reasons.append(f"room_area_customer_{key}_missing")
        if str(metadata.get("row_role") or "").strip() != "floor_area":
            reasons.append("room_area_customer_row_role_invalid")

        if room is not None:
            room_label = str(room.room_label or "").strip()
            if (
                not room_label
                or not room.room_label_binding_record_id
                or not room.room_label_evidence_ids
            ):
                reasons.append("canonical_room_authenticated_label_unavailable")
            metadata_label = str(metadata.get("room_label") or "").strip()
            if not metadata_label or _norm(metadata_label) != _norm(room_label):
                reasons.append("room_area_customer_label_lineage_mismatch")

        if floor is not None:
            if floor.metric_area_m2 is None:
                reasons.append("canonical_floor_metric_area_unavailable")
            else:
                try:
                    floor_area = float(floor.metric_area_m2)
                except (TypeError, ValueError, OverflowError):
                    floor_area = float("nan")
                if (
                    not math.isfinite(floor_area)
                    or abs(floor_area - numeric_value) > 1e-9
                ):
                    reasons.append("canonical_floor_metric_area_mismatch")
            if str(floor.metric_area_authority or "") != str(quantity.authority or ""):
                reasons.append("canonical_floor_metric_authority_mismatch")
            if not floor.physical_floor_surface_identity_resolved:
                reasons.append("canonical_floor_physical_identity_unresolved")

        if reasons:
            for reason in reasons:
                _blocking_entry(blocked, quantity_id, reason)
            continue

        assert floor is not None
        assert room is not None
        try:
            page_no = int(str(floor.page_id))
        except (TypeError, ValueError, OverflowError):
            _blocking_entry(blocked, quantity_id, "canonical_floor_source_page_invalid")
            continue
        if page_no <= 0 or not str(floor.viewport_id or "").strip():
            _blocking_entry(blocked, quantity_id, "canonical_floor_source_scope_unavailable")
            continue

        context = ProviderContext(
            run_id=stable_contract_id(
                "room_area_customer_projection",
                {
                    "workspace_id": workspace_record_id,
                    "project_id": trusted_project_id,
                    "quantity_id": quantity_id,
                },
            ),
            workspace_id=str(workspace_record_id),
            workspace_record_id=workspace_record_id,
            project_id=trusted_project_id,
            document_id=str(floor.document_id),
            source_sha256=str(floor.source_sha256),
            revision_id=str(floor.revision_id),
            current_revision_id=str(floor.revision_id),
            selected_pages=(page_no - 1,),
            owned_page_numbers=(page_no,),
            owned_viewport_ids=(str(floor.viewport_id),),
            viewport_page_ownership=((str(floor.viewport_id), page_no),),
            evidence_snapshot_id=str(floor.snapshot_id),
            canonical_graph_snapshot_id=str(floor.physical_floor_surface_id),
            measurement_authority_snapshot_id=stable_contract_id(
                "room_area_figured_dimensions",
                {"quantity_id": quantity_id, "dimension_ids": figured_ids},
            ),
        )

        try:
            trace = bind_commercial_source_trace(
                quantity,
                context,
                primary_page=page_no,
                primary_viewport_id=str(floor.viewport_id),
            )
            authority = bind_commercial_measurement_authority(
                quantity,
                figured_dimension_ids=figured_ids,
            )
            row = quantity_evidence_to_takeoff_output_row(
                quantity,
                trace=trace,
                authority=authority,
            )
        except (
            SourceTraceBindingError,
            MeasurementAuthorityBindingError,
            CommercialTakeoffProjectionError,
            ValueError,
        ) as exc:
            _blocking_entry(
                blocked,
                quantity_id,
                f"commercial_binding_failed:{type(exc).__name__}",
            )
            continue

        if row is None:
            _blocking_entry(blocked, quantity_id, "commercial_projection_abstained")
            continue
        if str(row.get("quantity_status") or "") != "To review":
            _blocking_entry(blocked, quantity_id, "commercial_projection_not_unreviewed")
            continue

        rows.append(row)
        projected_ids.append(quantity_id)

    return RoomAreaCustomerBridgeResult(
        rows=tuple(rows),
        projected_quantity_ids=tuple(projected_ids),
        blocked=tuple(
            (quantity_id, tuple(sorted(reasons)))
            for quantity_id, reasons in sorted(blocked.items())
        ),
    )


__all__ = [
    "ROOM_AREA_CUSTOMER_BRIDGE_VERSION",
    "RoomAreaCustomerBridgeResult",
    "project_room_area_customer_rows",
]
