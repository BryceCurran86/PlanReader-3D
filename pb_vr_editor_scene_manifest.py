"""Source-bound read-only scene contract for the PlanReader browser/XR editor.

This is a renderer input compiled from EXISTING EditableGeometryObject records.
It does not discover physical walls, make canonical identities, approve geometry,
or issue commercial quantities. Source and revision scope must be supplied by
the authenticated workspace loader, never by a browser request.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Mapping, Sequence

from pb_editable_3d_correction_model import EditableGeometryObject
from pb_vr_verified_surface_patches import SourceVerified3DSurface

_SOURCE_SHA = re.compile(r"[0-9a-fA-F]{64}\Z")
_AUTHENTICATED_HEIGHT_ROLES = frozenset({
    "documented_ceiling_height", "figured_dimension", "section_derived",
    "schedule_derived", "user_entered", "user_approved",
})
_APPROVED_STATES = frozenset({"firm", "user_approved"})
_MAX_SCENE_OBJECTS = 20_000


@dataclass(frozen=True)
class EditorWorkspaceScope:
    """Validated, server-owned identity; NOT trusted client-side state."""

    workspace_id: str
    project_id: str
    document_id: str
    revision_id: str
    snapshot_id: str
    source_sha256: str
    model_revision: int

    def __post_init__(self) -> None:
        for key in ("workspace_id", "project_id", "document_id",
                    "revision_id", "snapshot_id"):
            v = getattr(self, key)
            if not isinstance(v, str) or not v.strip():
                raise ValueError(f"{key} is required")
        if not isinstance(self.source_sha256, str) or not _SOURCE_SHA.fullmatch(self.source_sha256):
            raise ValueError("source_sha256 must be an exact original SHA-256")
        if type(self.model_revision) is not int or self.model_revision < 0:
            raise ValueError("model_revision must be a nonnegative integer")

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspaceId": self.workspace_id,
            "projectId": self.project_id,
            "documentId": self.document_id,
            "revisionId": self.revision_id,
            "snapshotId": self.snapshot_id,
            "sourceSha256": self.source_sha256.lower(),
            "modelRevision": self.model_revision,
        }


@dataclass(frozen=True)
class VerifiedSourceWitness:
    """Receipt minted ONLY by the server's original-source/identity resolver.

    Merely recording a sheet name, object status or model_mass record is not
    proof that its wall originated from this exact source document revision.
    """

    document_id: str
    revision_id: str
    source_sha256: str
    source_file_id: str
    source_page: int
    source_sheet: str
    original_geometry_ref: str

    def matches(self, scope: EditorWorkspaceScope, obj: EditableGeometryObject) -> bool:
        return (
            isinstance(self.document_id, str)
            and self.document_id == scope.document_id
            and isinstance(self.revision_id, str)
            and self.revision_id == scope.revision_id
            and isinstance(self.source_sha256, str)
            and bool(_SOURCE_SHA.fullmatch(self.source_sha256))
            and self.source_sha256.lower() == scope.source_sha256.lower()
            and isinstance(self.source_file_id, str)
            and bool(self.source_file_id)
            and self.source_file_id == obj.source_file_id
            and type(self.source_page) is int
            and self.source_page == obj.source_page
            and isinstance(self.source_sheet, str)
            and bool(self.source_sheet)
            and self.source_sheet == obj.source_sheet
            and isinstance(self.original_geometry_ref, str)
            and bool(self.original_geometry_ref)
            and self.original_geometry_ref == obj.original_geometry_ref
        )


def _finite_positive(value: Any) -> float | None:
    if type(value) not in (float, int):
        return None
    f = float(value)
    return f if math.isfinite(f) and f > 0 else None


def _point(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    if any(type(v) not in (float, int) for v in value):
        return None
    x, y = float(value[0]), float(value[1])
    return (x, y) if math.isfinite(x) and math.isfinite(y) else None


def _scene_object(
    obj: EditableGeometryObject,
    canonical_object_id: str | None,
    source_verified: bool,
) -> dict[str, Any]:
    m = obj.coordinates_or_measurements
    issues: list[str] = []
    if not source_verified:
        issues.append("source_ownership_unverified")
    if not obj.source_sheet or obj.source_page is None:
        issues.append("source_trace_missing")
    if not canonical_object_id:
        issues.append("canonical_identity_unresolved")
    if not obj.revision_hash:
        issues.append("object_revision_missing")

    geometry: dict[str, Any] | None = None
    dimensions: dict[str, float] = {}
    if obj.object_type == "wall":
        a = _point(m.get("start_pt"))
        b = _point(m.get("end_pt"))
        length = _finite_positive(m.get("length"))
        if a is None or b is None or length is None:
            issues.append("wall_plan_geometry_missing")
        elif not math.isclose(math.dist(a, b), length, rel_tol=1e-7, abs_tol=1e-6):
            issues.append("wall_length_geometry_conflict")
        else:
            dimensions["lengthM"] = length
            height = _finite_positive(m.get("height"))
            role = m.get("height_authority")
            if height is not None and role in _AUTHENTICATED_HEIGHT_ROLES:
                # A zero-thickness wall face is all current source geometry
                # proves; no invented thickness, box solid, or opening cutout.
                geometry = {"kind": "wallFace", "start": list(a),
                            "end": list(b), "heightM": height}
                dimensions["heightM"] = height
            else:
                geometry = {"kind": "wallLine", "start": list(a), "end": list(b)}
                issues.append("wall_height_unverified")
    else:
        # Non-wall editor objects are inspector-only until an authenticated
        # planar/solid geometry adapter supplies actual source-owned vertices.
        issues.append("render_geometry_not_authenticated")

    status = str(obj.authority_status or "provisional").lower()
    verified = bool(geometry and not issues and status in _APPROVED_STATES)
    return {
        "objectId": obj.object_id,
        "canonicalObjectId": canonical_object_id,
        "objectType": obj.object_type,
        "levelId": obj.level_id,
        "objectRevision": obj.revision_hash,
        "authority": status,
        "renderState": "verified" if verified else "review",
        "geometry": geometry,
        "dimensions": dimensions,
        "source": {
            "sourceFileId": obj.source_file_id,
            "page": obj.source_page,
            "sheet": obj.source_sheet,
            "sourceRegion": obj.source_region,
            "originalGeometryRef": obj.original_geometry_ref,
            "currentGeometryRef": obj.geometry_ref,
        },
        "quantityLinks": sorted(set(str(q) for q in obj.dependent_quantity_ids if q)),
        "unresolvedIssues": issues,
        "canEdit": False,  # enabled only by a separate authenticated command API
    }


def compile_editor_scene(
    scope: EditorWorkspaceScope,
    objects: Sequence[EditableGeometryObject],
    *,
    canonical_object_ids: Mapping[str, str] | None = None,
    source_witnesses: Mapping[str, VerifiedSourceWitness] | None = None,
    source_surfaces: Sequence[SourceVerified3DSurface] = (),
) -> dict[str, Any]:
    """Compile read-only display geometry; never turn missing source into FIRM.

    All objects must belong to a single authenticated workspace. Canonical IDs
    are accepted only from the server-side canonical resolver, not from a name,
    proximity, or browser-supplied guess. An unresolved record stays visible in
    the inspector but has no invented render mesh.
    """
    if len(objects) > _MAX_SCENE_OBJECTS:
        raise ValueError("editor_scene_object_safety_cap_exceeded")
    canonical_object_ids = canonical_object_ids or {}
    # No source witness means REVIEW, not a trust shortcut. The repository
    # loader must bind a real original document SHA + native geometry ref.
    source_witnesses = source_witnesses or {}
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for obj in objects:
        if not isinstance(obj, EditableGeometryObject) or not obj.object_id:
            raise ValueError("editor_scene_invalid_object")
        if obj.object_id in seen:
            raise ValueError("editor_scene_duplicate_object_id")
        seen.add(obj.object_id)
        cid = canonical_object_ids.get(obj.object_id)
        if cid is not None and (not isinstance(cid, str) or not cid.strip()):
            raise ValueError("editor_scene_invalid_canonical_identity")
        witness = source_witnesses.get(obj.object_id)
        source_verified = (
            isinstance(witness, VerifiedSourceWitness)
            and witness.matches(scope, obj)
        )
        rows.append(_scene_object(obj, cid, source_verified))
    rows.sort(key=lambda x: x["objectId"])
    # An independent registered physical-surface producer may provide real
    # triangulated floors/ceilings/roofs. Never extrude rooms from approximate
    # polylines or inherit source authority from a merely approved model.
    source_surfaces_out: list[dict[str, Any]] = []
    if len(source_surfaces) > _MAX_SCENE_OBJECTS:
        raise ValueError("source_surface_count_cap_exceeded")
    by_object = {o.object_id: o for o in objects}
    used_surface_ids: set[str] = set()
    triangle_count = 0
    for surface in source_surfaces:
        if type(surface) is not SourceVerified3DSurface:
            raise ValueError("untrusted_surface_producer_record")
        obj = by_object.get(surface.object_id)
        witness = source_witnesses.get(surface.object_id)
        cid = canonical_object_ids.get(surface.object_id)
        role_allowed = (
            surface.surface_kind in ("floor", "ceiling")
            and obj is not None and obj.object_type in ("room", "surface")
        ) or (
            surface.surface_kind == "roof" and obj is not None
            and obj.object_type in ("roof", "surface")
        )
        if (not role_allowed or obj is None or
            not isinstance(witness, VerifiedSourceWitness) or
            not surface.matches_original(scope, obj, witness, cid) or
            obj.authority_status not in _APPROVED_STATES):
            raise ValueError("source_surface_object_or_native_witness_mismatch")
        if surface.surface_id in used_surface_ids:
            raise ValueError("duplicate_source_surface_id")
        used_surface_ids.add(surface.surface_id)
        triangle_count += len(surface.vertices) // 3
        if triangle_count > _MAX_SCENE_OBJECTS:
            raise ValueError("source_surface_primitive_cap_exceeded")
        source_surfaces_out.append(surface.to_scene_dict())
    source_surfaces_out.sort(key=lambda s: s["surfaceId"])
    result = {
        "schemaVersion": "1.0.0",
        "scope": scope.to_dict(),
        "coordinateSystem": {
            "unit": "metres",
            "sourceToModelTransform": None,
            "renderOrigin": [0, 0, 0],
        },
        "readOnly": True,
        "objects": rows,
        "commercialQuantityPublicationAllowed": False,
    }
    if source_surfaces_out:
        result["sourceSurfaces"] = source_surfaces_out
    return result
