"""Default-off, read-only FACE-FAMILY inventory of a NOMINATED glazing strip, strictly SHADOW.

A nominator (for example the plan callout to glazing strip shadow) names a set of immutable VISIBLE source
observation ids. This module re-derives everything else from the producer itself and answers one narrow
question: which solid black strokes PARALLEL to the strip axis run through the strip's whole along-extent
and past both of its terminals (a continuous host-face line), at what signed across-offset from the strip's
band, with which producer-verified stroke width and colour, and which parallel stroke groups instead stop or
break within the strip's extent?

A continuous face line running through the glazing prevents a jamb-bounded void in the existing wall-face
break reading; this shadow only makes that visible. The result is an INVENTORY, not a selection: every
overlapping parallel group is reported, ordered by signed offset, with no nearest / first / best choice and no
distance cap (the only bound is a work bound that abstains). It decides no wall, host, kind, scale, count or
quantity, never produces a `PhysicalOpeningExistenceRecord`, makes no call on the opening authority, and
imports nothing from the live issuer, the schedule binder, the host binder or the count producer.

Fail-closed census: the adapter reads EVERY published visible observation of the revision. One that cannot be
re-resolved, belongs to another document / revision / snapshot, is not a native segment, has malformed geometry,
or has no native primitive makes the whole call abstain; none is ever skipped, because a skipped stroke could hide
the very break (or the very stub) the inventory exists to show. A same-page stroke whose paint the producer cannot
prove (a fill-only shape edge, a clipped segment whose visible geometry differs from its primitive) is kept as an
UNVERIFIED stroke with no invented width, colour, dash or opacity: it can never be a through line, and it is
retained as a rival when it breaks a through line.
"""
from __future__ import annotations

import hashlib
import math
import re
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, fields
from typing import Optional, Sequence

from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import (
    AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES,
    OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,
    SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,
    VISIBLE_SOURCE_AUTHORITY_REQUIRED,
)
from pb_wall_room_topology_typed_negative_evidence import KIND_UNKNOWN, POLARITY_UNKNOWN

STRIP_FACE_FAMILY_SCHEMA_VERSION = "1.0.0"
STRIP_FACE_FAMILY_METHOD = "strip_face_family_shadow"

# the nomination vocabulary is shared, string for string, with the sibling strip shadows
NOMINATION_NOT_VISIBLE_ON_PAGE = "strip_nomination_not_visible_on_page"
SOURCE_ROLE_UNPROVEN = "strip_source_role_unproven"
NOMINATION_NOT_AXIS_ALIGNED = "strip_nomination_not_axis_aligned"
NOMINATION_AXIS_AMBIGUOUS = "strip_nomination_axis_ambiguous"
# face-family reason codes
FACE_FAMILY_DISABLED = "strip_face_family_disabled"
FACE_FAMILY_BUDGET_EXCEEDED = "strip_face_family_budget_exceeded"
FACE_FAMILY_NOT_OBSERVED = "strip_face_family_not_observed"
FACE_FAMILY_CONTINUOUS = "face_family_continuous_through_strip"
FACE_FAMILY_SAME_OFFSET_BROKEN = "strip_face_family_same_offset_through_and_broken"
# standing limits: what no face-family result ever says (never atom kinds)
FACE_LINE_WALL_ROLE_UNPROVEN = "strip_face_line_wall_role_unproven"
FACE_FAMILY_DISTANCE_UNBOUNDED = "strip_face_family_distance_unbounded"
STANDING_LIMITS = (FACE_LINE_WALL_ROLE_UNPROVEN, FACE_FAMILY_DISTANCE_UNBOUNDED)

# Work bound only: it stops a pathological page from being analysed, it decides nothing.
_MAX_GROUPS = 5_000
# The repository's own convention for black ink (the callout strip shadow reads colour the same way).
_BLACK_MAX_CHANNEL = 0.1
_SOLID_DASHES = re.compile(r"\s*\[\s*\]\s*[-+]?(?:\d+(?:\.\d*)?|\.\d+)\s*")

_STATUSES = (EvidenceResolutionStatus.CANDIDATE, EvidenceResolutionStatus.ABSTAINED, EvidenceResolutionStatus.CONFLICT)


# --------------------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class FaceFamilyOwnership:
    document_id: str
    revision_id: str
    snapshot_id: str
    source_sha256: str
    page_id: str


@dataclass(frozen=True)
class SourceStroke:
    """What the producer's own primitive says about one visible segment (never caller-supplied)."""

    observation_id: str
    geometry: tuple[float, float, float, float]
    stroke_width: Optional[float]
    stroke_rgb: Optional[tuple[float, ...]]
    solid: Optional[bool]                     # the dash pattern is solid; None = the producer states no pattern
    opaque: Optional[bool]                    # stroke opacity is exactly 1; None = the producer states none
    kind: str
    role_verified: bool


@dataclass(frozen=True)
class ViewportRef:
    view_id: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class FaceLineGroup:
    """Parallel strokes sharing one snapped across coordinate, one width, one colour, one dash state and one opacity
    state (an attribute the producer does not state is None and never merges with a stated one).

    `along_intervals` are the merged runs of the group that meet the strip's along-extent (touching or
    overlapping pieces merge, so collinear splitting and double ink do not matter). They describe the whole
    collinear run, not only the part inside the strip."""

    group_id: str
    across_pt: float                          # midrange of the member strokes' across coordinates
    across_span: tuple[float, float]
    offset_pt: float                          # signed from the band: < 0 lo side, > 0 hi side, 0.0 inside the band
    inside_band: bool
    stroke_width: Optional[float]
    stroke_rgb: Optional[tuple[float, ...]]
    solid: Optional[bool]
    opaque: Optional[bool]
    black: bool
    role_verified: bool
    member_observation_ids: tuple[str, ...]   # every member, duplicates (double ink) retained
    nominated_member_ids: tuple[str, ...]
    along_intervals: tuple[tuple[float, float], ...]
    covers_whole_extent: bool
    extends_past_lo: bool
    extends_past_hi: bool
    through_both_terminals: bool              # ONE merged run extends past both terminals
    uncovered_within_extent: tuple[tuple[float, float], ...]


_GRANT_FLAGS = (
    "physical_opening_granted", "host_granted", "opening_kind_granted", "frame_granted", "scale_granted",
    "metric_granted", "count_granted", "quantity_granted", "wall_binding_granted",
    "commercial_projection_allowed", "customer_publication_granted", "takeoff_eligible",
    "deduction_authority", "existence_record_issued",
)


@dataclass(frozen=True)
class StripFaceFamily:
    ownership: Optional[FaceFamilyOwnership]
    viewport_id: Optional[str]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    standing_limits: tuple[str, ...]
    nomination_id: Optional[str]
    nominated_observation_ids: tuple[str, ...]
    axis: Optional[str]
    along_extent: Optional[tuple[float, float]]
    band_extent: Optional[tuple[float, float]]
    snap_tolerance_pt: Optional[float]
    nominated_strokes: tuple[SourceStroke, ...]
    groups: tuple[FaceLineGroup, ...]
    continuous_group_ids: tuple[str, ...]     # black solid through groups at an offset with no broken group
    conflicted_group_ids: tuple[str, ...]     # every group at an offset holding both a through and a broken group
    evidence_atoms: tuple[EvidenceAtom, ...]
    record_id: Optional[str]
    shadow_only: bool = True
    physical_opening_granted: bool = False
    host_granted: bool = False
    opening_kind_granted: bool = False
    frame_granted: bool = False
    scale_granted: bool = False
    metric_granted: bool = False
    count_granted: bool = False
    quantity_granted: bool = False
    wall_binding_granted: bool = False
    commercial_projection_allowed: bool = False
    customer_publication_granted: bool = False
    takeoff_eligible: bool = False
    deduction_authority: bool = False
    existence_record_issued: bool = False
    schema_version: str = STRIP_FACE_FAMILY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.shadow_only is not True:
            raise ValueError("a strip face-family inventory cannot leave shadow mode")
        for name in _GRANT_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError(f"a strip face-family inventory cannot grant {name}")
        if self.status not in _STATUSES:
            raise ValueError("a strip face-family inventory is CANDIDATE, ABSTAINED or CONFLICT only")
        if any(atom.status not in _STATUSES for atom in self.evidence_atoms):
            raise ValueError("evidence atoms are CANDIDATE, ABSTAINED or CONFLICT only")
        if not set(_GRANT_FLAGS) <= {f.name for f in fields(self)}:
            raise ValueError("grant flag set is out of date")
        if self.status in (EvidenceResolutionStatus.CANDIDATE, EvidenceResolutionStatus.CONFLICT):
            if self.snap_tolerance_pt is None:
                raise ValueError("a verdict needs the snap quantum it was measured at")
        if self.snap_tolerance_pt is not None:
            continuous, conflicted = _classify(self.groups, self.snap_tolerance_pt)
            if self.status is EvidenceResolutionStatus.CANDIDATE and not (continuous and not conflicted):
                raise ValueError("a CANDIDATE needs a continuous through group and no conflicted offset")
            if self.status is EvidenceResolutionStatus.CONFLICT and not conflicted:
                raise ValueError("a face-family CONFLICT needs a through and a broken group at one offset")
            if self.status is EvidenceResolutionStatus.ABSTAINED and (continuous or conflicted):
                raise ValueError("an ABSTAINED inventory cannot hold a continuous or conflicted offset")
            if (tuple(sorted(g.group_id for g in continuous)) != tuple(sorted(self.continuous_group_ids))
                    or tuple(sorted(g.group_id for g in conflicted)) != tuple(sorted(self.conflicted_group_ids))):
                raise ValueError("the continuous and conflicted group ids must follow from the groups")
        elif self.groups or self.continuous_group_ids or self.conflicted_group_ids:
            raise ValueError("groups need the snap quantum they were measured at")


# --------------------------------------------------------------------------------------
# pure geometry
# --------------------------------------------------------------------------------------


def _orientation(g: Sequence[float], axis: str, eq: float) -> str:
    horizontal = abs(g[1] - g[3]) <= eq and abs(g[0] - g[2]) > eq
    vertical = abs(g[0] - g[2]) <= eq and abs(g[1] - g[3]) > eq
    if not (horizontal or vertical):
        return "oblique"
    along_is_x = axis == "H"
    return "parallel" if (horizontal == along_is_x) else "perpendicular"


def _along_across(g: Sequence[float], axis: str) -> tuple[tuple[float, float], tuple[float, float]]:
    x = (min(g[0], g[2]), max(g[0], g[2]))
    y = (min(g[1], g[3]), max(g[1], g[3]))
    return (x, y) if axis == "H" else (y, x)


def _hypothesis(strokes: Sequence[SourceStroke], eq: float):
    """The strip hypothesis measured from the nominated segments alone: axis, outer extent, band."""
    boxes = [s.geometry for s in strokes]
    if any(_orientation(g, "H", eq) == "oblique" for g in boxes):
        return None, NOMINATION_NOT_AXIS_ALIGNED
    x0 = min(min(g[0], g[2]) for g in boxes)
    x1 = max(max(g[0], g[2]) for g in boxes)
    y0 = min(min(g[1], g[3]) for g in boxes)
    y1 = max(max(g[1], g[3]) for g in boxes)
    if abs((x1 - x0) - (y1 - y0)) <= eq:
        return None, NOMINATION_AXIS_AMBIGUOUS
    axis = "H" if (x1 - x0) > (y1 - y0) else "V"
    along = (x0, x1) if axis == "H" else (y0, y1)
    band = (y0, y1) if axis == "H" else (x0, x1)
    return (axis, along, band), None


def _signed_offset(across: float, band: tuple[float, float], eq: float) -> float:
    if across < band[0] - eq:
        return across - band[0]
    if across > band[1] + eq:
        return across - band[1]
    return 0.0


def _is_black(rgb: Optional[tuple[float, ...]]) -> bool:
    return bool(rgb) and len(rgb) == 3 and max(rgb) <= _BLACK_MAX_CHANNEL


def _finite(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _well_formed(stroke: SourceStroke) -> bool:
    """A record whose numbers are finite; a malformed page stroke is an integrity failure, never ink that is
    silently left out of the inventory."""
    return (type(stroke.geometry) in (tuple, list) and len(stroke.geometry) == 4
            and all(_finite(v) for v in stroke.geometry)
            and (stroke.stroke_width is None or _finite(stroke.stroke_width))
            and (stroke.stroke_rgb is None or all(_finite(v) for v in stroke.stroke_rgb)))


def _is_through(group: FaceLineGroup) -> bool:
    """A black, solid, fully opaque, producer-verified run that passes both terminals unbroken (the band is
    excluded by `_offset_classes`, which only ever sees groups outside it)."""
    return (group.through_both_terminals and group.black and group.solid is True and group.opaque is True
            and group.role_verified)


def _offset_classes(groups: Sequence[FaceLineGroup], eq: float) -> list[list[FaceLineGroup]]:
    """Groups outside the band whose across spans chain within `eq` are the SAME offset (single linkage)."""
    outside = sorted((g for g in groups if not g.inside_band), key=lambda g: (g.across_span[0], g.across_span[1], g.group_id))
    classes: list[list[FaceLineGroup]] = []
    reach = None
    for group in outside:
        if classes and reach is not None and group.across_span[0] - reach <= eq:
            classes[-1].append(group)
            reach = max(reach, group.across_span[1])
        else:
            classes.append([group])
            reach = group.across_span[1]
    return classes


def _classify(groups: Sequence[FaceLineGroup], eq: float):
    """(continuous groups, conflicted groups): a through group at an offset that holds no group with a gap inside
    the strip extent, and every group at an offset that holds both a through and a broken group."""
    continuous: list[FaceLineGroup] = []
    conflicted: list[FaceLineGroup] = []
    for members in _offset_classes(groups, eq):
        through = [g for g in members if _is_through(g)]
        if not through:
            continue
        broken = [g for g in members if not g.covers_whole_extent]
        if broken:
            conflicted.extend(members)
        else:
            continuous.extend(through)
    return continuous, conflicted


def _merge_runs(pieces: Sequence[tuple[float, float, str, float]], eq: float):
    """Merge along-intervals that touch or overlap within `eq`; each run keeps the pieces it was made from."""
    runs: list[list] = []
    for piece in sorted(pieces, key=lambda p: (p[0], p[1], p[2])):
        if runs and piece[0] <= runs[-1][1] + eq:
            runs[-1][1] = max(runs[-1][1], piece[1])
            runs[-1][2].append(piece)
        else:
            runs.append([piece[0], piece[1], [piece]])
    return runs


def _uncovered(runs: Sequence[Sequence], along: tuple[float, float], eq: float) -> tuple[tuple[float, float], ...]:
    lo, hi = along
    gaps: list[tuple[float, float]] = []
    position = lo
    for a0, a1, _ in sorted(runs, key=lambda r: (r[0], r[1])):
        if a0 > position + eq:
            gaps.append((position, min(a0, hi)))
        position = max(position, a1)
        if position >= hi:
            break
    if position < hi - eq:
        gaps.append((position, hi))
    return tuple((g0, g1) for g0, g1 in gaps if g1 - g0 > eq)


def _paint_key(stroke: SourceStroke) -> tuple:
    """What keeps two collinear strokes apart: width, colour, dash state and opacity, exactly as the producer states
    them (an unproven attribute stays None and never merges with a proven one)."""
    return (None if stroke.stroke_width is None else round(stroke.stroke_width, 6),
            None if stroke.stroke_rgb is None else tuple(round(v, 6) for v in stroke.stroke_rgb),
            stroke.solid, stroke.opaque)


def _inventory(page: Sequence[SourceStroke], nominated: frozenset, axis: str, along: tuple[float, float],
               band: tuple[float, float], eq: float, nomination_id: str, root: tuple):
    """Every parallel stroke group whose merged runs meet the strip's along-extent; None when over the work bound.

    The across snap (single linkage at quantum / 4) is taken over the strokes that themselves meet the strip's
    along-extent, so a stroke elsewhere on the page can never bridge two offsets that are further apart than the
    snap. A stroke that does not itself meet the extent can only CONTINUE a group of the same paint whose across
    coordinate it sits within the snap of (it is kept in every such group, never assigned to one by distance)."""
    lo, hi = along
    pieces = []        # (c, a0, a1, id, stroke)
    for stroke in page:
        if _orientation(stroke.geometry, axis, eq) != "parallel":
            continue
        (a0, a1), (c0, c1) = _along_across(stroke.geometry, axis)
        pieces.append(((c0 + c1) / 2.0, a0, a1, stroke.observation_id, stroke))
    pieces.sort(key=lambda p: (p[0], p[3]))
    meeting = [p for p in pieces if p[2] >= lo - eq and p[1] <= hi + eq]
    continuing = [p for p in pieces if not (p[2] >= lo - eq and p[1] <= hi + eq)]

    cluster_of: dict[str, int] = {}
    cluster = -1
    previous = None
    for piece in meeting:                  # single-linkage snap of the across coordinate at quantum / 4
        if previous is None or piece[0] - previous > eq:
            cluster += 1
        cluster_of[piece[3]] = cluster
        previous = piece[0]

    buckets: dict[tuple, list] = {}
    anchors: dict[tuple, list] = {}        # paint -> [(across, cluster)] of the meeting strokes, ascending
    for c, a0, a1, oid, stroke in meeting:
        paint = _paint_key(stroke)
        buckets.setdefault((cluster_of[oid], *paint), []).append((a0, a1, oid, c))
        anchors.setdefault(paint, []).append((c, cluster_of[oid]))
    anchor_across = {paint: [v for v, _ in ranked] for paint, ranked in anchors.items()}
    for c, a0, a1, oid, stroke in continuing:
        paint = _paint_key(stroke)
        ranked = anchors.get(paint)
        if not ranked:
            continue
        values = anchor_across[paint]
        reachable = {ranked[k][1] for k in range(bisect_left(values, c - eq), bisect_right(values, c + eq))}
        for owner in sorted(reachable):
            buckets[(owner, *paint)].append((a0, a1, oid, c))

    stroke_by_id = {s.observation_id: s for s in page}
    groups: list[FaceLineGroup] = []
    for key in sorted(buckets, key=lambda k: (k[0], k[1] is not None, k[1] or 0.0, k[2] or (), repr(k[3]), repr(k[4]))):
        runs = [r for r in _merge_runs(buckets[key], eq) if r[1] >= lo - eq and r[0] <= hi + eq]
        if not runs:
            continue
        members = [p for r in runs for p in r[2]]
        across = [p[3] for p in members]
        across_pt = (min(across) + max(across)) / 2.0
        offset = _signed_offset(across_pt, band, eq)
        ids = tuple(sorted(p[2] for p in members))
        verified = all(stroke_by_id[i].role_verified for i in ids)
        intervals = tuple((r[0], r[1]) for r in runs)
        covers = any(a0 <= lo + eq and a1 >= hi - eq for a0, a1 in intervals)
        past_lo = any(a0 < lo - eq and a1 > lo + eq for a0, a1 in intervals)
        past_hi = any(a0 < hi - eq and a1 > hi + eq for a0, a1 in intervals)
        through = any(a0 < lo - eq and a1 > hi + eq for a0, a1 in intervals)
        width, rgb, solid, opaque = key[1], key[2], key[3], key[4]
        groups.append(FaceLineGroup(
            group_id=stable_contract_id("shadow_strip_face_group", {
                "root": root, "nomination": nomination_id, "members": ids, "width": width, "rgb": rgb, "solid": solid,
                "opaque": opaque}),
            across_pt=across_pt, across_span=(min(across), max(across)), offset_pt=offset,
            inside_band=offset == 0.0, stroke_width=width, stroke_rgb=rgb, solid=solid, opaque=opaque,
            black=_is_black(rgb), role_verified=verified, member_observation_ids=ids,
            nominated_member_ids=tuple(i for i in ids if i in nominated), along_intervals=intervals,
            covers_whole_extent=covers, extends_past_lo=past_lo, extends_past_hi=past_hi,
            through_both_terminals=through, uncovered_within_extent=_uncovered(runs, along, eq)))
        if len(groups) > _MAX_GROUPS:
            return None
    groups.sort(key=lambda g: (g.offset_pt, g.across_pt, g.stroke_width is not None, g.stroke_width or 0.0,
                               g.stroke_rgb or (), g.group_id))
    return tuple(groups)


def audit_strip_face_family(
    *, ownership: FaceFamilyOwnership, viewport: Optional[ViewportRef], nominated_ids: Sequence[str],
    page_strokes: Sequence[SourceStroke], coordinate_quantum_pt: float,
) -> StripFaceFamily:
    """Pure core over records the adapter has already re-derived from the producer."""
    if not (type(coordinate_quantum_pt) in (int, float) and coordinate_quantum_pt > 0
            and math.isfinite(coordinate_quantum_pt)):
        raise ValueError("a positive finite coordinate quantum is required")
    eq = coordinate_quantum_pt * 0.25
    nominated = tuple(sorted(nominated_ids))
    by_id = {s.observation_id: s for s in page_strokes}
    strokes = tuple(by_id[i] for i in nominated if i in by_id)
    root = (ownership.document_id, ownership.revision_id, ownership.snapshot_id, ownership.source_sha256,
            ownership.page_id)
    nomination_id = stable_contract_id("shadow_strip_nomination", {"root": root, "ids": nominated})

    def done(status, reason_codes, *, axis=None, along=None, band=None, groups=(), continuous=(), conflicted=()):
        record_id = stable_contract_id("shadow_strip_face_family", {
            "root": root, "viewport": viewport.view_id if viewport else None, "ids": nominated,
            "status": status.value, "reasons": tuple(reason_codes),
            "groups": tuple(sorted(g.group_id for g in groups))})
        bbox = None
        if along and band:
            bbox = (along[0], band[0], along[1], band[1]) if axis == "H" else (band[0], along[0], band[1], along[1])
        atom = EvidenceAtom(
            evidence_id=stable_contract_id("shadow_strip_face_family_atom", {"record": record_id}),
            document_id=ownership.document_id, page_id=ownership.page_id, kind=KIND_UNKNOWN,
            method=STRIP_FACE_FAMILY_METHOD, viewport_id=viewport.view_id if viewport else None, bbox=bbox,
            status=status, reason_codes=tuple(reason_codes),
            metadata={
                "revision_id": ownership.revision_id, "source_sha256": ownership.source_sha256,
                "snapshot_id": ownership.snapshot_id, "polarity": POLARITY_UNKNOWN,
                "source_observation_ids": nominated, "nomination_id": nomination_id,
                "face_group_ids": tuple(sorted(g.group_id for g in groups)),
                "continuous_group_ids": tuple(sorted(g.group_id for g in continuous)),
                "conflicted_group_ids": tuple(sorted(g.group_id for g in conflicted)),
                **{flag: False for flag in _GRANT_FLAGS}})
        return StripFaceFamily(
            ownership=ownership, viewport_id=viewport.view_id if viewport else None, status=status,
            reason_codes=tuple(reason_codes), standing_limits=STANDING_LIMITS, nomination_id=nomination_id,
            nominated_observation_ids=nominated, axis=axis, along_extent=along, band_extent=band,
            snap_tolerance_pt=eq, nominated_strokes=strokes, groups=tuple(groups),
            continuous_group_ids=tuple(sorted(g.group_id for g in continuous)),
            conflicted_group_ids=tuple(sorted(g.group_id for g in conflicted)),
            evidence_atoms=(atom,), record_id=record_id)

    ABSTAIN, CONFLICT = EvidenceResolutionStatus.ABSTAINED, EvidenceResolutionStatus.CONFLICT
    if len(by_id) != len(page_strokes) or not all(_well_formed(s) for s in page_strokes):
        return done(ABSTAIN, (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,))
    if not nominated or len(set(nominated)) != len(nominated) or any(i not in by_id for i in nominated):
        return done(ABSTAIN, (NOMINATION_NOT_VISIBLE_ON_PAGE,))
    if any(not s.role_verified or s.stroke_width is None for s in strokes):
        return done(ABSTAIN, (SOURCE_ROLE_UNPROVEN, SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE))
    hypothesis, failure = _hypothesis(strokes, eq)
    if hypothesis is None:
        return done(ABSTAIN, (failure,))
    axis, along, band = hypothesis
    strip_box = (along[0], band[0], along[1], band[1]) if axis == "H" else (band[0], along[0], band[1], along[1])
    if viewport is None or not (viewport.bbox[0] <= strip_box[0] and viewport.bbox[1] <= strip_box[1]
                                and strip_box[2] <= viewport.bbox[2] and strip_box[3] <= viewport.bbox[3]):
        return done(ABSTAIN, (OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,), axis=axis, along=along, band=band)
    groups = _inventory(page_strokes, frozenset(nominated), axis, along, band, eq, nomination_id, root)
    if groups is None:
        return done(ABSTAIN, (FACE_FAMILY_BUDGET_EXCEEDED,), axis=axis, along=along, band=band)
    continuous, conflicted = _classify(groups, eq)
    common = dict(axis=axis, along=along, band=band, groups=groups, continuous=continuous, conflicted=conflicted)
    if conflicted:
        return done(CONFLICT, (AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES, FACE_FAMILY_SAME_OFFSET_BROKEN), **common)
    if continuous:
        return done(EvidenceResolutionStatus.CANDIDATE, (FACE_FAMILY_CONTINUOUS,), **common)
    return done(ABSTAIN, (FACE_FAMILY_NOT_OBSERVED,), **common)


# --------------------------------------------------------------------------------------
# producer adapter
# --------------------------------------------------------------------------------------


def _disabled_or_failed(*codes: str) -> StripFaceFamily:
    return StripFaceFamily(
        ownership=None, viewport_id=None, status=EvidenceResolutionStatus.ABSTAINED, reason_codes=tuple(codes),
        standing_limits=STANDING_LIMITS, nomination_id=None, nominated_observation_ids=(), axis=None,
        along_extent=None, band_extent=None, snap_tolerance_pt=None, nominated_strokes=(), groups=(),
        continuous_group_ids=(), conflicted_group_ids=(), evidence_atoms=(), record_id=None)


class StripFaceFamilyShadow:
    """Read-only face-family inventory bound to one `SourceVisibilityProducer`; default OFF."""

    def __init__(self, source, *, enabled: bool = False):
        from pb_source_visibility_authority import SourceVisibilityProducer

        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be a producer-owned SourceVisibilityProducer")
        if type(enabled) is not bool:
            raise ValueError("strip face-family gate must be an explicit boolean")
        self._source = source
        self._enabled = enabled

    def audit(self, *, revision_id: str, page_id: int, nominated_observation_ids: Sequence[str],
              coordinate_quantum_pt: float) -> StripFaceFamily:
        if not self._enabled:
            return _disabled_or_failed(FACE_FAMILY_DISABLED)
        if isinstance(nominated_observation_ids, (str, bytes)) or not hasattr(nominated_observation_ids, "__iter__"):
            raise ValueError("nominated observation ids must be a collection of strings")
        nominated = tuple(nominated_observation_ids)
        if (type(revision_id) is not str or type(page_id) is not int or isinstance(page_id, bool)
                or any(type(i) is not str or not i for i in nominated)
                or not (type(coordinate_quantum_pt) in (int, float) and coordinate_quantum_pt > 0
                        and math.isfinite(coordinate_quantum_pt))):
            raise ValueError("revision id, integer page id, string observation ids and a positive quantum required")
        nominated = tuple(sorted(nominated))
        import fitz

        from pb_source_observation_authority import ObservationSelector
        from pb_source_visibility_authority import NATIVE_PDF_VISIBLE_SEGMENT, VISIBLE_SOURCE_OBSERVATION_EXISTS
        from pb_vector_geometry_v130 import extract_native_page
        from pb_viewport_segmentation import ViewportSegmentationStatus, segment_page_viewports

        source = self._source
        published = source.published_snapshot_for_revision(revision_id)
        if published is None:
            return _disabled_or_failed(VISIBLE_SOURCE_AUTHORITY_REQUIRED)
        document_id = published.revision.document_id
        if (page_id not in tuple(int(v) for v in published.coverage.decoded_pages)
                or int(page_id) in tuple(int(v) for v in published.coverage.failed_pages)
                or source._producer.current_revision_id(document_id) != revision_id):
            return _disabled_or_failed(VISIBLE_SOURCE_AUTHORITY_REQUIRED)
        source_bytes = source._producer._store.source_bytes_by_revision.get(revision_id)
        if source_bytes is None or hashlib.sha256(source_bytes).hexdigest() != published.revision.source_sha256:
            return _disabled_or_failed(SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE)
        ownership = FaceFamilyOwnership(document_id, revision_id, published.snapshot.snapshot_id,
                                        published.revision.source_sha256, str(page_id))
        integrity_failure = _disabled_or_failed(SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE)

        def selector(observation_id: str) -> ObservationSelector:
            return ObservationSelector(document_id, revision_id, ownership.source_sha256, ownership.snapshot_id,
                                       observation_id)

        # one pass over the page: the producer's own primitives and the paint of the drawing each belongs to
        with fitz.open(stream=bytes(source_bytes), filetype="pdf") as document:
            page = document[page_id - 1]
            segments = extract_native_page(page)["segments"]
            drawing_paint = {index: (drawing.get("seqno"), drawing.get("stroke_opacity"))
                             for index, drawing in enumerate(page.get_drawings())}
            segmented = segment_page_viewports(page, page_number=page_id)
        primitives = {s["id"]: s for s in segments}
        if len(primitives) != len(segments):
            return integrity_failure              # two primitives sharing an id cannot be joined to an observation

        # EVERY published visible observation is re-resolved and accounted for: none is skipped, because a skipped
        # stroke could hide the very break (or stub) this inventory exists to show
        visibility = source.authority()
        page_strokes: list[SourceStroke] = []
        for observation_id in published.visible_observation_ids:
            result = visibility.resolve_visible(selector(observation_id))
            observation = result.observation
            if (result.status is not EvidenceResolutionStatus.CORROBORATED
                    or result.proposition != VISIBLE_SOURCE_OBSERVATION_EXISTS or observation is None):
                return integrity_failure
            # a positive wrapper is not authority to substitute a foreign observation: check the immutable identity
            if (observation.observation_id != observation_id or observation.document_id != document_id
                    or observation.revision_id != revision_id or observation.source_sha256 != ownership.source_sha256
                    or observation.snapshot_id != ownership.snapshot_id):
                return integrity_failure
            if str(observation.page_id) != str(page_id):
                continue
            raw_geometry = observation.geometry
            if (observation.observation_kind != NATIVE_PDF_VISIBLE_SEGMENT
                    or type(raw_geometry) not in (tuple, list) or len(raw_geometry) != 4
                    or any(type(v) not in (int, float) or not math.isfinite(v) for v in raw_geometry)):
                return integrity_failure
            geometry = tuple(float(v) for v in raw_geometry)
            primitive = primitives.get(str(observation.source_primitive_ref).removeprefix("visible:segment:"))
            if primitive is None:
                return integrity_failure          # an observation with no native primitive is not source ink
            width, stroke = primitive.get("width"), primitive.get("stroke")
            verified = (geometry == (float(primitive["x1"]), float(primitive["y1"]),
                                     float(primitive["x2"]), float(primitive["y2"]))
                        and bool(primitive.get("width_present")) and bool(primitive.get("stroke_present"))
                        and _finite(width) and type(stroke) in (tuple, list) and len(stroke) == 3
                        and all(_finite(v) for v in stroke))
            solid = opaque = None
            if verified:
                if primitive.get("dashes_present"):
                    solid = bool(_SOLID_DASHES.fullmatch(str(primitive.get("dashes", ""))))
                seqno, opacity = drawing_paint.get(primitive.get("path_index"), (None, None))
                if seqno is not None and seqno == primitive.get("sequence_number") and _finite(opacity):
                    opaque = opacity == 1.0
            page_strokes.append(SourceStroke(
                observation_id=str(observation_id), geometry=geometry,
                stroke_width=float(width) if verified else None,
                stroke_rgb=tuple(float(c) for c in stroke) if verified else None,
                solid=solid, opaque=opaque, kind=str(primitive.get("kind", "unknown")), role_verified=verified))

        # one positively authenticated RESOLVED floor-plan viewport containing the strip, or no verdict
        floor_plans = [v for v in segmented if v.status == ViewportSegmentationStatus.RESOLVED.value
                       and v.bounding_box is not None and v.view_type == "floor_plan"]
        by_id = {s.observation_id: s for s in page_strokes}
        viewport: Optional[ViewportRef] = None
        if nominated and len(set(nominated)) == len(nominated) and all(i in by_id for i in nominated):
            xs = [v for i in nominated for v in (by_id[i].geometry[0], by_id[i].geometry[2])]
            ys = [v for i in nominated for v in (by_id[i].geometry[1], by_id[i].geometry[3])]
            box = (min(xs), min(ys), max(xs), max(ys))
            holders = [v for v in floor_plans if v.bounding_box[0] <= box[0] and v.bounding_box[1] <= box[1]
                       and box[2] <= v.bounding_box[2] and box[3] <= v.bounding_box[3]]
            if len(holders) == 1:
                viewport = ViewportRef(str(holders[0].view_id), tuple(float(c) for c in holders[0].bounding_box))
        return audit_strip_face_family(
            ownership=ownership, viewport=viewport, nominated_ids=nominated, page_strokes=page_strokes,
            coordinate_quantum_pt=float(coordinate_quantum_pt))


__all__ = [
    "FACE_FAMILY_BUDGET_EXCEEDED", "FACE_FAMILY_CONTINUOUS", "FACE_FAMILY_DISABLED", "FACE_FAMILY_DISTANCE_UNBOUNDED",
    "FACE_FAMILY_NOT_OBSERVED", "FACE_FAMILY_SAME_OFFSET_BROKEN", "FACE_LINE_WALL_ROLE_UNPROVEN", "FaceFamilyOwnership",
    "FaceLineGroup", "SourceStroke", "STANDING_LIMITS", "STRIP_FACE_FAMILY_SCHEMA_VERSION", "StripFaceFamily",
    "StripFaceFamilyShadow", "ViewportRef", "audit_strip_face_family",
]
