"""Fail-closed live assembly of the source-owned canonical building core.

This layer does not extract geometry or invent storeys. It groups already
canonicalized live objects under one source-revision building root and assigns
objects to a level only when level ownership is explicitly present or can be
propagated through an already-proven physical relationship.

Cross-revision building identity is deliberately unresolved until a project-
owned identity authority exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id


LIVE_CANONICAL_BUILDING_CORE_SCHEMA_VERSION = "1.0.0"
LIVE_CANONICAL_BUILDING_CORE_ASSEMBLED = "live_canonical_building_core_assembled"
LIVE_CANONICAL_BUILDING_CORE_LEVEL_PARTIAL = (
    "live_canonical_building_core_level_ownership_partial"
)
LIVE_CANONICAL_BUILDING_CORE_LEVEL_UNAVAILABLE = (
    "live_canonical_building_core_level_ownership_unavailable"
)
LIVE_CANONICAL_BUILDING_CORE_UNAVAILABLE = (
    "live_canonical_building_core_unavailable"
)
LIVE_CANONICAL_BUILDING_RELATIONSHIPS_RESOLVED = (
    "live_canonical_building_relationships_resolved"
)
LIVE_CANONICAL_BUILDING_RELATIONSHIPS_PARTIAL = (
    "live_canonical_building_relationships_partial"
)
LIVE_CANONICAL_BUILDING_RELATIONSHIPS_CONFLICT = (
    "live_canonical_building_relationships_conflict"
)

_FAMILY_ID_FIELD = MappingProxyType({
    "walls": "canonical_wall_id",
    "openings": "canonical_opening_id",
    "rooms": "canonical_room_id",
    "floors": "canonical_floor_id",
    "slabs": "canonical_slab_id",
    "ceilings": "canonical_ceiling_id",
    "roofs": "canonical_roof_id",
    "structural_members": "canonical_structural_member_id",
})

def _clean(value: object) -> str:
    return str(value or "").strip()


def _dict_items(values: Sequence[Mapping[str, object]] | None) -> tuple[dict, ...]:
    return tuple(dict(value) for value in (values or ()) if isinstance(value, Mapping))


def _object_id(family: str, payload: Mapping[str, object]) -> str:
    return _clean(payload.get(_FAMILY_ID_FIELD[family]))


@dataclass(frozen=True)
class LiveCanonicalRelationshipIssue:
    relationship: str
    child_family: str
    child_id: str
    parent_family: str
    parent_id: str | None
    severity: str
    reason_code: str

    def to_dict(self) -> dict:
        return {
            "relationship": self.relationship,
            "child_family": self.child_family,
            "child_id": self.child_id,
            "parent_family": self.parent_family,
            "parent_id": self.parent_id,
            "severity": self.severity,
            "reason_code": self.reason_code,
        }


def _one_level_id(values: object) -> str | None:
    if isinstance(values, str):
        clean = _clean(values)
        return clean or None
    if isinstance(values, (list, tuple, set, frozenset)):
        cleaned = tuple(dict.fromkeys(_clean(value) for value in values if _clean(value)))
        return cleaned[0] if len(cleaned) == 1 else None
    return None


@dataclass(frozen=True)
class LiveCanonicalLevelBucket:
    level_id: str
    level_label: str | None = None
    normalized_level_label: str | None = None
    level_index: int | None = None
    source_page: int | None = None
    source_viewport_id: str | None = None
    cross_view_identity_resolved: bool = False
    walls: tuple[Mapping[str, object], ...] = ()
    openings: tuple[Mapping[str, object], ...] = ()
    rooms: tuple[Mapping[str, object], ...] = ()
    floors: tuple[Mapping[str, object], ...] = ()
    slabs: tuple[Mapping[str, object], ...] = ()
    ceilings: tuple[Mapping[str, object], ...] = ()
    roofs: tuple[Mapping[str, object], ...] = ()
    structural_members: tuple[Mapping[str, object], ...] = ()
    schema_version: str = LIVE_CANONICAL_BUILDING_CORE_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "level_id": self.level_id,
            "level_label": self.level_label,
            "normalized_level_label": self.normalized_level_label,
            "level_index": self.level_index,
            "source_page": self.source_page,
            "source_viewport_id": self.source_viewport_id,
            "cross_view_identity_resolved": self.cross_view_identity_resolved,
            "walls": [dict(item) for item in self.walls],
            "openings": [dict(item) for item in self.openings],
            "doors": [
                dict(item)
                for item in self.openings
                if item.get("opening_kind") == "door"
            ],
            "windows": [
                dict(item)
                for item in self.openings
                if item.get("opening_kind") == "window"
            ],
            "rooms": [dict(item) for item in self.rooms],
            "floors": [dict(item) for item in self.floors],
            "slabs": [dict(item) for item in self.slabs],
            "ceilings": [dict(item) for item in self.ceilings],
            "roofs": [dict(item) for item in self.roofs],
            "structural_members": [
                dict(item) for item in self.structural_members
            ],
            "schema_version": self.schema_version,
        }

@dataclass(frozen=True)
class LiveCanonicalBuildingCore:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    building_id: str | None
    source_sha256: str | None
    cross_revision_identity_resolved: bool
    levels: tuple[LiveCanonicalLevelBucket, ...]
    unassigned: Mapping[str, tuple[Mapping[str, object], ...]]
    object_counts: Mapping[str, int]
    level_assignment_complete: bool
    relationship_status: EvidenceResolutionStatus
    relationship_reason_codes: tuple[str, ...]
    relationship_issues: tuple[LiveCanonicalRelationshipIssue, ...]
    relationship_counts: Mapping[str, int]
    relationship_complete: bool
    schema_version: str = LIVE_CANONICAL_BUILDING_CORE_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "reason_codes": list(self.reason_codes),
            "building_id": self.building_id,
            "source_sha256": self.source_sha256,
            "cross_revision_identity_resolved": self.cross_revision_identity_resolved,
            "levels": [level.to_dict() for level in self.levels],
            "unassigned": {
                family: [dict(item) for item in items]
                for family, items in self.unassigned.items()
            },
            "object_counts": dict(self.object_counts),
            "level_assignment_complete": self.level_assignment_complete,
            "relationship_status": self.relationship_status.value,
            "relationship_reason_codes": list(self.relationship_reason_codes),
            "relationship_issues": [
                issue.to_dict() for issue in self.relationship_issues
            ],
            "relationship_counts": dict(self.relationship_counts),
            "relationship_complete": self.relationship_complete,
            "schema_version": self.schema_version,
        }


def _empty() -> LiveCanonicalBuildingCore:
    return LiveCanonicalBuildingCore(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=(LIVE_CANONICAL_BUILDING_CORE_UNAVAILABLE,),
        building_id=None,
        source_sha256=None,
        cross_revision_identity_resolved=False,
        levels=(),
        unassigned=MappingProxyType({family: () for family in _FAMILY_ID_FIELD}),
        object_counts=MappingProxyType({family: 0 for family in _FAMILY_ID_FIELD}),
        level_assignment_complete=False,
        relationship_status=EvidenceResolutionStatus.ABSTAINED,
        relationship_reason_codes=(
            LIVE_CANONICAL_BUILDING_CORE_UNAVAILABLE,
        ),
        relationship_issues=(),
        relationship_counts=MappingProxyType(
            {"resolved": 0, "unresolved": 0, "conflict": 0}
        ),
        relationship_complete=False,
    )

def _relationship_integrity(
    families: Mapping[str, tuple[dict, ...]],
) -> tuple[
    EvidenceResolutionStatus,
    tuple[str, ...],
    tuple[LiveCanonicalRelationshipIssue, ...],
    Mapping[str, int],
    bool,
]:
    wall_ids = {
        _object_id("walls", wall)
        for wall in families["walls"]
        if _object_id("walls", wall)
    }
    room_ids = {
        _object_id("rooms", room)
        for room in families["rooms"]
        if _object_id("rooms", room)
    }

    issues: list[LiveCanonicalRelationshipIssue] = []
    resolved = 0

    for opening in families["openings"]:
        opening_id = _object_id("openings", opening)
        host_wall_id = _clean(opening.get("host_wall_id"))
        if not host_wall_id:
            issues.append(
                LiveCanonicalRelationshipIssue(
                    relationship="opening_host_wall",
                    child_family="openings",
                    child_id=opening_id,
                    parent_family="walls",
                    parent_id=None,
                    severity="unresolved",
                    reason_code="opening_host_wall_unresolved",
                )
            )
        elif host_wall_id not in wall_ids:
            issues.append(
                LiveCanonicalRelationshipIssue(
                    relationship="opening_host_wall",
                    child_family="openings",
                    child_id=opening_id,
                    parent_family="walls",
                    parent_id=host_wall_id,
                    severity="conflict",
                    reason_code="opening_host_wall_missing_from_building",
                )
            )
        else:
            resolved += 1

    for room in families["rooms"]:
        room_id = _object_id("rooms", room)
        canonical_wall_ids = tuple(
            dict.fromkeys(
                _clean(value)
                for value in (
                    room.get("canonical_bounding_wall_ids") or ()
                )
                if _clean(value)
            )
        )
        relationship_complete = (
            room.get("wall_relationships_complete") is True
        )
        if relationship_complete and not canonical_wall_ids:
            issues.append(
                LiveCanonicalRelationshipIssue(
                    relationship="room_bounding_walls",
                    child_family="rooms",
                    child_id=room_id,
                    parent_family="walls",
                    parent_id=None,
                    severity="conflict",
                    reason_code="room_claims_complete_wall_relationship_without_walls",
                )
            )
            continue
        missing = tuple(
            wall_id
            for wall_id in canonical_wall_ids
            if wall_id not in wall_ids
        )
        if missing:
            for wall_id in missing:
                issues.append(
                    LiveCanonicalRelationshipIssue(
                        relationship="room_bounding_walls",
                        child_family="rooms",
                        child_id=room_id,
                        parent_family="walls",
                        parent_id=wall_id,
                        severity="conflict",
                        reason_code="room_bounding_wall_missing_from_building",
                    )
                )
            continue
        if relationship_complete:
            resolved += max(1, len(canonical_wall_ids))
        else:
            issues.append(
                LiveCanonicalRelationshipIssue(
                    relationship="room_bounding_walls",
                    child_family="rooms",
                    child_id=room_id,
                    parent_family="walls",
                    parent_id=None,
                    severity="unresolved",
                    reason_code="room_bounding_wall_relationship_partial",
                )
            )

    for family, relationship in (
        ("floors", "floor_room"),
        ("ceilings", "ceiling_room"),
    ):
        for item in families[family]:
            child_id = _object_id(family, item)
            room_id = _clean(item.get("room_entity_id"))
            if not room_id:
                issues.append(
                    LiveCanonicalRelationshipIssue(
                        relationship=relationship,
                        child_family=family,
                        child_id=child_id,
                        parent_family="rooms",
                        parent_id=None,
                        severity="conflict",
                        reason_code=f"{relationship}_identity_missing",
                    )
                )
            elif room_id not in room_ids:
                issues.append(
                    LiveCanonicalRelationshipIssue(
                        relationship=relationship,
                        child_family=family,
                        child_id=child_id,
                        parent_family="rooms",
                        parent_id=room_id,
                        severity="conflict",
                        reason_code=f"{relationship}_parent_missing_from_building",
                    )
                )
            else:
                resolved += 1

    issues.sort(
        key=lambda issue: (
            issue.severity,
            issue.relationship,
            issue.child_family,
            issue.child_id,
            issue.parent_id or "",
        )
    )
    conflict_count = sum(
        1 for issue in issues if issue.severity == "conflict"
    )
    unresolved_count = sum(
        1 for issue in issues if issue.severity == "unresolved"
    )
    counts = MappingProxyType(
        {
            "resolved": int(resolved),
            "unresolved": int(unresolved_count),
            "conflict": int(conflict_count),
        }
    )
    if conflict_count:
        status = EvidenceResolutionStatus.CONFLICT
        reasons = (LIVE_CANONICAL_BUILDING_RELATIONSHIPS_CONFLICT,)
    elif unresolved_count:
        status = EvidenceResolutionStatus.CANDIDATE
        reasons = (LIVE_CANONICAL_BUILDING_RELATIONSHIPS_PARTIAL,)
    else:
        status = EvidenceResolutionStatus.CORROBORATED
        reasons = (LIVE_CANONICAL_BUILDING_RELATIONSHIPS_RESOLVED,)

    return (
        status,
        reasons,
        tuple(issues),
        counts,
        not issues,
    )


def assemble_live_canonical_building_core(
    *,
    source_sha256: str,
    levels: Sequence[Mapping[str, object]] = (),
    walls: Sequence[Mapping[str, object]] = (),
    openings: Sequence[Mapping[str, object]] = (),
    rooms: Sequence[Mapping[str, object]] = (),
    floors: Sequence[Mapping[str, object]] = (),
    slabs: Sequence[Mapping[str, object]] = (),
    ceilings: Sequence[Mapping[str, object]] = (),
    roofs: Sequence[Mapping[str, object]] = (),
    structural_members: Sequence[Mapping[str, object]] = (),
) -> LiveCanonicalBuildingCore:
    """Assemble one source-revision building graph without guessing storeys."""

    source_sha = _clean(source_sha256).lower()
    if len(source_sha) != 64 or any(ch not in "0123456789abcdef" for ch in source_sha):
        return _empty()

    source_levels = _dict_items(levels)
    families: dict[str, tuple[dict, ...]] = {
        "walls": _dict_items(walls),
        "openings": _dict_items(openings),
        "rooms": _dict_items(rooms),
        "floors": _dict_items(floors),
        "slabs": _dict_items(slabs),
        "ceilings": _dict_items(ceilings),
        "roofs": _dict_items(roofs),
        "structural_members": _dict_items(structural_members),
    }
    if not any(families.values()) and not source_levels:
        return _empty()

    level_metadata_by_id: dict[str, dict] = {}
    for level in source_levels:
        level_id = _clean(level.get("canonical_level_id"))
        if not level_id or level_id in level_metadata_by_id:
            return _empty()
        level_metadata_by_id[level_id] = level

    # Reject duplicate canonical IDs within a family. Different families may
    # legitimately share related identities (for example door/window views are
    # not separate input families here; they remain opening subtypes).
    for family, items in families.items():
        ids = [_object_id(family, item) for item in items]
        if any(not item_id for item_id in ids) or len(ids) != len(set(ids)):
            return _empty()

    building_id = stable_contract_id(
        "live_canonical_building_source_revision",
        {"source_sha256": source_sha},
        digest_chars=32,
    )

    level_by_wall_id: dict[str, str] = {}
    level_by_wall_candidate_id: dict[str, str] = {}
    for wall in families["walls"]:
        level_id = _one_level_id(wall.get("level_ids"))
        if level_id is None:
            continue
        wall_id = _object_id("walls", wall)
        level_by_wall_id[wall_id] = level_id
        for candidate_id in wall.get("member_wall_candidate_ids") or ():
            candidate = _clean(candidate_id)
            if candidate:
                level_by_wall_candidate_id[candidate] = level_id

    level_by_opening_id: dict[str, str] = {}
    for opening in families["openings"]:
        host_wall_id = _clean(opening.get("host_wall_id"))
        level_id = level_by_wall_id.get(host_wall_id)
        if level_id:
            level_by_opening_id[_object_id("openings", opening)] = level_id

    level_by_room_id: dict[str, str] = {}
    for room in families["rooms"]:
        bounding_ids = tuple(
            _clean(value)
            for value in (room.get("bounding_wall_ids") or ())
            if _clean(value)
        )
        if not bounding_ids:
            continue
        resolved = tuple(
            level_by_wall_id.get(wall_id)
            or level_by_wall_candidate_id.get(wall_id)
            for wall_id in bounding_ids
        )
        if any(level_id is None for level_id in resolved):
            continue
        unique = tuple(dict.fromkeys(level_id for level_id in resolved if level_id))
        if len(unique) == 1:
            level_by_room_id[_object_id("rooms", room)] = unique[0]

    level_by_floor_id: dict[str, str] = {}
    for floor in families["floors"]:
        room_id = _clean(floor.get("room_entity_id"))
        level_id = level_by_room_id.get(room_id)
        if level_id:
            level_by_floor_id[_object_id("floors", floor)] = level_id

    level_by_ceiling_id: dict[str, str] = {}
    for ceiling in families["ceilings"]:
        room_id = _clean(ceiling.get("room_entity_id"))
        level_id = level_by_room_id.get(room_id)
        if level_id:
            level_by_ceiling_id[_object_id("ceilings", ceiling)] = level_id

    explicit_maps: dict[str, dict[str, str]] = {
        "walls": level_by_wall_id,
        "openings": level_by_opening_id,
        "rooms": level_by_room_id,
        "floors": level_by_floor_id,
        "ceilings": level_by_ceiling_id,
        "slabs": {},
        "roofs": {},
        "structural_members": {},
    }

    # Honor explicit level_id / single level_ids on any object family before
    # leaving it unassigned. This is source data, not a guessed default.
    for family, items in families.items():
        mapping = explicit_maps[family]
        for item in items:
            object_id = _object_id(family, item)
            explicit = _one_level_id(item.get("level_id"))
            if explicit is None:
                explicit = _one_level_id(item.get("level_ids"))
            if explicit is not None:
                prior = mapping.get(object_id)
                if prior is None:
                    mapping[object_id] = explicit
                elif prior != explicit:
                    return _empty()

    bucket_payloads: dict[str, dict[str, list[dict]]] = {
        level_id: {name: [] for name in families}
        for level_id in level_metadata_by_id
    }
    unassigned: dict[str, list[dict]] = {family: [] for family in families}
    for family, items in families.items():
        mapping = explicit_maps[family]
        for item in items:
            object_id = _object_id(family, item)
            level_id = mapping.get(object_id)
            if not level_id:
                unassigned[family].append(item)
                continue
            bucket = bucket_payloads.setdefault(
                level_id,
                {name: [] for name in families},
            )
            bucket[family].append(item)

    levels = tuple(
        LiveCanonicalLevelBucket(
            level_id=level_id,
            level_label=(
                _clean(level_metadata_by_id[level_id].get("level_label")) or None
                if level_id in level_metadata_by_id
                else None
            ),
            normalized_level_label=(
                _clean(
                    level_metadata_by_id[level_id].get(
                        "normalized_level_label"
                    )
                )
                or None
                if level_id in level_metadata_by_id
                else None
            ),
            level_index=(
                int(level_metadata_by_id[level_id]["level_index"])
                if level_id in level_metadata_by_id
                and level_metadata_by_id[level_id].get("level_index")
                is not None
                else None
            ),
            source_page=(
                int(level_metadata_by_id[level_id]["source_page"])
                if level_id in level_metadata_by_id
                and level_metadata_by_id[level_id].get("source_page")
                is not None
                else None
            ),
            source_viewport_id=(
                _clean(
                    level_metadata_by_id[level_id].get(
                        "source_viewport_id"
                    )
                )
                or None
                if level_id in level_metadata_by_id
                else None
            ),
            cross_view_identity_resolved=(
                bool(
                    level_metadata_by_id[level_id].get(
                        "cross_view_identity_resolved",
                        False,
                    )
                )
                if level_id in level_metadata_by_id
                else False
            ),
            walls=tuple(payload["walls"]),
            openings=tuple(payload["openings"]),
            rooms=tuple(payload["rooms"]),
            floors=tuple(payload["floors"]),
            slabs=tuple(payload["slabs"]),
            ceilings=tuple(payload["ceilings"]),
            roofs=tuple(payload["roofs"]),
            structural_members=tuple(payload["structural_members"]),
        )
        for level_id, payload in sorted(bucket_payloads.items())
    )

    unassigned_frozen = MappingProxyType(
        {
            family: tuple(items)
            for family, items in unassigned.items()
        }
    )
    counts = MappingProxyType(
        {
            **{family: len(items) for family, items in families.items()},
            "levels": len(source_levels),
        }
    )
    unassigned_count = sum(len(items) for items in unassigned.values())
    level_assignment_complete = unassigned_count == 0

    (
        relationship_status,
        relationship_reason_codes,
        relationship_issues,
        relationship_counts,
        relationship_complete,
    ) = _relationship_integrity(families)

    if level_assignment_complete:
        reasons = (LIVE_CANONICAL_BUILDING_CORE_ASSEMBLED,)
    elif levels:
        reasons = (
            LIVE_CANONICAL_BUILDING_CORE_ASSEMBLED,
            LIVE_CANONICAL_BUILDING_CORE_LEVEL_PARTIAL,
        )
    else:
        reasons = (
            LIVE_CANONICAL_BUILDING_CORE_ASSEMBLED,
            LIVE_CANONICAL_BUILDING_CORE_LEVEL_UNAVAILABLE,
        )

    return LiveCanonicalBuildingCore(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=reasons,
        building_id=building_id,
        source_sha256=source_sha,
        cross_revision_identity_resolved=False,
        levels=levels,
        unassigned=unassigned_frozen,
        object_counts=counts,
        level_assignment_complete=level_assignment_complete,
        relationship_status=relationship_status,
        relationship_reason_codes=relationship_reason_codes,
        relationship_issues=relationship_issues,
        relationship_counts=relationship_counts,
        relationship_complete=relationship_complete,
    )


__all__ = [
    "LIVE_CANONICAL_BUILDING_RELATIONSHIPS_CONFLICT",
    "LIVE_CANONICAL_BUILDING_RELATIONSHIPS_PARTIAL",
    "LIVE_CANONICAL_BUILDING_RELATIONSHIPS_RESOLVED",
    "LIVE_CANONICAL_BUILDING_CORE_ASSEMBLED",
    "LIVE_CANONICAL_BUILDING_CORE_LEVEL_PARTIAL",
    "LIVE_CANONICAL_BUILDING_CORE_LEVEL_UNAVAILABLE",
    "LIVE_CANONICAL_BUILDING_CORE_SCHEMA_VERSION",
    "LIVE_CANONICAL_BUILDING_CORE_UNAVAILABLE",
    "LiveCanonicalBuildingCore",
    "LiveCanonicalLevelBucket",
    "LiveCanonicalRelationshipIssue",
    "assemble_live_canonical_building_core",
]
