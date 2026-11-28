"""Default-off generic cross-block RCP ceiling bubble-to-room correspondence shadow (AG-R05 / A12).

Resolves the ``same block_no`` limitation in RCP ceiling-to-room association by
linking producer-owned RCP ceiling bubbles (material + ceiling height + flat /
raked / stepped / bulkhead subzone) to authenticated room labels inside the
same RCP viewport/page across distinct PDF text blocks, while strictly enforcing:

- Exact ``document_id`` / ``revision_id`` / ``source_sha256`` / ``page_id`` /
  ``viewport_id`` provenance agreement (cross-revision or cross-viewport links
  are rejected).
- Containment-first correspondence (bubble center strictly inside a room's
  authenticated bounding polygon/box), with bounded nearest-label fallback ONLY
  when no competing room label lies within ``ambiguity_ratio`` of the winner.
- Explicit stepped/raked/bulkhead subzone separation: distinct ceiling heights
  or materials within the same room are preserved as separate subzone records
  rather than collapsed or overwritten, and conflicting same-subzone height/
  material definitions fail closed (``CONFLICT``).
- Zero floor-copy ceilings: a room without an explicit RCP ceiling bubble
  abstains (``rcp_ceiling_bubble_unavailable``) and never borrows floor area or
  floor finish.

Shadow-only (``shadow_only=True``, ``commercial_authority_granted=False``).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import math
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus


SCHEMA_VERSION = "1.0.0"

CEILING_PROFILE_FLAT = "flat"
CEILING_PROFILE_RAKED = "raked"
CEILING_PROFILE_STEPPED = "stepped"
CEILING_PROFILE_BULKHEAD = "bulkhead"
VALID_CEILING_PROFILES = frozenset(
    {
        CEILING_PROFILE_FLAT,
        CEILING_PROFILE_RAKED,
        CEILING_PROFILE_STEPPED,
        CEILING_PROFILE_BULKHEAD,
    }
)


@dataclass(frozen=True)
class RcpCeilingBubbleWitness:
    """One producer-owned RCP ceiling bubble (material + height + profile)."""

    bubble_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str
    block_no: int
    center_pt: tuple[float, float]
    material_code: str
    height_mm: Optional[float] = None
    height_max_mm: Optional[float] = None
    profile: str = CEILING_PROFILE_FLAT
    subzone_label: str = ""


@dataclass(frozen=True)
class RcpRoomAnchorWitness:
    """One producer-owned room label / region anchor inside an RCP viewport."""

    room_anchor_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str
    block_no: int
    room_key: str
    label_center_pt: tuple[float, float]
    region_bbox_pt: Optional[tuple[float, float, float, float]] = None


@dataclass(frozen=True)
class RcpCeilingRoomLink:
    """One auditable cross-block RCP ceiling bubble-to-room link (shadow only)."""

    room_anchor_id: str
    room_key: str
    bubble_id: str
    material_code: str
    height_mm: Optional[float]
    height_max_mm: Optional[float]
    profile: str
    subzone_label: str
    match_mode: str  # "containment" | "nearest_unambiguous"
    cross_block: bool
    distance_pt: float
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    shadow_only: bool = True
    commercial_authority_granted: bool = False
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class RcpRoomCorrespondenceShadowResult:
    """Aggregated shadow-only RCP room-to-ceiling correspondence result."""

    links: tuple[RcpCeilingRoomLink, ...]
    abstained_room_anchor_ids: tuple[str, ...]
    unmatched_bubble_ids: tuple[str, ...]
    conflict_room_anchor_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    shadow_only: bool = True
    commercial_authority_granted: bool = False
    schema_version: str = SCHEMA_VERSION


def _point_in_bbox(
    pt: tuple[float, float],
    bbox: tuple[float, float, float, float],
) -> bool:
    x, y = pt
    x0, y0, x1, y1 = bbox
    return x0 <= x <= x1 and y0 <= y <= y1


def _same_scope(bubble: RcpCeilingBubbleWitness, room: RcpRoomAnchorWitness) -> bool:
    return (
        bubble.document_id == room.document_id
        and bubble.revision_id == room.revision_id
        and bubble.source_sha256 == room.source_sha256
        and bubble.page_id == room.page_id
        and bubble.viewport_id == room.viewport_id
    )


def _valid_height(value: Optional[float]) -> bool:
    if value is None:
        return True
    return (
        not isinstance(value, bool)
        and math.isfinite(value)
        and 1500.0 <= float(value) <= 15000.0
    )


def link_rcp_bubbles_to_rooms_shadow(
    *,
    bubbles: Sequence[RcpCeilingBubbleWitness],
    room_anchors: Sequence[RcpRoomAnchorWitness],
    max_proximity_pt: float = 120.0,
    ambiguity_ratio: float = 1.25,
) -> RcpRoomCorrespondenceShadowResult:
    """Link RCP ceiling bubbles to room anchors across distinct PDF text blocks.

    Never copies floor areas/finishes into rooms lacking an explicit RCP bubble.
    """
    if max_proximity_pt <= 0.0 or ambiguity_ratio <= 1.0:
        raise ValueError("max_proximity_pt must be > 0 and ambiguity_ratio must be > 1.0")

    room_list = tuple(room_anchors)
    bubble_list = tuple(bubbles)
    links: list[RcpCeilingRoomLink] = []
    unmatched_bubbles: list[str] = []
    conflict_rooms: set[str] = set()
    matched_rooms: set[str] = set()
    reasons: list[str] = []

    # Group corroborated links by (room_anchor_id, subzone_key) to catch conflicts
    subzone_signatures: dict[tuple[str, str], tuple[str, Optional[float], Optional[float], str]] = {}

    for bubble in bubble_list:
        mat = str(bubble.material_code or "").strip()
        prof = str(bubble.profile or CEILING_PROFILE_FLAT).strip().lower()
        if (
            not mat
            or prof not in VALID_CEILING_PROFILES
            or not _valid_height(bubble.height_mm)
            or not _valid_height(bubble.height_max_mm)
            or (
                bubble.height_mm is not None
                and bubble.height_max_mm is not None
                and bubble.height_max_mm < bubble.height_mm
            )
        ):
            unmatched_bubbles.append(bubble.bubble_id)
            reasons.append("rcp_bubble_invalid_material_or_height")
            continue

        scoped_rooms = [r for r in room_list if _same_scope(bubble, r)]
        if not scoped_rooms:
            unmatched_bubbles.append(bubble.bubble_id)
            reasons.append("rcp_bubble_no_same_scope_room_anchor")
            continue

        # 1) Containment-first correspondence
        containing = [
            r
            for r in scoped_rooms
            if r.region_bbox_pt is not None and _point_in_bbox(bubble.center_pt, r.region_bbox_pt)
        ]
        chosen_room: Optional[RcpRoomAnchorWitness] = None
        match_mode = ""
        dist = 0.0

        if len(containing) == 1:
            chosen_room = containing[0]
            match_mode = "containment"
            dist = math.hypot(
                bubble.center_pt[0] - chosen_room.label_center_pt[0],
                bubble.center_pt[1] - chosen_room.label_center_pt[1],
            )
        elif len(containing) > 1:
            unmatched_bubbles.append(bubble.bubble_id)
            reasons.append("rcp_bubble_ambiguous_overlapping_room_regions")
            continue
        else:
            # 2) Bounded nearest-label fallback with strict ambiguity veto
            scored = sorted(
                (
                    (
                        math.hypot(
                            bubble.center_pt[0] - r.label_center_pt[0],
                            bubble.center_pt[1] - r.label_center_pt[1],
                        ),
                        r.room_anchor_id,
                        r,
                    )
                    for r in scoped_rooms
                ),
                key=lambda item: (item[0], item[1]),
            )
            best_dist, _best_id, best_room = scored[0]
            if best_dist > max_proximity_pt:
                unmatched_bubbles.append(bubble.bubble_id)
                reasons.append("rcp_bubble_outside_proximity_radius")
                continue
            if len(scored) >= 2 and scored[1][0] <= best_dist * ambiguity_ratio:
                unmatched_bubbles.append(bubble.bubble_id)
                reasons.append("rcp_bubble_ambiguous_competing_room_labels")
                continue
            chosen_room = best_room
            match_mode = "nearest_unambiguous"
            dist = best_dist

        assert chosen_room is not None
        subzone_key = str(bubble.subzone_label or "").strip().lower() or prof
        sig = (mat.upper(), bubble.height_mm, bubble.height_max_mm, prof)
        prev_sig = subzone_signatures.get((chosen_room.room_anchor_id, subzone_key))
        if prev_sig is not None and prev_sig != sig:
            conflict_rooms.add(chosen_room.room_anchor_id)
            links.append(
                RcpCeilingRoomLink(
                    room_anchor_id=chosen_room.room_anchor_id,
                    room_key=chosen_room.room_key,
                    bubble_id=bubble.bubble_id,
                    material_code=mat,
                    height_mm=bubble.height_mm,
                    height_max_mm=bubble.height_max_mm,
                    profile=prof,
                    subzone_label=subzone_key,
                    match_mode=match_mode,
                    cross_block=(bubble.block_no != chosen_room.block_no),
                    distance_pt=round(dist, 3),
                    status=EvidenceResolutionStatus.CONFLICT,
                    reason_codes=("rcp_subzone_conflicting_ceiling_spec",),
                )
            )
            reasons.append("rcp_subzone_conflicting_ceiling_spec")
            continue

        subzone_signatures[(chosen_room.room_anchor_id, subzone_key)] = sig
        matched_rooms.add(chosen_room.room_anchor_id)
        links.append(
            RcpCeilingRoomLink(
                room_anchor_id=chosen_room.room_anchor_id,
                room_key=chosen_room.room_key,
                bubble_id=bubble.bubble_id,
                material_code=mat,
                height_mm=bubble.height_mm,
                height_max_mm=bubble.height_max_mm,
                profile=prof,
                subzone_label=subzone_key,
                match_mode=match_mode,
                cross_block=(bubble.block_no != chosen_room.block_no),
                distance_pt=round(dist, 3),
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(
                    "rcp_bubble_room_corroborated_cross_block"
                    if bubble.block_no != chosen_room.block_no
                    else "rcp_bubble_room_corroborated_same_block",
                ),
            )
        )

    abstained_rooms = tuple(
        sorted(
            r.room_anchor_id
            for r in room_list
            if r.room_anchor_id not in matched_rooms and r.room_anchor_id not in conflict_rooms
        )
    )
    if abstained_rooms:
        reasons.append("rcp_ceiling_bubble_unavailable_no_floor_copy")

    return RcpRoomCorrespondenceShadowResult(
        links=tuple(links),
        abstained_room_anchor_ids=abstained_rooms,
        unmatched_bubble_ids=tuple(sorted(unmatched_bubbles)),
        conflict_room_anchor_ids=tuple(sorted(conflict_rooms)),
        reason_codes=tuple(dict.fromkeys(reasons)),
    )


__all__ = [
    "CEILING_PROFILE_BULKHEAD",
    "CEILING_PROFILE_FLAT",
    "CEILING_PROFILE_RAKED",
    "CEILING_PROFILE_STEPPED",
    "RcpCeilingBubbleWitness",
    "RcpCeilingRoomLink",
    "RcpRoomAnchorWitness",
    "RcpRoomCorrespondenceShadowResult",
    "SCHEMA_VERSION",
    "VALID_CEILING_PROFILES",
    "link_rcp_bubbles_to_rooms_shadow",
]
