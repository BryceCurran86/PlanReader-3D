"""Source-owned floor-plan level identity from authoritative F.07 viewports.

Only explicit level/storey language in a producer-owned floor-plan viewport
label can create a level scope. Page-wide text, default "Ground" values,
commercial rows, and caller labels are not authority.

A level scope is intentionally view-scoped. Two views that both say
"GROUND FLOOR PLAN" are not silently merged into one cross-sheet storey until
an independent equivalence authority proves that relationship.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Mapping, Optional, Sequence

from pb_ceiling_lining_scope_binder import (
    source_room_polygon_owned_by_bbox,
)
from pb_hosted_opening_instance_adapter import authoritative_floor_plan_viewports
from pb_migration_contracts import stable_contract_id


LIVE_FLOOR_PLAN_LEVEL_SCHEMA_VERSION = "1.0.0"
LIVE_FLOOR_PLAN_LEVEL_RESOLVED = "live_floor_plan_level_identity_resolved"
LIVE_FLOOR_PLAN_LEVEL_UNAVAILABLE = "live_floor_plan_level_identity_unavailable"

_LEVEL_SEAL = object()
_VIEWPORT_SEAL = object()

_WORD_ORDINALS = {
    "GROUND": 0,
    "FIRST": 1,
    "SECOND": 2,
    "THIRD": 3,
    "FOURTH": 4,
    "FIFTH": 5,
    "SIXTH": 6,
    "SEVENTH": 7,
    "EIGHTH": 8,
    "NINTH": 9,
    "TENTH": 10,
}
_ORDINAL_RE = re.compile(
    r"\b(?P<ordinal>GROUND|FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|"
    r"\d{1,2}(?:ST|ND|RD|TH))\s+FLOOR\s+PLAN\b",
    re.IGNORECASE,
)
_LEVEL_NUMBER_RE = re.compile(
    r"\bLEVEL\s+(?P<number>-?\d{1,2})\s+(?:FLOOR\s+)?PLAN\b",
    re.IGNORECASE,
)
_BASEMENT_RE = re.compile(
    r"\b(?:(?P<prefix>LOWER\s+GROUND|BASEMENT(?:\s+\d{1,2})?|MEZZANINE))\s+(?:FLOOR\s+)?PLAN\b",
    re.IGNORECASE,
)


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def _normalized_level_label(label: str) -> Optional[tuple[str, Optional[int]]]:
    text = _clean(label).upper()
    if not text or "ROOF PLAN" in text:
        return None

    match = _ORDINAL_RE.search(text)
    if match is not None:
        ordinal = match.group("ordinal").upper()
        if ordinal in _WORD_ORDINALS:
            index = _WORD_ORDINALS[ordinal]
        else:
            index = int(re.match(r"\d+", ordinal).group(0))
        return (f"{ordinal.lower()}_floor", index)

    match = _LEVEL_NUMBER_RE.search(text)
    if match is not None:
        number = int(match.group("number"))
        return (f"level_{number}", number)

    match = _BASEMENT_RE.search(text)
    if match is not None:
        prefix = _clean(match.group("prefix")).upper()
        if prefix == "LOWER GROUND":
            return ("lower_ground", None)
        if prefix == "MEZZANINE":
            return ("mezzanine", None)
        basement_no_match = re.search(r"\d{1,2}", prefix)
        basement_no = int(basement_no_match.group(0)) if basement_no_match else 1
        return (f"basement_{basement_no}", -basement_no)

    return None


@dataclass(frozen=True)
class LiveFloorPlanViewportRecord:
    source_page: int
    source_viewport_id: str
    viewport_label: str
    viewport_bbox: tuple[float, float, float, float]
    viewport_confidence: float
    source_sha256: str
    schema_version: str = LIVE_FLOOR_PLAN_LEVEL_SCHEMA_VERSION
    _seal: object = field(default=None, repr=False, compare=False)

    @property
    def is_source_owned(self) -> bool:
        return self._seal is _VIEWPORT_SEAL

    def to_dict(self) -> dict:
        return {
            "source_page": self.source_page,
            "source_viewport_id": self.source_viewport_id,
            "viewport_label": self.viewport_label,
            "viewport_bbox": list(self.viewport_bbox),
            "viewport_confidence": self.viewport_confidence,
            "source_sha256": self.source_sha256,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class LiveFloorPlanLevelRecord:
    canonical_level_id: str
    level_label: str
    normalized_level_label: str
    level_index: Optional[int]
    source_page: int
    source_viewport_id: str
    viewport_bbox: tuple[float, float, float, float]
    viewport_confidence: float
    source_sha256: str
    cross_view_identity_resolved: bool = False
    schema_version: str = LIVE_FLOOR_PLAN_LEVEL_SCHEMA_VERSION
    _seal: object = field(default=None, repr=False, compare=False)

    @property
    def is_source_owned(self) -> bool:
        return self._seal is _LEVEL_SEAL

    def to_dict(self) -> dict:
        return {
            "canonical_level_id": self.canonical_level_id,
            "level_label": self.level_label,
            "normalized_level_label": self.normalized_level_label,
            "level_index": self.level_index,
            "source_page": self.source_page,
            "source_viewport_id": self.source_viewport_id,
            "viewport_bbox": list(self.viewport_bbox),
            "viewport_confidence": self.viewport_confidence,
            "source_sha256": self.source_sha256,
            "cross_view_identity_resolved": self.cross_view_identity_resolved,
            "schema_version": self.schema_version,
        }


def collect_source_owned_floor_plan_viewports(
    doc: Any,
    *,
    page_indices: Sequence[int],
    source_sha256: str,
) -> tuple[LiveFloorPlanViewportRecord, ...]:
    """Collect all authoritative F.07 floor-plan viewport ownership records."""

    source_sha = _clean(source_sha256).lower()
    if len(source_sha) != 64 or any(ch not in "0123456789abcdef" for ch in source_sha):
        return ()

    output: dict[str, LiveFloorPlanViewportRecord] = {}
    for page_index in sorted(
        {
            int(index)
            for index in page_indices
            if not isinstance(index, bool)
            and 0 <= int(index) < len(doc)
        }
    ):
        for viewport in authoritative_floor_plan_viewports(
            doc[page_index],
            page_number=page_index + 1,
        ):
            if viewport.bounding_box is None:
                continue
            view_id = _clean(viewport.view_id)
            if not view_id:
                continue
            record = LiveFloorPlanViewportRecord(
                source_page=page_index + 1,
                source_viewport_id=view_id,
                viewport_label=_clean(viewport.label),
                viewport_bbox=tuple(
                    float(value) for value in viewport.bounding_box
                ),
                viewport_confidence=float(viewport.confidence),
                source_sha256=source_sha,
                _seal=_VIEWPORT_SEAL,
            )
            prior = output.get(view_id)
            if prior is not None and prior != record:
                return ()
            output[view_id] = record

    return tuple(
        sorted(
            output.values(),
            key=lambda record: (
                record.source_page,
                record.source_viewport_id,
            ),
        )
    )


def collect_source_owned_floor_plan_levels(
    doc: Any,
    *,
    page_indices: Sequence[int],
    source_sha256: str,
    viewport_records: Optional[Sequence[LiveFloorPlanViewportRecord]] = None,
) -> tuple[LiveFloorPlanLevelRecord, ...]:
    """Collect explicit level identities only from authoritative floor-plan viewports."""

    source_sha = _clean(source_sha256).lower()
    if len(source_sha) != 64 or any(ch not in "0123456789abcdef" for ch in source_sha):
        return ()

    viewports = (
        tuple(viewport_records)
        if viewport_records is not None
        else collect_source_owned_floor_plan_viewports(
            doc,
            page_indices=page_indices,
            source_sha256=source_sha,
        )
    )
    output: list[LiveFloorPlanLevelRecord] = []
    seen_view_ids: set[str] = set()
    for viewport in viewports:
        if (
            type(viewport) is not LiveFloorPlanViewportRecord
            or not viewport.is_source_owned
            or viewport.source_sha256 != source_sha
        ):
            return ()
        parsed = _normalized_level_label(viewport.viewport_label)
        if parsed is None:
            continue
        view_id = viewport.source_viewport_id
        if view_id in seen_view_ids:
            return ()
        seen_view_ids.add(view_id)
        normalized_label, level_index = parsed
        canonical_level_id = stable_contract_id(
            "live_floor_plan_level_scope",
            {
                "source_sha256": source_sha,
                "source_page": viewport.source_page,
                "source_viewport_id": view_id,
                "normalized_level_label": normalized_label,
            },
            digest_chars=32,
        )
        output.append(
            LiveFloorPlanLevelRecord(
                canonical_level_id=canonical_level_id,
                level_label=viewport.viewport_label,
                normalized_level_label=normalized_label,
                level_index=level_index,
                source_page=viewport.source_page,
                source_viewport_id=view_id,
                viewport_bbox=viewport.viewport_bbox,
                viewport_confidence=viewport.viewport_confidence,
                source_sha256=source_sha,
                _seal=_LEVEL_SEAL,
            )
        )

    output.sort(key=lambda record: (record.source_page, record.source_viewport_id))
    return tuple(output)


def enrich_live_room_viewport_ownership(
    rooms: Sequence[Mapping[str, object]],
    *,
    viewports: Sequence[LiveFloorPlanViewportRecord],
) -> tuple[dict, ...]:
    """Attach one authoritative F.07 viewport to each room when unambiguous."""

    owned = tuple(
        viewport
        for viewport in viewports
        if (
            type(viewport) is LiveFloorPlanViewportRecord
            and viewport.is_source_owned
        )
    )
    output: list[dict] = []

    for raw in rooms:
        room = dict(raw)
        if _clean(room.get("viewport_id")):
            output.append(room)
            continue
        page_id = _clean(room.get("page_id"))
        polygon = room.get("polygon_pdf_pts") or ()
        candidates = tuple(
            viewport
            for viewport in owned
            if str(viewport.source_page) == page_id
            and source_room_polygon_owned_by_bbox(
                polygon,
                viewport.viewport_bbox,
            )
        )
        if len(candidates) == 1:
            viewport = candidates[0]
            room["viewport_id"] = viewport.source_viewport_id
            room["viewport_relationship_complete"] = True
            room["viewport_ownership"] = {
                "authority": "source_owned_floor_plan_viewport",
                "source_page": viewport.source_page,
                "source_viewport_id": viewport.source_viewport_id,
                "viewport_label": viewport.viewport_label,
                "viewport_bbox": list(viewport.viewport_bbox),
                "viewport_confidence": viewport.viewport_confidence,
                "source_sha256": viewport.source_sha256,
            }
        else:
            room["viewport_relationship_complete"] = False
            room["viewport_relationship_reason"] = (
                "room_viewport_ambiguous"
                if len(candidates) > 1
                else "room_viewport_unavailable"
            )
        output.append(room)

    return tuple(output)


def enrich_live_floor_viewport_ownership(
    floors: Sequence[Mapping[str, object]],
    *,
    rooms: Sequence[Mapping[str, object]],
) -> tuple[dict, ...]:
    """Propagate only proven room viewport ownership onto room-floor surfaces."""

    rooms_by_id = {
        _clean(room.get("canonical_room_id")): room
        for room in rooms
        if _clean(room.get("canonical_room_id"))
    }
    output: list[dict] = []

    for raw in floors:
        floor = dict(raw)
        room_id = _clean(floor.get("room_entity_id"))
        room = rooms_by_id.get(room_id)
        if room is None:
            floor["viewport_relationship_complete"] = False
            floor["viewport_relationship_reason"] = "floor_room_unavailable"
            output.append(floor)
            continue
        viewport_id = _clean(room.get("viewport_id"))
        if (
            not viewport_id
            or room.get("viewport_relationship_complete") is not True
        ):
            floor["viewport_relationship_complete"] = False
            floor["viewport_relationship_reason"] = (
                "floor_room_viewport_unresolved"
            )
            output.append(floor)
            continue

        floor["viewport_id"] = viewport_id
        floor["viewport_relationship_complete"] = True
        floor["viewport_ownership"] = dict(
            room.get("viewport_ownership") or {}
        )
        output.append(floor)

    return tuple(output)


def enrich_live_wall_level_ownership(
    walls: Sequence[Mapping[str, object]],
    *,
    levels: Sequence[LiveFloorPlanLevelRecord],
) -> tuple[dict, ...]:
    """Copy wall payloads and attach one proven level scope where unambiguous."""

    level_by_viewport = {
        record.source_viewport_id: record
        for record in levels
        if type(record) is LiveFloorPlanLevelRecord and record.is_source_owned
    }
    output: list[dict] = []

    for raw in walls:
        wall = dict(raw)
        existing = tuple(
            dict.fromkeys(
                _clean(value)
                for value in (wall.get("level_ids") or ())
                if _clean(value)
            )
        )
        if existing:
            output.append(wall)
            continue

        members = tuple(
            member
            for member in (wall.get("plan_members") or ())
            if isinstance(member, Mapping)
        )
        if not members:
            output.append(wall)
            continue

        viewport_ids = tuple(
            _clean(member.get("viewport_id"))
            for member in members
        )
        if any(not viewport_id for viewport_id in viewport_ids):
            output.append(wall)
            continue
        records = tuple(level_by_viewport.get(viewport_id) for viewport_id in viewport_ids)
        if any(record is None for record in records):
            output.append(wall)
            continue
        level_ids = tuple(
            dict.fromkeys(record.canonical_level_id for record in records if record)
        )
        if len(level_ids) != 1:
            output.append(wall)
            continue

        level_record = records[0]
        wall["level_ids"] = [level_ids[0]]
        wall["level_ownership"] = {
            "authority": "source_owned_floor_plan_viewport_label",
            "canonical_level_id": level_ids[0],
            "level_label": level_record.level_label,
            "normalized_level_label": level_record.normalized_level_label,
            "level_index": level_record.level_index,
            "source_page": level_record.source_page,
            "source_viewport_id": level_record.source_viewport_id,
            "cross_view_identity_resolved": False,
        }
        output.append(wall)

    return tuple(output)


__all__ = [
    "LIVE_FLOOR_PLAN_LEVEL_RESOLVED",
    "LIVE_FLOOR_PLAN_LEVEL_SCHEMA_VERSION",
    "LIVE_FLOOR_PLAN_LEVEL_UNAVAILABLE",
    "LiveFloorPlanLevelRecord",
    "LiveFloorPlanViewportRecord",
    "collect_source_owned_floor_plan_levels",
    "collect_source_owned_floor_plan_viewports",
    "enrich_live_floor_viewport_ownership",
    "enrich_live_room_viewport_ownership",
    "enrich_live_wall_level_ownership",
]
