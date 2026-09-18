"""Producer-owned source-backed physical-wall candidate authority.

This module proves one narrow proposition only: the physical wall candidates
produced by the existing W2/W3/W4 wall pipeline for a complete exact
producer-owned visible PDF page scope.

Physical equivalence is also producer-owned here. The generic wall-identity
classifier stays fail-closed for independent provenance; this producer may
strengthen otherwise-AMBIGUOUS pair relations only when the already-reviewed
G17 source authority independently re-proves a jamb-bounded two-face opening
from the exact same immutable visible source snapshot and the six proven source
primitives map bijectively back to six W4 wall candidates. No caller-supplied
wall list, equivalence flag, completeness flag, confidence, nearest/first rule,
or geometry body can enter that proof path.

It does NOT prove opening host binding, wall role, wall height, wall thickness,
opening deductions, net wall area, FIRM/commercial publication or JobHub data.
Ordinary callers can address a scope only by lineage; they cannot supply walls,
segments, graphs, candidate lists/counts or completeness flags.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_physical_wall_identity import (
    PhysicalEquivalenceClass,
    PhysicalWallEquivalenceResolution,
    PhysicalWallIdentity,
    collect_physical_wall_identities,
    resolve_physical_wall_equivalence,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    SourceVisibilityProducer,
    classify_native_segment_visibility,
)
from pb_vector_geometry_v130 import extract_native_page
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_wall_assembly import assemble_wall_topology


PHYSICAL_WALL_CANDIDATE_AUTHORITY_SCHEMA_VERSION = "1.1.0"
PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED = "physical_wall_candidate_scope_resolved"
PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE = "physical_wall_candidate_scope_unavailable"
PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE = (
    "physical_wall_candidate_source_integrity_failure"
)
PHYSICAL_WALL_CANDIDATE_IDENTITY_UNRESOLVED = (
    "physical_wall_candidate_identity_unresolved"
)
PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_BOUNDARY = (
    "physical_wall_candidate_scope_cropped_at_boundary"
)

# A dangling end counts as "at the page edge" only when it lies essentially
# exactly on it -- this is the page's own coordinate boundary, not a
# proximity heuristic tuned against any drawing.
_PAGE_BOUNDARY_TOL_PT = 0.5

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_COORD_TOL = 1e-6
_PARALLEL_REL_TOL = 1e-9
Point = tuple[float, float]
Line = tuple[float, float, float, float]


@dataclass(frozen=True)
class PhysicalWallCandidateSelector:
    """Consumer addressing only; never a caller-authored wall universe."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str


@dataclass(frozen=True)
class PhysicalWallCandidateRecord:
    wall_candidate_id: str
    wall_candidate: WallCandidate
    physical_identity: PhysicalWallIdentity
    schema_version: str = PHYSICAL_WALL_CANDIDATE_AUTHORITY_SCHEMA_VERSION


@dataclass(frozen=True)
class PhysicalWallCandidateScopeResult:
    status: EvidenceResolutionStatus
    scope_complete: bool
    records: tuple[PhysicalWallCandidateRecord, ...]
    source_observation_ids: tuple[str, ...]
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    reason_codes: tuple[str, ...]
    equivalence: Optional[PhysicalWallEquivalenceResolution] = None
    proposition: Optional[str] = None
    schema_version: str = PHYSICAL_WALL_CANDIDATE_AUTHORITY_SCHEMA_VERSION


@dataclass(frozen=True)
class _ScopeKey:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str


@dataclass(frozen=True)
class _TrustedFaceBreak:
    first_raw_id: str
    second_raw_id: str
    gap_start: float
    gap_end: float
    start_point: Point
    end_point: Point
    direction: Point


def _decision_scope_id(page_id: str) -> str:
    return f"wall-source:page-{str(page_id)}"


def _blocked(selector: PhysicalWallCandidateSelector, reason: str) -> PhysicalWallCandidateScopeResult:
    return PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        scope_complete=False,
        records=(),
        source_observation_ids=(),
        document_id=str(selector.document_id),
        revision_id=str(selector.revision_id),
        source_sha256=str(selector.source_sha256),
        snapshot_id=str(selector.snapshot_id),
        page_id=str(selector.page_id),
        decision_scope_id=str(selector.decision_scope_id),
        reason_codes=(reason,),
    )


def _source_page_segments(
    *,
    source_producer: SourceVisibilityProducer,
    published,
    source_bytes: bytes,
    page_id: str,
    decision_scope_id: str,
) -> tuple[list[dict], tuple[str, ...], float, float]:
    """Rebuild W2 inputs from exact bytes and exact receipted visible membership.

    Also returns the page's own (width, height) in points, so callers can
    determine whether a wall's dangling end actually terminates inside the
    drawing (a real wall end) or merely at the page edge (the wall's true
    continuation is unknown -- it may simply be cropped by this sheet).
    """

    visibility = source_producer.authority()
    visible_by_raw_id: dict[str, tuple[str, tuple[float, ...]]] = {}
    page_visible_ids: list[str] = []

    for observation_id in published.visible_observation_ids:
        result = visibility.resolve_visible(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        observation = result.observation
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or observation is None
        ):
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        if observation.page_id != page_id:
            continue
        prefix = "visible:segment:"
        if not observation.source_primitive_ref.startswith(prefix):
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        raw_id = observation.source_primitive_ref[len(prefix) :]
        if not raw_id or raw_id in visible_by_raw_id:
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        visible_by_raw_id[raw_id] = (
            observation_id,
            tuple(float(value) for value in observation.geometry),
        )
        page_visible_ids.append(observation_id)

    try:
        page_number = int(page_id)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE) from exc
    if page_number < 1:
        raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)

    pdf = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        if page_number > int(pdf.page_count):
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        native = extract_native_page(pdf.load_page(page_number - 1))
    finally:
        pdf.close()

    segments: list[dict] = []
    native_visible_ids: set[str] = set()
    for source_segment in native.get("segments") or ():
        decision = classify_native_segment_visibility(source_segment)
        if not decision.visible:
            continue
        raw_id = str(source_segment.get("id") or "").strip()
        if not raw_id:
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        expected = visible_by_raw_id.get(raw_id)
        if expected is None:
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        observation_id, observation_geometry = expected
        geometry = (
            float(source_segment["x1"]),
            float(source_segment["y1"]),
            float(source_segment["x2"]),
            float(source_segment["y2"]),
        )
        if tuple(geometry) != tuple(observation_geometry):
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        native_visible_ids.add(observation_id)
        segment = dict(source_segment)
        segment["document_id"] = published.revision.document_id
        segment["page_id"] = page_id
        segment["viewport_id"] = decision_scope_id
        segments.append(segment)

    if native_visible_ids != set(page_visible_ids):
        raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)

    return (
        segments,
        tuple(sorted(page_visible_ids)),
        float(native["width"]),
        float(native["height"]),
    )


def _wall_touches_page_boundary(
    wall: WallCandidate, *, page_width: float, page_height: float
) -> bool:
    """True when a genuinely dangling end of this wall lies on the page's
    own edge rather than terminating inside the drawing.

    A wall end classified ``JunctionType.ENDPOINT`` (not connected to any
    other wall) whose coordinate sits on the page boundary is not proven to
    actually end there -- the drawing may simply be cropped by this sheet,
    with the wall's true continuation on an adjoining sheet or off-page. An
    end that meets another wall (any other junction type) is a real,
    resolved terminus regardless of its position on the page.
    """
    if not wall.centerline_pts or len(wall.centerline_pts) < 2:
        return False
    if len(wall.junction_types) != 2:
        return False
    ends = (
        (wall.centerline_pts[0], wall.junction_types[0]),
        (wall.centerline_pts[-1], wall.junction_types[1]),
    )
    for (x, y), junction_type in ends:
        if junction_type != JunctionType.ENDPOINT:
            continue
        if (
            x <= _PAGE_BOUNDARY_TOL_PT
            or y <= _PAGE_BOUNDARY_TOL_PT
            or x >= page_width - _PAGE_BOUNDARY_TOL_PT
            or y >= page_height - _PAGE_BOUNDARY_TOL_PT
        ):
            return True
    return False


def _line(values: Sequence[float]) -> Optional[Line]:
    if len(values) != 4:
        return None
    try:
        line = tuple(float(value) for value in values)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in line):
        return None
    if math.hypot(line[2] - line[0], line[3] - line[1]) <= _COORD_TOL:
        return None
    return line  # type: ignore[return-value]


def _canonical_direction(line: Line) -> Point:
    dx, dy = line[2] - line[0], line[3] - line[1]
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    if ux < -_COORD_TOL or (abs(ux) <= _COORD_TOL and uy < 0.0):
        ux, uy = -ux, -uy
    return (ux, uy)


def _projection(point: Point, direction: Point) -> float:
    return point[0] * direction[0] + point[1] * direction[1]


def _cross(left: Point, right: Point) -> float:
    return left[0] * right[1] - left[1] * right[0]


def _parallel(left: Line, right: Line) -> bool:
    ldx, ldy = left[2] - left[0], left[3] - left[1]
    rdx, rdy = right[2] - right[0], right[3] - right[1]
    llen = math.hypot(ldx, ldy)
    rlen = math.hypot(rdx, rdy)
    return abs(ldx * rdy - ldy * rdx) <= _PARALLEL_REL_TOL * llen * rlen


def _collinear(left: Line, right: Line) -> bool:
    if not _parallel(left, right):
        return False
    direction = _canonical_direction(left)
    return abs(
        _cross(direction, (right[0] - left[0], right[1] - left[1]))
    ) <= _COORD_TOL


def _endpoint_at_projection(line: Line, direction: Point, target: float) -> Optional[Point]:
    for point in ((line[0], line[1]), (line[2], line[3])):
        if abs(_projection(point, direction) - target) <= _COORD_TOL:
            return point
    return None


def _trusted_face_break(
    first_raw_id: str,
    first_line: Line,
    second_raw_id: str,
    second_line: Line,
) -> Optional[_TrustedFaceBreak]:
    if not _collinear(first_line, second_line):
        return None
    direction = _canonical_direction(first_line)
    first_values = sorted(
        (_projection((first_line[0], first_line[1]), direction),
         _projection((first_line[2], first_line[3]), direction))
    )
    second_values = sorted(
        (_projection((second_line[0], second_line[1]), direction),
         _projection((second_line[2], second_line[3]), direction))
    )
    if first_values[0] <= second_values[0]:
        left_id, left_line, left_values = first_raw_id, first_line, first_values
        right_id, right_line, right_values = second_raw_id, second_line, second_values
    else:
        left_id, left_line, left_values = second_raw_id, second_line, second_values
        right_id, right_line, right_values = first_raw_id, first_line, first_values
    gap_start, gap_end = left_values[1], right_values[0]
    if gap_end - gap_start <= _COORD_TOL:
        return None
    start_point = _endpoint_at_projection(left_line, direction, gap_start)
    end_point = _endpoint_at_projection(right_line, direction, gap_end)
    if start_point is None or end_point is None:
        return None
    return _TrustedFaceBreak(
        first_raw_id=left_id,
        second_raw_id=right_id,
        gap_start=gap_start,
        gap_end=gap_end,
        start_point=start_point,
        end_point=end_point,
        direction=direction,
    )


def _same_gap(left: _TrustedFaceBreak, right: _TrustedFaceBreak) -> bool:
    if abs(left.gap_start - right.gap_start) > _COORD_TOL:
        return False
    if abs(left.gap_end - right.gap_end) > _COORD_TOL:
        return False
    dot = left.direction[0] * right.direction[0] + left.direction[1] * right.direction[1]
    return abs(abs(dot) - 1.0) <= _PARALLEL_REL_TOL


def _distinct_parallel_axes(left: _TrustedFaceBreak, right: _TrustedFaceBreak) -> bool:
    delta = (
        right.start_point[0] - left.start_point[0],
        right.start_point[1] - left.start_point[1],
    )
    return abs(_cross(left.direction, delta)) > _COORD_TOL


def _segment_matches(line: Line, first: Point, second: Point) -> bool:
    start = (line[0], line[1])
    end = (line[2], line[3])
    direct = (
        abs(start[0] - first[0]) <= _COORD_TOL
        and abs(start[1] - first[1]) <= _COORD_TOL
        and abs(end[0] - second[0]) <= _COORD_TOL
        and abs(end[1] - second[1]) <= _COORD_TOL
    )
    reverse = (
        abs(start[0] - second[0]) <= _COORD_TOL
        and abs(start[1] - second[1]) <= _COORD_TOL
        and abs(end[0] - first[0]) <= _COORD_TOL
        and abs(end[1] - first[1]) <= _COORD_TOL
    )
    return direct or reverse


def _opening_raw_relation_sets(
    raw_lines: Mapping[str, Line],
) -> dict[tuple[str, str], set[PhysicalEquivalenceClass]]:
    """Derive relations only for a complete six-primitive G17 opening pattern."""
    if len(raw_lines) != 6:
        return {}
    items = sorted(raw_lines.items())
    breaks: list[_TrustedFaceBreak] = []
    for index, (left_id, left_line) in enumerate(items):
        for right_id, right_line in items[index + 1 :]:
            candidate = _trusted_face_break(left_id, left_line, right_id, right_line)
            if candidate is not None:
                breaks.append(candidate)

    relation_sets: dict[tuple[str, str], set[PhysicalEquivalenceClass]] = {}
    all_ids = set(raw_lines)
    for index, first in enumerate(breaks):
        for second in breaks[index + 1 :]:
            if not _same_gap(first, second) or not _distinct_parallel_axes(first, second):
                continue
            face_ids = {
                first.first_raw_id,
                first.second_raw_id,
                second.first_raw_id,
                second.second_raw_id,
            }
            if len(face_ids) != 4:
                continue
            remaining = sorted(all_ids - face_ids)
            if len(remaining) != 2:
                continue
            start_matches = [
                raw_id
                for raw_id in remaining
                if _segment_matches(
                    raw_lines[raw_id], first.start_point, second.start_point
                )
            ]
            end_matches = [
                raw_id
                for raw_id in remaining
                if _segment_matches(
                    raw_lines[raw_id], first.end_point, second.end_point
                )
            ]
            if len(start_matches) != 1 or len(end_matches) != 1:
                continue
            if start_matches[0] == end_matches[0]:
                continue

            same_pairs = {
                tuple(sorted((first.first_raw_id, second.first_raw_id))),
                tuple(sorted((first.second_raw_id, second.second_raw_id))),
            }
            pattern_ids = sorted(face_ids | {start_matches[0], end_matches[0]})
            if len(pattern_ids) != 6:
                continue
            for left_index, left_id in enumerate(pattern_ids):
                for right_id in pattern_ids[left_index + 1 :]:
                    pair = tuple(sorted((left_id, right_id)))
                    classification = (
                        PhysicalEquivalenceClass.SAME_PHYSICAL_WALL
                        if pair in same_pairs
                        else PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS
                    )
                    relation_sets.setdefault(pair, set()).add(classification)
    return relation_sets


def _producer_opening_relation_overrides(
    *,
    source_producer: SourceVisibilityProducer,
    published,
    page_id: str,
    records: Sequence[PhysicalWallCandidateRecord],
) -> dict[tuple[str, str], PhysicalEquivalenceClass]:
    """Re-prove G17 source openings and map their exact primitives to W4 candidates."""
    visibility = source_producer.authority()
    opening_authority = PhysicalOpeningAuthority(visibility)
    proven_records: dict[str, object] = {}

    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = opening_authority.prove_existence(selector)
        existence = result.existence_record
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and existence is not None
            and existence.page_id == page_id
        ):
            proven_records[existence.record_id] = existence

    by_raw_id: dict[str, list[PhysicalWallCandidateRecord]] = {}
    for record in records:
        for raw_id in record.physical_identity.source_primitive_ids:
            by_raw_id.setdefault(str(raw_id), []).append(record)

    candidate_relation_sets: dict[
        tuple[str, str], set[PhysicalEquivalenceClass]
    ] = {}
    prefix = "visible:segment:"

    for existence in proven_records.values():
        raw_lines: dict[str, Line] = {}
        valid = True
        for observation_id in existence.source_observation_ids:  # type: ignore[attr-defined]
            resolved = visibility.resolve_visible(
                ObservationSelector(
                    document_id=existence.document_id,  # type: ignore[attr-defined]
                    revision_id=existence.revision_id,  # type: ignore[attr-defined]
                    source_sha256=existence.source_sha256,  # type: ignore[attr-defined]
                    snapshot_id=existence.snapshot_id,  # type: ignore[attr-defined]
                    observation_id=observation_id,
                )
            )
            observation = resolved.observation
            if (
                resolved.status is not EvidenceResolutionStatus.CORROBORATED
                or observation is None
                or not observation.source_primitive_ref.startswith(prefix)
            ):
                valid = False
                break
            raw_id = observation.source_primitive_ref[len(prefix) :]
            geometry = _line(observation.geometry)
            if not raw_id or geometry is None or raw_id in raw_lines:
                valid = False
                break
            raw_lines[raw_id] = geometry
        if not valid or len(raw_lines) != 6:
            continue

        raw_relations = _opening_raw_relation_sets(raw_lines)
        if not raw_relations:
            continue

        candidate_for_raw: dict[str, str] = {}
        for raw_id in raw_lines:
            matches = by_raw_id.get(raw_id, [])
            if len(matches) != 1:
                valid = False
                break
            candidate_for_raw[raw_id] = matches[0].wall_candidate_id
        if not valid or len(set(candidate_for_raw.values())) != 6:
            continue

        for (left_raw, right_raw), classifications in raw_relations.items():
            left_id = candidate_for_raw[left_raw]
            right_id = candidate_for_raw[right_raw]
            if left_id == right_id:
                valid = False
                break
            pair = tuple(sorted((left_id, right_id)))
            candidate_relation_sets.setdefault(pair, set()).update(classifications)
        if not valid:
            continue

    return {
        pair: next(iter(classifications))
        for pair, classifications in candidate_relation_sets.items()
        if len(classifications) == 1
    }


def _union_find_groups(
    pairs: Sequence[tuple[str, str]], members: Sequence[str]
) -> list[list[str]]:
    parent = {member: member for member in members}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for left, right in pairs:
        if left in parent and right in parent:
            union(left, right)
    groups: dict[str, list[str]] = {}
    for member in members:
        groups.setdefault(find(member), []).append(member)
    return [sorted(group) for group in groups.values()]


def _apply_trusted_relation_overrides(
    identities: Sequence[PhysicalWallIdentity],
    baseline: PhysicalWallEquivalenceResolution,
    overrides: Mapping[tuple[str, str], PhysicalEquivalenceClass],
) -> PhysicalWallEquivalenceResolution:
    """Reconcile source-proven relations without changing generic classifier semantics."""
    usable = [identity for identity in identities if identity.usable]
    if len(usable) != len(identities) or not overrides:
        return baseline

    pair_map = {
        tuple(sorted((left, right))): classification
        for left, right, classification in baseline.pair_classifications
    }
    for pair, classification in overrides.items():
        current = pair_map.get(tuple(sorted(pair)))
        if current == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value:
            pair_map[tuple(sorted(pair))] = classification.value

    member_ids = [identity.wall_candidate_id for identity in usable]
    same_links: list[tuple[str, str]] = []
    ambiguous_links: list[tuple[str, str]] = []
    for pair, classification in pair_map.items():
        if classification == PhysicalEquivalenceClass.SAME_PHYSICAL_WALL.value:
            same_links.append(pair)
        elif classification == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value:
            ambiguous_links.append(pair)

    related_links = same_links + ambiguous_links
    components = _union_find_groups(related_links, member_ids) if member_ids else []
    ambiguous_edges = {frozenset(pair) for pair in ambiguous_links}
    same_edges = {frozenset(pair) for pair in same_links}
    blockers: dict[str, list[str]] = {}
    ambiguous_walls: set[str] = set()
    same_groups: list[tuple[str, ...]] = []
    representatives: list[str] = []

    for component in components:
        has_ambiguous = any(
            frozenset((left, right)) in ambiguous_edges
            for index, left in enumerate(component)
            for right in component[index + 1 :]
        )
        has_same = any(
            frozenset((left, right)) in same_edges
            for index, left in enumerate(component)
            for right in component[index + 1 :]
        )
        if has_ambiguous:
            ambiguous_walls.update(component)
            for wall_id in component:
                blockers.setdefault(wall_id, []).append(
                    "ambiguous_physical_wall_equivalence"
                )
            continue
        if has_same and len(component) > 1:
            group = tuple(sorted(component))
            same_groups.append(group)
            representative = sorted(group)[0]
            representatives.append(representative)
            for wall_id in group:
                if wall_id != representative:
                    blockers.setdefault(wall_id, []).append(
                        f"equivalent_physical_wall_represented_by:{representative}"
                    )
            continue
        representatives.extend(
            wall_id for wall_id in component if wall_id not in blockers
        )

    linked = {wall_id for component in components for wall_id in component}
    for wall_id in member_ids:
        if wall_id not in linked and wall_id not in blockers:
            representatives.append(wall_id)

    representatives = list(dict.fromkeys(representatives))
    abstained = [wall_id for wall_id in member_ids if wall_id in blockers]
    return PhysicalWallEquivalenceResolution(
        scope_viewport_id=baseline.scope_viewport_id,
        representative_wall_ids=tuple(representatives),
        abstained_wall_ids=tuple(dict.fromkeys(abstained)),
        equivalence_groups=tuple(same_groups),
        ambiguous_wall_ids=tuple(sorted(ambiguous_walls)),
        same_wall_ids=tuple(
            sorted({wall_id for group in same_groups for wall_id in group})
        ),
        pair_classifications=tuple(
            sorted((left, right, classification) for (left, right), classification in pair_map.items())
        ),
        blocking_reasons_by_wall_id={
            wall_id: tuple(dict.fromkeys(reasons))
            for wall_id, reasons in blockers.items()
            if reasons
        },
    )


def _build_scope_result(
    *,
    source_producer: SourceVisibilityProducer,
    published,
    source_bytes: bytes,
    page_id: str,
) -> PhysicalWallCandidateScopeResult:
    scope_id = _decision_scope_id(page_id)
    selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        decision_scope_id=scope_id,
    )

    page_number = int(page_id)
    if (
        published.coverage.state != "complete"
        or published.coverage.failed_pages
        or page_number not in published.coverage.decoded_pages
    ):
        return _blocked(selector, PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE)

    segments, source_observation_ids, page_width, page_height = _source_page_segments(
        source_producer=source_producer,
        published=published,
        source_bytes=source_bytes,
        page_id=page_id,
        decision_scope_id=scope_id,
    )

    graph = build_wall_graph_for_viewport(segments)
    junctions, relationships = classify_junctions(
        graph,
        document_id=published.revision.document_id,
        page_id=page_id,
        viewport_id=scope_id,
    )
    walls, _rekeyed_junctions = assemble_wall_topology(
        graph,
        junctions,
        relationships,
        viewport_id=scope_id,
    )
    identities = collect_physical_wall_identities(walls, graph)

    ordered_walls = sorted(walls, key=lambda item: item.candidate_id)
    records: list[PhysicalWallCandidateRecord] = []
    ordered_identities: list[PhysicalWallIdentity] = []
    for wall in ordered_walls:
        identity = identities.get(wall.candidate_id)
        if identity is None or not identity.usable:
            return _blocked(selector, PHYSICAL_WALL_CANDIDATE_IDENTITY_UNRESOLVED)
        records.append(
            PhysicalWallCandidateRecord(
                wall_candidate_id=wall.candidate_id,
                wall_candidate=wall,
                physical_identity=identity,
            )
        )
        ordered_identities.append(identity)

    baseline_equivalence = resolve_physical_wall_equivalence(
        tuple(ordered_identities),
        walls_by_id={wall.candidate_id: wall for wall in ordered_walls},
    )
    trusted_overrides = _producer_opening_relation_overrides(
        source_producer=source_producer,
        published=published,
        page_id=page_id,
        records=tuple(records),
    )
    equivalence = _apply_trusted_relation_overrides(
        tuple(ordered_identities),
        baseline_equivalence,
        trusted_overrides,
    )

    cropped = any(
        _wall_touches_page_boundary(wall, page_width=page_width, page_height=page_height)
        for wall in ordered_walls
    )
    reason_codes = (
        (PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED, PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_BOUNDARY)
        if cropped
        else (PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,)
    )

    return PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=not cropped,
        records=tuple(records),
        source_observation_ids=source_observation_ids,
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        decision_scope_id=scope_id,
        reason_codes=reason_codes,
        equivalence=equivalence,
        proposition=PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
    )


class PhysicalWallCandidateProducer:
    """Trusted writer derived only from an already-ingested visibility producer."""

    def __init__(self, scopes: Mapping[_ScopeKey, PhysicalWallCandidateScopeResult], *, _seal=None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "PhysicalWallCandidateProducer must be obtained from "
                "from_source_visibility_producer()"
            )
        self._scopes = MappingProxyType(dict(scopes))

    @classmethod
    def from_source_visibility_producer(cls, source_visibility_producer):
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError(
                "source_visibility_producer must be an actual SourceVisibilityProducer"
            )

        published_by_revision = dict(source_visibility_producer._published_by_revision)
        store = source_visibility_producer._producer._store
        scopes: dict[_ScopeKey, PhysicalWallCandidateScopeResult] = {}

        for revision_id, published in sorted(published_by_revision.items()):
            if source_visibility_producer._producer.current_revision_id(
                published.revision.document_id
            ) != revision_id:
                continue
            source_bytes = store.source_bytes_by_revision.get(revision_id)
            if source_bytes is None:
                raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
            digest = hashlib.sha256(source_bytes).hexdigest()
            if digest != published.revision.source_sha256:
                raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)

            for page_number in published.coverage.decoded_pages:
                page_id = str(page_number)
                result = _build_scope_result(
                    source_producer=source_visibility_producer,
                    published=published,
                    source_bytes=source_bytes,
                    page_id=page_id,
                )
                key = _ScopeKey(
                    document_id=result.document_id,
                    revision_id=result.revision_id,
                    source_sha256=result.source_sha256,
                    snapshot_id=result.snapshot_id,
                    page_id=result.page_id,
                    decision_scope_id=result.decision_scope_id,
                )
                scopes[key] = result

        return cls(scopes, _seal=_PRODUCER_SEAL)

    def authority(self):
        return PhysicalWallCandidateAuthority(self._scopes, _seal=_AUTHORITY_SEAL)


class PhysicalWallCandidateAuthority:
    """Read-only exact-scope resolver. Construction is producer-sealed."""

    def __init__(self, scopes: Mapping[_ScopeKey, PhysicalWallCandidateScopeResult], *, _seal=None) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError(
                "PhysicalWallCandidateAuthority must be obtained from "
                "PhysicalWallCandidateProducer.authority()"
            )
        self._scopes = MappingProxyType(dict(scopes))

    def resolve_scope(self, selector):
        if not isinstance(selector, PhysicalWallCandidateSelector):
            raise TypeError("selector must be PhysicalWallCandidateSelector")

        if selector.decision_scope_id != _decision_scope_id(selector.page_id):
            return _blocked(selector, PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE)

        key = _ScopeKey(
            document_id=str(selector.document_id),
            revision_id=str(selector.revision_id),
            source_sha256=str(selector.source_sha256),
            snapshot_id=str(selector.snapshot_id),
            page_id=str(selector.page_id),
            decision_scope_id=str(selector.decision_scope_id),
        )
        result = self._scopes.get(key)
        if result is None:
            return _blocked(selector, PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE)
        return result


__all__ = [
    "PHYSICAL_WALL_CANDIDATE_AUTHORITY_SCHEMA_VERSION",
    "PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_BOUNDARY",
    "PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED",
    "PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE",
    "PhysicalWallCandidateAuthority",
    "PhysicalWallCandidateProducer",
    "PhysicalWallCandidateRecord",
    "PhysicalWallCandidateScopeResult",
    "PhysicalWallCandidateSelector",
]
