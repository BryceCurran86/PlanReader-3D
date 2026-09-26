"""Producer-owned local wall-component completeness authority.

Global authenticated viewport scope completeness remains unchanged.  This
authority proves only the narrower proposition that one connected physical-wall
component is complete enough for a later topology authority to inspect.

A component is locally complete only when:
- it belongs to an authenticated floor-plan viewport wall scope;
- every member wall is source-owned and usable;
- no member has a dangling endpoint on the authenticated viewport boundary;
- every withheld boundary / ambiguous structural observation is replayable;
- no withheld primitive intersects or snap-continues a component wall;
- no withheld primitive shares the same immutable native drawing-path family;
- no withheld parallel overlapping primitive lies within a separation already
  demonstrated by an upstream positive SAME_PHYSICAL_WALL pair.

The final rule uses only a separation already observed in producer-owned
positive wall equivalence; it does not invent a wall-thickness radius.

No wall role, opening host, deduction, net wall, finish quantity, benchmark
value, or commercial output is published here.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY,
    PhysicalWallCandidateProducer,
    _viewport_scope_boundary_reason,
)
from pb_physical_wall_identity import PhysicalEquivalenceClass
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_room_topology_stage_a import DEFAULT_GAP_SNAP_TOLERANCE_PT


WALL_COMPONENT_COMPLETENESS_SCHEMA_VERSION = "1.0.0"
WALL_COMPONENT_COMPLETE = "wall_component_locally_complete"
WALL_COMPONENT_UNAVAILABLE = "wall_component_completeness_unavailable"
WALL_COMPONENT_VIEW_TYPE_UNSUPPORTED = "wall_component_floor_plan_required"
WALL_COMPONENT_MEMBER_BOUNDARY_CROPPED = "wall_component_member_boundary_cropped"
WALL_COMPONENT_WITHHELD_SOURCE_UNREPLAYABLE = (
    "wall_component_withheld_source_unreplayable"
)
WALL_COMPONENT_WITHHELD_SOURCE_CONTACT = "wall_component_withheld_source_contact"
WALL_COMPONENT_WITHHELD_SOURCE_PATH_RELATED = (
    "wall_component_withheld_source_path_related"
)
WALL_COMPONENT_WITHHELD_PLAUSIBLE_SAME_FACE = (
    "wall_component_withheld_plausible_same_face"
)

_RECORD_SEAL = object()
_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_COORD_TOL = 1e-6
_RAW_PATH_RE = re.compile(r"^d(?P<path>\d+)i\d+$")


Point = tuple[float, float]
Line = tuple[float, float, float, float]


@dataclass(frozen=True)
class WallComponentCompletenessSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str

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
    viewport_id: str
    decision_scope_id: str
    component_id: str
    member_wall_ids: tuple[str, ...]
    member_source_primitive_ids: tuple[str, ...]
    positive_equivalence_groups: tuple[tuple[str, ...], ...]
    checked_withheld_observation_ids: tuple[str, ...]
    source_scope_complete: bool
    source_scope_reason_codes: tuple[str, ...]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    schema_version: str = WALL_COMPONENT_COMPLETENESS_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("WallComponentCompletenessRecord is producer-owned")
        if self.status is not EvidenceResolutionStatus.CORROBORATED:
            raise ValueError("positive completeness record must be CORROBORATED")
        if not self.member_wall_ids:
            raise ValueError("component must contain at least one wall")


@dataclass(frozen=True)
class WallComponentCompletenessResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[WallComponentCompletenessRecord] = None
    schema_version: str = WALL_COMPONENT_COMPLETENESS_SCHEMA_VERSION


def _blocked(reason: str, *extras: str) -> WallComponentCompletenessResult:
    return WallComponentCompletenessResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=tuple(dict.fromkeys((reason, *extras))),
        record=None,
    )


def _point(value) -> Point:
    return (float(value[0]), float(value[1]))


def _wall_lines(record) -> tuple[Line, ...]:
    points = tuple(_point(p) for p in record.wall_candidate.centerline_pts)
    return tuple(
        (a[0], a[1], b[0], b[1])
        for a, b in zip(points, points[1:])
        if math.hypot(b[0] - a[0], b[1] - a[1]) > _COORD_TOL
    )


def _observation_line(observation) -> Optional[Line]:
    geometry = tuple(float(v) for v in tuple(observation.geometry or ()))
    if len(geometry) != 4:
        return None
    if not all(math.isfinite(v) for v in geometry):
        return None
    if math.hypot(geometry[2] - geometry[0], geometry[3] - geometry[1]) <= _COORD_TOL:
        return None
    return geometry  # type: ignore[return-value]


def _cross(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * by - ay * bx


def _orientation(a: Point, b: Point, c: Point) -> float:
    return _cross(b[0] - a[0], b[1] - a[1], c[0] - a[0], c[1] - a[1])


def _on_segment(a: Point, b: Point, p: Point, tol: float = _COORD_TOL) -> bool:
    if abs(_orientation(a, b, p)) > tol:
        return False
    return (
        min(a[0], b[0]) - tol <= p[0] <= max(a[0], b[0]) + tol
        and min(a[1], b[1]) - tol <= p[1] <= max(a[1], b[1]) + tol
    )


def _segments_intersect(left: Line, right: Line) -> bool:
    a, b = (left[0], left[1]), (left[2], left[3])
    c, d = (right[0], right[1]), (right[2], right[3])
    o1, o2 = _orientation(a, b, c), _orientation(a, b, d)
    o3, o4 = _orientation(c, d, a), _orientation(c, d, b)
    if (
        ((o1 > _COORD_TOL and o2 < -_COORD_TOL) or (o1 < -_COORD_TOL and o2 > _COORD_TOL))
        and ((o3 > _COORD_TOL and o4 < -_COORD_TOL) or (o3 < -_COORD_TOL and o4 > _COORD_TOL))
    ):
        return True
    return (
        _on_segment(a, b, c)
        or _on_segment(a, b, d)
        or _on_segment(c, d, a)
        or _on_segment(c, d, b)
    )


def _canonical_unit(line: Line) -> Optional[Point]:
    dx, dy = line[2] - line[0], line[3] - line[1]
    length = math.hypot(dx, dy)
    if length <= _COORD_TOL:
        return None
    ux, uy = dx / length, dy / length
    if ux < -_COORD_TOL or (abs(ux) <= _COORD_TOL and uy < 0.0):
        ux, uy = -ux, -uy
    return ux, uy


def _parallel(left: Line, right: Line) -> bool:
    lu, ru = _canonical_unit(left), _canonical_unit(right)
    if lu is None or ru is None:
        return False
    return abs(abs(lu[0] * ru[0] + lu[1] * ru[1]) - 1.0) <= 1e-9


def _project(point: Point, axis: Point) -> float:
    return point[0] * axis[0] + point[1] * axis[1]


def _interval(line: Line, axis: Point) -> tuple[float, float]:
    values = sorted((
        _project((line[0], line[1]), axis),
        _project((line[2], line[3]), axis),
    ))
    return values[0], values[1]


def _parallel_overlap_and_separation(left: Line, right: Line) -> Optional[tuple[float, float]]:
    if not _parallel(left, right):
        return None
    axis = _canonical_unit(left)
    if axis is None:
        return None
    liv, riv = _interval(left, axis), _interval(right, axis)
    overlap = min(liv[1], riv[1]) - max(liv[0], riv[0])
    if overlap <= _COORD_TOL:
        return None
    normal = (-axis[1], axis[0])
    separation = abs(
        (right[0] - left[0]) * normal[0]
        + (right[1] - left[1]) * normal[1]
    )
    return overlap, separation


def _collinear_snap_continuation(left: Line, right: Line) -> bool:
    if not _parallel(left, right):
        return False
    axis = _canonical_unit(left)
    if axis is None:
        return False
    normal = (-axis[1], axis[0])
    separation = abs(
        (right[0] - left[0]) * normal[0]
        + (right[1] - left[1]) * normal[1]
    )
    if separation > _COORD_TOL:
        return False
    liv, riv = _interval(left, axis), _interval(right, axis)
    if min(liv[1], riv[1]) - max(liv[0], riv[0]) >= -_COORD_TOL:
        return True
    gap = max(liv[0], riv[0]) - min(liv[1], riv[1])
    return 0.0 <= gap <= DEFAULT_GAP_SNAP_TOLERANCE_PT


def _raw_path_family(raw_id: str) -> Optional[str]:
    match = _RAW_PATH_RE.match(str(raw_id or ""))
    return None if match is None else match.group("path")


def _component_sets(records, equivalence) -> tuple[tuple[str, ...], ...]:
    by_id = {str(r.wall_candidate_id): r for r in records}
    parent = {wall_id: wall_id for wall_id in by_id}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    # Upstream positive SAME groups are physical connectivity authority.
    if equivalence is not None:
        for group in tuple(equivalence.equivalence_groups or ()):
            members = [str(x) for x in group if str(x) in by_id]
            for member in members[1:]:
                union(members[0], member)

    # Stage-A wall graph has already snapped genuine junction endpoints.
    endpoint_owners: dict[tuple[float, float], list[str]] = {}
    for wall_id, record in by_id.items():
        points = tuple(_point(p) for p in record.wall_candidate.centerline_pts)
        if not points:
            continue
        for point in (points[0], points[-1]):
            key = (round(point[0], 6), round(point[1], 6))
            endpoint_owners.setdefault(key, []).append(wall_id)
    for owners in endpoint_owners.values():
        for wall_id in owners[1:]:
            union(owners[0], wall_id)

    groups: dict[str, set[str]] = {}
    for wall_id in by_id:
        groups.setdefault(find(wall_id), set()).add(wall_id)
    return tuple(
        sorted(
            (tuple(sorted(group)) for group in groups.values()),
            key=lambda group: group,
        )
    )


def _positive_same_separations(records_by_id, equivalence) -> tuple[float, ...]:
    if equivalence is None:
        return ()
    values: list[float] = []
    pair_lookup = tuple(equivalence.pair_classifications or ())
    for left_id, right_id, raw in pair_lookup:
        if raw != PhysicalEquivalenceClass.SAME_PHYSICAL_WALL.value:
            continue
        left, right = records_by_id.get(left_id), records_by_id.get(right_id)
        if left is None or right is None:
            continue
        for left_line in _wall_lines(left):
            for right_line in _wall_lines(right):
                relation = _parallel_overlap_and_separation(left_line, right_line)
                if relation is None:
                    continue
                _overlap, separation = relation
                if separation > _COORD_TOL:
                    values.append(separation)
    return tuple(sorted(values))


def _withheld_affects_component(
    *,
    withheld_line: Line,
    withheld_raw_id: str,
    component_records,
    known_same_separations: Sequence[float],
) -> Optional[str]:
    component_lines = tuple(
        line
        for record in component_records
        for line in _wall_lines(record)
    )
    component_raw_ids = {
        str(raw_id)
        for record in component_records
        for raw_id in record.physical_identity.source_primitive_ids
    }
    withheld_family = _raw_path_family(withheld_raw_id)
    if withheld_family is not None and any(
        _raw_path_family(raw_id) == withheld_family
        for raw_id in component_raw_ids
    ):
        return WALL_COMPONENT_WITHHELD_SOURCE_PATH_RELATED

    for line in component_lines:
        if _segments_intersect(line, withheld_line) or _collinear_snap_continuation(
            line, withheld_line
        ):
            return WALL_COMPONENT_WITHHELD_SOURCE_CONTACT

    if known_same_separations:
        demonstrated_max = max(known_same_separations)
        for line in component_lines:
            relation = _parallel_overlap_and_separation(line, withheld_line)
            if relation is None:
                continue
            _overlap, separation = relation
            if _COORD_TOL < separation <= demonstrated_max + _COORD_TOL:
                return WALL_COMPONENT_WITHHELD_PLAUSIBLE_SAME_FACE
    return None


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
        wall_authority = PhysicalWallCandidateProducer.from_authenticated_viewports(
            source_visibility_producer,
            page_ids=page_ids,
        ).authority()
        visibility = source_visibility_producer.authority()
        results: dict[tuple[str, ...], WallComponentCompletenessResult] = {}

        for scope in wall_authority._scopes.values():
            if (
                scope.scope_kind != "viewport"
                or str(scope.viewport_view_type or "") != "floor_plan"
                or not scope.viewport_id
                or not scope.viewport_bbox
                or scope.status is not EvidenceResolutionStatus.CORROBORATED
                or not scope.records
            ):
                continue

            records_by_id = {
                str(record.wall_candidate_id): record for record in scope.records
            }
            components = _component_sets(scope.records, scope.equivalence)
            same_separations = _positive_same_separations(
                records_by_id,
                scope.equivalence,
            )
            withheld_ids = tuple(
                sorted(
                    set(scope.scope_boundary_observation_ids)
                    | set(scope.ambiguous_source_observation_ids)
                )
            )
            withheld: list[tuple[str, str, Line]] = []
            replay_failed = False
            for observation_id in withheld_ids:
                result = visibility.resolve_visible(
                    ObservationSelector(
                        document_id=scope.document_id,
                        revision_id=scope.revision_id,
                        source_sha256=scope.source_sha256,
                        snapshot_id=scope.snapshot_id,
                        observation_id=observation_id,
                    )
                )
                observation = result.observation
                if (
                    result.status is not EvidenceResolutionStatus.CORROBORATED
                    or observation is None
                ):
                    replay_failed = True
                    break
                line = _observation_line(observation)
                if line is None:
                    replay_failed = True
                    break
                raw_id = str(
                    getattr(observation, "source_primitive_ref", "") or ""
                )
                withheld.append((observation_id, raw_id, line))

            for members in components:
                component_records = tuple(records_by_id[wall_id] for wall_id in members)
                selector_payload = {
                    "document_id": scope.document_id,
                    "revision_id": scope.revision_id,
                    "source_sha256": scope.source_sha256,
                    "snapshot_id": scope.snapshot_id,
                    "page_id": scope.page_id,
                    "decision_scope_id": scope.decision_scope_id,
                    "member_wall_ids": members,
                }
                component_id = stable_contract_id(
                    "wall_component",
                    selector_payload,
                    digest_chars=32,
                )
                blocked_reason = None
                if replay_failed:
                    blocked_reason = WALL_COMPONENT_WITHHELD_SOURCE_UNREPLAYABLE

                if blocked_reason is None:
                    for record in component_records:
                        reason = _viewport_scope_boundary_reason(
                            record.wall_candidate,
                            bbox=scope.viewport_bbox,
                            page_width=max(scope.viewport_bbox[2], 1.0),
                            page_height=max(scope.viewport_bbox[3], 1.0),
                        )
                        if reason is not None:
                            blocked_reason = WALL_COMPONENT_MEMBER_BOUNDARY_CROPPED
                            break

                if blocked_reason is None:
                    for _obs_id, raw_id, line in withheld:
                        blocked_reason = _withheld_affects_component(
                            withheld_line=line,
                            withheld_raw_id=raw_id,
                            component_records=component_records,
                            known_same_separations=same_separations,
                        )
                        if blocked_reason is not None:
                            break

                positive_groups = ()
                if scope.equivalence is not None:
                    member_set = set(members)
                    positive_groups = tuple(
                        tuple(sorted(group))
                        for group in scope.equivalence.equivalence_groups
                        if member_set & set(group)
                    )

                member_source_ids = tuple(
                    sorted({
                        str(raw_id)
                        for record in component_records
                        for raw_id in record.physical_identity.source_primitive_ids
                    })
                )

                if blocked_reason is None:
                    record_payload = {
                        **selector_payload,
                        "component_id": component_id,
                        "member_source_primitive_ids": member_source_ids,
                        "checked_withheld_observation_ids": withheld_ids,
                    }
                    record = WallComponentCompletenessRecord(
                        record_id=stable_contract_id(
                            "wall_component_completeness",
                            record_payload,
                            digest_chars=32,
                        ),
                        document_id=scope.document_id,
                        revision_id=scope.revision_id,
                        source_sha256=scope.source_sha256,
                        snapshot_id=scope.snapshot_id,
                        page_id=scope.page_id,
                        viewport_id=scope.viewport_id,
                        decision_scope_id=scope.decision_scope_id,
                        component_id=component_id,
                        member_wall_ids=members,
                        member_source_primitive_ids=member_source_ids,
                        positive_equivalence_groups=positive_groups,
                        checked_withheld_observation_ids=withheld_ids,
                        source_scope_complete=bool(scope.scope_complete),
                        source_scope_reason_codes=tuple(scope.reason_codes),
                        status=EvidenceResolutionStatus.CORROBORATED,
                        reason_codes=(WALL_COMPONENT_COMPLETE,),
                        _seal=_RECORD_SEAL,
                    )
                    result = WallComponentCompletenessResult(
                        status=EvidenceResolutionStatus.CORROBORATED,
                        reason_codes=(WALL_COMPONENT_COMPLETE,),
                        record=record,
                    )
                else:
                    result = _blocked(blocked_reason)

                for wall_id in members:
                    key = (
                        scope.document_id,
                        scope.revision_id,
                        scope.source_sha256,
                        scope.snapshot_id,
                        scope.page_id,
                        scope.decision_scope_id,
                        wall_id,
                    )
                    results[key] = result

        return cls(results, _seal=_PRODUCER_SEAL)

    def authority(self) -> WallComponentCompletenessAuthority:
        return WallComponentCompletenessAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def published_results(self) -> tuple[WallComponentCompletenessResult, ...]:
        unique: dict[str, WallComponentCompletenessResult] = {}
        for result in self._results.values():
            if result.record is not None:
                unique[result.record.record_id] = result
        return tuple(unique[key] for key in sorted(unique))


__all__ = [
    "WALL_COMPONENT_COMPLETE",
    "WALL_COMPONENT_COMPLETENESS_SCHEMA_VERSION",
    "WALL_COMPONENT_MEMBER_BOUNDARY_CROPPED",
    "WALL_COMPONENT_UNAVAILABLE",
    "WALL_COMPONENT_VIEW_TYPE_UNSUPPORTED",
    "WALL_COMPONENT_WITHHELD_PLAUSIBLE_SAME_FACE",
    "WALL_COMPONENT_WITHHELD_SOURCE_CONTACT",
    "WALL_COMPONENT_WITHHELD_SOURCE_PATH_RELATED",
    "WALL_COMPONENT_WITHHELD_SOURCE_UNREPLAYABLE",
    "WallComponentCompletenessAuthority",
    "WallComponentCompletenessProducer",
    "WallComponentCompletenessRecord",
    "WallComponentCompletenessResult",
    "WallComponentCompletenessSelector",
]
