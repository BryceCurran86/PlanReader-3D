"""Hardened deterministic authority contracts shared by opening and surface publication.

This module separates physical identity from evidence reproducibility, keeps
figured-dimension authority independent from drawing-scale authority, and
requires internal-elevation wall-face ownership before wall-tile quantity can
become canonical.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable, Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id


IDENTITY_SCHEMA_VERSION = "1.0.0"
EVIDENCE_SCHEMA_VERSION = "1.0.0"
MEASUREMENT_FIGURED_DIMENSION = "figured_dimension"
MEASUREMENT_GEOMETRY_SCALED = "geometry_scaled"
MEASUREMENT_SCALE_REQUIRED = "measurement_scale_required"
MEASUREMENT_SCALE_CONFLICT = "measurement_scale_conflict"
INTERNAL_ELEVATION_VIEWPORT_REQUIRED = "internal_elevation_viewport_required"
WALL_VIEW_IDENTITY_REQUIRED = "wall_view_identity_required"
PHYSICAL_WALL_FACE_REQUIRED = "physical_wall_face_required"
TILE_EXTENT_REQUIRED = "tile_extent_required"
VIEWPORT_SCOPE_MISMATCH = "viewport_scope_mismatch"
WALL_VIEW_SCOPE_MISMATCH = "wall_view_scope_mismatch"
WALL_FACE_SCOPE_MISMATCH = "wall_face_scope_mismatch"
TILE_EXTENT_INVALID = "tile_extent_invalid"
WALL_SURFACE_RESOLVED = "canonical_wall_surface_resolved"

_COORD_DIGITS = 6


def _q(value: Any) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("geometry coordinates must be finite")
    rounded = round(number, _COORD_DIGITS)
    return 0.0 if rounded == 0 else rounded


def _as_points(geometry: Sequence[Any]) -> tuple[tuple[float, float], ...]:
    if not geometry:
        raise ValueError("geometry must not be empty")

    first = geometry[0]
    if isinstance(first, (tuple, list)):
        points = tuple((_q(p[0]), _q(p[1])) for p in geometry if len(p) >= 2)
    else:
        flat = tuple(_q(value) for value in geometry)
        if len(flat) % 2:
            raise ValueError("flat geometry must contain x/y pairs")
        points = tuple((flat[i], flat[i + 1]) for i in range(0, len(flat), 2))

    if len(points) < 2:
        raise ValueError("geometry must contain at least two points")
    if len(points) > 2 and points[0] == points[-1]:
        points = points[:-1]
    return points


def _rotations(points: tuple[tuple[float, float], ...]) -> Iterable[tuple[tuple[float, float], ...]]:
    for index in range(len(points)):
        yield points[index:] + points[:index]


def normalize_geometry_for_identity(
    geometry: Sequence[Any],
) -> tuple[tuple[float, float], ...]:
    """Return a deterministic physical-geometry representation.

    Lines are endpoint-order independent. Polygon/ring identity is invariant to
    starting vertex and winding direction. Numerical coordinates are quantized
    only at a sub-drawing tolerance so detector serialization noise cannot mint
    a new physical object.
    """
    points = _as_points(geometry)
    if len(points) == 2:
        return tuple(sorted(points))

    forward = min(_rotations(points))
    reverse_points = tuple(reversed(points))
    reverse = min(_rotations(reverse_points))
    return min(forward, reverse)


def build_physical_opening_identity_fingerprint(
    *,
    document_id: str,
    source_sha256: str,
    page_id: str,
    viewport_id: Optional[str],
    geometry: Sequence[Any],
) -> str:
    payload = {
        "schema_version": IDENTITY_SCHEMA_VERSION,
        "document_id": str(document_id),
        "source_sha256": str(source_sha256),
        "page_id": str(page_id),
        "viewport_id": None if viewport_id is None else str(viewport_id),
        "semantic_class": "opening",
        "geometry": normalize_geometry_for_identity(geometry),
    }
    return stable_contract_id("physical_opening_identity", payload, digest_chars=32)


def build_opening_evidence_fingerprint(
    *,
    physical_identity_fingerprint: str,
    observation_ids: Sequence[str],
    producer_method: str,
    producer_version: str,
    producer_generation: int,
    revision_id: Optional[str] = None,
    snapshot_id: Optional[str] = None,
    lineage_root_ids: Sequence[str] = (),
) -> str:
    payload = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "physical_identity_fingerprint": str(physical_identity_fingerprint),
        "observation_ids": tuple(sorted(str(v) for v in observation_ids if str(v))),
        "lineage_root_ids": tuple(sorted(str(v) for v in lineage_root_ids if str(v))),
        "producer_method": str(producer_method),
        "producer_version": str(producer_version),
        "producer_generation": int(producer_generation),
        "revision_id": None if revision_id is None else str(revision_id),
        "snapshot_id": None if snapshot_id is None else str(snapshot_id),
    }
    return stable_contract_id("opening_evidence", payload, digest_chars=32)


@dataclass(frozen=True)
class OpeningMeasurementResult:
    status: EvidenceResolutionStatus
    value_mm: Optional[float]
    measurement_source: Optional[str]
    reason_codes: tuple[str, ...]


def _positive(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def resolve_opening_measurement(
    *,
    figured_dimension_mm: Any,
    geometry_extent_points: Any,
    scale_status: EvidenceResolutionStatus,
    points_per_mm: Any,
) -> OpeningMeasurementResult:
    """Resolve one opening measurement without coupling figured dimensions to scale.

    An authenticated figured dimension is already a physical measurement and is
    therefore authoritative even when drawing scale is absent or conflicting.
    Geometry-derived measurement requires independently corroborated scale.
    """
    figured = _positive(figured_dimension_mm)
    if figured is not None:
        return OpeningMeasurementResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            value_mm=figured,
            measurement_source=MEASUREMENT_FIGURED_DIMENSION,
            reason_codes=(MEASUREMENT_FIGURED_DIMENSION,),
        )

    extent = _positive(geometry_extent_points)
    scale = _positive(points_per_mm)
    if scale_status is EvidenceResolutionStatus.CONFLICT:
        return OpeningMeasurementResult(
            status=EvidenceResolutionStatus.CONFLICT,
            value_mm=None,
            measurement_source=None,
            reason_codes=(MEASUREMENT_SCALE_CONFLICT,),
        )
    if (
        scale_status is not EvidenceResolutionStatus.CORROBORATED
        or scale is None
        or extent is None
    ):
        return OpeningMeasurementResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            value_mm=None,
            measurement_source=None,
            reason_codes=(MEASUREMENT_SCALE_REQUIRED,),
        )
    return OpeningMeasurementResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        value_mm=extent / scale,
        measurement_source=MEASUREMENT_GEOMETRY_SCALED,
        reason_codes=(MEASUREMENT_GEOMETRY_SCALED,),
    )


def _evidence(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


@dataclass(frozen=True)
class InternalElevationViewport:
    viewport_id: str
    page_id: str
    evidence_ids: tuple[str, ...]
    view_kind: str = "internal_elevation"

    def valid(self) -> bool:
        return (
            self.view_kind == "internal_elevation"
            and bool(str(self.viewport_id).strip())
            and bool(str(self.page_id).strip())
            and bool(_evidence(self.evidence_ids))
        )


@dataclass(frozen=True)
class WallViewIdentity:
    wall_view_id: str
    viewport_id: str
    canonical_wall_id: str
    evidence_ids: tuple[str, ...]

    def valid(self) -> bool:
        return all(
            (
                str(self.wall_view_id).strip(),
                str(self.viewport_id).strip(),
                str(self.canonical_wall_id).strip(),
                _evidence(self.evidence_ids),
            )
        )


@dataclass(frozen=True)
class PhysicalWallFace:
    physical_wall_face_id: str
    wall_view_id: str
    canonical_wall_id: str
    evidence_ids: tuple[str, ...]

    def valid(self) -> bool:
        return all(
            (
                str(self.physical_wall_face_id).strip(),
                str(self.wall_view_id).strip(),
                str(self.canonical_wall_id).strip(),
                _evidence(self.evidence_ids),
            )
        )


@dataclass(frozen=True)
class TileExtent:
    tile_extent_id: str
    viewport_id: str
    wall_view_id: str
    physical_wall_face_id: str
    area_m2: float
    evidence_ids: tuple[str, ...]

    def valid(self) -> bool:
        return all(
            (
                str(self.tile_extent_id).strip(),
                str(self.viewport_id).strip(),
                str(self.wall_view_id).strip(),
                str(self.physical_wall_face_id).strip(),
                _positive(self.area_m2),
                _evidence(self.evidence_ids),
            )
        )


@dataclass(frozen=True)
class CanonicalWallSurface:
    canonical_wall_surface_id: str
    canonical_wall_id: str
    physical_wall_face_id: str
    wall_view_id: str
    viewport_id: str
    tile_extent_id: str
    tile_extent_m2: float
    evidence_ids: tuple[str, ...]
    authority_status: str = "corroborated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_wall_surface_id": self.canonical_wall_surface_id,
            "canonical_wall_id": self.canonical_wall_id,
            "physical_wall_face_id": self.physical_wall_face_id,
            "wall_view_id": self.wall_view_id,
            "viewport_id": self.viewport_id,
            "tile_extent_id": self.tile_extent_id,
            "tile_extent_m2": self.tile_extent_m2,
            "evidence_ids": list(self.evidence_ids),
            "authority_status": self.authority_status,
        }


@dataclass(frozen=True)
class WallSurfaceResolution:
    status: EvidenceResolutionStatus
    canonical_wall_surface: Optional[CanonicalWallSurface]
    quantity_m2: Optional[float]
    reason_codes: tuple[str, ...]


def resolve_internal_elevation_wall_surface(
    *,
    viewport: Optional[InternalElevationViewport],
    wall_view: Optional[WallViewIdentity],
    wall_face: Optional[PhysicalWallFace],
    tile_extent: Optional[TileExtent],
    plan_room_viewport_id: Optional[str] = None,
) -> WallSurfaceResolution:
    """Resolve tile quantity only through an authenticated internal-elevation face chain."""
    if viewport is None or not viewport.valid():
        return WallSurfaceResolution(
            EvidenceResolutionStatus.ABSTAINED, None, None,
            (INTERNAL_ELEVATION_VIEWPORT_REQUIRED,),
        )
    if plan_room_viewport_id and str(plan_room_viewport_id) == viewport.viewport_id:
        return WallSurfaceResolution(
            EvidenceResolutionStatus.CONFLICT, None, None,
            (VIEWPORT_SCOPE_MISMATCH,),
        )
    if wall_view is None or not wall_view.valid():
        return WallSurfaceResolution(
            EvidenceResolutionStatus.ABSTAINED, None, None,
            (WALL_VIEW_IDENTITY_REQUIRED,),
        )
    if wall_view.viewport_id != viewport.viewport_id:
        return WallSurfaceResolution(
            EvidenceResolutionStatus.CONFLICT, None, None,
            (VIEWPORT_SCOPE_MISMATCH,),
        )
    if wall_face is None or not wall_face.valid():
        return WallSurfaceResolution(
            EvidenceResolutionStatus.ABSTAINED, None, None,
            (PHYSICAL_WALL_FACE_REQUIRED,),
        )
    if (
        wall_face.wall_view_id != wall_view.wall_view_id
        or wall_face.canonical_wall_id != wall_view.canonical_wall_id
    ):
        return WallSurfaceResolution(
            EvidenceResolutionStatus.CONFLICT, None, None,
            (WALL_VIEW_SCOPE_MISMATCH,),
        )
    if tile_extent is None or not tile_extent.valid():
        return WallSurfaceResolution(
            EvidenceResolutionStatus.ABSTAINED, None, None,
            (TILE_EXTENT_REQUIRED,),
        )
    if (
        tile_extent.viewport_id != viewport.viewport_id
        or tile_extent.wall_view_id != wall_view.wall_view_id
    ):
        return WallSurfaceResolution(
            EvidenceResolutionStatus.CONFLICT, None, None,
            (VIEWPORT_SCOPE_MISMATCH,),
        )
    if tile_extent.physical_wall_face_id != wall_face.physical_wall_face_id:
        return WallSurfaceResolution(
            EvidenceResolutionStatus.CONFLICT, None, None,
            (WALL_FACE_SCOPE_MISMATCH,),
        )
    area = _positive(tile_extent.area_m2)
    if area is None:
        return WallSurfaceResolution(
            EvidenceResolutionStatus.ABSTAINED, None, None,
            (TILE_EXTENT_INVALID,),
        )

    evidence_ids = _evidence(
        viewport.evidence_ids
        + wall_view.evidence_ids
        + wall_face.evidence_ids
        + tile_extent.evidence_ids
    )
    payload = {
        "canonical_wall_id": wall_view.canonical_wall_id,
        "physical_wall_face_id": wall_face.physical_wall_face_id,
        "wall_view_id": wall_view.wall_view_id,
        "viewport_id": viewport.viewport_id,
        "tile_extent_id": tile_extent.tile_extent_id,
        "tile_extent_m2": round(area, 9),
    }
    surface = CanonicalWallSurface(
        canonical_wall_surface_id=stable_contract_id(
            "canonical_wall_surface", payload, digest_chars=32
        ),
        canonical_wall_id=wall_view.canonical_wall_id,
        physical_wall_face_id=wall_face.physical_wall_face_id,
        wall_view_id=wall_view.wall_view_id,
        viewport_id=viewport.viewport_id,
        tile_extent_id=tile_extent.tile_extent_id,
        tile_extent_m2=area,
        evidence_ids=evidence_ids,
    )
    return WallSurfaceResolution(
        EvidenceResolutionStatus.CORROBORATED,
        surface,
        area,
        (WALL_SURFACE_RESOLVED,),
    )


class AuthenticatedWallFaceTileExtentAuthority:
    """Read-only registry of corroborated elevation wall-face tile extents.

    The quantity layer can resolve an extent only by the exact elevation
    viewport + physical wall-face identity.  Raw caller numbers, room geometry,
    and net-wall area are not accepted by this seam.
    """

    def __init__(
        self,
        surfaces: Mapping[tuple[str, str], CanonicalWallSurface],
    ) -> None:
        self._surfaces = dict(surfaces)

    @classmethod
    def from_resolutions(
        cls,
        resolutions: Sequence[WallSurfaceResolution],
    ) -> "AuthenticatedWallFaceTileExtentAuthority":
        surfaces: dict[tuple[str, str], CanonicalWallSurface] = {}
        for resolution in resolutions:
            if (
                not isinstance(resolution, WallSurfaceResolution)
                or resolution.status is not EvidenceResolutionStatus.CORROBORATED
                or resolution.canonical_wall_surface is None
                or _positive(resolution.quantity_m2) is None
            ):
                continue
            surface = resolution.canonical_wall_surface
            if str(surface.authority_status).strip().lower() != "corroborated":
                continue
            key = (
                str(surface.viewport_id).strip(),
                str(surface.physical_wall_face_id).strip(),
            )
            if not all(key):
                continue
            prior = surfaces.get(key)
            if (
                prior is not None
                and prior.canonical_wall_surface_id
                != surface.canonical_wall_surface_id
            ):
                raise ValueError(
                    "conflicting authenticated tile extents for one physical wall face"
                )
            surfaces[key] = surface
        return cls(surfaces)

    def resolve(
        self,
        *,
        viewport_id: str,
        physical_wall_face_id: str,
    ) -> Optional[CanonicalWallSurface]:
        key = (
            str(viewport_id or "").strip(),
            str(physical_wall_face_id or "").strip(),
        )
        if not all(key):
            return None
        return self._surfaces.get(key)


def authenticated_tile_surface_rows(
    spec: Mapping[str, Any],
    *,
    canonical_wall_id: str,
) -> tuple[Mapping[str, Any], ...]:
    rows = spec.get("authenticated_wall_face_extents")
    if not isinstance(rows, (list, tuple)):
        return ()
    resolved = []
    seen_surfaces: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        surface_id = str(row.get("canonical_wall_surface_id") or "").strip()
        wall_id = str(row.get("canonical_wall_id") or "").strip()
        face_id = str(row.get("physical_wall_face_id") or "").strip()
        extent_id = str(row.get("tile_extent_id") or "").strip()
        viewport_id = str(row.get("viewport_id") or "").strip()
        wall_view_id = str(row.get("wall_view_id") or "").strip()
        authority_status = str(row.get("authority_status") or "").strip().lower()
        area = _positive(row.get("tile_extent_m2"))
        evidence_ids = _evidence(row.get("evidence_ids") or ())
        if (
            authority_status != "corroborated"
            or wall_id != canonical_wall_id
            or not surface_id
            or surface_id in seen_surfaces
            or not face_id
            or not extent_id
            or not viewport_id
            or not wall_view_id
            or area is None
            or not evidence_ids
        ):
            continue
        seen_surfaces.add(surface_id)
        resolved.append(row)
    return tuple(resolved)


__all__ = [
    "AuthenticatedWallFaceTileExtentAuthority",
    "CanonicalWallSurface",
    "InternalElevationViewport",
    "OpeningMeasurementResult",
    "PhysicalWallFace",
    "TileExtent",
    "WallSurfaceResolution",
    "WallViewIdentity",
    "authenticated_tile_surface_rows",
    "build_opening_evidence_fingerprint",
    "build_physical_opening_identity_fingerprint",
    "normalize_geometry_for_identity",
    "resolve_internal_elevation_wall_surface",
    "resolve_opening_measurement",
]
