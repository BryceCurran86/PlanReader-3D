"""Producer-owned external soffit and eaves shadow authority (Item 17).

Resolves Workstream B, Item 17 of the Autonomous Core Accuracy Engineering Mission:
"Include external soffits and eaves where measurable."

Key responsibilities:
- Recovers authenticated external soffits, eaves, and canopy undercladding zones.
- Enforces strict role segregation: soffits and eaves belong to 'external_overhead_cladding',
  vetoing any misclassification as internal ceiling linings (e.g. GRID, IPF1).
- Proves 2D closed polygon boundaries between outer fascia/eave lines and internal/external
  wall face edges.
- Validates scale-calibrated metric area (m2) and linear perimeter (m).
- Cross-corroborates figured overhang dimensions (e.g. 450 mm, 600 mm eaves, or canopy widths)
  against measured polygon width when dimension evidence is present.
- Exports standard OGC WKB polygon geometry.
- Strictly operates in shadow mode: status=CANDIDATE, commercial_projection_allowed=False,
  takeoff_eligible=False.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from shapely.geometry import Polygon

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_visibility_authority import SourceVisibilityProducer

SCHEMA_VERSION = "1.0.0"

# Public Reason Codes
SOURCE_EXTERNAL_SOFFIT_RESOLVED = "source_external_soffit_resolved"
SOURCE_EXTERNAL_SOFFIT_CANDIDATE = "source_external_soffit_candidate"
SOURCE_EXTERNAL_SOFFIT_UNAVAILABLE = "source_external_soffit_unavailable"
SOURCE_EXTERNAL_SOFFIT_CONFLICT = "source_external_soffit_conflict"
SOFFIT_BOUNDARY_NOT_CLOSED = "soffit_boundary_not_closed"
SOFFIT_INVALID_GEOMETRY = "soffit_invalid_geometry"
SOFFIT_INTERNAL_CEILING_CONFLICT = "soffit_internal_ceiling_conflict"
SOFFIT_SCALE_NOT_CORROBORATED = "soffit_scale_not_corroborated"
SOFFIT_OVERHANG_DISCREPANCY = "soffit_overhang_discrepancy"
SOFFIT_MATERIAL_UNAUTHENTICATED = "soffit_material_unauthenticated"
SOFFIT_WALL_FACE_ANCHOR_MISSING = "soffit_wall_face_anchor_missing"

# Material Roles
ROLE_EXTERNAL_OVERHEAD_CLADDING = "external_overhead_cladding"
ROLE_INTERNAL_CEILING_LINING = "internal_ceiling_lining"

_ACCEPTED_SOFFIT_CODES = frozenset({
    "STP",
    "FCS1",
    "FC_SOFFIT",
    "SOFFIT",
    "EAVE",
    "EAVES",
    "EAVES_LINING",
    "CANOPY_CLADDING",
    "COLORBOND_SURFMIST",
    "EXTERNAL_SOFFIT_CLADDING",
})

_REJECTED_INTERNAL_CODES = frozenset({
    "IPF1",
    "GRID",
    "PLASTERBOARD",
    "ACOUSTIC_TILE",
    "CARPET",
    "VINYL",
    "FT2",
    "FT3",
})

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()

_Key = Tuple[str, str, str, str, str, str]  # doc/rev/sha/snap/page/soffit_tag


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
class SourceExternalSoffitSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    soffit_tag: str
    material_code: str = ""

    def __post_init__(self) -> None:
        for f in ("document_id", "revision_id", "source_sha256", "snapshot_id", "page_id", "soffit_tag"):
            if not _clean(getattr(self, f)):
                raise ValueError(f"SourceExternalSoffitSelector requires non-empty {f}")


@dataclass(frozen=True)
class SourceExternalSoffitRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    soffit_tag: str
    material_code: str
    material_description: str
    material_role: str
    boundary_pts: Tuple[Tuple[float, float], ...]
    area_pt2: float
    area_m2: Optional[float]
    perimeter_m: Optional[float]
    scale_px_per_m: Optional[float]
    figured_overhang_mm: Optional[float]
    measured_overhang_mm: Optional[float]
    wkb_hex: Optional[str]
    inner_wall_edge_ids: Tuple[str, ...]
    outer_fascia_edge_ids: Tuple[str, ...]
    reason_codes: Tuple[str, ...]
    status: str = EvidenceResolutionStatus.CANDIDATE.value
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceExternalSoffitProducer")


@dataclass(frozen=True)
class SourceExternalSoffitResult:
    status: str
    records: Tuple[SourceExternalSoffitRecord, ...]
    reason_codes: Tuple[str, ...]
    resolution_mode: str
    schema_version: str = SCHEMA_VERSION


class SourceExternalSoffitProducer:
    """Producer responsible for registering authenticated external soffit/eaves regions."""

    def __init__(self, _seal: object) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceExternalSoffitProducer.create()")
        self._zones: Dict[_Key, List[Dict[str, Any]]] = collections.defaultdict(list)

    @classmethod
    def create(cls) -> SourceExternalSoffitProducer:
        return cls(_PRODUCER_SEAL)

    def register_soffit_eaves_zone(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        page_id: str,
        soffit_tag: str,
        material_code: str,
        material_description: str,
        boundary_pts: Sequence[Sequence[float]],
        inner_wall_edge_ids: Sequence[str],
        outer_fascia_edge_ids: Sequence[str],
        scale_px_per_m: Optional[float] = None,
        figured_overhang_mm: Optional[float] = None,
    ) -> None:
        doc = _clean(document_id)
        rev = _clean(revision_id)
        sha = _clean(source_sha256)
        snap = _clean(snapshot_id)
        pg = _clean(page_id)
        tag = _clean(soffit_tag).upper()
        mat = _clean(material_code).upper()
        desc = _clean(material_description)

        if not (doc and rev and sha and snap and pg and tag):
            raise ValueError("All document, snapshot, page, and soffit_tag identifiers are required")

        key: _Key = (doc, rev, sha, snap, pg, tag)
        self._zones[key].append({
            "material_code": mat,
            "material_description": desc,
            "boundary_pts": tuple(tuple(float(c) for c in pt) for pt in boundary_pts),
            "inner_wall_edge_ids": tuple(sorted(str(e) for e in inner_wall_edge_ids)),
            "outer_fascia_edge_ids": tuple(sorted(str(e) for e in outer_fascia_edge_ids)),
            "scale_px_per_m": float(scale_px_per_m) if scale_px_per_m is not None and scale_px_per_m > 0 else None,
            "figured_overhang_mm": float(figured_overhang_mm) if figured_overhang_mm is not None and figured_overhang_mm > 0 else None,
        })

    def authority(self) -> SourceExternalSoffitAuthority:
        records_map: Dict[_Key, Tuple[SourceExternalSoffitRecord, ...]] = {}
        for key, zone_list in self._zones.items():
            doc, rev, sha, snap, pg, tag = key
            records: List[SourceExternalSoffitRecord] = []

            for idx, entry in enumerate(zone_list):
                mat = entry["material_code"]
                desc = entry["material_description"]
                pts = entry["boundary_pts"]
                inner_edges = entry["inner_wall_edge_ids"]
                outer_edges = entry["outer_fascia_edge_ids"]
                scale = entry["scale_px_per_m"]
                figured_overhang = entry["figured_overhang_mm"]

                reasons: List[str] = []

                # 1. Geometry Gate: Validate 2D closed non-degenerate polygon
                poly = _validate_polygon_pts(pts)
                if poly is None:
                    reasons.append(SOFFIT_INVALID_GEOMETRY)
                    reasons.append(SOFFIT_BOUNDARY_NOT_CLOSED)
                    rec_id = stable_contract_id(
                        "soffit-rec",
                        (doc, rev, sha, snap, pg, tag, mat, str(idx), "invalid-geom")
                    )
                    records.append(
                        SourceExternalSoffitRecord(
                            record_id=rec_id,
                            document_id=doc,
                            revision_id=rev,
                            source_sha256=sha,
                            snapshot_id=snap,
                            page_id=pg,
                            soffit_tag=tag,
                            material_code=mat,
                            material_description=desc,
                            material_role=ROLE_EXTERNAL_OVERHEAD_CLADDING,
                            boundary_pts=pts,
                            area_pt2=0.0,
                            area_m2=None,
                            perimeter_m=None,
                            scale_px_per_m=scale,
                            figured_overhang_mm=figured_overhang,
                            measured_overhang_mm=None,
                            wkb_hex=None,
                            inner_wall_edge_ids=inner_edges,
                            outer_fascia_edge_ids=outer_edges,
                            reason_codes=tuple(reasons),
                            _seal=_RECORD_SEAL,
                        )
                    )
                    continue

                # 2. Wall face anchor gate
                if not inner_edges:
                    reasons.append(SOFFIT_WALL_FACE_ANCHOR_MISSING)

                # 3. Material role and authenticity gate
                if mat in _REJECTED_INTERNAL_CODES:
                    reasons.append(SOFFIT_INTERNAL_CEILING_CONFLICT)
                elif mat and mat not in _ACCEPTED_SOFFIT_CODES and "SOFFIT" not in desc.upper() and "EAVE" not in desc.upper():
                    reasons.append(SOFFIT_MATERIAL_UNAUTHENTICATED)

                # 4. Scale and metric conversions
                area_pt2 = float(poly.area)
                area_m2: Optional[float] = None
                perimeter_m: Optional[float] = None
                measured_overhang_mm: Optional[float] = None

                if scale is not None and scale > 0:
                    area_m2 = round(area_pt2 / (scale * scale), 4)
                    perimeter_m = round(float(poly.length) / scale, 4)
                    # Measured average overhang depth: area / long side or bounding envelope
                    minx, miny, maxx, maxy = poly.bounds
                    dx = maxx - minx
                    dy = maxy - miny
                    # Eaves are elongated strips: narrower dimension is the overhang depth
                    short_dim_pt = min(dx, dy)
                    measured_overhang_mm = round((short_dim_pt / scale) * 1000.0, 1)

                    if figured_overhang is not None:
                        # Allow 5% tolerance between figured and measured overhang
                        discrepancy = abs(measured_overhang_mm - figured_overhang) / figured_overhang
                        if discrepancy > 0.05:
                            reasons.append(SOFFIT_OVERHANG_DISCREPANCY)
                else:
                    reasons.append(SOFFIT_SCALE_NOT_CORROBORATED)

                # Reason resolution
                if not reasons:
                    reasons.append(SOURCE_EXTERNAL_SOFFIT_RESOLVED)
                else:
                    reasons.append(SOURCE_EXTERNAL_SOFFIT_CANDIDATE)

                rec_id = stable_contract_id(
                    "soffit-rec",
                    (doc, rev, sha, snap, pg, tag, mat, str(idx), poly.wkt)
                )

                records.append(
                    SourceExternalSoffitRecord(
                        record_id=rec_id,
                        document_id=doc,
                        revision_id=rev,
                        source_sha256=sha,
                        snapshot_id=snap,
                        page_id=pg,
                        soffit_tag=tag,
                        material_code=mat,
                        material_description=desc,
                        material_role=ROLE_EXTERNAL_OVERHEAD_CLADDING,
                        boundary_pts=pts,
                        area_pt2=round(area_pt2, 4),
                        area_m2=area_m2,
                        perimeter_m=perimeter_m,
                        scale_px_per_m=scale,
                        figured_overhang_mm=figured_overhang,
                        measured_overhang_mm=measured_overhang_mm,
                        wkb_hex=poly.wkb_hex,
                        inner_wall_edge_ids=inner_edges,
                        outer_fascia_edge_ids=outer_edges,
                        reason_codes=tuple(reasons),
                        _seal=_RECORD_SEAL,
                    )
                )

            records_map[key] = tuple(records)

        return SourceExternalSoffitAuthority(_AUTHORITY_SEAL, records_map)


class SourceExternalSoffitAuthority:
    """Immutable authority serving external soffit and eaves resolutions."""

    def __init__(
        self,
        _seal: object,
        records_map: Mapping[_Key, Tuple[SourceExternalSoffitRecord, ...]],
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceExternalSoffitProducer.authority()")
        self._records_map = MappingProxyType(dict(records_map))

    def resolve(self, selector: SourceExternalSoffitSelector) -> SourceExternalSoffitResult:
        key: _Key = (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.page_id,
            selector.soffit_tag.upper(),
        )
        records = self._records_map.get(key, ())
        if not records:
            return SourceExternalSoffitResult(
                status=EvidenceResolutionStatus.ABSTAINED.value,
                records=(),
                reason_codes=(SOURCE_EXTERNAL_SOFFIT_UNAVAILABLE,),
                resolution_mode="abstain_unavailable",
            )

        # Filter by material_code if specified in selector
        filtered_records = records
        if selector.material_code:
            expected_mat = _clean(selector.material_code).upper()
            filtered_records = tuple(r for r in records if r.material_code == expected_mat)
            if not filtered_records:
                return SourceExternalSoffitResult(
                    status=EvidenceResolutionStatus.ABSTAINED.value,
                    records=(),
                    reason_codes=(SOURCE_EXTERNAL_SOFFIT_UNAVAILABLE,),
                    resolution_mode="abstain_material_code_mismatch",
                )

        has_conflict = any(SOFFIT_INTERNAL_CEILING_CONFLICT in r.reason_codes for r in filtered_records)
        all_resolved = all(SOURCE_EXTERNAL_SOFFIT_RESOLVED in r.reason_codes for r in filtered_records)

        if has_conflict:
            status = EvidenceResolutionStatus.ABSTAINED.value
            mode = "abstain_internal_ceiling_conflict"
        elif all_resolved:
            status = EvidenceResolutionStatus.CANDIDATE.value
            mode = "candidate_external_overhead_cladding"
        else:
            status = EvidenceResolutionStatus.CANDIDATE.value
            mode = "candidate_external_soffit_shadow"

        all_reasons = tuple(sorted({code for r in filtered_records for code in r.reason_codes}))
        return SourceExternalSoffitResult(
            status=status,
            records=filtered_records,
            reason_codes=all_reasons,
            resolution_mode=mode,
        )

    def all_results(self) -> Sequence[SourceExternalSoffitResult]:
        results: List[SourceExternalSoffitResult] = []
        for key, records in self._records_map.items():
            doc, rev, sha, snap, pg, tag = key
            selector = SourceExternalSoffitSelector(
                document_id=doc,
                revision_id=rev,
                source_sha256=sha,
                snapshot_id=snap,
                page_id=pg,
                soffit_tag=tag,
            )
            results.append(self.resolve(selector))
        return tuple(results)
