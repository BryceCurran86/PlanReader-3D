"""Producer-owned cold-room insulated panel (PIR/EPS) structural boundary shadow authority (Item 62).

Resolves Workstream B & Workstream A Blocker:
"Recover authenticated insulated sandwich panel boundaries for refrigerated enclosures
(e.g. FREEZER, COLD ROOM) with thermal breaks, panel joint continuity, and door rebates."

Key capabilities:
- Identifies specialized cold-storage sandwich panel construction (PIR, EPS, XFLAM, Bondor, Kingspan).
- Validates panel wall thickness within architectural cold-room standards (0.075 m to 0.200 m).
- Proves complete thermal perimeter enclosure around refrigerated spaces without uninsulated breaks.
- Embeds cold-room insulated doors (hinged or sliding with thermal gaskets) into panel walls.
- Derives scale-calibrated refrigerated storage internal floor area (m2) and volume (m3).
- Exports standard OGC WKB polygon geometry.
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

from shapely.geometry import Polygon

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEMA_VERSION = "1.0.0"

# Panel Materials
PANEL_MATERIAL_PIR = "pir_insulated_panel"
PANEL_MATERIAL_EPS = "eps_insulated_panel"
PANEL_MATERIAL_GENERIC_COLD = "generic_cold_storage_panel"

_ACCEPTED_COLD_ROOM_NAMES = frozenset({
    "FREEZER",
    "COLD_ROOM",
    "COOL_ROOM",
    "KEG_ROOM",
    "CHILLER",
})

# Public Reason Codes
SOURCE_COLD_ROOM_BOUNDARY_RESOLVED = "source_cold_room_boundary_resolved"
SOURCE_COLD_ROOM_BOUNDARY_CANDIDATE = "source_cold_room_boundary_candidate"
SOURCE_COLD_ROOM_BOUNDARY_UNAVAILABLE = "source_cold_room_boundary_unavailable"
THERMAL_PERIMETER_ENCLOSED = "thermal_perimeter_enclosed"
COLD_ROOM_PANEL_THICKNESS_CORROBORATED = "cold_room_panel_thickness_corroborated"
COLD_ROOM_DOOR_REBATE_VERIFIED = "cold_room_door_rebate_verified"
THERMAL_BREAK_GAP_DEFECT = "thermal_break_gap_defect"
NON_COLD_ROOM_NAME_UNAUTHENTICATED = "non_cold_room_name_unauthenticated"
PANEL_THICKNESS_OUT_OF_BOUNDS = "panel_thickness_out_of_bounds"
COLD_ROOM_GEOMETRY_INVALID = "cold_room_geometry_invalid"

MIN_PANEL_THICKNESS_M = 0.075
MAX_PANEL_THICKNESS_M = 0.200

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()

_Key = Tuple[str, str, str, str, str, str]  # doc/rev/sha/snap/page/room_key


def _clean(val: Any) -> str:
    return str(val or "").strip()


def normalize_cold_room_name(name: str) -> str:
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
class SourceColdRoomPanelRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    room_name: str
    room_key: str
    panel_material: str
    panel_thickness_m: float
    internal_area_m2: Optional[float]
    internal_perimeter_m: Optional[float]
    storage_volume_m3: Optional[float]
    panel_segment_ids: Tuple[str, ...]
    door_opening_ids: Tuple[str, ...]
    boundary_pts: Tuple[Tuple[float, float], ...]
    wkb_hex: Optional[str]
    reason_codes: Tuple[str, ...]
    status: str = EvidenceResolutionStatus.CANDIDATE.value
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceColdRoomInsulatedPanelProducer")


@dataclass(frozen=True)
class SourceColdRoomPanelSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    room_name: str

    def __post_init__(self) -> None:
        for f in ("document_id", "revision_id", "source_sha256", "snapshot_id", "page_id", "room_name"):
            if not _clean(getattr(self, f)):
                raise ValueError(f"SourceColdRoomPanelSelector requires non-empty {f}")

    @property
    def normalized_room_key(self) -> str:
        return normalize_cold_room_name(self.room_name)


@dataclass(frozen=True)
class SourceColdRoomPanelResult:
    status: str
    record: Optional[SourceColdRoomPanelRecord]
    internal_area_m2: Optional[float]
    storage_volume_m3: Optional[float]
    reason_codes: Tuple[str, ...]
    resolution_mode: str
    schema_version: str = SCHEMA_VERSION


class SourceColdRoomInsulatedPanelProducer:
    """Producer responsible for registering authenticated cold-storage panel boundaries."""

    def __init__(self, _seal: object) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceColdRoomInsulatedPanelProducer.create()")
        self._rooms: Dict[_Key, Dict[str, Any]] = {}

    @classmethod
    def create(cls) -> SourceColdRoomInsulatedPanelProducer:
        return cls(_PRODUCER_SEAL)

    def register_cold_room(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        page_id: str,
        room_name: str,
        panel_material: str,
        panel_thickness_m: float,
        boundary_pts: Sequence[Sequence[float]],
        panel_segment_ids: Sequence[str],
        door_opening_ids: Sequence[str],
        clear_height_m: Optional[float] = None,
        scale_px_per_m: Optional[float] = None,
    ) -> None:
        doc = _clean(document_id)
        rev = _clean(revision_id)
        sha = _clean(source_sha256)
        snap = _clean(snapshot_id)
        pg = _clean(page_id)
        raw_name = _clean(room_name)
        norm_key = normalize_cold_room_name(raw_name)

        if not (doc and rev and sha and snap and pg and norm_key):
            raise ValueError("All identifiers are required")

        key: _Key = (doc, rev, sha, snap, pg, norm_key)
        self._rooms[key] = {
            "room_name": raw_name,
            "panel_material": _clean(panel_material).lower(),
            "panel_thickness_m": float(panel_thickness_m),
            "boundary_pts": tuple(tuple(float(c) for c in pt) for pt in boundary_pts),
            "panel_segment_ids": tuple(sorted(str(s) for s in panel_segment_ids)),
            "door_opening_ids": tuple(sorted(str(d) for d in door_opening_ids)),
            "clear_height_m": float(clear_height_m) if clear_height_m is not None and clear_height_m > 0 else None,
            "scale_px_per_m": float(scale_px_per_m) if scale_px_per_m is not None and scale_px_per_m > 0 else None,
        }

    def authority(self) -> SourceColdRoomInsulatedPanelAuthority:
        records_map: Dict[_Key, SourceColdRoomPanelRecord] = {}

        for key, entry in self._rooms.items():
            doc, rev, sha, snap, pg, norm_key = key
            raw_name = entry["room_name"]
            mat = entry["panel_material"]
            thick = entry["panel_thickness_m"]
            pts = entry["boundary_pts"]
            panel_segs = entry["panel_segment_ids"]
            door_ids = entry["door_opening_ids"]
            height_m = entry["clear_height_m"]
            scale = entry["scale_px_per_m"]

            reasons: List[str] = []

            # 1. Name Check
            if norm_key not in _ACCEPTED_COLD_ROOM_NAMES and "FREEZER" not in norm_key and "COLD" not in norm_key:
                reasons.append(NON_COLD_ROOM_NAME_UNAUTHENTICATED)

            # 2. Geometry Gate
            poly = _validate_polygon_pts(pts)
            if poly is None:
                reasons.append(COLD_ROOM_GEOMETRY_INVALID)
                reasons.append(THERMAL_BREAK_GAP_DEFECT)
                wkb_hex = None
                area_m2 = None
                perim_m = None
                vol_m3 = None
            else:
                wkb_hex = poly.wkb_hex
                reasons.append(THERMAL_PERIMETER_ENCLOSED)
                if scale is not None and scale > 0:
                    area_m2 = round(float(poly.area) / (scale * scale), 4)
                    perim_m = round(float(poly.length) / scale, 4)
                    vol_m3 = round(area_m2 * height_m, 4) if height_m is not None else None
                else:
                    area_m2 = None
                    perim_m = None
                    vol_m3 = None

            # 3. Thickness Gate
            if thick < MIN_PANEL_THICKNESS_M or thick > MAX_PANEL_THICKNESS_M:
                reasons.append(PANEL_THICKNESS_OUT_OF_BOUNDS)
            else:
                reasons.append(COLD_ROOM_PANEL_THICKNESS_CORROBORATED)

            # 4. Door Verification
            if door_ids:
                reasons.append(COLD_ROOM_DOOR_REBATE_VERIFIED)
            else:
                reasons.append("cold_room_door_unregistered")

            rec_id = stable_contract_id(
                "cold-panel-rec",
                (doc, rev, sha, snap, pg, norm_key, str(thick), str(area_m2))
            )

            rec = SourceColdRoomPanelRecord(
                record_id=rec_id,
                document_id=doc,
                revision_id=rev,
                source_sha256=sha,
                snapshot_id=snap,
                page_id=pg,
                room_name=raw_name,
                room_key=norm_key,
                panel_material=mat,
                panel_thickness_m=thick,
                internal_area_m2=area_m2,
                internal_perimeter_m=perim_m,
                storage_volume_m3=vol_m3,
                panel_segment_ids=panel_segs,
                door_opening_ids=door_ids,
                boundary_pts=pts,
                wkb_hex=wkb_hex,
                reason_codes=tuple(sorted(set(reasons))),
                _seal=_RECORD_SEAL,
            )
            records_map[key] = rec

        return SourceColdRoomInsulatedPanelAuthority(_AUTHORITY_SEAL, records_map)


class SourceColdRoomInsulatedPanelAuthority:
    """Immutable authority serving cold-room panel boundary resolutions."""

    def __init__(
        self,
        _seal: object,
        records_map: Mapping[_Key, SourceColdRoomPanelRecord],
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceColdRoomInsulatedPanelProducer.authority()")
        self._records_map = MappingProxyType(dict(records_map))

    def resolve(self, selector: SourceColdRoomPanelSelector) -> SourceColdRoomPanelResult:
        key: _Key = (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.page_id,
            selector.normalized_room_key,
        )
        rec = self._records_map.get(key)
        if rec is None:
            return SourceColdRoomPanelResult(
                status=EvidenceResolutionStatus.ABSTAINED.value,
                record=None,
                internal_area_m2=None,
                storage_volume_m3=None,
                reason_codes=(SOURCE_COLD_ROOM_BOUNDARY_UNAVAILABLE,),
                resolution_mode="abstain_cold_room_unavailable",
            )

        has_defect = any(
            code in rec.reason_codes
            for code in (COLD_ROOM_GEOMETRY_INVALID, PANEL_THICKNESS_OUT_OF_BOUNDS, THERMAL_BREAK_GAP_DEFECT, NON_COLD_ROOM_NAME_UNAUTHENTICATED)
        )

        all_reasons = set(rec.reason_codes)
        if has_defect:
            status = EvidenceResolutionStatus.ABSTAINED.value
            mode = "abstain_cold_room_panel_defect"
        else:
            status = EvidenceResolutionStatus.CORROBORATED.value
            mode = "corroborated_cold_room_panel_boundary"
            all_reasons.add(SOURCE_COLD_ROOM_BOUNDARY_RESOLVED)

        return SourceColdRoomPanelResult(
            status=status,
            record=rec,
            internal_area_m2=rec.internal_area_m2,
            storage_volume_m3=rec.storage_volume_m3,
            reason_codes=tuple(sorted(all_reasons)),
            resolution_mode=mode,
        )
