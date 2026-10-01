"""Canonical wall-finish surfaces from source-owned face bindings.

This projection preserves a proven relationship:

    canonical physical wall -> exact physical face -> finish/trade semantic

It does not calculate a finish quantity, infer left/right face geometry, expand a
local callout to an unproven wider scope, or publish commercial authority.

Repeated source bindings that prove the same physical face/trade/material enrich
one canonical surface. Conflicting materials for the same physical face/trade
fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_wall_finish_face_binding_authority import WallFinishFaceBindingRecord


LIVE_CANONICAL_WALL_FINISH_SURFACE_SCHEMA_VERSION = "1.0.0"
LIVE_CANONICAL_WALL_FINISH_SURFACE_RESOLVED = (
    "live_canonical_wall_finish_surface_resolved"
)
LIVE_CANONICAL_WALL_FINISH_SURFACE_PARTIAL = (
    "live_canonical_wall_finish_surface_partial"
)
LIVE_CANONICAL_WALL_FINISH_SURFACE_UNAVAILABLE = (
    "live_canonical_wall_finish_surface_unavailable"
)
LIVE_CANONICAL_WALL_FINISH_SURFACE_HOST_UNAVAILABLE = (
    "live_canonical_wall_finish_surface_host_wall_unavailable"
)
LIVE_CANONICAL_WALL_FINISH_SURFACE_LINEAGE_MISMATCH = (
    "live_canonical_wall_finish_surface_lineage_mismatch"
)
LIVE_CANONICAL_WALL_FINISH_SURFACE_CONFLICT = (
    "live_canonical_wall_finish_surface_conflict"
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _enum_value(value: object) -> str:
    return _clean(getattr(value, "value", value))


def _dedupe(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_clean(value) for value in values if _clean(value)))


def _positive(value: object) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number <= 0.0:
        return None
    return number


@dataclass(frozen=True)
class LiveCanonicalWallFinishSurfaceObject:
    canonical_surface_id: str
    canonical_wall_id: str
    physical_wall_id: str
    physical_face_id: str
    physical_face_role: str
    trade_scope_id: str
    finish_material: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_ids: tuple[str, ...]
    decision_scope_ids: tuple[str, ...]
    finish_binding_ids: tuple[str, ...]
    source_face_segment_ids: tuple[str, ...]
    wall_role_record_ids: tuple[str, ...]
    source_evidence_ids: tuple[str, ...]
    level_ids: tuple[str, ...]
    host_net_area_m2: Optional[float]
    host_quantity_complete: bool
    finish_scope_complete: bool = False
    geometry_complete: bool = False
    metric_area_complete: bool = False
    surface_area_m2: Optional[float] = None
    commercial_quantity_authority: bool = False
    schema_version: str = LIVE_CANONICAL_WALL_FINISH_SURFACE_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "canonical_surface_id": self.canonical_surface_id,
            "canonical_wall_id": self.canonical_wall_id,
            "physical_wall_id": self.physical_wall_id,
            "physical_face_id": self.physical_face_id,
            "physical_face_role": self.physical_face_role,
            "trade_scope_id": self.trade_scope_id,
            "finish_material": self.finish_material,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "snapshot_id": self.snapshot_id,
            "page_id": self.page_id,
            "viewport_ids": list(self.viewport_ids),
            "decision_scope_ids": list(self.decision_scope_ids),
            "finish_binding_ids": list(self.finish_binding_ids),
            "source_face_segment_ids": list(self.source_face_segment_ids),
            "wall_role_record_ids": list(self.wall_role_record_ids),
            "source_evidence_ids": list(self.source_evidence_ids),
            "level_ids": list(self.level_ids),
            "host_net_area_m2": self.host_net_area_m2,
            "host_quantity_complete": self.host_quantity_complete,
            "finish_scope_complete": self.finish_scope_complete,
            "geometry_complete": self.geometry_complete,
            "metric_area_complete": self.metric_area_complete,
            "surface_area_m2": self.surface_area_m2,
            "commercial_quantity_authority": self.commercial_quantity_authority,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class LiveCanonicalWallFinishSurfaceProjection:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    surfaces: tuple[LiveCanonicalWallFinishSurfaceObject, ...]
    unresolved_binding_ids: tuple[str, ...]
    schema_version: str = LIVE_CANONICAL_WALL_FINISH_SURFACE_SCHEMA_VERSION


def _resolved_wall_map(
    canonical_walls: Sequence[Mapping[str, object]],
) -> tuple[dict[str, dict], bool]:
    by_physical_id: dict[str, dict] = {}
    for raw in canonical_walls:
        if not isinstance(raw, Mapping):
            continue
        wall = dict(raw)
        canonical_wall_id = _clean(wall.get("canonical_wall_id"))
        physical_wall_id = _clean(wall.get("physical_wall_id"))
        if (
            not canonical_wall_id
            or not physical_wall_id
            or wall.get("physical_identity_resolved") is not True
        ):
            continue
        prior = by_physical_id.get(physical_wall_id)
        if prior is not None and _clean(prior.get("canonical_wall_id")) != canonical_wall_id:
            return {}, False
        by_physical_id[physical_wall_id] = wall
    return by_physical_id, True


def _lineage_matches(
    wall: Mapping[str, object],
    binding: WallFinishFaceBindingRecord,
) -> bool:
    return (
        _clean(wall.get("document_id")) == _clean(binding.document_id)
        and _clean(wall.get("revision_id")) == _clean(binding.revision_id)
        and _clean(wall.get("source_sha256")) == _clean(binding.source_sha256)
        and _clean(wall.get("snapshot_id")) == _clean(binding.snapshot_id)
        and _clean(wall.get("page_id")) == _clean(binding.page_id)
    )


def project_wall_finish_bindings(
    *,
    canonical_walls: Sequence[Mapping[str, object]],
    bindings: Sequence[WallFinishFaceBindingRecord],
) -> LiveCanonicalWallFinishSurfaceProjection:
    """Project exact producer-owned finish/face bindings onto canonical walls."""

    if not bindings:
        return LiveCanonicalWallFinishSurfaceProjection(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(LIVE_CANONICAL_WALL_FINISH_SURFACE_UNAVAILABLE,),
            surfaces=(),
            unresolved_binding_ids=(),
        )

    for binding in bindings:
        if type(binding) is not WallFinishFaceBindingRecord:
            raise TypeError(
                "bindings must contain producer-owned WallFinishFaceBindingRecord values"
            )

    walls_by_physical_id, wall_map_valid = _resolved_wall_map(canonical_walls)
    if not wall_map_valid:
        return LiveCanonicalWallFinishSurfaceProjection(
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(LIVE_CANONICAL_WALL_FINISH_SURFACE_CONFLICT,),
            surfaces=(),
            unresolved_binding_ids=tuple(
                sorted(_clean(binding.binding_id) for binding in bindings)
            ),
        )

    groups: dict[tuple[str, str, str], list[WallFinishFaceBindingRecord]] = {}
    for binding in bindings:
        key = (
            _clean(binding.physical_wall_id),
            _clean(binding.physical_face_id),
            _clean(binding.trade_scope_id),
        )
        groups.setdefault(key, []).append(binding)

    output: list[LiveCanonicalWallFinishSurfaceObject] = []
    unresolved: list[str] = []
    host_missing = False
    lineage_mismatch = False

    for (physical_wall_id, physical_face_id, trade_scope_id), group in sorted(
        groups.items()
    ):
        materials = {_clean(binding.finish_material) for binding in group}
        roles = {_enum_value(binding.physical_face_role) for binding in group}
        if (
            not physical_wall_id
            or not physical_face_id
            or not trade_scope_id
            or "" in materials
            or "" in roles
            or len(materials) != 1
            or len(roles) != 1
        ):
            return LiveCanonicalWallFinishSurfaceProjection(
                status=EvidenceResolutionStatus.CONFLICT,
                reason_codes=(LIVE_CANONICAL_WALL_FINISH_SURFACE_CONFLICT,),
                surfaces=(),
                unresolved_binding_ids=tuple(
                    sorted(_clean(binding.binding_id) for binding in bindings)
                ),
            )

        wall = walls_by_physical_id.get(physical_wall_id)
        if wall is None:
            host_missing = True
            unresolved.extend(binding.binding_id for binding in group)
            continue
        if any(not _lineage_matches(wall, binding) for binding in group):
            lineage_mismatch = True
            unresolved.extend(binding.binding_id for binding in group)
            continue

        finish_material = next(iter(materials))
        physical_face_role = next(iter(roles))
        canonical_wall_id = _clean(wall.get("canonical_wall_id"))
        canonical_surface_id = stable_contract_id(
            "live_canonical_wall_finish_surface",
            {
                "source_sha256": _clean(wall.get("source_sha256")),
                "canonical_wall_id": canonical_wall_id,
                "physical_face_id": physical_face_id,
                "trade_scope_id": trade_scope_id,
                "finish_material": finish_material,
            },
            digest_chars=32,
        )
        host_quantity_complete = wall.get("quantity_complete") is True
        host_net_area_m2 = (
            _positive(wall.get("net_area_m2"))
            if host_quantity_complete
            else None
        )
        source_evidence_ids = _dedupe(
            [
                *(wall.get("evidence_ids") or ()),
                *(binding.binding_id for binding in group),
                *(
                    evidence_id
                    for binding in group
                    for evidence_id in binding.source_evidence_ids
                ),
            ]
        )
        output.append(
            LiveCanonicalWallFinishSurfaceObject(
                canonical_surface_id=canonical_surface_id,
                canonical_wall_id=canonical_wall_id,
                physical_wall_id=physical_wall_id,
                physical_face_id=physical_face_id,
                physical_face_role=physical_face_role,
                trade_scope_id=trade_scope_id,
                finish_material=finish_material,
                document_id=_clean(group[0].document_id),
                revision_id=_clean(group[0].revision_id),
                source_sha256=_clean(group[0].source_sha256),
                snapshot_id=_clean(group[0].snapshot_id),
                page_id=_clean(group[0].page_id),
                viewport_ids=_dedupe(binding.viewport_id for binding in group),
                decision_scope_ids=_dedupe(
                    binding.decision_scope_id for binding in group
                ),
                finish_binding_ids=_dedupe(
                    binding.binding_id for binding in group
                ),
                source_face_segment_ids=_dedupe(
                    segment_id
                    for binding in group
                    for segment_id in binding.source_face_segment_ids
                ),
                wall_role_record_ids=_dedupe(
                    binding.wall_role_record_id for binding in group
                ),
                source_evidence_ids=source_evidence_ids,
                level_ids=_dedupe(wall.get("level_ids") or ()),
                host_net_area_m2=host_net_area_m2,
                host_quantity_complete=host_quantity_complete,
            )
        )

    output.sort(
        key=lambda surface: (
            surface.canonical_wall_id,
            surface.physical_face_id,
            surface.trade_scope_id,
            surface.finish_material,
        )
    )

    unresolved_ids = tuple(sorted(_dedupe(unresolved)))
    if output and not unresolved_ids:
        return LiveCanonicalWallFinishSurfaceProjection(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(LIVE_CANONICAL_WALL_FINISH_SURFACE_RESOLVED,),
            surfaces=tuple(output),
            unresolved_binding_ids=(),
        )
    if output:
        return LiveCanonicalWallFinishSurfaceProjection(
            status=EvidenceResolutionStatus.CANDIDATE,
            reason_codes=(
                LIVE_CANONICAL_WALL_FINISH_SURFACE_PARTIAL,
                LIVE_CANONICAL_WALL_FINISH_SURFACE_HOST_UNAVAILABLE,
            ),
            surfaces=tuple(output),
            unresolved_binding_ids=unresolved_ids,
        )

    reason = (
        LIVE_CANONICAL_WALL_FINISH_SURFACE_LINEAGE_MISMATCH
        if lineage_mismatch
        else LIVE_CANONICAL_WALL_FINISH_SURFACE_HOST_UNAVAILABLE
    )
    return LiveCanonicalWallFinishSurfaceProjection(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=(reason,),
        surfaces=(),
        unresolved_binding_ids=unresolved_ids,
    )


__all__ = [
    "LIVE_CANONICAL_WALL_FINISH_SURFACE_CONFLICT",
    "LIVE_CANONICAL_WALL_FINISH_SURFACE_HOST_UNAVAILABLE",
    "LIVE_CANONICAL_WALL_FINISH_SURFACE_LINEAGE_MISMATCH",
    "LIVE_CANONICAL_WALL_FINISH_SURFACE_PARTIAL",
    "LIVE_CANONICAL_WALL_FINISH_SURFACE_RESOLVED",
    "LIVE_CANONICAL_WALL_FINISH_SURFACE_SCHEMA_VERSION",
    "LIVE_CANONICAL_WALL_FINISH_SURFACE_UNAVAILABLE",
    "LiveCanonicalWallFinishSurfaceObject",
    "LiveCanonicalWallFinishSurfaceProjection",
    "project_wall_finish_bindings",
]
