"""pb_clos_opening_tag_spatial_ranking.py -- Conditional-line-of-sight (CLOS)
candidate ranking layer for opening-to-tag spatial association.

Producer-owned PRE-FILTER for OpeningIdentityResolver.resolve_tag_binding()'s
`nearby_tags` argument (pb_source_opening_candidate_authority.py). Computes
which TagObservations have a genuine, wall-aware line of sight to a given
PhysicalOpeningCandidateRecord's aperture anchor -- rejecting any tag whose
line-of-sight segment crosses authenticated solid wall geometry other than
the candidate's own host wall -- and ranks the CLOS-passing tags by
distance, only once visibility has already passed.

What this module is NOT: an opening-identity authority. It never produces
PROVEN_SAME or PROVEN_DISTINCT, and it does not create, seal, or bypass
TagObservation / TagBindingEvidence / OpeningTagBindingResult in any way.
Its only output states are POSSIBLE_BINDING (line of sight to the
candidate is unobstructed by any other wall) and NOT_VISIBLE (a wall
other than the candidate's own host blocks the path). Passing CLOS is a
necessary precondition for a tag to even be worth offering to
OpeningIdentityResolver.resolve_tag_binding() -- via its own nearby_tags
argument, unmodified -- but it is never sufficient on its own to bind
identity. That still strictly requires a typed TagBindingEvidence
(LEADER_TO_OPENING, SHARED_ANNOTATION, EXPLICIT_APERTURE_TAG) produced by
authenticate_tag_binding_evidence(), exactly as before this module
existed; resolve_tag_binding() already independently fails closed to
UNRESOLVED/CONFLICT for spatial-proximity-only or multiple-competing-tag
cases, and this module changes nothing about that -- it only supplies a
geometry-aware candidate list instead of "every tag on the page" or
"every tag within a fixed radius," neither of which knows about walls.

Ambiguity is a first-class outcome, not an error to paper over: when two
or more tags are equally CLOS-plausible for one candidate, this module
returns all of them, ranked, rather than picking the nearest as if
distance alone settled anything -- resolve_tag_binding() is the one
place identity gets decided, and it already fails closed on that case.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Sequence, Tuple

from pb_source_opening_candidate_authority import PhysicalOpeningCandidateRecord, TagObservation

__all__ = [
    "CLOSVisibilityState",
    "WallSegment",
    "CLOSCandidate",
    "has_line_of_sight",
    "rank_clos_candidates",
    "clos_passing_tag_observations",
]

Point = Tuple[float, float]


class CLOSVisibilityState(str, Enum):
    """Deliberately NOT IdentityState. CLOS answers a visibility question,
    never an identity one -- reusing IdentityState's vocabulary here would
    invite exactly the confusion this module exists to prevent."""

    POSSIBLE_BINDING = "possible_binding"
    NOT_VISIBLE = "not_visible"


@dataclass(frozen=True)
class WallSegment:
    """One straight run of authenticated solid wall geometry, as a line
    segment. `segment_id` is whatever identity the wall-geometry producer
    that authenticated this segment assigned -- this module does not
    mint wall identity, only consumes it."""

    segment_id: str
    p1: Point
    p2: Point


@dataclass(frozen=True)
class CLOSCandidate:
    tag_observation_id: str
    state: CLOSVisibilityState
    distance_pt: Optional[float]
    blocking_wall_segment_ids: Tuple[str, ...] = ()


def _sub(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1])


def _cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _segments_intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    """True if closed segments p1-p2 and p3-p4 properly or touch-intersect.

    Standard orientation-based test. Segments that only touch at a shared
    endpoint (e.g. the tag's line-of-sight segment ending exactly on a
    wall corner it is meant to reach) are treated as intersecting too --
    conservative (fail-closed toward NOT_VISIBLE) is the correct default
    for a solid-wall obstruction test.
    """
    d1 = _cross(_sub(p4, p3), _sub(p1, p3))
    d2 = _cross(_sub(p4, p3), _sub(p2, p3))
    d3 = _cross(_sub(p2, p1), _sub(p3, p1))
    d4 = _cross(_sub(p2, p1), _sub(p4, p1))

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
        (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)
    ):
        return True

    def _on_segment(p: Point, q: Point, r: Point) -> bool:
        return (
            min(p[0], r[0]) - 1e-9 <= q[0] <= max(p[0], r[0]) + 1e-9
            and min(p[1], r[1]) - 1e-9 <= q[1] <= max(p[1], r[1]) + 1e-9
        )

    if abs(d1) < 1e-9 and _on_segment(p3, p1, p4):
        return True
    if abs(d2) < 1e-9 and _on_segment(p3, p2, p4):
        return True
    if abs(d3) < 1e-9 and _on_segment(p1, p3, p2):
        return True
    if abs(d4) < 1e-9 and _on_segment(p1, p4, p2):
        return True
    return False


def has_line_of_sight(
    anchor: Point,
    target: Point,
    wall_segments: Sequence[WallSegment],
    host_wall_segment_ids: frozenset,
) -> Tuple[bool, Tuple[str, ...]]:
    """True (and no blocking IDs) iff the straight anchor-target segment
    crosses no wall segment other than one of the candidate's own
    host_wall_segment_ids. A candidate's own host wall is explicitly
    excluded -- a door/window aperture is a break IN its host wall, so the
    line from the aperture out to a tag will often, correctly, graze or
    cross that same wall's run near the break; that is not evidence
    against visibility, only an artifact of where the anchor sits.
    """
    blockers: List[str] = []
    for wall in wall_segments:
        if wall.segment_id in host_wall_segment_ids:
            continue
        if _segments_intersect(anchor, target, wall.p1, wall.p2):
            blockers.append(wall.segment_id)
    return (len(blockers) == 0, tuple(blockers))


def rank_clos_candidates(
    candidate: PhysicalOpeningCandidateRecord,
    tags: Sequence[TagObservation],
    wall_segments: Sequence[WallSegment],
    host_wall_segment_ids: frozenset = frozenset(),
) -> List[CLOSCandidate]:
    """Rank every supplied tag's CLOS relationship to `candidate`.

    Returns one CLOSCandidate per input tag (never drops any silently),
    sorted by distance ascending among POSSIBLE_BINDING results, with
    NOT_VISIBLE results appended after. Distance is computed only for
    tags that already passed visibility -- consistent with "calculate
    distance only after visibility passes," a blocked tag's distance is
    never computed or compared, so it can never win purely by being close.
    """
    anchor = candidate.center()
    results: List[CLOSCandidate] = []
    for tag in tags:
        target = tag.center()
        visible, blockers = has_line_of_sight(anchor, target, wall_segments, host_wall_segment_ids)
        if visible:
            distance = math.hypot(target[0] - anchor[0], target[1] - anchor[1])
            results.append(
                CLOSCandidate(
                    tag_observation_id=tag.observation_id,
                    state=CLOSVisibilityState.POSSIBLE_BINDING,
                    distance_pt=distance,
                )
            )
        else:
            results.append(
                CLOSCandidate(
                    tag_observation_id=tag.observation_id,
                    state=CLOSVisibilityState.NOT_VISIBLE,
                    distance_pt=None,
                    blocking_wall_segment_ids=blockers,
                )
            )

    possible = sorted(
        (r for r in results if r.state == CLOSVisibilityState.POSSIBLE_BINDING),
        key=lambda r: r.distance_pt if r.distance_pt is not None else math.inf,
    )
    blocked = [r for r in results if r.state == CLOSVisibilityState.NOT_VISIBLE]
    return possible + blocked


def clos_passing_tag_observations(
    candidate: PhysicalOpeningCandidateRecord,
    tags: Sequence[TagObservation],
    wall_segments: Sequence[WallSegment],
    host_wall_segment_ids: frozenset = frozenset(),
) -> List[TagObservation]:
    """Convenience: the subset of `tags` that passed CLOS for `candidate`,
    ranked by distance, as plain TagObservations ready to hand to
    OpeningIdentityResolver.resolve_tag_binding(nearby_tags=...) unchanged.

    Deliberately returns ALL passing tags, not just the nearest one: if
    two remain equally plausible after this filter, resolve_tag_binding()
    is where that gets resolved (or correctly fails closed) -- this
    function must not pre-empt that by silently keeping only a single
    "best" candidate.
    """
    ranked = rank_clos_candidates(candidate, tags, wall_segments, host_wall_segment_ids)
    by_id = {t.observation_id: t for t in tags}
    return [
        by_id[r.tag_observation_id]
        for r in ranked
        if r.state == CLOSVisibilityState.POSSIBLE_BINDING
    ]
