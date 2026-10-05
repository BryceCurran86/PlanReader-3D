"""Live bridge from source-owned room objects into CanonicalSpace.

This is an adapter into the repository's existing canonical building schema,
not a second room graph. Source-page geometry remains provenance until a
metric-coordinate authority exists; no PDF point is relabelled as metres.
"""
from __future__ import annotations

from dataclasses import dataclass

from pb_canonical_building import CanonicalSpace, Provenance, ReviewState
from pb_live_canonical_room_composition import LiveCanonicalRoomComposition
from pb_migration_contracts import EvidenceResolutionStatus


LIVE_CANONICAL_SPACE_BRIDGE_SCHEMA_VERSION = "1.0.0"
LIVE_CANONICAL_SPACE_BRIDGE_RESOLVED = "live_canonical_space_bridge_resolved"
LIVE_CANONICAL_SPACE_BRIDGE_PARTIAL = "live_canonical_space_bridge_partial"
LIVE_CANONICAL_SPACE_BRIDGE_UNAVAILABLE = "live_canonical_space_bridge_unavailable"
LIVE_CANONICAL_SPACE_BRIDGE_PRODUCER = "pb_live_canonical_space_bridge"


@dataclass(frozen=True)
class LiveCanonicalSpaceComposition:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    spaces: tuple[CanonicalSpace, ...]
    schema_version: str = LIVE_CANONICAL_SPACE_BRIDGE_SCHEMA_VERSION


def _page_number(page_id: str) -> int | None:
    value = str(page_id or "").strip()
    return int(value) if value.isdigit() else None


def _space_from_room(room, *, review_state: ReviewState) -> CanonicalSpace:
    evidence_ids = tuple(
        dict.fromkeys(
            (
                *tuple(room.evidence_ids or ()),
                *tuple(room.room_label_evidence_ids or ()),
            )
        )
    )
    source_polygon = [
        [float(point[0]), float(point[1])]
        for point in tuple(room.polygon_pdf_pts or ())
    ]
    return CanonicalSpace(
        id=str(room.canonical_room_id),
        name=str(room.room_label or "Unnamed Element"),
        level_id=None,
        confidence=None,
        review_state=review_state,
        provenance=Provenance(
            document_id=str(room.document_id),
            page_number=_page_number(room.page_id),
            page_id=str(room.page_id),
            source_coords={
                "polygon_pdf_pts": source_polygon,
                "area_page_pts2": float(room.area_page_pts2),
            },
            coordinate_space="source_page_points",
            producer_module=LIVE_CANONICAL_SPACE_BRIDGE_PRODUCER,
            producer_version=LIVE_CANONICAL_SPACE_BRIDGE_SCHEMA_VERSION,
            contributing_evidence=list(evidence_ids),
        ),
        metadata={
            "physical_room_id": str(room.physical_room_id),
            "source_room_face_record_id": str(room.source_room_face_record_id),
            "viewport_id": room.viewport_id,
            "decision_scope_id": str(room.decision_scope_id),
            "bounding_wall_ids": list(room.bounding_wall_ids),
            "canonical_bounding_wall_ids": list(
                room.canonical_bounding_wall_ids
            ),
            "wall_relationships_complete": bool(
                room.wall_relationships_complete
            ),
            "geometry_complete": bool(room.geometry_complete),
            "metric_geometry_complete": bool(room.metric_geometry_complete),
            "room_label_binding_record_id": room.room_label_binding_record_id,
            "room_label_reason_codes": list(room.room_label_reason_codes),
            "source_room_schema_version": str(room.schema_version),
        },
        takeoff_eligible=False,
        deduction_authority=False,
        boundary_polygon=[],
        height_m=None,
        specified_floor_area_m2=None,
        room_number=None,
    )


def compose_live_canonical_spaces(
    room_composition: LiveCanonicalRoomComposition,
) -> LiveCanonicalSpaceComposition:
    """Adapt already-proven live rooms into the existing CanonicalSpace schema."""
    if type(room_composition) is not LiveCanonicalRoomComposition:
        raise TypeError(
            "room_composition must be LiveCanonicalRoomComposition"
        )
    if not room_composition.rooms:
        return LiveCanonicalSpaceComposition(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(LIVE_CANONICAL_SPACE_BRIDGE_UNAVAILABLE,),
            spaces=(),
        )

    review_state = (
        ReviewState.INFERRED
        if room_composition.status is EvidenceResolutionStatus.CORROBORATED
        else ReviewState.REVIEW_REQUIRED
    )
    spaces = tuple(
        sorted(
            (
                _space_from_room(room, review_state=review_state)
                for room in room_composition.rooms
            ),
            key=lambda space: space.id,
        )
    )
    return LiveCanonicalSpaceComposition(
        status=room_composition.status,
        reason_codes=(
            (LIVE_CANONICAL_SPACE_BRIDGE_RESOLVED,)
            if room_composition.status is EvidenceResolutionStatus.CORROBORATED
            else (
                LIVE_CANONICAL_SPACE_BRIDGE_PARTIAL,
                *tuple(room_composition.reason_codes),
            )
        ),
        spaces=spaces,
    )


__all__ = [
    "LIVE_CANONICAL_SPACE_BRIDGE_PARTIAL",
    "LIVE_CANONICAL_SPACE_BRIDGE_PRODUCER",
    "LIVE_CANONICAL_SPACE_BRIDGE_RESOLVED",
    "LIVE_CANONICAL_SPACE_BRIDGE_SCHEMA_VERSION",
    "LIVE_CANONICAL_SPACE_BRIDGE_UNAVAILABLE",
    "LiveCanonicalSpaceComposition",
    "compose_live_canonical_spaces",
]
