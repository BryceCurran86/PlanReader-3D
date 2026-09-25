"""Shadow component-level completeness for authenticated physical-wall scopes.

A viewport may be globally incomplete because unrelated structural primitives
cross or ambiguously occupy its boundary.  That does not automatically mean
that every disconnected wall component inside the viewport is incomplete.

This authority proves a *component-local* proposition only when:
- the upstream physical-wall scope is producer-owned and CORROBORATED;
- the wall belongs to an authenticated viewport scope;
- no wall in its positive-equivalence / topology component has a dangling end
  on the page or viewport boundary;
- every structural source observation withheld by viewport ownership can be
  replayed from the immutable source; and
- none of those withheld primitives intersects any source primitive owned by
  the component.

It never changes PhysicalWallCandidateScopeResult.scope_complete.  It does not
mint room topology, wall role, quantity, opening deduction, or commercial
output.  It is a shadow prerequisite for a later source-topology review.

No nearest / first / confidence ranking and no benchmark or project identity.
The only coordinate tolerance reused here is the existing wall-authority
coordinate tolerance.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateProducer,
    _COORD_TOL,
    _segment_geometry,
    _source_page_segments,
    _viewport_scope_boundary_reason,
)
from pb_source_visibility_authority import SourceVisibilityProducer


WALL_COMPONENT_COMPLETENESS_SCHEMA_VERSION = "1.0.0"
WALL_COMPONENT_COMPLETE = "wall_component_scope_complete"
WALL_COMPONENT_UNAVAILABLE = "wall_component_scope_unavailable"
WALL_COMPONENT_NOT_VIEWPORT = "wall_component_scope_not_authenticated_viewport"
WALL_COMPONENT_VIEWPORT_BOUNDS_UNAVAILABLE = "wall_component_viewport_bounds_unavailable"
WALL_COMPONENT_BOUNDARY_WALL = "wall_component_contains_boundary_wall"
WALL_COMPONENT_WITHHELD_GEOMETRY_UNAVAILABLE = (
    "wall_component_withheld_source_geometry_unavailable"
)
WALL_COMPONENT_SOURCE_GEOMETRY_UNAVAILABLE = (
    "wall_component_source_geometry_unavailable"
)
WALL_COMPONENT_TOUCHED_BY_WITHHELD_PRIMITIVE = (
    "wall_component_touched_by_withheld_structural_primitive"
)
WALL_COMPONENT_SOURCE_INTEGRITY_FAILURE = "wall_component_source_integrity_failure"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()


@dataclass(frozen=True)
class WallComponentCompletenessSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "physical_wall_id",
        ):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"{name} must be non-empty")

    @property
    def key(self) -> tuple[str, ...]:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.decision_scope_id,
            self.physical_wall_id,
        )


@dataclass(frozen=True)
class WallComponentCompletenessRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str
    component_id: str
    component_wall_ids: tuple[str, ...]
    checked_withheld_observation_ids: tuple[str, ...]
    disjoint_withheld_observation_ids: tuple[str, ...]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    schema_version: str = WALL_COMPONENT_COMPLETENESS_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("WallComponentCompletenessRecord is producer-owned")
        if self.status is not EvidenceResolutionStatus.CORROBORATED:
            raise ValueError("positive component completeness must be CORROBORATED")
        if self.physical_wall_id not in self.component_wall_ids:
            raise ValueError("physical wall must belong to component")


@dataclass(frozen=True)
class WallComponentCompletenessResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[WallComponentCompletenessRecord] = None
    schema_version: str = WALL_COMPONENT_COMPLETENESS_SCHEMA_VERSION


def _blocked(*reasons: str) -> WallComponentCompletenessResult:
    clean = tuple(dict.fromkeys(str(reason) for reason in reasons if str(reason)))
    return WallComponentCompletenessResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=clean or (WALL_COMPONENT_UNAVAILABLE,),
        record=None,
    )


def _bbox(line: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    return (
        min(line[0], line[2]),
        min(line[1], line[3]),
        max(line[0], line[2]),
        max(line[1], line[3]),
    )


def _bbox_overlap(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    return not (
        left[2] < right[0] - _COORD_TOL
        or right[2] < left[0] - _COORD_TOL
        or left[3] < right[1] - _COORD_TOL
        or right[3] < left[1] - _COORD_TOL
    )


def _cross(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, p) -> bool:
    return (
        min(a[0], b[0]) - _COORD_TOL <= p[0] <= max(a[0], b[0]) + _COORD_TOL
        and min(a[1], b[1]) - _COORD_TOL <= p[1] <= max(a[1], b[1]) + _COORD_TOL
        and abs(_cross(a, b, p)) <= _COORD_TOL
    )


def _line_intersects(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    if not _bbox_overlap(_bbox(left), _bbox(right)):
        return False
    a, b = (left[0], left[1]), (left[2], left[3])
    c, d = (right[0], right[1]), (right[2], right[3])
    o1, o2 = _cross(a, b, c), _cross(a, b, d)
    o3, o4 = _cross(c, d, a), _cross(c, d, b)

    if (
        ((o1 > _COORD_TOL and o2 < -_COORD_TOL) or (o1 < -_COORD_TOL and o2 > _COORD_TOL))
        and ((o3 > _COORD_TOL and o4 < -_COORD_TOL) or (o3 < -_COORD_TOL and o4 > _COORD_TOL))
    ):
        return True
    return (
        (abs(o1) <= _COORD_TOL and _on_segment(a, b, c))
        or (abs(o2) <= _COORD_TOL and _on_segment(a, b, d))
        or (abs(o3) <= _COORD_TOL and _on_segment(c, d, a))
        or (abs(o4) <= _COORD_TOL and _on_segment(c, d, b))
    )


def _component_groups(scope) -> tuple[tuple[str, ...], ...]:
    records = tuple(scope.records or ())
    ids = tuple(sorted(str(record.wall_candidate_id) for record in records))
    parent = {wall_id: wall_id for wall_id in ids}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: str, right: str) -> None:
        if left not in parent or right not in parent:
            return
        a, b = find(left), find(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    by_id = {str(record.wall_candidate_id): record for record in records}
    wall_ids_by_node: dict[str, list[str]] = {}
    for wall_id, record in by_id.items():
        for node_id in tuple(getattr(record.wall_candidate, "end_node_ids", ()) or ()):
            if str(node_id):
                wall_ids_by_node.setdefault(str(node_id), []).append(wall_id)
    for values in wall_ids_by_node.values():
        for wall_id in values[1:]:
            union(values[0], wall_id)

    equivalence = getattr(scope, "equivalence", None)
    if equivalence is not None:
        for group in tuple(equivalence.equivalence_groups or ()):
            members = [str(value) for value in group if str(value) in parent]
            for wall_id in members[1:]:
                union(members[0], wall_id)

    grouped: dict[str, list[str]] = {}
    for wall_id in ids:
        grouped.setdefault(find(wall_id), []).append(wall_id)
    return tuple(tuple(sorted(values)) for _, values in sorted(grouped.items()))


def _derive_scope_results(
    *,
    scope,
    page_segments: Sequence[Mapping[str, object]],
    page_width: float,
    page_height: float,
) -> dict[str, WallComponentCompletenessResult]:
    records = tuple(scope.records or ())
    if (
        scope.status is not EvidenceResolutionStatus.CORROBORATED
        or not records
    ):
        return {
            str(record.wall_candidate_id): _blocked(WALL_COMPONENT_UNAVAILABLE)
            for record in records
        }
    if str(getattr(scope, "scope_kind", "")) != "viewport":
        return {
            str(record.wall_candidate_id): _blocked(WALL_COMPONENT_NOT_VIEWPORT)
            for record in records
        }
    viewport_bbox = getattr(scope, "viewport_bbox", None)
    if viewport_bbox is None:
        return {
            str(record.wall_candidate_id): _blocked(
                WALL_COMPONENT_VIEWPORT_BOUNDS_UNAVAILABLE
            )
            for record in records
        }

    by_raw_id = {
        str(segment.get("id")): segment
        for segment in page_segments
        if str(segment.get("id") or "")
    }
    by_observation: dict[str, list[Mapping[str, object]]] = {}
    for segment in page_segments:
        observation_id = str(segment.get("source_observation_id") or "")
        if observation_id:
            by_observation.setdefault(observation_id, []).append(segment)

    withheld_ids = tuple(
        sorted(
            set(
                tuple(getattr(scope, "scope_boundary_observation_ids", ()) or ())
                + tuple(getattr(scope, "ambiguous_source_observation_ids", ()) or ())
            )
        )
    )
    missing_withheld = tuple(
        observation_id
        for observation_id in withheld_ids
        if observation_id not in by_observation
    )

    by_wall = {str(record.wall_candidate_id): record for record in records}
    results: dict[str, WallComponentCompletenessResult] = {}
    for component in _component_groups(scope):
        reasons: list[str] = []
        if missing_withheld:
            reasons.append(WALL_COMPONENT_WITHHELD_GEOMETRY_UNAVAILABLE)

        component_segments: list[tuple[float, float, float, float]] = []
        for wall_id in component:
            record = by_wall[wall_id]
            if (
                _viewport_scope_boundary_reason(
                    record.wall_candidate,
                    bbox=viewport_bbox,
                    page_width=page_width,
                    page_height=page_height,
                )
                is not None
            ):
                reasons.append(WALL_COMPONENT_BOUNDARY_WALL)

            for raw_id in tuple(record.physical_identity.source_primitive_ids or ()):
                segment = by_raw_id.get(str(raw_id))
                if segment is None:
                    reasons.append(WALL_COMPONENT_SOURCE_GEOMETRY_UNAVAILABLE)
                    continue
                component_segments.append(_segment_geometry(segment))

        if not reasons and withheld_ids:
            for observation_id in withheld_ids:
                for withheld in by_observation.get(observation_id, ()):
                    withheld_line = _segment_geometry(withheld)
                    if any(
                        _line_intersects(owned_line, withheld_line)
                        for owned_line in component_segments
                    ):
                        reasons.append(WALL_COMPONENT_TOUCHED_BY_WITHHELD_PRIMITIVE)
                        break
                if reasons:
                    break

        if reasons:
            result = _blocked(*reasons)
            for wall_id in component:
                results[wall_id] = result
            continue

        component_id = stable_contract_id(
            "wall_component_scope",
            {
                "document_id": scope.document_id,
                "revision_id": scope.revision_id,
                "source_sha256": scope.source_sha256,
                "snapshot_id": scope.snapshot_id,
                "page_id": scope.page_id,
                "decision_scope_id": scope.decision_scope_id,
                "component_wall_ids": component,
            },
            digest_chars=32,
        )
        for wall_id in component:
            payload = {
                "document_id": scope.document_id,
                "revision_id": scope.revision_id,
                "source_sha256": scope.source_sha256,
                "snapshot_id": scope.snapshot_id,
                "page_id": scope.page_id,
                "decision_scope_id": scope.decision_scope_id,
                "physical_wall_id": wall_id,
                "component_id": component_id,
                "component_wall_ids": component,
                "checked_withheld_observation_ids": withheld_ids,
                "disjoint_withheld_observation_ids": withheld_ids,
            }
            record = WallComponentCompletenessRecord(
                record_id=stable_contract_id(
                    "wall_component_completeness",
                    payload,
                    digest_chars=32,
                ),
                **payload,
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(WALL_COMPONENT_COMPLETE,),
                _seal=_RECORD_SEAL,
            )
            results[wall_id] = WallComponentCompletenessResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(WALL_COMPONENT_COMPLETE,),
                record=record,
            )
    return results


class WallComponentCompletenessAuthority:
    def __init__(self, results: Mapping[tuple[str, ...], WallComponentCompletenessResult], *, _seal=None):
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("WallComponentCompletenessAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: WallComponentCompletenessSelector) -> WallComponentCompletenessResult:
        if type(selector) is not WallComponentCompletenessSelector:
            raise TypeError("selector must be WallComponentCompletenessSelector")
        return self._results.get(selector.key, _blocked(WALL_COMPONENT_UNAVAILABLE))


class WallComponentCompletenessProducer:
    def __init__(self, results: Mapping[tuple[str, ...], WallComponentCompletenessResult], *, _seal=None):
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "WallComponentCompletenessProducer must be obtained "
                "from_source_visibility_producer()"
            )
        self._results = MappingProxyType(dict(results))

    @classmethod
    def from_source_visibility_producer(
        cls,
        source_visibility_producer: SourceVisibilityProducer,
        *,
        page_ids: Optional[Sequence[str]] = None,
    ) -> "WallComponentCompletenessProducer":
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        selected = (
            None
            if page_ids is None
            else tuple(
                sorted(
                    {str(page).strip() for page in page_ids if str(page).strip()},
                    key=int,
                )
            )
        )
        if page_ids is not None and not selected:
            raise ValueError("page_ids must contain at least one source page")

        wall_authority = PhysicalWallCandidateProducer.from_authenticated_viewports(
            source_visibility_producer,
            page_ids=selected,
        ).authority()
        return cls.from_authorities(
            source_visibility_producer=source_visibility_producer,
            physical_wall_candidate_authority=wall_authority,
        )

    @classmethod
    def from_authorities(
        cls,
        *,
        source_visibility_producer: SourceVisibilityProducer,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
    ) -> "WallComponentCompletenessProducer":
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError(
                "physical_wall_candidate_authority must be producer-owned"
            )

        store = source_visibility_producer._producer._store
        results: dict[tuple[str, ...], WallComponentCompletenessResult] = {}

        for scope in physical_wall_candidate_authority._scopes.values():
            published = source_visibility_producer._published_by_revision.get(
                scope.revision_id
            )
            if published is None:
                continue
            source_bytes = store.source_bytes_by_revision.get(scope.revision_id)
            if (
                source_bytes is None
                or hashlib.sha256(source_bytes).hexdigest() != scope.source_sha256
            ):
                raise RuntimeError(WALL_COMPONENT_SOURCE_INTEGRITY_FAILURE)
            page_segments, _observation_ids, page_width, page_height = (
                _source_page_segments(
                    source_producer=source_visibility_producer,
                    published=published,
                    source_bytes=source_bytes,
                    page_id=str(scope.page_id),
                    decision_scope_id=str(scope.decision_scope_id),
                )
            )
            derived = _derive_scope_results(
                scope=scope,
                page_segments=page_segments,
                page_width=page_width,
                page_height=page_height,
            )
            for wall_id, result in derived.items():
                selector = WallComponentCompletenessSelector(
                    document_id=scope.document_id,
                    revision_id=scope.revision_id,
                    source_sha256=scope.source_sha256,
                    snapshot_id=scope.snapshot_id,
                    page_id=scope.page_id,
                    decision_scope_id=scope.decision_scope_id,
                    physical_wall_id=wall_id,
                )
                results[selector.key] = result

        return cls(results, _seal=_PRODUCER_SEAL)

    def authority(self) -> WallComponentCompletenessAuthority:
        return WallComponentCompletenessAuthority(
            self._results,
            _seal=_AUTHORITY_SEAL,
        )

    def published_results(self) -> tuple[WallComponentCompletenessResult, ...]:
        return tuple(self._results[key] for key in sorted(self._results))


__all__ = [
    "WALL_COMPONENT_BOUNDARY_WALL",
    "WALL_COMPONENT_COMPLETE",
    "WALL_COMPONENT_NOT_VIEWPORT",
    "WALL_COMPONENT_SCHEMA_VERSION",
    "WALL_COMPONENT_SOURCE_GEOMETRY_UNAVAILABLE",
    "WALL_COMPONENT_SOURCE_INTEGRITY_FAILURE",
    "WALL_COMPONENT_TOUCHED_BY_WITHHELD_PRIMITIVE",
    "WALL_COMPONENT_UNAVAILABLE",
    "WALL_COMPONENT_VIEWPORT_BOUNDS_UNAVAILABLE",
    "WALL_COMPONENT_WITHHELD_GEOMETRY_UNAVAILABLE",
    "WallComponentCompletenessAuthority",
    "WallComponentCompletenessProducer",
    "WallComponentCompletenessRecord",
    "WallComponentCompletenessResult",
    "WallComponentCompletenessSelector",
]
