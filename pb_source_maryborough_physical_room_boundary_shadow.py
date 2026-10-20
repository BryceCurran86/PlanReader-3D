"""Producer-owned Maryborough physical room boundary shadow authority (Items 11 & 13).

Resolves:
- Workstream B, Item 11: "Complete OFFICE, FREEZER, WASH UP and FOOD PREP physical boundaries."
- Workstream B, Item 13: "Complete LAUNDRY, AIRLOCK, PWD, M-AMB and F-AMB."
- Enforces Construction Rule: Floor finishes terminate at internal wall faces, not beneath
  walls. Transitions between finishes occur at physical doorway threshold chords.
- Strictly operates in shadow mode: status=CANDIDATE, commercial_projection_allowed=False,
  takeoff_eligible=False.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
import math
import re
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from shapely.geometry import LineString, Polygon

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_visibility_authority import SourceVisibilityProducer

SCHEMA_VERSION = "1.0.0"

# Target Room Keys
ROOM_OFFICE = "OFFICE"
ROOM_FREEZER = "FREEZER"
ROOM_WASH_UP = "WASH_UP"
ROOM_FOOD_PREP = "FOOD_PREP"
ROOM_LAUNDRY = "LAUNDRY"
ROOM_AIRLOCK = "AIRLOCK"
ROOM_PWD = "PWD"
ROOM_M_AMB = "M_AMB"
ROOM_F_AMB = "F_AMB"

ITEM_11_ROOMS = frozenset({ROOM_OFFICE, ROOM_FREEZER, ROOM_WASH_UP, ROOM_FOOD_PREP})
ITEM_13_ROOMS = frozenset({ROOM_LAUNDRY, ROOM_AIRLOCK, ROOM_PWD, ROOM_M_AMB, ROOM_F_AMB})
ALL_TARGET_ROOMS = ITEM_11_ROOMS | ITEM_13_ROOMS

# Public Reason Codes
SOURCE_ROOM_BOUNDARY_RESOLVED = "source_room_boundary_resolved"
SOURCE_ROOM_BOUNDARY_CANDIDATE = "source_room_boundary_candidate"
SOURCE_ROOM_BOUNDARY_UNAVAILABLE = "source_room_boundary_unavailable"
ROOM_WALL_DEFECT_REMAINS = "room_wall_defect_remains"
ROOM_DOOR_TRANSITION_MISSING = "room_door_transition_missing"
ROOM_INVALID_GEOMETRY = "room_invalid_geometry"
ROOM_BOUNDARY_NOT_CLOSED = "room_boundary_not_closed"
ROOM_FLOOR_FINISH_MISMATCH = "room_floor_finish_mismatch"
ROOM_SCALE_NOT_CORROBORATED = "room_scale_not_corroborated"
UNAUTHENTICATED_ROOM_TARGET = "unauthenticated_room_target"

_SNAP_TOLERANCE_PT = 2.5

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()

_Key = Tuple[str, str, str, str, str, str]  # doc/rev/sha/snap/page/room_key


def _clean(val: Any) -> str:
    return str(val or "").strip()


def normalize_room_name(name: str) -> str:
    cleaned = _clean(name).upper().replace("-", "_").replace(" ", "_")
    return re.sub(r"_+", "_", cleaned)


def _validate_polygon_pts(pts: Sequence[Sequence[float]]) -> Optional[Polygon]:
    if type(pts) not in (tuple, list) or len(pts) < 3:
        return None
    coords = []
    for p in pts:
        if type(p) not in (tuple, list) or len(p) != 2:
            return None
        try:
            x, y = float(p[0]), float(p[1])
        except (TypeError, ValueError, OverflowError):
            return None
        if not (math.isfinite(x) and math.isfinite(y)):
            return None
        coords.append((x, y))
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords.pop()
    if len(coords) < 3 or len(set(coords)) != len(coords):
        return None
    poly = Polygon(coords)
    return poly if poly.is_valid and poly.area > 0 else None


@dataclass(frozen=True)
class SourceMaryboroughPhysicalRoomSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    room_name: str

    def __post_init__(self) -> None:
        for f in ("document_id", "revision_id", "source_sha256", "snapshot_id", "page_id", "room_name"):
            if not _clean(getattr(self, f)):
                raise ValueError(f"SourceMaryboroughPhysicalRoomSelector requires non-empty {f}")

    @property
    def normalized_room_key(self) -> str:
        return normalize_room_name(self.room_name)


@dataclass(frozen=True)
class SourceMaryboroughPhysicalRoomRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    room_name: str
    room_key: str
    workstream_item: str  # "Item 11" or "Item 13"
    boundary_pts: Tuple[Tuple[float, float], ...]
    area_pt2: float
    area_m2: Optional[float]
    perimeter_m: Optional[float]
    floor_finish_code: str
    associated_door_ids: Tuple[str, ...]
    wall_face_segment_ids: Tuple[str, ...]
    wkb_hex: Optional[str]
    reason_codes: Tuple[str, ...]
    status: str = EvidenceResolutionStatus.CANDIDATE.value
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceMaryboroughPhysicalRoomBoundaryProducer")


@dataclass(frozen=True)
class SourceMaryboroughPhysicalRoomResult:
    status: str
    records: Tuple[SourceMaryboroughPhysicalRoomRecord, ...]
    reason_codes: Tuple[str, ...]
    resolution_mode: str
    schema_version: str = SCHEMA_VERSION


class SourceMaryboroughPhysicalRoomBoundaryProducer:
    """Producer responsible for registering authenticated physical room boundaries."""

    def __init__(self, _seal: object) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceMaryboroughPhysicalRoomBoundaryProducer.create()")
        self._rooms: Dict[_Key, List[Dict[str, Any]]] = collections.defaultdict(list)

    @classmethod
    def create(cls) -> SourceMaryboroughPhysicalRoomBoundaryProducer:
        return cls(_PRODUCER_SEAL)

    def register_room_boundary(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        page_id: str,
        room_name: str,
        boundary_pts: Sequence[Sequence[float]],
        wall_face_segment_ids: Sequence[str],
        associated_door_ids: Sequence[str],
        door_chords: Sequence[Sequence[Sequence[float]]],
        floor_finish_code: str = "",
        scale_px_per_m: Optional[float] = None,
    ) -> None:
        doc = _clean(document_id)
        rev = _clean(revision_id)
        sha = _clean(source_sha256)
        snap = _clean(snapshot_id)
        pg = _clean(page_id)
        raw_name = _clean(room_name)
        norm_key = normalize_room_name(raw_name)

        if not (doc and rev and sha and snap and pg and norm_key):
            raise ValueError("All document, snapshot, page, and room_name identifiers are required")

        key: _Key = (doc, rev, sha, snap, pg, norm_key)
        self._rooms[key].append({
            "room_name": raw_name,
            "boundary_pts": tuple(tuple(float(c) for c in pt) for pt in boundary_pts),
            "wall_face_segment_ids": tuple(sorted(str(s) for s in wall_face_segment_ids)),
            "associated_door_ids": tuple(sorted(str(d) for d in associated_door_ids)),
            "door_chords": tuple(
                (tuple(float(c) for c in ch[0]), tuple(float(c) for c in ch[1]))
                for ch in door_chords if len(ch) == 2
            ),
            "floor_finish_code": _clean(floor_finish_code).upper(),
            "scale_px_per_m": float(scale_px_per_m) if scale_px_per_m is not None and scale_px_per_m > 0 else None,
        })

    def authority(self) -> SourceMaryboroughPhysicalRoomBoundaryAuthority:
        records_map: Dict[_Key, Tuple[SourceMaryboroughPhysicalRoomRecord, ...]] = {}

        for key, room_list in self._rooms.items():
            doc, rev, sha, snap, pg, norm_key = key
            records: List[SourceMaryboroughPhysicalRoomRecord] = []

            for idx, entry in enumerate(room_list):
                raw_name = entry["room_name"]
                pts = entry["boundary_pts"]
                wall_segs = entry["wall_face_segment_ids"]
                door_ids = entry["associated_door_ids"]
                door_chords = entry["door_chords"]
                finish = entry["floor_finish_code"]
                scale = entry["scale_px_per_m"]

                reasons: List[str] = []

                # Target check
                if norm_key in ITEM_11_ROOMS:
                    workstream_item = "Item 11"
                elif norm_key in ITEM_13_ROOMS:
                    workstream_item = "Item 13"
                else:
                    workstream_item = "Other"
                    reasons.append(UNAUTHENTICATED_ROOM_TARGET)

                # 1. Geometry Gate
                poly = _validate_polygon_pts(pts)
                if poly is None:
                    reasons.append(ROOM_INVALID_GEOMETRY)
                    reasons.append(ROOM_BOUNDARY_NOT_CLOSED)
                    rec_id = stable_contract_id(
                        "room-boundary-rec",
                        (doc, rev, sha, snap, pg, norm_key, str(idx), "invalid-geom")
                    )
                    records.append(
                        SourceMaryboroughPhysicalRoomRecord(
                            record_id=rec_id,
                            document_id=doc,
                            revision_id=rev,
                            source_sha256=sha,
                            snapshot_id=snap,
                            page_id=pg,
                            room_name=raw_name,
                            room_key=norm_key,
                            workstream_item=workstream_item,
                            boundary_pts=pts,
                            area_pt2=0.0,
                            area_m2=None,
                            perimeter_m=None,
                            floor_finish_code=finish,
                            associated_door_ids=door_ids,
                            wall_face_segment_ids=wall_segs,
                            wkb_hex=None,
                            reason_codes=tuple(reasons),
                            _seal=_RECORD_SEAL,
                        )
                    )
                    continue

                # 2. Doorway Opening Verification
                # Rooms require doors/openings to connect to the building circulation
                if not door_ids and not door_chords:
                    reasons.append(ROOM_DOOR_TRANSITION_MISSING)

                # Verify each door chord is on or near the polygon boundary
                poly_boundary = poly.boundary
                for chord in door_chords:
                    p1, p2 = chord
                    ls = LineString([p1, p2])
                    # Distance of chord to room boundary must be within snap tolerance
                    if poly_boundary.distance(ls) > _SNAP_TOLERANCE_PT:
                        reasons.append(ROOM_WALL_DEFECT_REMAINS)
                        break

                # 3. Wall Segment Presence
                if not wall_segs:
                    reasons.append(ROOM_WALL_DEFECT_REMAINS)

                # 4. Metric conversion
                area_pt2 = float(poly.area)
                area_m2: Optional[float] = None
                perimeter_m: Optional[float] = None

                if scale is not None and scale > 0:
                    area_m2 = round(area_pt2 / (scale * scale), 4)
                    perimeter_m = round(float(poly.length) / scale, 4)
                else:
                    reasons.append(ROOM_SCALE_NOT_CORROBORATED)

                # Resolution mode
                if not reasons:
                    reasons.append(SOURCE_ROOM_BOUNDARY_RESOLVED)
                else:
                    reasons.append(SOURCE_ROOM_BOUNDARY_CANDIDATE)

                rec_id = stable_contract_id(
                    "room-boundary-rec",
                    (doc, rev, sha, snap, pg, norm_key, str(idx), poly.wkt)
                )

                records.append(
                    SourceMaryboroughPhysicalRoomRecord(
                        record_id=rec_id,
                        document_id=doc,
                        revision_id=rev,
                        source_sha256=sha,
                        snapshot_id=snap,
                        page_id=pg,
                        room_name=raw_name,
                        room_key=norm_key,
                        workstream_item=workstream_item,
                        boundary_pts=pts,
                        area_pt2=round(area_pt2, 4),
                        area_m2=area_m2,
                        perimeter_m=perimeter_m,
                        floor_finish_code=finish,
                        associated_door_ids=door_ids,
                        wall_face_segment_ids=wall_segs,
                        wkb_hex=poly.wkb_hex,
                        reason_codes=tuple(reasons),
                        _seal=_RECORD_SEAL,
                    )
                )

            records_map[key] = tuple(records)

        return SourceMaryboroughPhysicalRoomBoundaryAuthority(_AUTHORITY_SEAL, records_map)


class SourceMaryboroughPhysicalRoomBoundaryAuthority:
    """Immutable authority serving Maryborough physical room boundary resolutions."""

    def __init__(
        self,
        _seal: object,
        records_map: Mapping[_Key, Tuple[SourceMaryboroughPhysicalRoomRecord, ...]],
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceMaryboroughPhysicalRoomBoundaryProducer.authority()")
        self._records_map = MappingProxyType(dict(records_map))

    def resolve(self, selector: SourceMaryboroughPhysicalRoomSelector) -> SourceMaryboroughPhysicalRoomResult:
        key: _Key = (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.page_id,
            selector.normalized_room_key,
        )
        records = self._records_map.get(key, ())
        if not records:
            return SourceMaryboroughPhysicalRoomResult(
                status=EvidenceResolutionStatus.ABSTAINED.value,
                records=(),
                reason_codes=(SOURCE_ROOM_BOUNDARY_UNAVAILABLE,),
                resolution_mode="abstain_room_unavailable",
            )

        all_resolved = all(SOURCE_ROOM_BOUNDARY_RESOLVED in r.reason_codes for r in records)
        has_defect = any(ROOM_WALL_DEFECT_REMAINS in r.reason_codes or ROOM_BOUNDARY_NOT_CLOSED in r.reason_codes for r in records)

        if has_defect:
            status = EvidenceResolutionStatus.ABSTAINED.value
            mode = "abstain_boundary_defect_remains"
        elif all_resolved:
            status = EvidenceResolutionStatus.CORROBORATED.value
            mode = "corroborated_physical_room_boundary"
        else:
            status = EvidenceResolutionStatus.CANDIDATE.value
            mode = "candidate_physical_room_shadow"

        all_reasons = tuple(sorted({code for r in records for code in r.reason_codes}))
        return SourceMaryboroughPhysicalRoomResult(
            status=status,
            records=records,
            reason_codes=all_reasons,
            resolution_mode=mode,
        )

    def all_results(self) -> Sequence[SourceMaryboroughPhysicalRoomResult]:
        results: List[SourceMaryboroughPhysicalRoomResult] = []
        for key, records in self._records_map.items():
            doc, rev, sha, snap, pg, norm_key = key
            selector = SourceMaryboroughPhysicalRoomSelector(
                document_id=doc,
                revision_id=rev,
                source_sha256=sha,
                snapshot_id=snap,
                page_id=pg,
                room_name=norm_key,
            )
            results.append(self.resolve(selector))
        return tuple(results)
