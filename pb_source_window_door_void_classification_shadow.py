"""Producer-owned window vs door physical void classification shadow authority (Item 61).

Resolves Workstream A & Workstream C Blocker:
"Differentiate door voids from window voids using source-authenticated physical geometry,
sill line presence, floor finish continuity, and schedule evidence."

Key capabilities:
- Proves whether an opening in a structural wall is a walk-through DOOR void or a fenestration WINDOW void:
    * DOOR: Floor finish transitions or terminates at opening chord; sill line is absent;
      door swing arc, sliding pocket, or schedule code 'Dxx' present; sill height = 0.
    * WINDOW: Floor finish is continuous beneath the opening; physical sill lines (1 or 2 lines
      spanning jambs) are present; glazing tick/line present; schedule code 'Wxx' present;
      sill height > 0 (or full-height glazing tagged as window).
- Vetoes ambiguous or contradictory openings where door and window evidence conflict (e.g. tag 'D01'
  with raised sill line and continuous floor finish).
- Exports validated physical void parameters: sill_height_m, head_height_m, clear_width_m,
  floor_interrupted, and OGC WKB opening line/chord geometry.
- Strictly operates in shadow mode: status=CANDIDATE, commercial_projection_allowed=False,
  takeoff_eligible=False.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
import math
import re
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from shapely.geometry import LineString

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEMA_VERSION = "1.0.0"

# Opening Kinds
OPENING_KIND_DOOR = "door"
OPENING_KIND_WINDOW = "window"
OPENING_KIND_AMBIGUOUS = "ambiguous"

# Public Reason Codes
SOURCE_OPENING_VOID_CLASSIFIED_DOOR = "source_opening_void_classified_door"
SOURCE_OPENING_VOID_CLASSIFIED_WINDOW = "source_opening_void_classified_window"
SOURCE_OPENING_VOID_UNAVAILABLE = "source_opening_void_unavailable"
OPENING_EVIDENCE_CONFLICT = "opening_evidence_conflict"
DOOR_SWING_ARC_PROVEN = "door_swing_arc_proven"
DOOR_THRESHOLD_LINE_PROVEN = "door_threshold_line_proven"
WINDOW_SILL_LINE_PROVEN = "window_sill_line_proven"
FLOOR_CONTINUITY_PROVEN = "floor_continuity_proven"
FLOOR_INTERRUPTION_PROVEN = "floor_interruption_proven"
SCHEDULE_TAG_DOOR_MATCH = "schedule_tag_door_match"
SCHEDULE_TAG_WINDOW_MATCH = "schedule_tag_window_match"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()

_Key = Tuple[str, str, str, str, str, str]  # doc/rev/sha/snap/page/opening_id


def _clean(val: Any) -> str:
    return str(val or "").strip()


@dataclass(frozen=True)
class SourceWindowDoorVoidRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    opening_id: str
    opening_kind: str  # "door" or "window"
    host_wall_id: str
    clear_width_m: float
    sill_height_m: Optional[float]
    head_height_m: Optional[float]
    floor_interrupted: bool
    sill_line_present: bool
    swing_arc_present: bool
    schedule_code: str
    chord_pts: Tuple[Tuple[float, float], Tuple[float, float]]
    wkb_hex: Optional[str]
    reason_codes: Tuple[str, ...]
    status: str = EvidenceResolutionStatus.CANDIDATE.value
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceWindowDoorVoidClassificationProducer")


@dataclass(frozen=True)
class SourceWindowDoorVoidSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    opening_id: str

    def __post_init__(self) -> None:
        for f in ("document_id", "revision_id", "source_sha256", "snapshot_id", "page_id", "opening_id"):
            if not _clean(getattr(self, f)):
                raise ValueError(f"SourceWindowDoorVoidSelector requires non-empty {f}")


@dataclass(frozen=True)
class SourceWindowDoorVoidResult:
    status: str
    record: Optional[SourceWindowDoorVoidRecord]
    opening_kind: str
    reason_codes: Tuple[str, ...]
    resolution_mode: str
    schema_version: str = SCHEMA_VERSION


class SourceWindowDoorVoidClassificationProducer:
    """Producer evaluating physical opening void geometry and schedule corroboration."""

    def __init__(self, _seal: object) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceWindowDoorVoidClassificationProducer.create()")
        self._openings: Dict[_Key, Dict[str, Any]] = {}

    @classmethod
    def create(cls) -> SourceWindowDoorVoidClassificationProducer:
        return cls(_PRODUCER_SEAL)

    def register_opening_void(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        page_id: str,
        opening_id: str,
        host_wall_id: str,
        chord_pts: Sequence[Sequence[float]],
        clear_width_m: float,
        sill_line_present: bool,
        floor_interrupted: bool,
        swing_arc_present: bool = False,
        schedule_code: str = "",
        sill_height_m: Optional[float] = None,
        head_height_m: Optional[float] = None,
    ) -> None:
        doc = _clean(document_id)
        rev = _clean(revision_id)
        sha = _clean(source_sha256)
        snap = _clean(snapshot_id)
        pg = _clean(page_id)
        op_id = _clean(opening_id)

        if not (doc and rev and sha and snap and pg and op_id):
            raise ValueError("All identifiers are required")

        if len(chord_pts) != 2:
            raise ValueError("chord_pts must contain exactly 2 endpoints")

        key: _Key = (doc, rev, sha, snap, pg, op_id)
        self._openings[key] = {
            "host_wall_id": _clean(host_wall_id),
            "chord_pts": ((float(chord_pts[0][0]), float(chord_pts[0][1])), (float(chord_pts[1][0]), float(chord_pts[1][1]))),
            "clear_width_m": float(clear_width_m),
            "sill_line_present": bool(sill_line_present),
            "floor_interrupted": bool(floor_interrupted),
            "swing_arc_present": bool(swing_arc_present),
            "schedule_code": _clean(schedule_code).upper(),
            "sill_height_m": float(sill_height_m) if sill_height_m is not None else None,
            "head_height_m": float(head_height_m) if head_height_m is not None else None,
        }

    def authority(self) -> SourceWindowDoorVoidClassificationAuthority:
        records_map: Dict[_Key, SourceWindowDoorVoidRecord] = {}

        for key, entry in self._openings.items():
            doc, rev, sha, snap, pg, op_id = key
            host_wall = entry["host_wall_id"]
            chord = entry["chord_pts"]
            width = entry["clear_width_m"]
            sill_present = entry["sill_line_present"]
            floor_int = entry["floor_interrupted"]
            swing_present = entry["swing_arc_present"]
            sched_code = entry["schedule_code"]
            sill_h = entry["sill_height_m"]
            head_h = entry["head_height_m"]

            reasons: List[str] = []
            door_votes = 0
            window_votes = 0

            # 1. Floor Interruption Check
            if floor_int:
                door_votes += 2
                reasons.append(FLOOR_INTERRUPTION_PROVEN)
            else:
                window_votes += 2
                reasons.append(FLOOR_CONTINUITY_PROVEN)

            # 2. Sill Line Check
            if sill_present:
                window_votes += 2
                reasons.append(WINDOW_SILL_LINE_PROVEN)
            else:
                door_votes += 1
                reasons.append(DOOR_THRESHOLD_LINE_PROVEN)

            # 3. Swing Arc Check
            if swing_present:
                door_votes += 3
                reasons.append(DOOR_SWING_ARC_PROVEN)

            # 4. Schedule Code Tag Check
            if sched_code.startswith("D"):
                door_votes += 2
                reasons.append(SCHEDULE_TAG_DOOR_MATCH)
            elif sched_code.startswith("W"):
                window_votes += 2
                reasons.append(SCHEDULE_TAG_WINDOW_MATCH)

            # 5. Sill Height Check
            if sill_h is not None and sill_h > 0:
                window_votes += 2

            # Disambiguation & Conflict Resolution
            if door_votes >= 3 and window_votes == 0:
                kind = OPENING_KIND_DOOR
                reasons.append(SOURCE_OPENING_VOID_CLASSIFIED_DOOR)
            elif window_votes >= 3 and door_votes == 0:
                kind = OPENING_KIND_WINDOW
                reasons.append(SOURCE_OPENING_VOID_CLASSIFIED_WINDOW)
            elif door_votes > window_votes and window_votes <= 1:
                kind = OPENING_KIND_DOOR
                reasons.append(SOURCE_OPENING_VOID_CLASSIFIED_DOOR)
            elif window_votes > door_votes and door_votes <= 1:
                kind = OPENING_KIND_WINDOW
                reasons.append(SOURCE_OPENING_VOID_CLASSIFIED_WINDOW)
            else:
                kind = OPENING_KIND_AMBIGUOUS
                reasons.append(OPENING_EVIDENCE_CONFLICT)

            # Generate OGC LineString for opening chord
            ls = LineString(chord)
            rec_id = stable_contract_id(
                "opening-void-rec",
                (doc, rev, sha, snap, pg, op_id, kind, str(width))
            )

            rec = SourceWindowDoorVoidRecord(
                record_id=rec_id,
                document_id=doc,
                revision_id=rev,
                source_sha256=sha,
                snapshot_id=snap,
                page_id=pg,
                opening_id=op_id,
                opening_kind=kind,
                host_wall_id=host_wall,
                clear_width_m=width,
                sill_height_m=sill_h,
                head_height_m=head_h,
                floor_interrupted=floor_int,
                sill_line_present=sill_present,
                swing_arc_present=swing_present,
                schedule_code=sched_code,
                chord_pts=chord,
                wkb_hex=ls.wkb_hex,
                reason_codes=tuple(sorted(set(reasons))),
                _seal=_RECORD_SEAL,
            )
            records_map[key] = rec

        return SourceWindowDoorVoidClassificationAuthority(_AUTHORITY_SEAL, records_map)


class SourceWindowDoorVoidClassificationAuthority:
    """Immutable authority serving window vs door void classifications."""

    def __init__(
        self,
        _seal: object,
        records_map: Mapping[_Key, SourceWindowDoorVoidRecord],
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceWindowDoorVoidClassificationProducer.authority()")
        self._records_map = MappingProxyType(dict(records_map))

    def resolve(self, selector: SourceWindowDoorVoidSelector) -> SourceWindowDoorVoidResult:
        key: _Key = (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.page_id,
            selector.opening_id,
        )
        rec = self._records_map.get(key)
        if rec is None:
            return SourceWindowDoorVoidResult(
                status=EvidenceResolutionStatus.ABSTAINED.value,
                record=None,
                opening_kind=OPENING_KIND_AMBIGUOUS,
                reason_codes=(SOURCE_OPENING_VOID_UNAVAILABLE,),
                resolution_mode="abstain_opening_unavailable",
            )

        if rec.opening_kind == OPENING_KIND_AMBIGUOUS or OPENING_EVIDENCE_CONFLICT in rec.reason_codes:
            status = EvidenceResolutionStatus.ABSTAINED.value
            mode = "abstain_opening_evidence_conflict"
        else:
            status = EvidenceResolutionStatus.CORROBORATED.value
            mode = f"corroborated_{rec.opening_kind}_physical_void"

        return SourceWindowDoorVoidResult(
            status=status,
            record=rec,
            opening_kind=rec.opening_kind,
            reason_codes=rec.reason_codes,
            resolution_mode=mode,
        )
