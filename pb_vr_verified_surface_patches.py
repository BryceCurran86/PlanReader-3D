"""Source-authenticated existing 3D floor, ceiling and roof surface triangles.

An independent *server producer* supplies this data. These records never
derive a floor, roof or opening from walls or a guessed 2.7m ceiling. Each
triangle is backed by the exact original PDF SHA, native source, canonical
object and source geometry/triangulation receipts. No takeoff is issued.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pb_vr_editor_scene_manifest import (
        EditorWorkspaceScope, VerifiedSourceWitness,
    )
    from pb_editable_3d_correction_model import EditableGeometryObject

_ALLOWED_KINDS = frozenset({"floor", "ceiling", "roof"})
_MAX_TRIANGLES_PER_SURFACE = 2000
_MAX_COORD_M = 10_000.0
_MAX_AREA_M2 = 100_000.0


def _vec(point: object) -> tuple[float, float, float]:
    if (type(point) is not tuple or len(point) != 3 or
        any(type(x) not in (float, int) or not math.isfinite(x) or
            abs(float(x)) > _MAX_COORD_M for x in point)):
        raise ValueError("source_surface_coordinate_unverified")
    return tuple(float(x) for x in point)


def _triangle_area(a, b, c) -> float:
    u = tuple(b[i] - a[i] for i in range(3))
    v = tuple(c[i] - a[i] for i in range(3))
    cross = (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )
    return 0.5 * math.sqrt(sum(n * n for n in cross))


@dataclass(frozen=True)
class SourceVerified3DSurface:
    surface_id: str
    object_id: str
    object_revision: str
    canonical_object_id: str
    surface_kind: str  # floor, ceiling or roof only; never inferred opening
    document_id: str
    revision_id: str
    source_sha256: str
    source_file_id: str
    source_page: int
    source_sheet: str
    original_geometry_ref: str
    snapshot_id: str
    vertices: tuple[tuple[float, float, float], ...]
    source_area_m2: float
    geometry_evidence_id: str
    triangulation_evidence_id: str
    producer_accepted: bool

    def __post_init__(self) -> None:
        for key in ("surface_id", "object_id", "object_revision",
                    "canonical_object_id", "document_id", "revision_id",
                    "source_sha256", "source_file_id", "source_sheet",
                    "original_geometry_ref", "snapshot_id",
                    "geometry_evidence_id", "triangulation_evidence_id"):
            v = getattr(self, key)
            if type(v) is not str or not v.strip() or len(v) > 256:
                raise ValueError("surface_original_source_identity_missing:" + key)
        if (self.geometry_evidence_id == self.triangulation_evidence_id or
            self.surface_kind not in _ALLOWED_KINDS or
            self.producer_accepted is not True):
            raise ValueError("unproven_source_surface_or_geometry")
        if (type(self.source_page) is not int or self.source_page < 0 or
            type(self.vertices) is not tuple or
            len(self.vertices) < 3 or
            len(self.vertices) % 3 != 0 or
            len(self.vertices) > _MAX_TRIANGLES_PER_SURFACE * 3):
            raise ValueError("invalid_source_surface_triangle_set")
        vertices = tuple(_vec(point) for point in self.vertices)
        if self.surface_kind in ("floor", "ceiling"):
            ys = [point[1] for point in vertices]
            if max(ys) - min(ys) > 0.001:
                raise ValueError("floor_or_ceiling_not_planar")
        area = sum(_triangle_area(*vertices[i:i + 3])
                   for i in range(0, len(vertices), 3))
        if not math.isfinite(area) or area <= 1e-6 or area > _MAX_AREA_M2:
            raise ValueError("invalid_or_degenerate_surface_mesh")
        if (type(self.source_area_m2) not in (float, int) or
            not math.isfinite(self.source_area_m2) or
            self.source_area_m2 <= 0 or
            not math.isclose(area, self.source_area_m2,
                             rel_tol=0.001, abs_tol=0.005)):
            raise ValueError("source_surface_area_not_corroborated")

    def matches_original(self, scope: EditorWorkspaceScope,
                         obj: EditableGeometryObject,
                         witness: VerifiedSourceWitness,
                         canonical_id: str | None) -> bool:
        return bool(
            self.producer_accepted is True
            and witness.matches(scope, obj)
            and self.document_id == scope.document_id
            and self.revision_id == scope.revision_id
            and self.snapshot_id == scope.snapshot_id
            and self.source_sha256.lower() == scope.source_sha256.lower()
            and self.source_file_id == obj.source_file_id
            and self.source_page == obj.source_page
            and self.source_sheet == obj.source_sheet
            and self.original_geometry_ref == obj.original_geometry_ref
            and self.object_id == obj.object_id
            and self.object_revision == obj.revision_hash
            and self.canonical_object_id == canonical_id
        )

    def to_scene_dict(self) -> dict:
        return {
            "surfaceId": self.surface_id,
            "objectId": self.object_id,
            "objectRevision": self.object_revision,
            "canonicalObjectId": self.canonical_object_id,
            "kind": self.surface_kind,
            "vertices": [list(point) for point in self.vertices],
            "areaM2": self.source_area_m2,
            "geometryEvidenceId": self.geometry_evidence_id,
            "triangulationEvidenceId": self.triangulation_evidence_id,
            "originalGeometryRef": self.original_geometry_ref,
            "sourceSha256": self.source_sha256.lower(),
            "snapshotId": self.snapshot_id,
            "renderState": "verified",
            "commercialAuthority": False,
        }
