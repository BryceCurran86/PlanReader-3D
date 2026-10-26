"""Default-off, read-only structural assessment of a NOMINATED glazing strip, strictly SHADOW.

A nominator (for example the plan callout to glazing strip shadow) names a set of immutable VISIBLE
source observation ids. This module re-derives everything else from the producer itself and answers one
narrow question: how does the existing physical-opening stack see that strip, and what is drawn at its two
terminals? It retains every existing fragment as both a positive observation and a rival, preserves any
conflict between them, and issues only CANDIDATE / ABSTAINED / CONFLICT.

It decides no structural jamb, wall-depth rule, host, kind, scale, count or quantity. Those belong to the
physical-jamb / host, issuer and seal authorities. It never produces a `PhysicalOpeningExistenceRecord`,
never writes any cache of the producer's own opening authority (it owns a private authority instance), and
imports nothing from the live issuer, the schedule binder, the host binder or the count producer.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, fields
from typing import Optional, Sequence

from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import (
    AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES,
    JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,
    SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,
    VISIBLE_SOURCE_AUTHORITY_REQUIRED,
    VISIBLE_WALL_CONTINUATION_REQUIRED,
)
from pb_wall_room_topology_typed_negative_evidence import KIND_UNKNOWN, POLARITY_UNKNOWN

STRIP_STRUCTURAL_ASSESSMENT_SCHEMA_VERSION = "1.0.0"
STRIP_ASSESSMENT_METHOD = "strip_structural_assessment_shadow"

# existing vocabulary, reused verbatim
TERMINAL_ROLE_UNPROVEN = "original_terminal_paint_structural_role_unproven"   # pb_g17_terminal_flank_source_shadow
# the only new strings: standing capability limits, never atom kinds
STRIP_TYPE_VS_PHYSICAL_INSTANCE_UNPROVED = "strip_type_vs_physical_instance_unproved"
STRIP_MIXED_DOOR_WINDOW_ASSEMBLY_PARTITION_UNPROVED = "strip_mixed_door_window_assembly_partition_unproved"
STANDING_LIMITS = (STRIP_TYPE_VS_PHYSICAL_INSTANCE_UNPROVED, STRIP_MIXED_DOOR_WINDOW_ASSEMBLY_PARTITION_UNPROVED)
# assessment-local reason codes
ASSESSMENT_DISABLED = "strip_structural_assessment_disabled"
NOMINATION_INVALID = "strip_nomination_invalid"
NOMINATION_NOT_VISIBLE_ON_PAGE = "strip_nomination_not_visible_on_page"
SOURCE_ROLE_UNPROVEN = "strip_source_role_unproven"
NOMINATION_NOT_AXIS_ALIGNED = "strip_nomination_not_axis_aligned"
NOMINATION_AXIS_AMBIGUOUS = "strip_nomination_axis_ambiguous"
VIEWPORT_NOT_FLOOR_PLAN = "strip_viewport_not_resolved_floor_plan"
VIEWPORT_AMBIGUOUS = "strip_viewport_ambiguous"
TERMINAL_BUDGET_EXCEEDED = "strip_terminal_inventory_budget_exceeded"
WHOLE_EXTENT_CANDIDATE_PRESENT = "strip_whole_extent_candidate_present"
FRAGMENTS_ONLY = "strip_fragments_only_no_whole_extent_candidate"

# Work bound only: it stops a pathological page from being analysed, it decides nothing.
_MAX_TERMINAL_ITEMS = 5_000

_STATUSES = (EvidenceResolutionStatus.CANDIDATE, EvidenceResolutionStatus.ABSTAINED, EvidenceResolutionStatus.CONFLICT)


# --------------------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class AssessmentOwnership:
    document_id: str
    revision_id: str
    snapshot_id: str
    source_sha256: str
    page_id: str


@dataclass(frozen=True)
class SourceRole:
    """What the producer's own primitive says about one visible segment (never caller-supplied)."""

    observation_id: str
    geometry: tuple[float, float, float, float]
    stroke_width: Optional[float]
    stroke_rgb: Optional[tuple[float, ...]]
    kind: str
    role_verified: bool


@dataclass(frozen=True)
class ViewportRef:
    view_id: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class TerminalInk:
    end: str                      # "lo" | "hi" along the strip axis
    observation_id: str
    orientation: str              # "parallel" | "perpendicular" | "oblique"
    stroke_width: Optional[float]
    stroke_rgb: Optional[tuple[float, ...]]
    nominated: bool
    spans_band: bool              # a perpendicular stroke covering the band from edge to edge
    extends_beyond_band: bool
    role_verified: bool


@dataclass(frozen=True)
class FragmentObservation:
    candidate_id: str
    structural_pattern: str
    member_observation_ids: tuple[str, ...]
    member_span: Optional[tuple[float, float]]    # along-axis extent of ALL member lines (faces included)
    across_span: Optional[tuple[float, float]]
    gap_span: Optional[tuple[float, float]]       # the opening itself: between the two jamb members
    shares_nominated_members: int
    overlaps_strip: bool
    members_cross_lo_terminal: bool               # a member line runs past the strip's terminal
    members_cross_hi_terminal: bool
    gap_crosses_lo_terminal: bool                 # the opening itself starts/ends outside the strip
    gap_crosses_hi_terminal: bool
    spans_whole_extent: bool                      # the jambs sit at the strip's two outer terminals
    strong_pattern: bool
    existence: str                # "corroborated" | "contested" | "unresolved"
    rival_evidence_only: bool     # generic 3/4-observation patterns bypass the strong-pattern opposition test


_GRANT_FLAGS = (
    "physical_opening_granted", "host_granted", "opening_kind_granted", "frame_granted", "scale_granted",
    "metric_granted", "count_granted", "quantity_granted", "wall_binding_granted",
    "commercial_projection_allowed", "customer_publication_granted", "takeoff_eligible",
    "deduction_authority", "existence_record_issued",
)


@dataclass(frozen=True)
class StripStructuralAssessment:
    ownership: Optional[AssessmentOwnership]
    viewport_id: Optional[str]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    standing_limits: tuple[str, ...]
    nomination_id: Optional[str]
    nominated_observation_ids: tuple[str, ...]
    axis: Optional[str]
    along_extent: Optional[tuple[float, float]]
    band_extent: Optional[tuple[float, float]]
    roles: tuple[SourceRole, ...]
    terminals: tuple[TerminalInk, ...]
    fragments: tuple[FragmentObservation, ...]
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
    schema_version: str = STRIP_STRUCTURAL_ASSESSMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.shadow_only is not True:
            raise ValueError("a strip structural assessment cannot leave shadow mode")
        for name in _GRANT_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError(f"a strip structural assessment cannot grant {name}")
        if self.status not in _STATUSES:
            raise ValueError("a strip structural assessment is CANDIDATE, ABSTAINED or CONFLICT only")
        if any(atom.status not in _STATUSES for atom in self.evidence_atoms):
            raise ValueError("evidence atoms are CANDIDATE, ABSTAINED or CONFLICT only")
        if self.status is EvidenceResolutionStatus.CANDIDATE:
            whole = [f for f in self.fragments if f.overlaps_strip]
            if not (len(whole) == 1 and whole[0].spans_whole_extent and whole[0].strong_pattern
                    and whole[0].existence == "corroborated"):
                raise ValueError("a CANDIDATE needs exactly one overlapping fragment: a corroborated strong "
                                 "candidate spanning the whole extent")
        if not set(_GRANT_FLAGS) <= {f.name for f in fields(self)}:
            raise ValueError("grant flag set is out of date")


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


def _hypothesis(roles: Sequence[SourceRole], eq: float):
    """The strip hypothesis measured from the nominated segments alone: axis, outer extent, band."""
    boxes = [r.geometry for r in roles]
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


def _terminal_inventory(page: Sequence[SourceRole], nominated: frozenset, axis: str,
                        along: tuple[float, float], band: tuple[float, float], eq: float):
    margin = band[1] - band[0]     # the strip's own depth; a measured quantity, not a fitted constant
    region = (band[0] - margin, band[1] + margin)
    items: list[TerminalInk] = []
    for end, coordinate in (("lo", along[0]), ("hi", along[1])):
        for role in page:
            g = role.geometry
            orientation = _orientation(g, axis, eq)
            (a0, a1), (c0, c1) = _along_across(g, axis)
            if c1 < region[0] - eq or c0 > region[1] + eq:
                continue
            if orientation == "perpendicular":
                touches = abs(a0 - coordinate) <= eq
            else:
                touches = a0 - eq <= coordinate <= a1 + eq
            if not touches:
                continue
            items.append(TerminalInk(
                end=end, observation_id=role.observation_id, orientation=orientation,
                stroke_width=role.stroke_width, stroke_rgb=role.stroke_rgb,
                nominated=role.observation_id in nominated,
                spans_band=bool(orientation == "perpendicular" and c0 <= band[0] + eq and c1 >= band[1] - eq),
                extends_beyond_band=bool(c0 < band[0] - eq or c1 > band[1] + eq),
                role_verified=role.role_verified))
            if len(items) > _MAX_TERMINAL_ITEMS:
                return None
    items.sort(key=lambda t: (t.end, t.observation_id))
    return tuple(items)


def assess_strip_hypothesis(
    *, ownership: AssessmentOwnership, viewport: Optional[ViewportRef], nominated_ids: Sequence[str],
    page_segments: Sequence[SourceRole], candidates: Sequence[tuple[str, str, tuple[str, ...]]],
    corroborated_member_sets: frozenset, member_status: dict, coordinate_quantum_pt: float,
) -> StripStructuralAssessment:
    """Pure core over records the adapter has already re-derived from the producer.

    `candidates` is (candidate_id, structural_pattern, member_ids) for every candidate on the page;
    `corroborated_member_sets` holds the member sets of existence records the authority itself issued."""
    eq = coordinate_quantum_pt * 0.25
    nominated = tuple(sorted(nominated_ids))
    by_id = {r.observation_id: r for r in page_segments}
    roles = tuple(by_id[i] for i in nominated if i in by_id)

    def done(status, reason_codes, *, axis=None, along=None, band=None, terminals=(), fragments=()):
        root = (ownership.document_id, ownership.revision_id, ownership.snapshot_id, ownership.source_sha256,
                ownership.page_id)
        nomination_id = stable_contract_id("shadow_strip_nomination", {"root": root, "ids": nominated})
        record_id = stable_contract_id("shadow_strip_structural_assessment", {
            "root": root, "viewport": viewport.view_id if viewport else None, "ids": nominated,
            "status": status.value, "reasons": tuple(reason_codes),
            "fragments": tuple(sorted((f.candidate_id, f.existence) for f in fragments))})
        atom = EvidenceAtom(
            evidence_id=stable_contract_id("shadow_strip_structural_atom", {"record": record_id}),
            document_id=ownership.document_id, page_id=ownership.page_id, kind=KIND_UNKNOWN,
            method=STRIP_ASSESSMENT_METHOD, viewport_id=viewport.view_id if viewport else None,
            bbox=(along[0], band[0], along[1], band[1]) if (axis == "H" and along and band) else
            ((band[0], along[0], band[1], along[1]) if (axis == "V" and along and band) else None),
            status=status, reason_codes=tuple(reason_codes),
            metadata={
                "revision_id": ownership.revision_id, "source_sha256": ownership.source_sha256,
                "snapshot_id": ownership.snapshot_id, "polarity": POLARITY_UNKNOWN,
                "source_observation_ids": nominated, "nomination_id": nomination_id,
                "fragment_candidate_ids": tuple(sorted(f.candidate_id for f in fragments)),
                **{flag: False for flag in _GRANT_FLAGS}})
        return StripStructuralAssessment(
            ownership=ownership, viewport_id=viewport.view_id if viewport else None, status=status,
            reason_codes=tuple(reason_codes), standing_limits=STANDING_LIMITS, nomination_id=nomination_id,
            nominated_observation_ids=nominated, axis=axis, along_extent=along, band_extent=band, roles=roles,
            terminals=tuple(terminals), fragments=tuple(fragments), evidence_atoms=(atom,), record_id=record_id)

    ABSTAIN, CONFLICT = EvidenceResolutionStatus.ABSTAINED, EvidenceResolutionStatus.CONFLICT
    if not nominated or len(set(nominated)) != len(nominated) or any(i not in by_id for i in nominated):
        return done(ABSTAIN, (NOMINATION_NOT_VISIBLE_ON_PAGE,))
    if any(not r.role_verified or r.stroke_width is None for r in roles):
        return done(ABSTAIN, (SOURCE_ROLE_UNPROVEN, SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE))
    hypothesis, failure = _hypothesis(roles, eq)
    if hypothesis is None:
        return done(ABSTAIN, (failure,))
    axis, along, band = hypothesis
    strip_box = (along[0], band[0], along[1], band[1]) if axis == "H" else (band[0], along[0], band[1], along[1])
    if viewport is None or not (viewport.bbox[0] <= strip_box[0] and viewport.bbox[1] <= strip_box[1]
                                and strip_box[2] <= viewport.bbox[2] and strip_box[3] <= viewport.bbox[3]):
        return done(ABSTAIN, (OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,), axis=axis, along=along, band=band)
    nominated_set = frozenset(nominated)
    terminals = _terminal_inventory(page_segments, nominated_set, axis, along, band, eq)
    if terminals is None:
        return done(ABSTAIN, (TERMINAL_BUDGET_EXCEEDED,), axis=axis, along=along, band=band)

    fragments: list[FragmentObservation] = []
    for candidate_id, pattern, members in candidates:
        member_roles = [by_id[m] for m in members if m in by_id]
        shared = len(nominated_set & set(members))
        if member_roles and len(member_roles) == len(members):
            xs = [v for r in member_roles for v in (r.geometry[0], r.geometry[2])]
            ys = [v for r in member_roles for v in (r.geometry[1], r.geometry[3])]
            box = (min(xs), min(ys), max(xs), max(ys))
            (a0, a1), (c0, c1) = _along_across(box, axis)
            overlaps = shared > 0 or not (box[2] < strip_box[0] - eq or box[0] > strip_box[2] + eq
                                          or box[3] < strip_box[1] - eq or box[1] > strip_box[3] + eq)
            member_span, across_span = (a0, a1), (c0, c1)
            # the opening is the gap between the two jambs: members perpendicular to the strip axis
            jambs = sorted({round(_along_across(r.geometry, axis)[0][0], 6) for r in member_roles
                            if _orientation(r.geometry, axis, eq) == "perpendicular"})
            merged = [j for k, j in enumerate(jambs) if k == 0 or j - jambs[k - 1] > eq]
            gap_span = (merged[0], merged[-1]) if len(merged) == 2 else None
        else:
            overlaps, member_span, across_span, gap_span = shared > 0, None, None, None
        if not overlaps:
            continue
        members_lo = bool(member_span and member_span[0] < along[0] - eq)
        members_hi = bool(member_span and member_span[1] > along[1] + eq)
        gap_lo = bool(gap_span and gap_span[0] < along[0] - eq)
        gap_hi = bool(gap_span and gap_span[1] > along[1] + eq)
        spans_whole = bool(gap_span and abs(gap_span[0] - along[0]) <= eq and abs(gap_span[1] - along[1]) <= eq)
        strong = pattern == JAMB_BOUNDED_TWO_FACE_INTERRUPTION
        if frozenset(members) in corroborated_member_sets:
            existence = "corroborated"
        elif any(member_status.get(m) in ("conflict", "corroborated") for m in members):
            existence = "contested"
        else:
            existence = "unresolved"
        fragments.append(FragmentObservation(
            candidate_id=candidate_id, structural_pattern=pattern, member_observation_ids=tuple(sorted(members)),
            member_span=member_span, across_span=across_span, gap_span=gap_span, shares_nominated_members=shared,
            overlaps_strip=True, members_cross_lo_terminal=members_lo, members_cross_hi_terminal=members_hi,
            gap_crosses_lo_terminal=gap_lo, gap_crosses_hi_terminal=gap_hi, spans_whole_extent=spans_whole,
            strong_pattern=strong, existence=existence, rival_evidence_only=not strong))
    fragments.sort(key=lambda f: f.candidate_id)
    common = dict(axis=axis, along=along, band=band, terminals=terminals, fragments=fragments)

    whole = [f for f in fragments if f.spans_whole_extent and f.strong_pattern]
    corroborated = [f for f in fragments if f.existence == "corroborated"]
    if not fragments:
        return done(ABSTAIN, (VISIBLE_WALL_CONTINUATION_REQUIRED, TERMINAL_ROLE_UNPROVEN), **common)
    if len(fragments) == 1 and len(whole) == 1:
        if whole[0].existence == "corroborated":
            return done(EvidenceResolutionStatus.CANDIDATE, (WHOLE_EXTENT_CANDIDATE_PRESENT, TERMINAL_ROLE_UNPROVEN),
                        **common)
        return done(ABSTAIN, (AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES if whole[0].existence == "contested"
                              else VISIBLE_WALL_CONTINUATION_REQUIRED, TERMINAL_ROLE_UNPROVEN), **common)
    if whole:
        return done(CONFLICT, (AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES, TERMINAL_ROLE_UNPROVEN), **common)
    if corroborated or any(f.existence == "contested" for f in fragments):
        return done(CONFLICT, (AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES, FRAGMENTS_ONLY, TERMINAL_ROLE_UNPROVEN),
                    **common)
    return done(ABSTAIN, (FRAGMENTS_ONLY, TERMINAL_ROLE_UNPROVEN), **common)


# --------------------------------------------------------------------------------------
# producer adapter
# --------------------------------------------------------------------------------------


class StripStructuralAssessmentShadow:
    """Read-only assessment bound to one `SourceVisibilityProducer`; default OFF."""

    def __init__(self, source, *, enabled: bool = False):
        from pb_source_visibility_authority import SourceVisibilityProducer

        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be a producer-owned SourceVisibilityProducer")
        if type(enabled) is not bool:
            raise ValueError("strip structural assessment gate must be an explicit boolean")
        self._source = source
        self._enabled = enabled
        # Authority calls run on an INDEPENDENT replay of the immutable original bytes (the producer's own fork
        # mechanism), so neither the producer's cached opening authority nor any producer-level memo the existing
        # consumers fill (paint, dimension, viewport proofs) is touched by an assessment.
        self._forks: dict = {}

    def _fork_for(self, revision_id: str, published):
        """An independent replay whose revision, snapshot and visible observation ids equal the original's."""
        if revision_id not in self._forks:
            try:
                fork, _ = self._source.fork_native_source_shadow(revision_id)
                replayed = fork.published_snapshot_for_revision(revision_id)
                same = (replayed is not None
                        and replayed.revision.source_sha256 == published.revision.source_sha256
                        and replayed.snapshot.snapshot_id == published.snapshot.snapshot_id
                        and tuple(replayed.visible_observation_ids) == tuple(published.visible_observation_ids))
                self._forks[revision_id] = fork if same else None
            except (ValueError, RuntimeError):
                self._forks[revision_id] = None
        return self._forks[revision_id]

    def _disabled(self) -> StripStructuralAssessment:
        return StripStructuralAssessment(
            ownership=None, viewport_id=None, status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(ASSESSMENT_DISABLED,), standing_limits=STANDING_LIMITS, nomination_id=None,
            nominated_observation_ids=(), axis=None, along_extent=None, band_extent=None, roles=(),
            terminals=(), fragments=(), evidence_atoms=(), record_id=None)

    def assess(self, *, revision_id: str, page_id: int, nominated_observation_ids: Sequence[str],
               coordinate_quantum_pt: float) -> StripStructuralAssessment:
        if not self._enabled:
            return self._disabled()
        if (type(revision_id) is not str or type(page_id) is not int or isinstance(page_id, bool)
                or isinstance(nominated_observation_ids, (str, bytes))
                or any(type(i) is not str or not i for i in nominated_observation_ids)
                or not (type(coordinate_quantum_pt) in (int, float) and coordinate_quantum_pt > 0
                        and math.isfinite(coordinate_quantum_pt))):
            raise ValueError("revision id, integer page id, string observation ids and a positive quantum required")
        import fitz

        from pb_source_observation_authority import ObservationSelector
        from pb_source_visibility_authority import VISIBLE_SOURCE_OBSERVATION_EXISTS
        from pb_vector_geometry_v130 import extract_native_page
        from pb_viewport_segmentation import ViewportSegmentationStatus, segment_page_viewports

        source = self._source
        failure = lambda *codes: StripStructuralAssessment(   # noqa: E731
            ownership=None, viewport_id=None, status=EvidenceResolutionStatus.ABSTAINED, reason_codes=tuple(codes),
            standing_limits=STANDING_LIMITS, nomination_id=None, nominated_observation_ids=(), axis=None,
            along_extent=None, band_extent=None, roles=(), terminals=(), fragments=(), evidence_atoms=(),
            record_id=None)
        published = source.published_snapshot_for_revision(revision_id)
        if published is None:
            return failure(VISIBLE_SOURCE_AUTHORITY_REQUIRED)
        document_id = published.revision.document_id
        if (page_id not in tuple(int(v) for v in published.coverage.decoded_pages)
                or int(page_id) in tuple(int(v) for v in published.coverage.failed_pages)
                or source._producer.current_revision_id(document_id) != revision_id):
            return failure(VISIBLE_SOURCE_AUTHORITY_REQUIRED)
        source_bytes = source._producer._store.source_bytes_by_revision.get(revision_id)
        if source_bytes is None or hashlib.sha256(source_bytes).hexdigest() != published.revision.source_sha256:
            return failure(SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE)
        ownership = AssessmentOwnership(document_id, revision_id, published.snapshot.snapshot_id,
                                        published.revision.source_sha256, str(page_id))

        def selector(observation_id: str) -> ObservationSelector:
            return ObservationSelector(document_id, revision_id, ownership.source_sha256, ownership.snapshot_id,
                                       observation_id)

        # one pass over the page: visible observations re-resolved by the producer, joined to its own primitive
        with fitz.open(stream=bytes(source_bytes), filetype="pdf") as document:
            page = document[page_id - 1]
            primitives = {s["id"]: s for s in extract_native_page(page)["segments"]}
            segmented = segment_page_viewports(page, page_number=page_id)
        visibility = source.authority()
        page_segments: list[SourceRole] = []
        for observation_id in published.visible_observation_ids:
            result = visibility.resolve_visible(selector(observation_id))
            observation = result.observation
            if (result.status is not EvidenceResolutionStatus.CORROBORATED
                    or result.proposition != VISIBLE_SOURCE_OBSERVATION_EXISTS or observation is None
                    or str(observation.page_id) != str(page_id) or len(observation.geometry) != 4):
                continue
            geometry = tuple(float(v) for v in observation.geometry)
            primitive = primitives.get(str(observation.source_primitive_ref).removeprefix("visible:segment:"))
            verified = (primitive is not None
                        and geometry == (float(primitive["x1"]), float(primitive["y1"]),
                                         float(primitive["x2"]), float(primitive["y2"]))
                        and bool(primitive.get("width_present")) and bool(primitive.get("stroke_present")))
            page_segments.append(SourceRole(
                observation_id=str(observation_id), geometry=geometry,
                stroke_width=float(primitive["width"]) if verified else None,
                stroke_rgb=tuple(float(c) for c in primitive["stroke"]) if verified else None,
                kind=str(primitive["kind"]) if primitive is not None else "unknown", role_verified=verified))

        # one positively authenticated RESOLVED floor-plan viewport containing the strip, or no verdict
        floor_plans = [v for v in segmented if v.status == ViewportSegmentationStatus.RESOLVED.value
                       and v.bounding_box is not None and v.view_type == "floor_plan"]
        by_id = {r.observation_id: r for r in page_segments}
        nominated = tuple(sorted(set(nominated_observation_ids)))
        viewport: Optional[ViewportRef] = None
        if nominated and all(i in by_id for i in nominated):
            xs = [v for i in nominated for v in (by_id[i].geometry[0], by_id[i].geometry[2])]
            ys = [v for i in nominated for v in (by_id[i].geometry[1], by_id[i].geometry[3])]
            box = (min(xs), min(ys), max(xs), max(ys))
            holders = [v for v in floor_plans if v.bounding_box[0] <= box[0] and v.bounding_box[1] <= box[1]
                       and box[2] <= v.bounding_box[2] and box[3] <= v.bounding_box[3]]
            if len(holders) == 1:
                viewport = ViewportRef(str(holders[0].view_id), tuple(float(c) for c in holders[0].bounding_box))

        candidates: list[tuple[str, str, tuple[str, ...]]] = []
        corroborated_sets: set[frozenset] = set()
        member_status: dict[str, str] = {}
        if nominated and all(i in by_id for i in nominated) and viewport is not None:
            fork = self._fork_for(revision_id, published)
            if fork is None:
                return failure(SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE)
            authority = fork.physical_opening_authority()
            structures = authority.visible_candidate_structures(selector(nominated[0]))
            nominated_set = set(nominated)
            wanted = []
            for c in structures.candidates:
                members = tuple(c.source_observation_ids)
                if nominated_set & set(members) or _touches(members, by_id, nominated, eq=coordinate_quantum_pt * 0.25):
                    wanted.append(c)
            for c in wanted:
                candidates.append((c.candidate_id, c.structural_pattern, tuple(sorted(c.source_observation_ids))))
            for member in sorted({m for c in wanted for m in c.source_observation_ids}):
                outcome = authority.prove_existence(selector(member))
                member_status[member] = outcome.status.value
                record = outcome.existence_record
                if record is not None and outcome.status is EvidenceResolutionStatus.CORROBORATED:
                    corroborated_sets.add(frozenset(record.source_observation_ids))
        return assess_strip_hypothesis(
            ownership=ownership, viewport=viewport, nominated_ids=nominated, page_segments=page_segments,
            candidates=candidates, corroborated_member_sets=frozenset(corroborated_sets),
            member_status=member_status, coordinate_quantum_pt=float(coordinate_quantum_pt))


def _touches(members, by_id, nominated, *, eq: float) -> bool:
    """Does a candidate's member box meet the nominated strip's box (necessary overlap filter only)?"""
    if not all(m in by_id for m in members) or not all(i in by_id for i in nominated):
        return False
    xs = [v for i in nominated for v in (by_id[i].geometry[0], by_id[i].geometry[2])]
    ys = [v for i in nominated for v in (by_id[i].geometry[1], by_id[i].geometry[3])]
    mx = [v for m in members for v in (by_id[m].geometry[0], by_id[m].geometry[2])]
    my = [v for m in members for v in (by_id[m].geometry[1], by_id[m].geometry[3])]
    return not (max(mx) < min(xs) - eq or min(mx) > max(xs) + eq or max(my) < min(ys) - eq or min(my) > max(ys) + eq)


__all__ = [
    "ASSESSMENT_DISABLED", "AssessmentOwnership", "FragmentObservation", "SourceRole", "STANDING_LIMITS",
    "STRIP_STRUCTURAL_ASSESSMENT_SCHEMA_VERSION", "StripStructuralAssessment", "StripStructuralAssessmentShadow",
    "TerminalInk", "ViewportRef", "assess_strip_hypothesis",
]
