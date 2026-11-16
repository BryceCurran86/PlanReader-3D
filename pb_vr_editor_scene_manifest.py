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

_SOURCE_SHA = re.compile(r"[0-9a-fA-F]{64}\Z")
_AUTHENTICATED_HEIGHT_ROLES = frozenset({
    "documented_ceiling_height", "figured_dimension", "section_derived",
    "schedule_derived", "user_entered", "user_approved",
})
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


def _scene_object(obj: EditableGeometryObject,
                  canonical_object_id: str | None) -> dict[str, Any]:
    m = obj.coordinates_or_measurements
    issues: list[str] = []
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
    # EditableGeometryObject holds sheet/page and a geometry pointer, but NOT
    # an authenticated original source-primitive receipt tied to this SHA and
    # canonical ID. A previously approved *model correction* is insufficient
    # to mark an XR wall as independently source verified.
    issues.append("original_source_observation_receipt_unavailable")
    return {
        "objectId": obj.object_id,
        "canonicalObjectId": canonical_object_id,
        "objectType": obj.object_type,
        "levelId": obj.level_id,
        "objectRevision": obj.revision_hash,
        "authority": status,
        "renderState": "review",
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
        rows.append(_scene_object(obj, cid))
    rows.sort(key=lambda x: x["objectId"])
    return {
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
