"""Live canonical wall projection before commercial wall quantity publication.

Preserves producer-owned wall identity and plan geometry even when height, role,
gross area, opening-void geometry, or net-wall quantity abstains. Proven whole-
wall host frames and physical-equivalence representatives are reused as resolved
physical wall identities. Still-ambiguous wall candidates remain explicit
candidate canonical objects; they are never silently merged or discarded.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from pb_live_external_physical_net_wall_publication import (
    CanonicalWallPlanMember,
    LiveCanonicalWallObject,
)
from pb_live_wall_opening_authority_composition import (
    LiveWallOpeningAuthorityComposition,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_visibility_authority import SourceVisibilityProducer

LIVE_CANONICAL_WALL_SCHEMA_VERSION = "1.1.0"
LIVE_CANONICAL_WALL_RESOLVED = "live_canonical_wall_composition_resolved"
LIVE_CANONICAL_WALL_PARTIAL = "live_canonical_wall_composition_partial"
LIVE_CANONICAL_WALL_UNAVAILABLE = "live_canonical_wall_composition_unavailable"
LIVE_CANONICAL_WALL_EQUIVALENCE_UNAVAILABLE = (
    "live_canonical_wall_equivalence_unavailable"
)
LIVE_CANONICAL_WALL_IDENTITY_CANDIDATE = (
    "live_canonical_wall_physical_identity_unresolved"
)
LIVE_CANONICAL_WALL_FRAME_CONFLICT = "live_canonical_wall_frame_conflict"


@dataclass(frozen=True)
class LiveCanonicalWallComposition:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    walls: tuple[LiveCanonicalWallObject, ...]
    source_pages: tuple[int, ...]
    unresolved_wall_candidate_ids: tuple[str, ...]
    candidate_to_canonical_wall_id: Mapping[str, str]
    schema_version: str = LIVE_CANONICAL_WALL_SCHEMA_VERSION


def _clean(value: object) -> str:
    return str(value or "").strip()


def _enum_value(value: object) -> str:
    return _clean(getattr(value, "value", value))


def _dedupe(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(_clean(value) for value in values if _clean(value)))


def _plan_member(record: object) -> CanonicalWallPlanMember:
    wall = record.wall_candidate
    identity = record.physical_identity
    end_nodes = tuple(_clean(value) for value in wall.end_node_ids)
    if len(end_nodes) != 2:
        end_nodes = ("", "")
    return CanonicalWallPlanMember(
        wall_candidate_id=_clean(record.wall_candidate_id),
        physical_identity_id=(
            _clean(identity.physical_identity_id)
            if identity.physical_identity_id
            else None
        ),
        viewport_id=_clean(wall.viewport_id),
        centerline_pts=tuple(
            (float(point[0]), float(point[1])) for point in wall.centerline_pts
        ),
        curve_control_pts=tuple(
            (float(point[0]), float(point[1]))
            for point in (wall.curve_control_pts or ())
        ),
        is_curved=bool(wall.is_curved),
        thickness_m=(
            float(wall.thickness_m) if wall.thickness_m is not None else None
        ),
        length_m=float(wall.length_m) if wall.length_m is not None else None,
        level_id=_clean(wall.level_id) or None,
        end_node_ids=(end_nodes[0], end_nodes[1]),
        junction_types=tuple(_enum_value(value) for value in wall.junction_types),
        source_primitive_ids=tuple(identity.source_primitive_ids),
        supporting_evidence_ids=tuple(wall.supporting_evidence_ids),
    )


def _host_frame_maps(
    composition: LiveWallOpeningAuthorityComposition,
) -> tuple[
    dict[str, str],
    dict[str, set[str]],
    dict[str, set[str]],
    dict[str, set[str]],
    set[str],
]:
    member_to_frame: dict[str, str] = {}
    members_by_frame: dict[str, set[str]] = {}
    opening_ids_by_frame: dict[str, set[str]] = {}
    record_ids_by_frame: dict[str, set[str]] = {}
    conflicted_members: set[str] = set()
    authority = composition.opening_host_frame_authority

    for opening_id, selector in composition.host_frame_selectors.items():
        result = authority.resolve(selector)
        evidence = result.evidence
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or evidence is None
            or not _clean(evidence.whole_wall_frame_id)
        ):
            continue
        frame_id = _clean(evidence.whole_wall_frame_id)
        opening_ids_by_frame.setdefault(frame_id, set()).add(_clean(opening_id))
        record_ids_by_frame.setdefault(frame_id, set()).add(
            _clean(evidence.record_id)
        )
        frame_members = members_by_frame.setdefault(frame_id, set())
        for member_id in evidence.whole_wall_candidate_ids:
            member_id = _clean(member_id)
            if not member_id:
                continue
            frame_members.add(member_id)
            prior = member_to_frame.get(member_id)
            if prior is not None and prior != frame_id:
                conflicted_members.add(member_id)
            else:
                member_to_frame[member_id] = frame_id

    return (
        member_to_frame,
        members_by_frame,
        opening_ids_by_frame,
        record_ids_by_frame,
        conflicted_members,
    )


def _make_wall(
    *,
    canonical_wall_id: str,
    records: tuple[object, ...],
    scope: object,
    frame_id: str | None,
    opening_ids_by_frame: Mapping[str, set[str]],
    frame_record_ids: Mapping[str, set[str]],
    physical_identity_resolved: bool,
    identity_status: str,
) -> LiveCanonicalWallObject:
    plan_members = tuple(_plan_member(record) for record in records)
    evidence_ids = _dedupe(
        [
            *(
                evidence_id
                for member in plan_members
                for evidence_id in member.supporting_evidence_ids
            ),
            *(
                frame_record_ids.get(frame_id, set())
                if frame_id is not None
                else ()
            ),
        ]
    )
    return LiveCanonicalWallObject(
        canonical_wall_id=canonical_wall_id,
        physical_wall_id=canonical_wall_id if physical_identity_resolved else None,
        document_id=scope.document_id,
        revision_id=scope.revision_id,
        source_sha256=scope.source_sha256,
        snapshot_id=scope.snapshot_id,
        page_id=scope.page_id,
        decision_scope_id=scope.decision_scope_id,
        wall_local_frame_id=frame_id,
        role=None,
        coordinate_unit="source_page_points",
        length_m=None,
        height_m=None,
        gross_area_m2=None,
        net_area_m2=None,
        gross_polygon_wkb_hex=None,
        net_polygon_wkb_hex=None,
        member_wall_candidate_ids=tuple(
            _clean(record.wall_candidate_id) for record in records
        ),
        plan_members=plan_members,
        level_ids=_dedupe(
            member.level_id for member in plan_members if member.level_id
        ),
        opening_identity_ids=tuple(
            sorted(opening_ids_by_frame.get(frame_id, set()))
            if frame_id is not None
            else ()
        ),
        opening_voids=(),
        gross_geometry_record_id=None,
        whole_wall_role_record_id=None,
        evidence_ids=evidence_ids,
        identity_status=identity_status,
        physical_identity_resolved=physical_identity_resolved,
    )


def compose_live_canonical_walls(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    wall_opening_composition: LiveWallOpeningAuthorityComposition,
) -> LiveCanonicalWallComposition:
    """Preserve resolved and candidate wall objects from producer-owned scopes."""

    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")
    if type(wall_opening_composition) is not LiveWallOpeningAuthorityComposition:
        raise TypeError(
            "wall_opening_composition must be live producer-owned composition"
        )

    published = source_visibility_producer.published_snapshot_for_revision(
        wall_opening_composition.revision_id
    )
    if published is None:
        return LiveCanonicalWallComposition(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(LIVE_CANONICAL_WALL_UNAVAILABLE,),
            walls=(),
            source_pages=(),
            unresolved_wall_candidate_ids=(),
            candidate_to_canonical_wall_id=MappingProxyType({}),
        )

    authority = wall_opening_composition.physical_wall_candidate_authority
    (
        member_to_frame,
        members_by_frame,
        opening_ids_by_frame,
        frame_record_ids,
        conflicted_members,
    ) = _host_frame_maps(wall_opening_composition)

    walls: list[LiveCanonicalWallObject] = []
    mapping: dict[str, str] = {}
    unresolved: set[str] = set(conflicted_members)
    reasons: list[str] = []
    source_pages: set[int] = set()
    all_pages_resolved = True

    for page_id in wall_opening_composition.page_ids:
        selector = PhysicalWallCandidateSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=page_id,
            decision_scope_id=f"wall-source:page-{page_id}",
        )
        scope = authority.resolve_scope(selector)
        if (
            scope.status is not EvidenceResolutionStatus.CORROBORATED
            or not scope.scope_complete
            or not scope.records
        ):
            all_pages_resolved = False
            reasons.extend(scope.reason_codes)
            unresolved.update(
                _clean(record.wall_candidate_id) for record in scope.records
            )
            continue

        if str(page_id).isdigit():
            source_pages.add(int(page_id))
        records_by_id = {
            _clean(record.wall_candidate_id): record for record in scope.records
        }
        page_member_ids = set(records_by_id)
        covered: set[str] = set()

        # A sealed whole-wall opening-host frame is independent positive proof
        # that its member candidates belong to one physical wall.
        page_frame_ids = sorted(
            {
                member_to_frame[member_id]
                for member_id in page_member_ids
                if member_id in member_to_frame
            }
        )
        for frame_id in page_frame_ids:
            claimed_members = set(members_by_frame.get(frame_id, set()))
            if (
                not claimed_members
                or not claimed_members.issubset(page_member_ids)
                or claimed_members & conflicted_members
            ):
                unresolved.update(claimed_members & page_member_ids)
                reasons.append(LIVE_CANONICAL_WALL_FRAME_CONFLICT)
                all_pages_resolved = False
                continue
            member_ids = tuple(sorted(claimed_members))
            wall = _make_wall(
                canonical_wall_id=frame_id,
                records=tuple(records_by_id[item] for item in member_ids),
                scope=scope,
                frame_id=frame_id,
                opening_ids_by_frame=opening_ids_by_frame,
                frame_record_ids=frame_record_ids,
                physical_identity_resolved=True,
                identity_status="physical_resolved_by_opening_host_frame",
            )
            walls.append(wall)
            for member_id in member_ids:
                mapping[member_id] = frame_id
            covered.update(member_ids)

        equivalence = scope.equivalence
        if equivalence is None:
            reasons.append(LIVE_CANONICAL_WALL_EQUIVALENCE_UNAVAILABLE)
            all_pages_resolved = False
        else:
            groups = tuple(
                frozenset(
                    _clean(member) for member in group if _clean(member)
                )
                for group in equivalence.equivalence_groups
                if group
            )
            for representative_id in equivalence.representative_wall_ids:
                representative_id = _clean(representative_id)
                wall_class = next(
                    (group for group in groups if representative_id in group),
                    frozenset((representative_id,)),
                )
                member_ids = tuple(sorted(wall_class))
                already = set(member_ids) & covered
                if already:
                    if set(member_ids).issubset(covered):
                        continue
                    unresolved.update(member_ids)
                    reasons.append(LIVE_CANONICAL_WALL_FRAME_CONFLICT)
                    all_pages_resolved = False
                    continue
                if not set(member_ids).issubset(page_member_ids):
                    unresolved.update(member_ids)
                    reasons.append(LIVE_CANONICAL_WALL_FRAME_CONFLICT)
                    all_pages_resolved = False
                    continue
                wall = _make_wall(
                    canonical_wall_id=representative_id,
                    records=tuple(records_by_id[item] for item in member_ids),
                    scope=scope,
                    frame_id=None,
                    opening_ids_by_frame=opening_ids_by_frame,
                    frame_record_ids=frame_record_ids,
                    physical_identity_resolved=True,
                    identity_status="physical_resolved_by_equivalence",
                )
                walls.append(wall)
                for member_id in member_ids:
                    mapping[member_id] = representative_id
                covered.update(member_ids)

        # Preserve remaining authenticated candidates without pretending their
        # physical equivalence has resolved.
        remaining = tuple(sorted(page_member_ids - covered))
        if remaining:
            all_pages_resolved = False
            reasons.append(LIVE_CANONICAL_WALL_IDENTITY_CANDIDATE)
        for member_id in remaining:
            record = records_by_id[member_id]
            identity = record.physical_identity
            canonical_id = (
                _clean(identity.candidate_identity_id)
                if identity.candidate_identity_id
                else member_id
            )
            wall = _make_wall(
                canonical_wall_id=canonical_id,
                records=(record,),
                scope=scope,
                frame_id=None,
                opening_ids_by_frame=opening_ids_by_frame,
                frame_record_ids=frame_record_ids,
                physical_identity_resolved=False,
                identity_status="candidate_physical_equivalence_unresolved",
            )
            walls.append(wall)
            mapping[member_id] = canonical_id
            unresolved.add(member_id)

    # Fail closed on accidental canonical-id collisions.
    ids = [wall.canonical_wall_id for wall in walls]
    if len(ids) != len(set(ids)):
        return LiveCanonicalWallComposition(
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(LIVE_CANONICAL_WALL_FRAME_CONFLICT,),
            walls=(),
            source_pages=tuple(sorted(source_pages)),
            unresolved_wall_candidate_ids=tuple(sorted(unresolved)),
            candidate_to_canonical_wall_id=MappingProxyType({}),
        )

    walls.sort(key=lambda wall: (wall.page_id, wall.canonical_wall_id))
    unresolved_tuple = tuple(sorted(value for value in unresolved if value))
    if walls and all_pages_resolved and not unresolved_tuple:
        status = EvidenceResolutionStatus.CORROBORATED
        reason_codes = (LIVE_CANONICAL_WALL_RESOLVED,)
    elif walls:
        status = EvidenceResolutionStatus.CANDIDATE
        reason_codes = (LIVE_CANONICAL_WALL_PARTIAL, *_dedupe(reasons))
    else:
        status = EvidenceResolutionStatus.ABSTAINED
        reason_codes = (LIVE_CANONICAL_WALL_UNAVAILABLE, *_dedupe(reasons))

    return LiveCanonicalWallComposition(
        status=status,
        reason_codes=reason_codes,
        walls=tuple(walls),
        source_pages=tuple(sorted(source_pages)),
        unresolved_wall_candidate_ids=unresolved_tuple,
        candidate_to_canonical_wall_id=MappingProxyType(dict(mapping)),
    )


__all__ = [
    "LIVE_CANONICAL_WALL_EQUIVALENCE_UNAVAILABLE",
    "LIVE_CANONICAL_WALL_FRAME_CONFLICT",
    "LIVE_CANONICAL_WALL_IDENTITY_CANDIDATE",
    "LIVE_CANONICAL_WALL_PARTIAL",
    "LIVE_CANONICAL_WALL_RESOLVED",
    "LIVE_CANONICAL_WALL_SCHEMA_VERSION",
    "LIVE_CANONICAL_WALL_UNAVAILABLE",
    "LiveCanonicalWallComposition",
    "compose_live_canonical_walls",
]
