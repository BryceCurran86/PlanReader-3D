"""Source-closed export for canonical floor-area quantities.

Consumes only floor-area QuantityEvidence already published from a FIRM room-area
authority by publish_live_floor_area_quantities. This module does not measure
floors and does not read benchmark truth.
"""
from __future__ import annotations

import math
from types import MappingProxyType
from typing import Mapping

from pb_live_floor_area_quantity_publication import (
    publish_live_floor_area_quantities,
)
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


def _source_floor_area_simple_bbox(
    points: list[tuple[float, float]] | tuple[tuple[float, float], ...],
    *,
    quantity_id: str,
) -> tuple[float, float, float, float]:
    """Reject invalid original floor topology; never infer m² from the bbox."""
    if not isinstance(points, (tuple, list)):
        raise SourceClosedRunConflictError(
            f"original floor source ring is not a typed coordinate list: {quantity_id}"
        )
    def finite_source_coordinate(value: object) -> bool:
        if type(value) not in (int, float):
            return False
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError, OverflowError):
            return False

    if any(
        type(point) not in (tuple, list) or len(point) != 2
        or any(not finite_source_coordinate(value) for value in point)
        for point in points
    ):
        raise SourceClosedRunConflictError(
            f"original floor source ring has malformed points: {quantity_id}"
        )
    ring = tuple((float(x), float(y)) for x, y in points)
    if len(ring) > 1 and ring[-1] == ring[0]:
        ring = ring[:-1]
    if len(ring) < 3 or len(set(ring)) != len(ring):
        raise SourceClosedRunConflictError(
            f"original floor source ring is not simple: {quantity_id}"
        )
    from shapely.errors import GEOSException
    from shapely.geometry import Polygon
    try:
        polygon = Polygon(ring)
        valid = (
            polygon.is_valid and polygon.exterior.is_simple
            and math.isfinite(polygon.area) and polygon.area > 0.0
        )
    except (GEOSException, ValueError, OverflowError) as exc:
        raise SourceClosedRunConflictError(
            f"original floor source ring GEOS geometry invalid: {quantity_id}"
        ) from exc
    if not valid:
        raise SourceClosedRunConflictError(
            f"original floor source ring is not simple: {quantity_id}"
        )
    return polygon.bounds


def _same_original_floor_room_ring(
    floor_points: object,
    room_points: object,
    *,
    quantity_id: str,
) -> bool:
    """Exact original PDF vertices, modulo cycle start, winding and closure.

    This is a negative source-ownership test, never a source of metric area.
    Both rings must independently be simple; no tolerance or snap can turn
    a different physical boundary into the same original room.
    """
    _source_floor_area_simple_bbox(floor_points, quantity_id=quantity_id)
    _source_floor_area_simple_bbox(room_points, quantity_id=quantity_id)
    floor_ring = tuple((float(x), float(y)) for x, y in floor_points)
    room_ring = tuple((float(x), float(y)) for x, y in room_points)
    if floor_ring[0] == floor_ring[-1]:
        floor_ring = floor_ring[:-1]
    if room_ring[0] == room_ring[-1]:
        room_ring = room_ring[:-1]
    if len(floor_ring) != len(room_ring):
        return False
    try:
        start = room_ring.index(floor_ring[0])
    except ValueError:
        return False
    n = len(floor_ring)
    return (
        all(floor_ring[i] == room_ring[(start + i) % n] for i in range(n))
        or all(floor_ring[i] == room_ring[(start - i) % n] for i in range(n))
    )


def build_live_floor_area_source_traces(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> Mapping[str, CommercialTakeoffSourceTrace]:
    """Build exact floor-owned source traces for final floor-area quantities."""
    if type(claim) is not LivePhysicalNetWallClaim:
        raise TypeError("claim must be LivePhysicalNetWallClaim")
    # A lossy int(True), int(7.9) or int("7") must not become a
    # source-authenticated commercial workspace at the final floor boundary.
    if type(workspace_id) is not int or workspace_id <= 0:
        raise SourceClosedRunConflictError(
            "floor source workspace_id must be an original positive integer"
        )

    # Canonical floor publication deliberately tolerates provisional replay
    # of a room measurement. A commercial floor-area seal cannot: two
    # producer-owned receipts using one original room-area source ID must
    # remain a conflict even when one has ABSTAINED before publication.
    original_room_area_ids: set[str] = set()
    for original in claim.room_area_quantity_evidence:
        if not isinstance(original, QuantityEvidence):
            raise TypeError("room_area_quantity_evidence must contain QuantityEvidence")
        if original.family != "room_area":
            raise SourceClosedRunConflictError(
                "floor area source inventory contains a non-room-area quantity"
            )
        source_id = original.quantity_id
        if (type(source_id) is not str or not source_id
                or source_id != source_id.strip()):
            raise SourceClosedRunConflictError(
                "invalid original room-area source ID in floor seal"
            )
        if source_id in original_room_area_ids:
            raise SourceClosedRunConflictError(
                f"duplicate original room-area source ID in floor seal: {source_id}"
            )
        original_room_area_ids.add(source_id)

        # The producer may correctly abstain from a numeric FIRM room-area
        # receipt that still carries source blockers. The final floor seal
        # must not quietly treat that contradictory original as absent,
        # including when no floor-area quantity survives publication.
        if (
            not original.abstained
            and original.value is not None
            and _clean(original.status).casefold() == "firm"
            and original.blocking_reasons
        ):
            raise SourceClosedRunConflictError(
                "original numeric firm room-area source retains unresolved blockers: "
                f"{source_id}"
            )

    floors_by_physical_id = {}
    for floor in claim.canonical_floors:
        physical_id = _clean(floor.physical_floor_surface_id)
        if not physical_id:
            continue
        if physical_id in floors_by_physical_id:
            raise SourceClosedRunConflictError(
                f"duplicate physical floor surface identity: {physical_id}"
            )
        floors_by_physical_id[physical_id] = floor

    # A source-derived canonical floor normally copies the physical ROOM's
    # original PDF ring. Keep the legacy room-less floor seal unchanged, but
    # when the producer supplies canonical rooms, do not allow a mismatched
    # room or two rival room owners to lend their original face to a FIRM floor.
    room_owners_by_id: dict[str, list[object]] = {}
    for room in claim.canonical_rooms:
        room_id = _clean(getattr(room, "canonical_room_id", None))
        if room_id:
            room_owners_by_id.setdefault(room_id, []).append(room)

    traces: dict[str, CommercialTakeoffSourceTrace] = {}
    for quantity in publish_live_floor_area_quantities(claim):
        if not isinstance(quantity, QuantityEvidence):
            raise TypeError("floor quantities must contain QuantityEvidence")
        if quantity.family != "floor_area":
            raise SourceClosedRunConflictError(
                f"non-floor quantity reached floor exporter: {quantity.quantity_id}"
            )
        if quantity.abstained or quantity.value is None:
            continue
        if len(quantity.input_entity_ids) != 1:
            raise SourceClosedRunConflictError(
                f"floor quantity must own one physical floor identity: {quantity.quantity_id}"
            )

        physical_id = _clean(quantity.input_entity_ids[0])
        floor = floors_by_physical_id.get(physical_id)
        if floor is None:
            raise SourceClosedRunConflictError(
                f"floor quantity references unknown physical floor: {physical_id}"
            )
        if not floor.physical_floor_surface_identity_resolved:
            raise SourceClosedRunConflictError(
                f"physical floor identity is unresolved: {physical_id}"
            )

        try:
            qvalue = float(quantity.value)
            floor_value = float(floor.metric_area_m2)
        except (TypeError, ValueError, OverflowError) as exc:
            raise SourceClosedRunConflictError(
                f"floor quantity is not metric: {quantity.quantity_id}"
            ) from exc
        if (
            not math.isfinite(qvalue)
            or qvalue <= 0.0
            or not math.isfinite(floor_value)
            or abs(qvalue - floor_value) > 1e-9
        ):
            raise SourceClosedRunConflictError(
                f"floor quantity value disagrees with canonical floor: {quantity.quantity_id}"
            )

        metadata = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
        if _clean(metadata.get("physical_floor_surface_id")) != physical_id:
            raise SourceClosedRunConflictError(
                f"floor quantity physical identity metadata mismatch: {quantity.quantity_id}"
            )
        if _clean(metadata.get("canonical_floor_id")) != _clean(floor.canonical_floor_id):
            raise SourceClosedRunConflictError(
                f"floor quantity canonical identity mismatch: {quantity.quantity_id}"
            )
        if _clean(metadata.get("source_sha256")).lower() != _clean(floor.source_sha256).lower():
            raise SourceClosedRunConflictError(
                f"floor quantity source SHA mismatch: {quantity.quantity_id}"
            )
        if _clean(metadata.get("revision_id")) != _clean(floor.revision_id):
            raise SourceClosedRunConflictError(
                f"floor quantity revision mismatch: {quantity.quantity_id}"
            )

        viewport_id = _clean(metadata.get("viewport_id"))
        if not viewport_id:
            raise SourceClosedRunConflictError(
                f"floor quantity lacks owned viewport: {quantity.quantity_id}"
            )
        if _clean(floor.viewport_id) and _clean(floor.viewport_id) != viewport_id:
            raise SourceClosedRunConflictError(
                f"floor quantity viewport mismatch: {quantity.quantity_id}"
            )

        for receipts in (floor.evidence_ids, quantity.evidence_ids):
            if (
                not isinstance(receipts, (tuple, list))
                or not receipts
                or any(type(value) is not str or not value or value != value.strip()
                       for value in receipts)
                or len(set(receipts)) != len(receipts)
            ):
                raise SourceClosedRunConflictError(
                    f"floor source evidence receipts are incomplete: {quantity.quantity_id}"
                )
        evidence_ids = tuple(floor.evidence_ids)
        if not set(quantity.evidence_ids).issubset(set(evidence_ids)):
            raise SourceClosedRunConflictError(
                f"floor source trace does not cover quantity evidence: {quantity.quantity_id}"
            )

        # Original page-point vertices are provenance, NOT measured m².
        # Validate their exact typed geometry before persisting a source bbox.
        # A positive bbox alone can surround a self-cancelling zero-area ring.
        points = floor.polygon_pdf_pts
        if (
            not floor.geometry_complete
            or type(points) not in (list, tuple)
            or len(points) < 3
        ):
            raise SourceClosedRunConflictError(
                f"floor source geometry is missing or incomplete: {quantity.quantity_id}"
            )
        checked: list[tuple[float, float]] = []
        for point in points:
            if (
                type(point) not in (list, tuple)
                or len(point) != 2
                or any(type(value) not in (int, float) for value in point)
            ):
                raise SourceClosedRunConflictError(
                    f"floor source polygon is invalid: {quantity.quantity_id}"
                )
            try:
                x, y = float(point[0]), float(point[1])
            except (TypeError, ValueError, OverflowError) as exc:
                raise SourceClosedRunConflictError(
                    f"floor source polygon is invalid: {quantity.quantity_id}"
                ) from exc
            if not math.isfinite(x) or not math.isfinite(y):
                raise SourceClosedRunConflictError(
                    f"floor source polygon is invalid: {quantity.quantity_id}"
                )
            checked.append((x, y))
        xs = [point[0] for point in checked]
        ys = [point[1] for point in checked]
        doubled_area = math.fsum(
            checked[i][0] * checked[(i + 1) % len(checked)][1]
            - checked[(i + 1) % len(checked)][0] * checked[i][1]
            for i in range(len(checked))
        )
        if (
            max(xs) <= min(xs) or max(ys) <= min(ys)
            or not math.isfinite(doubled_area)
            or abs(doubled_area) <= 1e-12
        ):
            raise SourceClosedRunConflictError(
                f"floor source polygon is invalid: {quantity.quantity_id}"
            )
        # A positive shoelace ring may still cross itself. Do not seal
        # a geometric physical floor quantity from that non-physical source.
        source_bbox = _source_floor_area_simple_bbox(
            checked, quantity_id=quantity.quantity_id
        )

        if claim.canonical_rooms:
            room_owners = room_owners_by_id.get(_clean(floor.room_entity_id), ())
            if len(room_owners) != 1:
                raise SourceClosedRunConflictError(
                    f"floor original canonical room owner missing or contested: {quantity.quantity_id}"
                )
            room = room_owners[0]
            # The original floor-surface producer copies its room's source
            # document/snapshot/face and PDF ring before metric enrichment.
            # A well-formed but foreign room ring must not be sealed under
            # the numeric area and original source receipts of this floor.
            exact_ids = (
                room.canonical_room_id, room.document_id, room.revision_id,
                room.source_sha256, room.snapshot_id, room.page_id,
                room.source_room_face_record_id,
            )
            if (
                any(type(value) is not str or not value
                    or value != value.strip() for value in exact_ids)
                or room.canonical_room_id != floor.room_entity_id
                or room.document_id != floor.document_id
                or room.revision_id != floor.revision_id
                or room.source_sha256.lower() != floor.source_sha256.lower()
                or room.snapshot_id != floor.snapshot_id
                or room.page_id != floor.page_id
                or room.source_room_face_record_id != floor.source_room_face_record_id
                or not _same_original_floor_room_ring(
                    points, room.polygon_pdf_pts, quantity_id=quantity.quantity_id,
                )
            ):
                raise SourceClosedRunConflictError(
                    f"floor original canonical room geometry/source mismatch: {quantity.quantity_id}"
                )

        trace = CommercialTakeoffSourceTrace(
            workspace_id=workspace_id,
            project_id=project_id,
            document_id=floor.document_id,
            source_sha256=floor.source_sha256,
            source_page=str(floor.page_id),
            viewport_id=viewport_id,
            revision_id=floor.revision_id,
            current_revision_id=floor.revision_id,
            evidence_ids=evidence_ids,
            canonical_entity_ids=tuple(
                dict.fromkeys(
                    value
                    for value in (
                        physical_id,
                        _clean(floor.canonical_floor_id),
                    )
                    if value
                )
            ),
            source_bbox=source_bbox,
            metadata={
                "family": "floor_area",
                "canonical_floor_id": floor.canonical_floor_id,
                "physical_floor_surface_id": physical_id,
                "room_entity_id": floor.room_entity_id,
                "source_room_face_record_id": floor.source_room_face_record_id,
                "upstream_room_area_quantity_id": metadata.get(
                    "upstream_room_area_quantity_id"
                ),
            },
        )
        if quantity.quantity_id in traces:
            raise SourceClosedRunConflictError(
                f"duplicate floor quantity id: {quantity.quantity_id}"
            )
        traces[quantity.quantity_id] = trace

    return MappingProxyType(traces)


def seal_live_floor_area_run(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> SealedSourceClosedRun:
    """Seal final canonical floor-area quantities on physical floor identity."""
    quantities = tuple(
        quantity
        for quantity in publish_live_floor_area_quantities(claim)
        if not quantity.abstained and quantity.value is not None
    )
    traces = build_live_floor_area_source_traces(
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
    "build_live_floor_area_source_traces",
    "seal_live_floor_area_run",
]
