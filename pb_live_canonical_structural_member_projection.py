"""Canonical structural-member identity projection.

Preserves source-authenticated PhysicalStructuralMember identities without
inventing member geometry or semantic subtype. Geometry remains explicitly
incomplete until a producer-owned position/section geometry authority exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_member_authority import StructuralMemberResolution


LIVE_CANONICAL_STRUCTURAL_MEMBER_SCHEMA_VERSION = "1.1.0"
LIVE_CANONICAL_STRUCTURAL_MEMBER_RESOLVED = (
    "live_canonical_structural_members_resolved"
)
LIVE_CANONICAL_STRUCTURAL_MEMBER_UNAVAILABLE = (
    "live_canonical_structural_members_unavailable"
)


@dataclass(frozen=True)
class LiveCanonicalStructuralMemberObject:
    canonical_structural_member_id: str
    physical_member_id: str
    member_kind: str
    observation_ids: tuple[str, ...]
    source_evidence_ids: tuple[str, ...]
    source_primitive_ids: tuple[str, ...]
    page_ids: tuple[str, ...]
    view_ids: tuple[str, ...]
    definition_ids: tuple[str, ...]
    section_specs: tuple[str, ...]
    provenance: Mapping[str, object]
    source_primitive_bboxes: tuple[
        tuple[str, tuple[float, float, float, float]], ...
    ] = ()
    plan_bbox_source_pts: Optional[tuple[float, float, float, float]] = None
    plan_geometry_page_id: Optional[str] = None
    plan_geometry_complete: bool = False
    geometry_coordinate_space: Optional[str] = None
    geometry_complete: bool = False
    commercial_quantity_authority: bool = False
    schema_version: str = LIVE_CANONICAL_STRUCTURAL_MEMBER_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "canonical_structural_member_id": self.canonical_structural_member_id,
            "physical_member_id": self.physical_member_id,
            "member_kind": self.member_kind,
            "observation_ids": list(self.observation_ids),
            "source_evidence_ids": list(self.source_evidence_ids),
            "source_primitive_ids": list(self.source_primitive_ids),
            "page_ids": list(self.page_ids),
            "view_ids": list(self.view_ids),
            "definition_ids": list(self.definition_ids),
            "section_specs": list(self.section_specs),
            "provenance": dict(self.provenance),
            "source_primitive_bboxes": [
                [primitive_id, list(bbox)]
                for primitive_id, bbox in self.source_primitive_bboxes
            ],
            "plan_bbox_source_pts": (
                list(self.plan_bbox_source_pts)
                if self.plan_bbox_source_pts is not None
                else None
            ),
            "plan_geometry_page_id": self.plan_geometry_page_id,
            "plan_geometry_complete": self.plan_geometry_complete,
            "geometry_coordinate_space": self.geometry_coordinate_space,
            "geometry_complete": self.geometry_complete,
            "commercial_quantity_authority": self.commercial_quantity_authority,
            "schema_version": self.schema_version,
        }

@dataclass(frozen=True)
class LiveCanonicalStructuralMemberProjection:
    objects: tuple[LiveCanonicalStructuralMemberObject, ...]
    reason_codes: tuple[str, ...]


def _plan_geometry(
    *,
    source_primitive_ids: tuple[str, ...],
    source_primitive_bboxes: tuple[
        tuple[str, tuple[float, float, float, float]], ...
    ],
    page_ids: tuple[str, ...],
) -> tuple[
    tuple[tuple[str, tuple[float, float, float, float]], ...],
    Optional[tuple[float, float, float, float]],
    Optional[str],
    bool,
]:
    geometry_by_id = {
        str(primitive_id): tuple(float(value) for value in bbox)
        for primitive_id, bbox in source_primitive_bboxes
    }
    primitive_ids = tuple(
        dict.fromkeys(
            str(value)
            for value in source_primitive_ids
            if str(value)
        )
    )
    if (
        not primitive_ids
        or len(page_ids) != 1
        or set(geometry_by_id) != set(primitive_ids)
    ):
        return tuple(sorted(geometry_by_id.items())), None, None, False

    boxes = tuple(geometry_by_id[primitive_id] for primitive_id in primitive_ids)
    union_bbox = (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )
    return (
        tuple(sorted(geometry_by_id.items())),
        union_bbox,
        str(page_ids[0]),
        True,
    )


def project_structural_member_resolution(
    resolution: StructuralMemberResolution,
) -> LiveCanonicalStructuralMemberProjection:
    """Preserve one corroborated structural-member universe as canonical identities."""

    if type(resolution) is not StructuralMemberResolution:
        raise TypeError("resolution must be StructuralMemberResolution")
    if (
        resolution.status is not EvidenceResolutionStatus.CORROBORATED
        or resolution.unresolved_observation_ids
        or not resolution.members
    ):
        return LiveCanonicalStructuralMemberProjection(
            objects=(),
            reason_codes=(LIVE_CANONICAL_STRUCTURAL_MEMBER_UNAVAILABLE,),
        )

    definitions_by_id = {
        definition.definition_id: definition
        for definition in resolution.definitions
    }
    output: list[LiveCanonicalStructuralMemberObject] = []
    seen: set[str] = set()

    for member in resolution.members:
        physical_id = str(member.physical_member_id or "").strip()
        if not physical_id or physical_id in seen:
            return LiveCanonicalStructuralMemberProjection(
                objects=(),
                reason_codes=(LIVE_CANONICAL_STRUCTURAL_MEMBER_UNAVAILABLE,),
            )
        seen.add(physical_id)
        section_specs = tuple(
            sorted(
                {
                    str(definitions_by_id[definition_id].section_spec)
                    for definition_id in member.definition_ids
                    if definition_id in definitions_by_id
                    and str(definitions_by_id[definition_id].section_spec).strip()
                }
            )
        )
        (
            source_primitive_bboxes,
            plan_bbox_source_pts,
            plan_geometry_page_id,
            plan_geometry_complete,
        ) = _plan_geometry(
            source_primitive_ids=tuple(member.source_primitive_ids),
            source_primitive_bboxes=tuple(
                getattr(member, "source_primitive_bboxes", ()) or ()
            ),
            page_ids=tuple(member.page_ids),
        )
        provenance = {
            "selector_document_id": resolution.selector.document_id,
            "selector_revision_id": resolution.selector.revision_id,
            "selector_source_sha256": resolution.selector.source_sha256,
            "selector_snapshot_id": resolution.selector.snapshot_id,
            "selector_decision_scope_id": resolution.selector.decision_scope_id,
            "source_evidence_ids": list(member.source_evidence_ids),
        }
        output.append(
            LiveCanonicalStructuralMemberObject(
                canonical_structural_member_id=physical_id,
                physical_member_id=physical_id,
                member_kind=str(member.member_kind),
                observation_ids=tuple(member.observation_ids),
                source_evidence_ids=tuple(member.source_evidence_ids),
                source_primitive_ids=tuple(member.source_primitive_ids),
                page_ids=tuple(member.page_ids),
                view_ids=tuple(member.view_ids),
                definition_ids=tuple(member.definition_ids),
                section_specs=section_specs,
                provenance=provenance,
                source_primitive_bboxes=source_primitive_bboxes,
                plan_bbox_source_pts=plan_bbox_source_pts,
                plan_geometry_page_id=plan_geometry_page_id,
                plan_geometry_complete=plan_geometry_complete,
                geometry_coordinate_space=(
                    "source_page_points"
                    if plan_geometry_complete
                    else None
                ),
                geometry_complete=False,
            )
        )

    output.sort(key=lambda item: item.canonical_structural_member_id)
    return LiveCanonicalStructuralMemberProjection(
        objects=tuple(output),
        reason_codes=(LIVE_CANONICAL_STRUCTURAL_MEMBER_RESOLVED,),
    )


__all__ = [
    "LIVE_CANONICAL_STRUCTURAL_MEMBER_RESOLVED",
    "LIVE_CANONICAL_STRUCTURAL_MEMBER_SCHEMA_VERSION",
    "LIVE_CANONICAL_STRUCTURAL_MEMBER_UNAVAILABLE",
    "LiveCanonicalStructuralMemberObject",
    "LiveCanonicalStructuralMemberProjection",
    "project_structural_member_resolution",
]
