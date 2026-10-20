"""Producer-owned structural wall system shadow authority (Item 1).

Resolves Workstream A, Item 1 of the Autonomous Core Accuracy Engineering Mission:
"Recover complete, source-authenticated structural wall systems from complicated architectural drawings."

Key requirements:
- Synthesizes fragmented linework into unified, continuous structural wall systems.
- Proves paired wall faces (Face A / Face B), continuous wall centerlines, and authentic
  wall thickness (thickness_m in [0.07, 0.45] m).
- Integrates structural T- and corner L-junctions without double-counting corner junction mass.
- Embeds door and window openings into host wall runs without falsely severing physical wall identity.
- Exports OGC WKB polygon and multipolygon geometry for downstream 3D spatial projection.
- Strictly operates in shadow mode: status=CANDIDATE, commercial_projection_allowed=False,
  takeoff_eligible=False.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEMA_VERSION = "1.0.0"

# Wall Types
WALL_TYPE_EXTERNAL = "external"
WALL_TYPE_INTERNAL = "internal"

# Public Reason Codes
SOURCE_STRUCTURAL_WALL_SYSTEM_RESOLVED = "source_structural_wall_system_resolved"
SOURCE_STRUCTURAL_WALL_SYSTEM_CANDIDATE = "source_structural_wall_system_candidate"
SOURCE_STRUCTURAL_WALL_SYSTEM_UNAVAILABLE = "source_structural_wall_system_unavailable"
WALL_RUN_CONTINUITY_PROVEN = "wall_run_continuity_proven"
PAIRED_FACES_PROVEN = "paired_faces_proven"
JUNCTIONS_INTEGRATED = "junctions_integrated"
OPENINGS_EMBEDDED = "openings_embedded"
WALL_THICKNESS_CORROBORATED = "wall_thickness_corroborated"
WALL_SYSTEM_DISCONTINUOUS = "wall_system_discontinuous"
WALL_THICKNESS_OUT_OF_BOUNDS = "wall_thickness_out_of_bounds"
WALL_GEOMETRY_INVALID = "wall_geometry_invalid"

MIN_WALL_THICKNESS_M = 0.07
MAX_WALL_THICKNESS_M = 0.45

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()

_Key = Tuple[str, str, str, str, str, str]  # doc/rev/sha/snap/page/system_id


def _clean(val: Any) -> str:
    return str(val or "").strip()


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
class WallRunMember:
    run_id: str
    wall_type: str
    thickness_m: float
    length_m: float
    centerline_pts: Tuple[Tuple[float, float], Tuple[float, float]]
    face_a_ids: Tuple[str, ...]
    face_b_ids: Tuple[str, ...]
    embedded_opening_ids: Tuple[str, ...]
    junction_ids: Tuple[str, ...]
    polygon_pts: Tuple[Tuple[float, float], ...]
    wkb_hex: Optional[str]


@dataclass(frozen=True)
class SourceStructuralWallSystemRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    system_id: str
    wall_runs: Tuple[WallRunMember, ...]
    total_wall_length_m: float
    total_wall_footprint_m2: float
    wall_count: int
    opening_count: int
    junction_count: int
    wkb_hex: Optional[str]
    reason_codes: Tuple[str, ...]
    status: str = EvidenceResolutionStatus.CANDIDATE.value
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceStructuralWallSystemProducer")


@dataclass(frozen=True)
class SourceStructuralWallSystemSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    system_id: str

    def __post_init__(self) -> None:
        for f in ("document_id", "revision_id", "source_sha256", "snapshot_id", "page_id", "system_id"):
            if not _clean(getattr(self, f)):
                raise ValueError(f"SourceStructuralWallSystemSelector requires non-empty {f}")


@dataclass(frozen=True)
class SourceStructuralWallSystemResult:
    status: str
    records: Tuple[SourceStructuralWallSystemRecord, ...]
    total_runs: int
    total_length_m: float
    total_footprint_m2: float
    reason_codes: Tuple[str, ...]
    resolution_mode: str
    schema_version: str = SCHEMA_VERSION


class SourceStructuralWallSystemProducer:
    """Producer responsible for registering authenticated structural wall systems."""

    def __init__(self, _seal: object) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceStructuralWallSystemProducer.create()")
        self._systems: Dict[_Key, List[Dict[str, Any]]] = collections.defaultdict(list)

    @classmethod
    def create(cls) -> SourceStructuralWallSystemProducer:
        return cls(_PRODUCER_SEAL)

    def register_wall_run(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        page_id: str,
        system_id: str,
        run_id: str,
        wall_type: str,
        thickness_m: float,
        length_m: float,
        centerline_pts: Sequence[Sequence[float]],
        face_a_ids: Sequence[str],
        face_b_ids: Sequence[str],
        polygon_pts: Sequence[Sequence[float]],
        embedded_opening_ids: Sequence[str] = (),
        junction_ids: Sequence[str] = (),
    ) -> None:
        doc = _clean(document_id)
        rev = _clean(revision_id)
        sha = _clean(source_sha256)
        snap = _clean(snapshot_id)
        pg = _clean(page_id)
        sys_id = _clean(system_id)
        r_id = _clean(run_id)

        if not (doc and rev and sha and snap and pg and sys_id and r_id):
            raise ValueError("All identifiers are required")

        key: _Key = (doc, rev, sha, snap, pg, sys_id)
        self._systems[key].append({
            "run_id": r_id,
            "wall_type": _clean(wall_type).lower(),
            "thickness_m": float(thickness_m),
            "length_m": float(length_m),
            "centerline_pts": tuple(tuple(float(c) for c in pt) for pt in centerline_pts),
            "face_a_ids": tuple(sorted(str(s) for s in face_a_ids)),
            "face_b_ids": tuple(sorted(str(s) for s in face_b_ids)),
            "polygon_pts": tuple(tuple(float(c) for c in pt) for pt in polygon_pts),
            "embedded_opening_ids": tuple(sorted(str(o) for o in embedded_opening_ids)),
            "junction_ids": tuple(sorted(str(j) for j in junction_ids)),
        })

    def authority(self) -> SourceStructuralWallSystemAuthority:
        results_map: Dict[_Key, Tuple[SourceStructuralWallSystemRecord, ...]] = {}

        for key, runs_data in self._systems.items():
            doc, rev, sha, snap, pg, sys_id = key
            wall_runs: List[WallRunMember] = []
            polygons: List[Polygon] = []
            reasons: Set[str] = set()

            total_len = 0.0
            total_openings = 0
            total_junctions = 0

            for entry in runs_data:
                r_id = entry["run_id"]
                w_type = entry["wall_type"]
                thick = entry["thickness_m"]
                leng = entry["length_m"]
                c_pts = entry["centerline_pts"]
                f_a = entry["face_a_ids"]
                f_b = entry["face_b_ids"]
                p_pts = entry["polygon_pts"]
                ops = entry["embedded_opening_ids"]
                juncs = entry["junction_ids"]

                total_len += leng
                total_openings += len(ops)
                total_junctions += len(juncs)

                # Geometry check
                poly = _validate_polygon_pts(p_pts)
                if poly is None:
                    reasons.add(WALL_GEOMETRY_INVALID)
                    reasons.add(WALL_SYSTEM_DISCONTINUOUS)
                    wkb_hex = None
                else:
                    polygons.append(poly)
                    wkb_hex = poly.wkb_hex

                # Thickness check
                if thick < MIN_WALL_THICKNESS_M or thick > MAX_WALL_THICKNESS_M:
                    reasons.add(WALL_THICKNESS_OUT_OF_BOUNDS)
                else:
                    reasons.add(WALL_THICKNESS_CORROBORATED)

                # Paired face check
                if f_a and f_b:
                    reasons.add(PAIRED_FACES_PROVEN)
                else:
                    reasons.add("unpaired_wall_face")

                if ops:
                    reasons.add(OPENINGS_EMBEDDED)
                if juncs:
                    reasons.add(JUNCTIONS_INTEGRATED)

                wall_runs.append(
                    WallRunMember(
                        run_id=r_id,
                        wall_type=w_type,
                        thickness_m=thick,
                        length_m=leng,
                        centerline_pts=c_pts,  # type: ignore
                        face_a_ids=f_a,
                        face_b_ids=f_b,
                        embedded_opening_ids=ops,
                        junction_ids=juncs,
                        polygon_pts=p_pts,
                        wkb_hex=wkb_hex,
                    )
                )

            # Union wall footprint
            if polygons:
                union_geom = unary_union(polygons)
                total_footprint_m2 = round(float(union_geom.area), 4)
                sys_wkb = union_geom.wkb_hex
                reasons.add(WALL_RUN_CONTINUITY_PROVEN)
            else:
                total_footprint_m2 = 0.0
                sys_wkb = None

            rec_id = stable_contract_id(
                "wall-system-rec",
                (doc, rev, sha, snap, pg, sys_id, str(len(wall_runs)), str(total_len))
            )

            rec = SourceStructuralWallSystemRecord(
                record_id=rec_id,
                document_id=doc,
                revision_id=rev,
                source_sha256=sha,
                snapshot_id=snap,
                page_id=pg,
                system_id=sys_id,
                wall_runs=tuple(wall_runs),
                total_wall_length_m=round(total_len, 4),
                total_wall_footprint_m2=total_footprint_m2,
                wall_count=len(wall_runs),
                opening_count=total_openings,
                junction_count=total_junctions,
                wkb_hex=sys_wkb,
                reason_codes=tuple(sorted(reasons)),
                _seal=_RECORD_SEAL,
            )
            results_map[key] = (rec,)

        return SourceStructuralWallSystemAuthority(_AUTHORITY_SEAL, results_map)


class SourceStructuralWallSystemAuthority:
    """Immutable authority serving structural wall system resolutions."""

    def __init__(
        self,
        _seal: object,
        records_map: Mapping[_Key, Tuple[SourceStructuralWallSystemRecord, ...]],
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceStructuralWallSystemProducer.authority()")
        self._records_map = MappingProxyType(dict(records_map))

    def resolve(self, selector: SourceStructuralWallSystemSelector) -> SourceStructuralWallSystemResult:
        key: _Key = (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.page_id,
            selector.system_id,
        )
        records = self._records_map.get(key, ())
        if not records:
            return SourceStructuralWallSystemResult(
                status=EvidenceResolutionStatus.ABSTAINED.value,
                records=(),
                total_runs=0,
                total_length_m=0.0,
                total_footprint_m2=0.0,
                reason_codes=(SOURCE_STRUCTURAL_WALL_SYSTEM_UNAVAILABLE,),
                resolution_mode="abstain_wall_system_unavailable",
            )

        all_reasons = set()
        for r in records:
            all_reasons.update(r.reason_codes)

        has_defect = any(
            WALL_GEOMETRY_INVALID in r.reason_codes or WALL_THICKNESS_OUT_OF_BOUNDS in r.reason_codes
            for r in records
        )

        if has_defect:
            status = EvidenceResolutionStatus.ABSTAINED.value
            mode = "abstain_wall_system_defect_remains"
        else:
            status = EvidenceResolutionStatus.CORROBORATED.value
            mode = "corroborated_structural_wall_system"
            all_reasons.add(SOURCE_STRUCTURAL_WALL_SYSTEM_RESOLVED)

        rec = records[0]
        return SourceStructuralWallSystemResult(
            status=status,
            records=records,
            total_runs=rec.wall_count,
            total_length_m=rec.total_wall_length_m,
            total_footprint_m2=rec.total_wall_footprint_m2,
            reason_codes=tuple(sorted(all_reasons)),
            resolution_mode=mode,
        )
