"""Equivalence-aware component-local source wall topology authority.

A drawing viewport can be globally incomplete because unrelated structural
geometry crosses an authenticated viewport partition.  This shadow adapter does
not upgrade that global scope.  It derives candidate topology only from the
physical-wall publication representatives, then publishes evidence solely for
topology components whose local source universe is complete.

Positive component proof requires:
- an authenticated floor-plan wall scope;
- one producer-approved publication representative for every consumed physical
  wall identity;
- no member wall in the component has a dangling endpoint on the page/viewport
  boundary;
- every structural observation withheld by viewport ownership can be replayed
  from immutable source lineage; and
- no withheld structural primitive touches a member wall or enters the exact
  component bounding region.

The last condition is deliberately conservative: an omitted structural line
inside a room component might split or alter room topology even when it does
not touch an already-published wall edge.

No nearest-wall rule, perimeter rank, project identity, benchmark value, or
caller role hint participates.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
from types import MappingProxyType
from typing import Mapping

import fitz

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    _viewport_scope_boundary_reason,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_source_wall_topology_authority import (
    _SOURCE_TOPOLOGY_AUTHORITY_SEAL,
    _derive_scope_records,
    _wall_edges,
)
from pb_wall_role_authority import WallTopologyAuthority, _AUTHORITY_SEAL


COMPONENT_LOCAL_WALL_TOPOLOGY_SCHEMA_VERSION = "1.1.0"
_COMPONENT_LOCAL_AUTHORITY_SEAL = object()
_COORD_TOL = 1e-6


@dataclass(frozen=True)
class ComponentLocalTopologyProof:
    proof_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    component_id: str
    representative_wall_ids: tuple[str, ...]
    member_wall_ids: tuple[str, ...]
    checked_withheld_observation_ids: tuple[str, ...]
    scope_was_globally_complete: bool
    schema_version: str = COMPONENT_LOCAL_WALL_TOPOLOGY_SCHEMA_VERSION


def _orientation(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_on_segment(point, first, second) -> bool:
    if abs(_orientation(first, second, point)) > _COORD_TOL:
        return False
    return (
        min(first[0], second[0]) - _COORD_TOL
        <= point[0]
        <= max(first[0], second[0]) + _COORD_TOL
        and min(first[1], second[1]) - _COORD_TOL
        <= point[1]
        <= max(first[1], second[1]) + _COORD_TOL
    )


def _segments_touch(first, second) -> bool:
    a, b = first
    c = (float(second[0]), float(second[1]))
    d = (float(second[2]), float(second[3]))
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    if (
        ((o1 > _COORD_TOL and o2 < -_COORD_TOL) or (o1 < -_COORD_TOL and o2 > _COORD_TOL))
        and ((o3 > _COORD_TOL and o4 < -_COORD_TOL) or (o3 < -_COORD_TOL and o4 > _COORD_TOL))
    ):
        return True
    return any(
        abs(value) <= _COORD_TOL and _point_on_segment(point, first_, second_)
        for value, point, first_, second_ in (
            (o1, c, a, b),
            (o2, d, a, b),
            (o3, a, c, d),
            (o4, b, c, d),
        )
    )


def _line_intersects_bbox(line, bbox) -> bool:
    x1, y1, x2, y2 = (float(value) for value in line)
    xmin, ymin, xmax, ymax = (float(value) for value in bbox)
    if (
        xmin - _COORD_TOL <= x1 <= xmax + _COORD_TOL
        and ymin - _COORD_TOL <= y1 <= ymax + _COORD_TOL
    ) or (
        xmin - _COORD_TOL <= x2 <= xmax + _COORD_TOL
        and ymin - _COORD_TOL <= y2 <= ymax + _COORD_TOL
    ):
        return True
    edges = (
        ((xmin, ymin), (xmax, ymin)),
        ((xmax, ymin), (xmax, ymax)),
        ((xmax, ymax), (xmin, ymax)),
        ((xmin, ymax), (xmin, ymin)),
    )
    return any(_segments_touch(edge, line) for edge in edges)


def _publication_groups(scope):
    records = {
        str(record.wall_candidate_id): record
        for record in tuple(scope.records or ())
    }
    if not records:
        return {}

    equivalence = getattr(scope, "equivalence", None)
    if equivalence is None:
        return {wall_id: (wall_id,) for wall_id in sorted(records)}

    representatives = set(tuple(equivalence.representative_wall_ids or ()))
    groups: dict[str, tuple[str, ...]] = {}
    claimed: set[str] = set()

    for group in tuple(equivalence.equivalence_groups or ()):
        members = tuple(sorted(wall_id for wall_id in group if wall_id in records))
        if not members:
            continue
        reps = sorted(set(members) & representatives)
        if len(reps) != 1:
            continue
        rep = reps[0]
        groups[rep] = members
        claimed.update(members)

    for rep in sorted(representatives):
        if rep in records and rep not in claimed:
            groups[rep] = (rep,)

    return groups


def _resolve_withheld_lines(source: SourceVisibilityProducer, scope):
    published = source.published_snapshot_for_revision(scope.revision_id)
    if published is None:
        return None
    if (
        published.revision.document_id != scope.document_id
        or published.revision.revision_id != scope.revision_id
        or published.revision.source_sha256 != scope.source_sha256
        or published.snapshot.snapshot_id != scope.snapshot_id
    ):
        return None

    observation_ids = tuple(
        dict.fromkeys(
            (
                *tuple(scope.scope_boundary_observation_ids or ()),
                *tuple(scope.ambiguous_source_observation_ids or ()),
            )
        )
    )
    authority = source.authority()
    lines = []
    for observation_id in observation_ids:
        result = authority.resolve_visible(
            ObservationSelector(
                document_id=scope.document_id,
                revision_id=scope.revision_id,
                source_sha256=scope.source_sha256,
                snapshot_id=scope.snapshot_id,
                observation_id=str(observation_id),
            )
        )
        observation = result.observation
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or observation is None
            or observation.page_id != scope.page_id
            or len(observation.geometry) != 4
        ):
            return None
        try:
            line = tuple(float(value) for value in observation.geometry)
        except (TypeError, ValueError):
            return None
        if (
            not all(math.isfinite(value) for value in line)
            or math.hypot(line[2] - line[0], line[3] - line[1]) <= _COORD_TOL
        ):
            return None
        lines.append((str(observation_id), line))
    return tuple(lines)


def _topology_components(topology_records):
    """Components linked by exact derived room-face membership."""
    by_wall = {key[-1]: value for key, value in topology_records.items()}
    walls = tuple(sorted(by_wall))
    parent = {wall_id: wall_id for wall_id in walls}

    def find(wall_id: str) -> str:
        while parent[wall_id] != wall_id:
            parent[wall_id] = parent[parent[wall_id]]
            wall_id = parent[wall_id]
        return wall_id

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    faces = {
        wall_id: set(tuple(by_wall[wall_id].enclosed_space_ids or ()))
        for wall_id in walls
    }
    for index, left in enumerate(walls):
        for right in walls[index + 1 :]:
            if faces[left] & faces[right]:
                union(left, right)

    components: dict[str, list[str]] = {}
    for wall_id in walls:
        components.setdefault(find(wall_id), []).append(wall_id)
    return tuple(
        tuple(sorted(values))
        for _root, values in sorted(components.items())
    )


def _component_member_records(component, publication_groups, records_by_id):
    member_ids = {
        member
        for rep in component
        for member in publication_groups.get(rep, ())
    }
    records = tuple(
        records_by_id[wall_id]
        for wall_id in sorted(member_ids)
        if wall_id in records_by_id
    )
    return tuple(sorted(member_ids)), records


def _component_bbox(member_records):
    edges = [
        edge
        for record in member_records
        for edge in _wall_edges(record)
    ]
    if not edges:
        return None
    xs = [point[0] for edge in edges for point in edge]
    ys = [point[1] for edge in edges for point in edge]
    return (min(xs), min(ys), max(xs), max(ys))


def _component_is_locally_complete(
    *,
    scope,
    member_records,
    withheld_lines,
    page_width: float,
    page_height: float,
) -> bool:
    if scope.viewport_bbox is None or not member_records:
        return False

    for record in member_records:
        if _viewport_scope_boundary_reason(
            record.wall_candidate,
            bbox=scope.viewport_bbox,
            page_width=page_width,
            page_height=page_height,
        ) is not None:
            return False

    bbox = _component_bbox(member_records)
    if bbox is None:
        return False

    # Exact segment/bbox intersection is a conservative contamination gate.
    # A withheld structural primitive entering the component region could alter
    # the room graph even if it does not touch an already-published wall.
    if any(_line_intersects_bbox(line, bbox) for _obs, line in withheld_lines):
        return False

    return True


def build_component_local_source_wall_topology_authority(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
) -> WallTopologyAuthority:
    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError(
            "source_visibility_producer must be an actual SourceVisibilityProducer"
        )
    if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
        raise TypeError(
            "physical_wall_candidate_authority must be producer-owned PhysicalWallCandidateAuthority"
        )

    store = source_visibility_producer._producer._store
    output_records = {}
    proofs: dict[str, ComponentLocalTopologyProof] = {}

    for scope in physical_wall_candidate_authority._scopes.values():
        if scope.status is not EvidenceResolutionStatus.CORROBORATED:
            continue
        if (
            getattr(scope, "scope_kind", "page") == "viewport"
            and str(getattr(scope, "viewport_view_type", "") or "") != "floor_plan"
        ):
            continue

        if scope.scope_complete:
            output_records.update(_derive_scope_records(scope))
            continue
        if getattr(scope, "scope_kind", "page") != "viewport":
            continue

        publication_groups = _publication_groups(scope)
        if not publication_groups:
            continue

        withheld_lines = _resolve_withheld_lines(
            source_visibility_producer,
            scope,
        )
        if withheld_lines is None:
            continue

        records_by_id = {
            str(record.wall_candidate_id): record
            for record in tuple(scope.records or ())
        }
        representative_records = tuple(
            records_by_id[rep]
            for rep in sorted(publication_groups)
            if rep in records_by_id
        )
        if len(representative_records) != len(publication_groups):
            continue

        # Derive candidate room topology over the entire producer-approved
        # representative universe first. Splitting walls before face extraction
        # destroys multi-room evidence.
        candidate_scope = replace(
            scope,
            scope_complete=True,
            records=representative_records,
        )
        candidate_records = _derive_scope_records(candidate_scope)
        if not candidate_records:
            continue

        source_bytes = store.source_bytes_by_revision.get(scope.revision_id)
        if (
            source_bytes is None
            or hashlib.sha256(source_bytes).hexdigest() != scope.source_sha256
        ):
            continue
        pdf = fitz.open(stream=source_bytes, filetype="pdf")
        try:
            page_number = int(scope.page_id)
            if not 1 <= page_number <= pdf.page_count:
                continue
            page = pdf.load_page(page_number - 1)
            page_width = float(page.rect.width)
            page_height = float(page.rect.height)
        finally:
            pdf.close()

        for component in _topology_components(candidate_records):
            member_ids, member_records = _component_member_records(
                component,
                publication_groups,
                records_by_id,
            )
            if not _component_is_locally_complete(
                scope=scope,
                member_records=member_records,
                withheld_lines=withheld_lines,
                page_width=page_width,
                page_height=page_height,
            ):
                continue

            component_set = set(component)
            for key, evidence in candidate_records.items():
                if key[-1] in component_set:
                    output_records[key] = evidence

            checked_ids = tuple(
                observation_id for observation_id, _line in withheld_lines
            )
            payload = {
                "document_id": scope.document_id,
                "revision_id": scope.revision_id,
                "source_sha256": scope.source_sha256,
                "snapshot_id": scope.snapshot_id,
                "page_id": scope.page_id,
                "decision_scope_id": scope.decision_scope_id,
                "representative_wall_ids": tuple(component),
                "member_wall_ids": member_ids,
                "checked_withheld_observation_ids": checked_ids,
            }
            component_id = stable_contract_id(
                "component_local_wall_topology_component",
                payload,
                digest_chars=32,
            )
            proofs[component_id] = ComponentLocalTopologyProof(
                proof_id=stable_contract_id(
                    "component_local_wall_topology_proof",
                    payload,
                    digest_chars=32,
                ),
                document_id=scope.document_id,
                revision_id=scope.revision_id,
                source_sha256=scope.source_sha256,
                snapshot_id=scope.snapshot_id,
                page_id=scope.page_id,
                decision_scope_id=scope.decision_scope_id,
                component_id=component_id,
                representative_wall_ids=tuple(component),
                member_wall_ids=member_ids,
                checked_withheld_observation_ids=checked_ids,
                scope_was_globally_complete=False,
            )

    authority = WallTopologyAuthority(output_records, _seal=_AUTHORITY_SEAL)
    object.__setattr__(
        authority,
        "_source_topology_provenance_seal",
        _SOURCE_TOPOLOGY_AUTHORITY_SEAL,
    )
    object.__setattr__(
        authority,
        "_component_local_topology_provenance_seal",
        _COMPONENT_LOCAL_AUTHORITY_SEAL,
    )
    object.__setattr__(
        authority,
        "_component_local_topology_proofs",
        MappingProxyType(dict(proofs)),
    )
    return authority


def is_component_local_source_wall_topology_authority(authority: object) -> bool:
    return (
        type(authority) is WallTopologyAuthority
        and getattr(
            authority,
            "_component_local_topology_provenance_seal",
            None,
        )
        is _COMPONENT_LOCAL_AUTHORITY_SEAL
    )


def component_local_topology_proofs(
    authority: WallTopologyAuthority,
) -> tuple[ComponentLocalTopologyProof, ...]:
    if not is_component_local_source_wall_topology_authority(authority):
        return ()
    proofs: Mapping[str, ComponentLocalTopologyProof] = getattr(
        authority,
        "_component_local_topology_proofs",
        {},
    )
    return tuple(proofs[key] for key in sorted(proofs))


__all__ = [
    "COMPONENT_LOCAL_WALL_TOPOLOGY_SCHEMA_VERSION",
    "ComponentLocalTopologyProof",
    "build_component_local_source_wall_topology_authority",
    "component_local_topology_proofs",
    "is_component_local_source_wall_topology_authority",
]
