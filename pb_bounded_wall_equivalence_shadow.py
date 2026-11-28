"""Default-off experiment (MAX 7240613240): bounded physical-wall equivalence.

The baseline abstains a whole connected component when any pair in it is ambiguous, and without a trusted scale
every parallel overlapping pair competes, so one component can hold most of a sheet. This rule releases an
ambiguity-only abstention only when a wall body the drawing itself paints owns the wall and no DIRECT competitor
exists. A competitor is direct when it shares a source primitive, lies in another viewport or level,
is not straight, or claims the same stretch of wall (overlaps along it) while coming within the two bodies' combined
thickness (an unowned competitor counts the wall's own thickness twice). Walls owned by one body over the same
stretch are its faces or copies: one representative at most, with those pairs recorded as the same wall. Typed
non-wall candidates (floor-grid lattice) neither compete nor get released. Walls without a body, with several bodies
or from rasters stay abstained, and nothing is ever demoted. See
docs/engineering/claude_bounded_wall_equivalence_note_20261129.md.
"""
from __future__ import annotations

import math
from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import Any

from pb_layered_wall_doorway_room_ring_shadow import (
    _collect_dark_painted_source_wall_strips,
    _collect_merged_collinear_dark_face_strips,
    _collect_strips,
    _collect_stroke_pair_strips,
)
from pb_physical_wall_identity import (
    _EQUIVALENCE_LATERAL_TOL_PT,
    PhysicalEquivalenceClass,
    PhysicalWallEquivalenceResolution,
    PhysicalWallIdentity,
    _deterministic_representative,
)

BOUNDED_EQUIVALENCE_VERSION = "bounded-wall-equivalence-1.0.0"
AMBIGUITY_BLOCKER = "ambiguous_physical_wall_equivalence"
RELEASED = "released_body_owned_without_direct_competitor"
KEPT_DIRECT = "direct_competitor"
KEPT_NO_BODY = "no_owning_source_body"
KEPT_SEVERAL_BODIES = "several_owning_source_bodies"
KEPT_SAME = "has_same_wall_relation"
KEPT_OTHER = "other_blocker"
KEPT_NON_WALL = "typed_non_wall"
KEPT_PARTIAL_FACES = "body_faces_cover_different_stretches"
KEPT_PUBLISHED_FACE = "body_stretch_already_published"
COVERED_FACE = "covered_by_released_representative"
_TOL = _EQUIVALENCE_LATERAL_TOL_PT
_COVER = 0.9


@dataclass(frozen=True)
class SourceWallBody:
    horizontal: bool
    along: tuple[float, float]
    across: tuple[float, float]
    path_indices: frozenset[int]

    @property
    def thickness(self) -> float:
        return self.across[1] - self.across[0]


def source_wall_bodies(drawings: Sequence[Any]) -> tuple[SourceWallBody, ...]:
    """Distinct paired or filled wall bodies painted by the page (the layered builder's own collectors)."""
    strips = (list(_collect_strips(drawings)[0]) + _collect_dark_painted_source_wall_strips(drawings)
              + _collect_stroke_pair_strips(drawings) + _collect_merged_collinear_dark_face_strips(drawings))
    grouped: dict[tuple, list] = {}
    for strip in strips:
        horizontal = bool(strip.horizontal)
        along = (strip.x0, strip.x1) if horizontal else (strip.y0, strip.y1)
        across = (strip.y0, strip.y1) if horizontal else (strip.x0, strip.x1)
        key = (horizontal, round(across[0], 1), round(across[1], 1))
        grouped.setdefault(key, []).append((along, across, frozenset(strip.native_path_indices())))
    bodies = []
    for (horizontal, _c0, _c1), members in sorted(grouped.items()):
        members.sort(key=lambda m: (m[0], sorted(m[2])))
        merged: list[list] = []
        for along, across, paths in members:
            if merged and along[0] <= merged[-1][0][1] + _TOL:
                last = merged[-1]
                last[0] = (last[0][0], max(last[0][1], along[1]))
                last[2] = last[2] | paths
            else:
                merged.append([along, across, paths])
        bodies += [SourceWallBody(horizontal, along, across, paths) for along, across, paths in merged]
    return tuple(bodies)


def _straight(path: Sequence[Sequence[float]] | None) -> tuple[bool, float, float, float] | None:
    """(horizontal, line position, along start, along end) of an axis-aligned straight path."""
    if not path or len(path) < 2:
        return None
    xs, ys = [float(p[0]) for p in path], [float(p[1]) for p in path]
    if max(ys) - min(ys) <= _TOL < max(xs) - min(xs):
        return True, sum(ys) / len(ys), min(xs), max(xs)
    if max(xs) - min(xs) <= _TOL < max(ys) - min(ys):
        return False, sum(xs) / len(xs), min(ys), max(ys)
    return None


def _paths_of(identity: PhysicalWallIdentity) -> set[int] | None:
    found = set()
    for primitive in identity.source_primitive_ids:
        head = str(primitive)
        digits = head[1:].split("i", 1)[0] if head.startswith("d") else ""
        if not digits.isdigit():
            return None
        found.add(int(digits))
    return found or None


def _owners(identity: PhysicalWallIdentity, bodies: Sequence[SourceWallBody]) -> list[SourceWallBody]:
    line = _straight(identity.path_fingerprint)
    paths = _paths_of(identity)
    if line is None or paths is None:
        return []
    horizontal, position, start, end = line
    return [b for b in bodies if b.horizontal == horizontal and b.across[0] - _TOL <= position <= b.across[1] + _TOL
            and min(end, b.along[1]) - max(start, b.along[0]) >= _COVER * (end - start) and paths <= b.path_indices]


def _gap(low: float, high: float, other_low: float, other_high: float) -> float:
    return max(0.0, max(low, other_low) - min(high, other_high))


def _direct(wall: PhysicalWallIdentity, body: SourceWallBody, other: PhysicalWallIdentity,
            other_body: SourceWallBody | None) -> bool:
    if set(wall.source_primitive_ids) & set(other.source_primitive_ids):
        return True
    if wall.viewport_id != other.viewport_id or (wall.level_id or "") != (other.level_id or ""):
        return True
    line, other_line = _straight(wall.path_fingerprint), _straight(other.path_fingerprint)
    if line is None or other_line is None:
        return True
    horizontal, _position, start, end = line
    other_horizontal, other_position, other_start, other_end = other_line
    if other_horizontal != horizontal or min(end, other_end) - max(start, other_start) <= _TOL:
        return False  # no stretch of this wall is claimed twice
    if other_body is None:
        reach, gap = 2.0 * body.thickness, _gap(*body.across, other_position, other_position)
    else:
        reach, gap = body.thickness + other_body.thickness, _gap(*body.across, *other_body.across)
    return gap <= reach + _TOL


def _stretch(identity: PhysicalWallIdentity) -> tuple[float, float]:
    line = _straight(identity.path_fingerprint)
    return (line[2], line[3]) if line else (0.0, 0.0)


def _overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return min(a[1], b[1]) - max(a[0], b[0])


def _face_clusters(members: Sequence[str], by_id) -> list[list[str]]:
    """Walls on one body that claim a common stretch of it."""
    ordered = sorted(members, key=lambda w: (_stretch(by_id[w]), w))
    clusters: list[list[str]] = []
    reach = -math.inf
    for wall_id in ordered:
        start, end = _stretch(by_id[wall_id])
        if clusters and start < reach - _TOL:
            clusters[-1].append(wall_id)
            reach = max(reach, end)
        else:
            clusters.append([wall_id])
            reach = end
    return [sorted(c) for c in clusters]


def _same_stretch(cluster: Sequence[str], by_id) -> bool:
    spans = [_stretch(by_id[w]) for w in cluster]
    return all(_overlap(a, b) >= _COVER * max(a[1] - a[0], b[1] - b[0]) for a in spans for b in spans)


def release_bounded_equivalence(
    identities: Sequence[PhysicalWallIdentity | None],
    equivalence: PhysicalWallEquivalenceResolution,
    bodies: Sequence[SourceWallBody],
    *,
    typed_non_wall_ids: Collection[str] = (),
) -> tuple[PhysicalWallEquivalenceResolution, dict[str, int], tuple[str, ...]]:
    """(resolution with one representative per free body stretch added, counts by outcome, released ids).

    Walls owned by one body that claim the same stretch are its faces (or copies): at most one of them is released,
    chosen by the existing deterministic representative rule, and the others are recorded as represented by it.
    """
    by_id = {i.wall_candidate_id: i for i in identities if i is not None}
    non_wall = set(typed_non_wall_ids)
    owners = {wall_id: _owners(identity, bodies) for wall_id, identity in by_id.items() if identity.usable}
    partners: dict[str, set[str]] = {}
    same: dict[str, set[str]] = {}
    for left, right, classification in equivalence.pair_classifications:
        target = (partners if classification == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value
                  else same if classification == PhysicalEquivalenceClass.SAME_PHYSICAL_WALL.value else None)
        if target is not None:
            target.setdefault(left, set()).add(right)
            target.setdefault(right, set()).add(left)
    abstained = set(equivalence.abstained_wall_ids)
    published = set(equivalence.representative_wall_ids)

    def ambiguity_only(wall_id: str) -> bool:
        return (wall_id in abstained and by_id[wall_id].usable
                and set(equivalence.blockers_for(wall_id)) == {AMBIGUITY_BLOCKER})

    counts: dict[str, int] = {}

    def count(outcome: str, number: int = 1) -> None:
        if number:
            counts[outcome] = counts.get(outcome, 0) + number

    grouped: dict[SourceWallBody, list[str]] = {}
    for wall_id in sorted(by_id):
        if wall_id not in non_wall and len(owners.get(wall_id, ())) == 1:
            grouped.setdefault(owners[wall_id][0], []).append(wall_id)
    for wall_id in sorted(abstained):
        if wall_id not in by_id or not ambiguity_only(wall_id):
            count(KEPT_OTHER)
        elif wall_id in non_wall:
            count(KEPT_NON_WALL)
        elif len(owners[wall_id]) != 1:
            count(KEPT_SEVERAL_BODIES if owners[wall_id] else KEPT_NO_BODY)

    released: dict[str, list[str]] = {}
    for body, members in sorted(grouped.items(), key=lambda item: (item[0].horizontal, item[0].across, item[0].along)):
        for cluster in _face_clusters(members, by_id):
            waiting = sum(1 for w in cluster if ambiguity_only(w))
            if not waiting:
                continue
            inside = set(cluster)
            if inside & published:
                outcome = KEPT_PUBLISHED_FACE
            elif not all(ambiguity_only(w) for w in cluster):
                outcome = KEPT_OTHER
            elif not _same_stretch(cluster, by_id):
                outcome = KEPT_PARTIAL_FACES
            elif any(same.get(w, set()) - inside for w in cluster):
                outcome = KEPT_SAME
            elif any(
                    other not in non_wall and (
                        other not in by_id or not by_id[other].usable
                        or _direct(by_id[w], body, by_id[other],
                                   owners[other][0] if len(owners.get(other, ())) == 1 else None))
                    for w in cluster for other in partners.get(w, set()) - inside):
                outcome = KEPT_DIRECT
            else:
                released[_deterministic_representative(cluster)] = cluster
                count(RELEASED)
                count(COVERED_FACE, len(cluster) - 1)
                continue
            count(outcome, waiting)
    if not released:
        return equivalence, counts, ()
    reps = set(released)
    members = {w for cluster in released.values() for w in cluster}
    pair_set = {frozenset((a, b)) for cluster in released.values() for a in cluster for b in cluster if a != b}
    blockers = {w: r for w, r in equivalence.blocking_reasons_by_wall_id.items() if w not in reps}
    for representative, cluster in released.items():
        for wall_id in cluster:
            if wall_id != representative:
                blockers[wall_id] = (f"equivalent_physical_wall_represented_by:{representative}",)
    groups = {tuple(cluster) for cluster in released.values() if len(cluster) > 1}
    return replace(
        equivalence,
        representative_wall_ids=tuple(sorted(published | reps)),
        abstained_wall_ids=tuple(w for w in equivalence.abstained_wall_ids if w not in reps),
        ambiguous_wall_ids=tuple(w for w in equivalence.ambiguous_wall_ids if w not in members),
        same_wall_ids=tuple(sorted(set(equivalence.same_wall_ids) | {w for g in groups for w in g})),
        equivalence_groups=tuple(sorted(set(equivalence.equivalence_groups) | groups)),
        pair_classifications=tuple(
            (a, b, PhysicalEquivalenceClass.SAME_PHYSICAL_WALL.value if frozenset((a, b)) in pair_set else c)
            for a, b, c in equivalence.pair_classifications),
        blocking_reasons_by_wall_id=blockers,
    ), counts, tuple(sorted(reps))


def straight_length_pt(identity: PhysicalWallIdentity) -> float:
    """Length of an identity's path (any shape), for reporting."""
    path = identity.path_fingerprint or ()
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in pairwise(path))
