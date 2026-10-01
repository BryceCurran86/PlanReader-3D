"""Canonical room-floor surface projection from source-owned room faces.

A source-authenticated room footprint is useful shared geometry for flooring,
tiling, coatings, skirtings, costing, 3D and drawings. This module preserves
that footprint once as a room-owned horizontal surface without claiming that:
- a structural slab has been identified,
- a floor finish/material has been identified,
- metric geometry or metric area is resolved,
- a commercial quantity is authorized.

Structural slabs remain a separate canonical object family.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pb_live_canonical_room_composition import (
    LiveCanonicalRoomComposition,
    LiveCanonicalRoomObject,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id


LIVE_CANONICAL_FLOOR_SURFACE_SCHEMA_VERSION = "1.0.0"
LIVE_CANONICAL_FLOOR_SURFACE_RESOLVED = (
    "live_canonical_floor_surface_projection_resolved"
)
LIVE_CANONICAL_FLOOR_SURFACE_PARTIAL = (
    "live_canonical_floor_surface_projection_partial"
)
LIVE_CANONICAL_FLOOR_SURFACE_UNAVAILABLE = (
    "live_canonical_floor_surface_projection_unavailable"
)


@dataclass(frozen=True)
class LiveCanonicalFloorSurfaceObject:
    canonical_floor_id: str
    room_entity_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str]
    polygon_pdf_pts: tuple[tuple[float, float], ...]
    area_page_pts2: float
    bounding_wall_ids: tuple[str, ...]
    canonical_bounding_wall_ids: tuple[str, ...]
    source_room_face_record_id: str
    evidence_ids: tuple[str, ...]
    geometry_complete: bool
    metric_geometry_complete: bool
    metric_area_m2: Optional[float]
    metric_area_quantity_id: Optional[str]
    metric_area_authority: Optional[str]
    finish_descriptor: Optional[str]
    structural_slab_id: Optional[str]
    physical_floor_surface_identity_resolved: bool
    commercial_quantity_authority: bool
    coordinate_space: str = "source_page_points"
    schema_version: str = LIVE_CANONICAL_FLOOR_SURFACE_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "canonical_floor_id": self.canonical_floor_id,
            "room_entity_id": self.room_entity_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "snapshot_id": self.snapshot_id,
            "page_id": self.page_id,
            "viewport_id": self.viewport_id,
            "polygon_pdf_pts": [list(point) for point in self.polygon_pdf_pts],
            "area_page_pts2": self.area_page_pts2,
            "bounding_wall_ids": list(self.bounding_wall_ids),
            "canonical_bounding_wall_ids": list(
                self.canonical_bounding_wall_ids
            ),
            "source_room_face_record_id": self.source_room_face_record_id,
            "evidence_ids": list(self.evidence_ids),
            "geometry_complete": self.geometry_complete,
            "metric_geometry_complete": self.metric_geometry_complete,
            "metric_area_m2": self.metric_area_m2,
            "metric_area_quantity_id": self.metric_area_quantity_id,
            "metric_area_authority": self.metric_area_authority,
            "finish_descriptor": self.finish_descriptor,
            "structural_slab_id": self.structural_slab_id,
            "physical_floor_surface_identity_resolved": (
                self.physical_floor_surface_identity_resolved
            ),
            "commercial_quantity_authority": self.commercial_quantity_authority,
            "coordinate_space": self.coordinate_space,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class LiveCanonicalFloorSurfaceComposition:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    floors: tuple[LiveCanonicalFloorSurfaceObject, ...]
    source_pages: tuple[int, ...]
    schema_version: str = LIVE_CANONICAL_FLOOR_SURFACE_SCHEMA_VERSION


def _floor_from_room(room: LiveCanonicalRoomObject) -> LiveCanonicalFloorSurfaceObject:
    floor_id = stable_contract_id(
        "live_canonical_room_floor_surface",
        {
            "source_sha256": room.source_sha256,
            "revision_id": room.revision_id,
            "room_entity_id": room.canonical_room_id,
            "source_room_face_record_id": room.source_room_face_record_id,
        },
        digest_chars=32,
    )
    return LiveCanonicalFloorSurfaceObject(
        canonical_floor_id=floor_id,
        room_entity_id=room.canonical_room_id,
        document_id=room.document_id,
        revision_id=room.revision_id,
        source_sha256=room.source_sha256,
        snapshot_id=room.snapshot_id,
        page_id=room.page_id,
        viewport_id=room.viewport_id,
        polygon_pdf_pts=room.polygon_pdf_pts,
        area_page_pts2=float(room.area_page_pts2),
        bounding_wall_ids=room.bounding_wall_ids,
        canonical_bounding_wall_ids=room.canonical_bounding_wall_ids,
        source_room_face_record_id=room.source_room_face_record_id,
        evidence_ids=room.evidence_ids,
        geometry_complete=bool(room.geometry_complete),
        metric_geometry_complete=False,
        metric_area_m2=None,
        metric_area_quantity_id=None,
        metric_area_authority=None,
        finish_descriptor=None,
        structural_slab_id=None,
        physical_floor_surface_identity_resolved=False,
        commercial_quantity_authority=False,
    )


def compose_live_canonical_floor_surfaces(
    room_composition: LiveCanonicalRoomComposition,
) -> LiveCanonicalFloorSurfaceComposition:
    """Project canonical room footprints into reusable floor-surface candidates."""

    if type(room_composition) is not LiveCanonicalRoomComposition:
        raise TypeError(
            "room_composition must be LiveCanonicalRoomComposition"
        )

    if not room_composition.rooms:
        return LiveCanonicalFloorSurfaceComposition(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(LIVE_CANONICAL_FLOOR_SURFACE_UNAVAILABLE,),
            floors=(),
            source_pages=(),
        )

    floors = tuple(
        sorted(
            (_floor_from_room(room) for room in room_composition.rooms),
            key=lambda floor: (floor.page_id, floor.canonical_floor_id),
        )
    )

    if room_composition.status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.CORROBORATED
        reasons = (LIVE_CANONICAL_FLOOR_SURFACE_RESOLVED,)
    else:
        status = EvidenceResolutionStatus.CANDIDATE
        reasons = (
            LIVE_CANONICAL_FLOOR_SURFACE_PARTIAL,
            *room_composition.reason_codes,
        )

    return LiveCanonicalFloorSurfaceComposition(
        status=status,
        reason_codes=reasons,
        floors=floors,
        source_pages=room_composition.source_pages,
    )


__all__ = [
    "LIVE_CANONICAL_FLOOR_SURFACE_PARTIAL",
    "LIVE_CANONICAL_FLOOR_SURFACE_RESOLVED",
    "LIVE_CANONICAL_FLOOR_SURFACE_SCHEMA_VERSION",
    "LIVE_CANONICAL_FLOOR_SURFACE_UNAVAILABLE",
    "LiveCanonicalFloorSurfaceComposition",
    "LiveCanonicalFloorSurfaceObject",
    "compose_live_canonical_floor_surfaces",
]
