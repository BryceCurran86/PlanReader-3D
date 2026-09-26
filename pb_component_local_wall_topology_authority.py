"""Equivalence-aware component-local source wall topology authority.

This shadow adapter exists for authenticated drawing viewports whose *global*
physical-wall scope is incomplete because unrelated structural primitives cross
or ambiguously occupy the viewport boundary.

It does not upgrade the global scope.  Instead it may publish topology for one
connected physical-wall component only when:

- the viewport is an authenticated floor-plan scope;
- physical-wall publication representatives are used (equivalent faces do not
  double-count as independent walls);
- no member wall in the component has a dangling end on the page/viewport
  boundary; and
- every source observation withheld by viewport ownership can be replayed from
  immutable source lineage and none geometrically touches the component.

Any unresolved withheld primitive, any exact touch, or any unresolved
representative mapping keeps the component fail-closed.

No proximity, perimeter rank, expected quantity, project identity, or caller
role hint participates.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

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
from pb_wall_role_authority import (
    WallTopologyAuthority,
    _AUTHORITY_SEAL,
)


COMPONENT_LOCAL_WALL_TOPOLOGY_SCHEMA_VERSION = "1.0.0"
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
        (
            abs(value) <= _COORD_TOL
            and _point_on_segment(point, seg_a, seg_b)
        )
        for value, point, seg_a, seg_b in (
            (o1, c, a, b),
            (o2, d, a, b),
            (o3, a, c, d),
            (o4, b, c, d),
        )
    )


def _publication_groups(scope):
    records = {str(record.wall_candidate_id): record for record in tuple(scope.records or ())}
    if not records:
        return {}

    equivalence = getattr(scope, "equivalence", None)
    if equivalence is None:
        return {
            wall_id: (wall_id,)
            for wall_id in sorted(records)
        }

    representatives = set(tuple(equivalence.representative_wall_ids or ()))
    groups: dict[str, tuple[str, ...]] = {}
    claimed: set[str] = set()

    for group in tuple(equivalence.equivalence_groups or ()):
        members = tuple(sorted(wall_id for wall_id in group if wall_id in records))
        if not members:
            continue
        reps = sorted(set(members) & representatives)
        if len(reps) != 1:
            # A positive SAME group without exactly one publication
            # representative cannot be converted into topology.
            continue
        rep = reps[0]
        groups[rep] = members
        claimed.update(members)

    for rep in sorted(representatives):
        if rep in records and rep not in claimed:
            groups[rep] = (rep,)

    return groups


def _component_groups(scope):
    publication_groups = _publication_groups(scope)
    if not publication_groups:
        return ()

    records = {str(record.wall_candidate_id): record for record in tuple(scope.records or ())}
    parent = {rep: rep for rep in publication_groups}

    def find(rep: str) -> str:
        while parent[rep] != rep:
            parent[rep] = parent[parent[rep]]
            rep = parent[rep]
        return rep

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    nodes_by_rep: dict[str, set[str]] = {}
    endpoints_by_rep: dict[str, set[tuple[float, float]]] = {}
    for rep, members in publication_groups.items():
        nodes: set[str] = set()
        endpoints: set[tuple[float, float]] = set()
        for member in members:
            record = records.get(member)
            if record is None:
                continue
            wall = record.wall_candidate
            nodes.update(str(node) for node in tuple(wall.end_node_ids or ()) if str(node))
            points = tuple(wall.centerline_pts or ())
            if points:
                endpoints.add((round(float(points[0][0]), 6), round(float(points[0][1]), 6)))
                endpoints.add((round(float(points[-1][0]), 6), round(float(points[-1][1]), 6)))
        nodes_by_rep[rep] = nodes
        endpoints_by_rep[rep] = endpoints

    reps = tuple(sorted(publication_groups))
    for index, left in enumerate(reps):
        for right in reps[index + 1 :]:
            if (
                nodes_by_rep[left] & nodes_by_rep[right]
                or endpoints_by_rep[left] & endpoints_by_rep[right]
            ):
                union(left, right)

    components: dict[str, list[str]] = {}
    for rep in reps:
        components.setdefault(find(rep), []).append(rep)

    return tuple(
        tuple(sorted(values))
        for _root, values in sorted(components.items())
    )


def _resolve_withheld_lines(source, scope):
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

    observation_ids = tuple(dict.fromkeys((
        *tuple(scope.scope_boundary_observation_ids or ()),
        *tuple(scope.ambiguous_source_observation_ids or ()),
    )))
    authority = source.authority()
    lines = []
    for observation_id in observation_ids:
        result = authority.resolve_visible(ObservationSelector(
            document_id=scope.document_id,
            revision_id=scope.revision_id,
            source_sha256=scope.source_sha256,
            snapshot_id=scope.snapshot_id,
            observation_id=str(observation_id),
        ))
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


def _component_is_locally_complete(
    *,
    scope,
    component_reps,
    publication_groups,
    records_by_id,
    withheld_lines,
    page_width: float,
    page_height: float,
) -> bool:
    if scope.viewport_bbox is None:
        return False

    member_ids = {
        member
        for rep in component_reps
        for member in publication_groups.get(rep, ())
    }
    member_records = [
        records_by_id[wall_id]
        for wall_id in sorted(member_ids)
        if wall_id in records_by_id
    ]
    if not member_records:
        return False

    # A member wall that is itself cropped cannot be certified by unrelated
    # global-boundary evidence.
    for record in member_records:
        if _viewport_scope_boundary_reason(
            record.wall_candidate,
            bbox=scope.viewport_bbox,
            page_width=page_width,
            page_height=page_height,
        ) is not None:
            return False

    component_edges = [
        edge
        for record in member_records
        for edge in _wall_edges(record)
    ]
    if not component_edges:
        return False

    for _observation_id, line in withheld_lines:
        if any(_segments_touch(edge, line) for edge in component_edges):
            return False
    return True


def build_component_local_source_wall_topology_authority(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
) -> WallTopologyAuthority:
    """Build source-derived topology for globally complete or locally complete components."""
    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be an actual SourceVisibilityProducer")
    if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
        raise TypeError(
            "physical_wall_candidate_authority must be producer-owned PhysicalWallCandidateAuthority"
        )

    store = source_visibility_producer._producer._store
    records = {}
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
            records.update(_derive_scope_records(scope))
            continue

        if getattr(scope, "scope_kind", "page") != "viewport":
            continue

        publication_groups = _publication_groups(scope)
        components = _component_groups(scope)
        if not publication_groups or not components:
            continue

        withheld_lines = _resolve_withheld_lines(source_visibility_producer, scope)
        if withheld_lines is None:
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

        records_by_id = {
            str(record.wall_candidate_id): record
            for record in tuple(scope.records or ())
        }
        for component_reps in components:
            if not _component_is_locally_complete(
                scope=scope,
                component_reps=component_reps,
                publication_groups=publication_groups,
                records_by_id=records_by_id,
                withheld_lines=withheld_lines,
                page_width=page_width,
                page_height=page_height,
            ):
                continue

            representative_records = tuple(
                records_by_id[rep]
                for rep in component_reps
                if rep in records_by_id
            )
            if len(representative_records) != len(component_reps):
                continue

            local_scope = replace(
                scope,
                scope_complete=True,
                records=representative_records,
                source_observation_ids=tuple(
                    sorted({
                        observation_id
                        for record in representative_records
                        for observation_id in tuple(
                            getattr(record, "source_observation_ids", ()) or ()
                        )
                    })
                ),
            )
            local_records = _derive_scope_records(local_scope)
            if not local_records:
                continue
            records.update(local_records)

            member_ids = tuple(sorted({
                member
                for rep in component_reps
                for member in publication_groups.get(rep, ())
            }))
            checked_ids = tuple(observation_id for observation_id, _line in withheld_lines)
            payload = {
                "document_id": scope.document_id,
                "revision_id": scope.revision_id,
                "source_sha256": scope.source_sha256,
                "snapshot_id": scope.snapshot_id,
                "page_id": scope.page_id,
                "decision_scope_id": scope.decision_scope_id,
                "representative_wall_ids": tuple(component_reps),
                "member_wall_ids": member_ids,
                "checked_withheld_observation_ids": checked_ids,
            }
            component_id = stable_contract_id(
                "component_local_wall_topology_component",
                payload,
                digest_chars=32,
            )
            proof = ComponentLocalTopologyProof(
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
                representative_wall_ids=tuple(component_reps),
                member_wall_ids=member_ids,
                checked_withheld_observation_ids=checked_ids,
                scope_was_globally_complete=False,
            )
            proofs[component_id] = proof

    authority = WallTopologyAuthority(records, _seal=_AUTHORITY_SEAL)
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
        and getattr(authority, "_component_local_topology_provenance_seal", None)
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
