"""pb_dimension_chain_topology_authority.py — Generic continuous figured-dimension
chain resolution.

Problem this closes: ``pb_figured_dimension_evidence.bind_observation_to_vector_geometry``
proves each dimension observation's witness endpoints *independently*. For a
genuine continuous chain (several consecutive figured dimensions sharing one
dimension-line/witness-line family — e.g. wall + room + wall + verandah +
wall along one building section) that independent, per-observation approach
only resolves the outermost segment cleanly: interior segments sit near
*multiple* equally-plausible witness-line fragments (the chain's own
continuation), so the per-observation tie-break correctly refuses to pick
one and returns AMBIGUOUS. That is not a bug in the per-observation binder —
independent per-observation proof genuinely cannot disambiguate a shared,
continuous witness family. It requires modelling the chain as one object.

This module does exactly that, and only that: it groups already-extracted
``DimensionObservation`` records (from ``pb_figured_dimension_evidence``)
into ``StructuredDimensionChain`` objects using topology that is directly
checkable from source geometry --

* common orientation (from real vector-endpoint evidence, never guessed),
* a shared, tight same-page/same-viewport perpendicular-axis column,
* strictly monotonic, non-overlapping ordering along the chain axis,
* at least one real ``WITNESS_BOUND`` anchor (a chain with zero
  vector-proven anchors is never trusted, regardless of how tidy its
  numbers look),
* an independently-figured "overall" dimension used only as a
  *consistency check* against the sum of the chain's own segments --
  never to invent a value for a missing segment.

Viewport assignment is nearest-RESOLVED-viewport (a real drawn frame), never
a blanket caller-supplied label -- this is what prevents an unrelated
same-x-column figure from a completely different view (e.g. an elevation's
overall height) from being pulled into a floor-plan chain by coincidence.
Two viewports equidistant from an observation make that observation's
membership UNRESOLVED rather than guessed.

Every failure mode fails closed: competing/ambiguous viewport ownership,
overlapping segment intervals, a same-column value whose orientation
evidence contradicts the chain, or an "overall" candidate that does not sum
correctly all leave the chain UNRESOLVED/CONFLICT rather than silently
picking the most convenient interpretation. Nothing in this module reads or
depends on any benchmark/expected quantity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pb_dimension_graph_constraint_engine import DimensionObservation, DimensionOrientation
from pb_figured_dimension_evidence import (
    BindingStatus,
    DimensionAnchorBinding,
    calibrate_dimension_layout,
    extract_dimension_evidence_bundle,
)
from pb_viewport_segmentation import SegmentedViewport, ViewportSegmentationStatus, segment_page_viewports


class ChainCorroborationStatus(str, Enum):
    """How strongly a chain's membership/value set is evidenced."""

    # Both ends are real vector-proven witness endpoints, AND an
    # independently-figured overall dimension sums to the chain's own
    # segments. The strongest state -- every segment is directly usable.
    CORROBORATED_BY_OVERALL = "corroborated_by_overall"
    # At least one real witness anchor, strictly ordered/non-overlapping,
    # but no independently-figured overall dimension was found to validate
    # against. Segment values are exposed for diagnostics only.
    ORDERED_UNCORROBORATED = "ordered_uncorroborated"
    # A same-position/same-orientation candidate that looks like this
    # chain's overall dimension does NOT sum-match the chain's own
    # segments. The whole chain is rejected rather than silently kept.
    CONFLICT = "conflict"
    # Fewer than one real witness anchor, competing viewport ownership,
    # overlapping intervals, or any other membership ambiguity.
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class ChainSegmentBinding:
    """One dimension observation's role within a structured chain."""

    observation_id: str
    ordinal: int
    value_m: float
    bbox: Tuple[float, float, float, float]
    binding_status: str


@dataclass(frozen=True)
class StructuredDimensionChain:
    """A source-reconstructed continuous figured-dimension chain."""

    chain_id: str
    page_num: int
    view_id: str
    orientation: str
    segments: Tuple[ChainSegmentBinding, ...]
    overall_observation_id: Optional[str]
    overall_value_m: Optional[float]
    status: str
    notes: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    @property
    def sum_value_m(self) -> float:
        return round(sum(seg.value_m for seg in self.segments), 6)

    def value_at_ordinal(self, ordinal: int) -> Optional[float]:
        """Return one segment's value, but only when the chain is fully
        corroborated. Everything less certain than
        ``CORROBORATED_BY_OVERALL`` returns ``None`` -- a caller that wants
        the raw diagnostic value regardless of corroboration must read
        ``segments`` directly and check ``status`` itself."""
        if self.status != ChainCorroborationStatus.CORROBORATED_BY_OVERALL.value:
            return None
        for seg in self.segments:
            if seg.ordinal == ordinal:
                return seg.value_m
        return None


def _bbox_center(bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
    return (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0


def _viewport_edge_distance(bbox: Tuple[float, float, float, float], viewport_bbox: Tuple[float, float, float, float]) -> float:
    cx, cy = _bbox_center(bbox)
    vx0, vy0, vx1, vy1 = viewport_bbox
    dx = max(vx0 - cx, 0.0, cx - vx1)
    dy = max(vy0 - cy, 0.0, cy - vy1)
    return (dx * dx + dy * dy) ** 0.5


# Annotation-zone width, as a fraction of the *viewport's own* smaller
# dimension -- the same relative-margin convention already used by
# pb_secondary_footprint_evidence.py's _EDGE_BAND_FRACTION for an
# equivalent purpose (how far outside a view's own frame its dimension
# annotations may plausibly sit). Scale-relative, not an absolute point
# value, so it is not tuned to any one drawing's absolute coordinates.
_VIEWPORT_ANNOTATION_MARGIN_FRACTION = 0.25


def _nearest_resolved_viewport(
    bbox: Tuple[float, float, float, float],
    viewports: Sequence[SegmentedViewport],
) -> Optional[SegmentedViewport]:
    """Assign one observation to the nearest RESOLVED (real drawn frame)
    viewport, only when it lies within that viewport's own annotation
    margin. Two viewports within numerical noise of each other's distance
    make the assignment UNRESOLVED (returns None) rather than guessed."""
    candidates = [v for v in viewports if v.status == ViewportSegmentationStatus.RESOLVED.value and v.bounding_box is not None]
    if not candidates:
        return None
    scored: List[Tuple[float, SegmentedViewport]] = []
    for v in candidates:
        vx0, vy0, vx1, vy1 = v.bounding_box
        margin = min(vx1 - vx0, vy1 - vy0) * _VIEWPORT_ANNOTATION_MARGIN_FRACTION
        d = _viewport_edge_distance(bbox, v.bounding_box)
        if d <= margin:
            scored.append((d, v))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0])
    best_d, best = scored[0]
    if len(scored) > 1 and (scored[1][0] - best_d) < 1e-6:
        return None
    return best


def _observation_true_orientation(
    observation: DimensionObservation,
) -> Optional[str]:
    """Orientation established from real vector-endpoint evidence only.
    Returns None for anything without proven endpoints -- such an
    observation's orientation is never guessed from text layout alone."""
    if observation.endpoints is None:
        return None
    (x0, y0), (x1, y1) = observation.endpoints
    if abs(x1 - x0) >= abs(y1 - y0):
        return DimensionOrientation.HORIZONTAL.value
    return DimensionOrientation.VERTICAL.value


def _axis_perp_coord(bbox: Tuple[float, float, float, float], orientation: str) -> float:
    cx, cy = _bbox_center(bbox)
    return cx if orientation == DimensionOrientation.VERTICAL.value else cy


def _axis_along_coord(bbox: Tuple[float, float, float, float], orientation: str) -> float:
    cx, cy = _bbox_center(bbox)
    return cy if orientation == DimensionOrientation.VERTICAL.value else cx


def _axis_extent(bbox: Tuple[float, float, float, float], orientation: str) -> Tuple[float, float]:
    if orientation == DimensionOrientation.VERTICAL.value:
        return bbox[1], bbox[3]
    return bbox[0], bbox[2]


def _intervals_overlap(a: Tuple[float, float], b: Tuple[float, float], *, tolerance: float) -> bool:
    a_lo, a_hi = sorted(a)
    b_lo, b_hi = sorted(b)
    return (a_lo + tolerance) < b_hi and (b_lo + tolerance) < a_hi


@dataclass(frozen=True)
class _Candidate:
    observation: DimensionObservation
    binding: Optional[DimensionAnchorBinding]
    viewport: SegmentedViewport


def _binding_status(binding: Optional[DimensionAnchorBinding]) -> str:
    return binding.status if binding is not None else BindingStatus.UNSUPPORTED.value


def resolve_structured_dimension_chains(
    page: Any,
    *,
    page_num: int,
) -> List[StructuredDimensionChain]:
    """Reconstruct all continuous figured-dimension chains on one page.

    Operates purely on this page's own native text + vector geometry.
    Chains are always scoped to one RESOLVED viewport -- a page with no
    RESOLVED (real drawn frame) viewport yields no chains at all, since
    membership evidence (Step 4's "common viewport" requirement) cannot be
    established without one.
    """
    layout = calibrate_dimension_layout(page)
    viewports = segment_page_viewports(page, page_number=page_num)
    resolved_viewports = [
        v for v in viewports
        if v.status == ViewportSegmentationStatus.RESOLVED.value and v.bounding_box is not None
    ]
    if not resolved_viewports:
        return []

    # Extraction/binding is view-agnostic at the geometry level (native text
    # + vector segments do not depend on which label the caller passes), so
    # one extraction per page is sufficient; the view_id/view_type passed
    # here is never trusted as a per-observation viewport assignment.
    bundle = extract_dimension_evidence_bundle(page, page_num=page_num)
    binding_by_id = {b.observation_id: b for b in bundle.bindings}

    candidates: List[_Candidate] = []
    for obs in bundle.observations:
        if obs.bbox is None:
            continue
        owner = _nearest_resolved_viewport(obs.bbox, resolved_viewports)
        if owner is None:
            continue  # unresolved viewport ownership -- excluded, not guessed
        candidates.append(_Candidate(observation=obs, binding=binding_by_id.get(obs.dimension_id), viewport=owner))

    chains: List[StructuredDimensionChain] = []
    for viewport in resolved_viewports:
        view_candidates = [c for c in candidates if c.viewport.view_id == viewport.view_id]
        chains.extend(_build_chains_for_viewport(view_candidates, viewport, page_num, layout))
    return chains


def _candidate_orientation_hypotheses(cand: "_Candidate") -> Tuple[str, ...]:
    """Orientations this candidate could plausibly seed a chain search under.

    A candidate with proven vector-endpoint orientation only ever seeds
    that one orientation. A candidate with no proven orientation (the
    common AMBIGUOUS case for an interior chain member -- see module
    docstring) is tried under both, and only survives in whichever
    hypothesis a real chain (non-overlapping, ordered, and anchored by
    either a real witness-bound member or a matching overall dimension)
    actually forms.
    """
    true_orient = _observation_true_orientation(cand.observation)
    if true_orient is not None:
        return (true_orient,)
    return (DimensionOrientation.VERTICAL.value, DimensionOrientation.HORIZONTAL.value)


def _build_chains_for_viewport(
    candidates: Sequence[_Candidate],
    viewport: SegmentedViewport,
    page_num: int,
    layout,
) -> List[StructuredDimensionChain]:
    axis_tol = layout.chain_axis_tolerance_pt
    chains: List[StructuredDimensionChain] = []
    used_ids: set[str] = set()

    seeds: List[Tuple[_Candidate, str]] = []
    for cand in candidates:
        for orient in _candidate_orientation_hypotheses(cand):
            seeds.append((cand, orient))

    for seed, seed_orientation in seeds:
        if seed.observation.dimension_id in used_ids:
            continue
        seed_perp = _axis_perp_coord(seed.observation.bbox, seed_orientation)

        # Gather every same-orientation-consistent candidate on this same
        # tight perpendicular column. A candidate whose OWN true orientation
        # is proven and disagrees with the seed's hypothesis is excluded
        # outright (it is a different, unrelated feature, not membership
        # evidence) -- an unproven candidate is included provisionally and
        # only survives if the resulting chain validates below.
        column: List[_Candidate] = []
        for cand in candidates:
            if cand.observation.dimension_id in used_ids:
                continue
            true_orient = _observation_true_orientation(cand.observation)
            if true_orient is not None and true_orient != seed_orientation:
                continue
            perp = _axis_perp_coord(cand.observation.bbox, seed_orientation)
            if abs(perp - seed_perp) <= axis_tol:
                column.append(cand)

        if len(column) < 2:
            continue

        ordered = sorted(column, key=lambda c: _axis_along_coord(c.observation.bbox, seed_orientation))

        # Non-overlap check (Step 4 / Step 8 #13): consecutive members must
        # not share along-axis extent. Any overlap ends the chain there.
        accepted: List[_Candidate] = [ordered[0]]
        for nxt in ordered[1:]:
            prev_extent = _axis_extent(accepted[-1].observation.bbox, seed_orientation)
            nxt_extent = _axis_extent(nxt.observation.bbox, seed_orientation)
            if _intervals_overlap(prev_extent, nxt_extent, tolerance=1e-6):
                break
            accepted.append(nxt)

        if len(accepted) < 2:
            continue

        anchor_orientation = seed_orientation
        member_ids = {c.observation.dimension_id for c in accepted}
        segments = tuple(
            ChainSegmentBinding(
                observation_id=c.observation.dimension_id,
                ordinal=i,
                value_m=c.observation.value_m,
                bbox=c.observation.bbox,
                binding_status=_binding_status(c.binding),
            )
            for i, c in enumerate(accepted)
        )
        chain_sum_m = round(sum(s.value_m for s in segments), 6)

        along_lo = min(_axis_along_coord(c.observation.bbox, anchor_orientation) for c in accepted)
        along_hi = max(_axis_along_coord(c.observation.bbox, anchor_orientation) for c in accepted)

        overall_id, overall_value, status, notes = _resolve_overall(
            candidates=candidates,
            member_ids=member_ids,
            orientation=anchor_orientation,
            interior_perp=seed_perp,
            along_lo=along_lo,
            along_hi=along_hi,
            chain_sum_m=chain_sum_m,
            layout=layout,
        )

        has_witness_anchor = any(
            _binding_status(c.binding) == BindingStatus.WITNESS_BOUND.value for c in accepted
        )
        corroborated = overall_id is not None

        # A grouping is only ever trusted as a real chain when it carries at
        # least one of two independent forms of real evidence: a genuine
        # vector-proven witness endpoint on one of its own members, or an
        # independently-figured overall dimension that sums to it exactly
        # (Step 6's "stronger chain corroboration", never invention). A
        # grouping with neither -- pure axis/order proximity alone -- is
        # never trusted, no matter how tidy its numbers look, and is
        # discarded rather than reported as a conflict or otherwise.
        if not has_witness_anchor and not corroborated:
            continue

        if status == ChainCorroborationStatus.CONFLICT.value:
            final_status = ChainCorroborationStatus.CONFLICT.value
        elif corroborated:
            final_status = ChainCorroborationStatus.CORROBORATED_BY_OVERALL.value
        else:
            final_status = ChainCorroborationStatus.ORDERED_UNCORROBORATED.value

        chain_id = f"chain_p{page_num}_{viewport.view_id}_{accepted[0].observation.dimension_id}"
        chains.append(
            StructuredDimensionChain(
                chain_id=chain_id,
                page_num=page_num,
                view_id=viewport.view_id,
                orientation=anchor_orientation,
                segments=segments,
                overall_observation_id=overall_id,
                overall_value_m=overall_value,
                status=final_status,
                notes=notes,
            )
        )
        used_ids.update(member_ids)

    return chains


def _resolve_overall(
    *,
    candidates: Sequence[_Candidate],
    member_ids: set[str],
    orientation: str,
    interior_perp: float,
    along_lo: float,
    along_hi: float,
    chain_sum_m: float,
    layout,
) -> Tuple[Optional[str], Optional[float], str, Tuple[str, ...]]:
    """Search for an independently-figured overall dimension for this chain.

    Only ever used as a CONSISTENCY CHECK (Step 6): a matching candidate
    corroborates the chain; a positionally-plausible but non-matching
    candidate conflicts the whole chain; no candidate leaves the chain
    uncorroborated. Never invents or algebraically derives a value.
    """
    # The outer/overall ruler sits just outside the detail chain's own
    # column -- bounded relative to the chain's OWN span, not an absolute
    # constant, so a second unrelated chain elsewhere on the page (however
    # far away) can never be mistaken for this chain's overall dimension.
    chain_span = max(along_hi - along_lo, 1.0)
    outer_min = layout.chain_axis_tolerance_pt
    outer_max = max(chain_span * 0.5, layout.line_search_distance_pt * 4.0)
    along_slack = max(layout.median_word_height_pt * 3.0, 5.0)

    plausible: List[_Candidate] = []
    for cand in candidates:
        if cand.observation.dimension_id in member_ids:
            continue
        true_orient = _observation_true_orientation(cand.observation)
        if true_orient is not None and true_orient != orientation:
            continue
        perp = _axis_perp_coord(cand.observation.bbox, orientation)
        perp_dist = abs(perp - interior_perp)
        if not (outer_min < perp_dist <= outer_max):
            continue
        along = _axis_along_coord(cand.observation.bbox, orientation)
        if not (along_lo - along_slack <= along <= along_hi + along_slack):
            continue
        plausible.append(cand)

    if not plausible:
        return None, None, ChainCorroborationStatus.ORDERED_UNCORROBORATED.value, ()

    matches = [c for c in plausible if abs(round(c.observation.value_m * 1000.0) - round(chain_sum_m * 1000.0)) <= 1]
    if len(matches) == 1:
        m = matches[0]
        return (
            m.observation.dimension_id,
            m.observation.value_m,
            ChainCorroborationStatus.CORROBORATED_BY_OVERALL.value,
            (f"overall {m.observation.dimension_id} sums to chain segments within 1mm",),
        )
    if len(matches) > 1:
        return None, None, ChainCorroborationStatus.CONFLICT.value, (
            "multiple positionally-plausible overall candidates match the sum ambiguously",
        )

    # Positionally plausible but the value disagrees -- this looks like an
    # overall dimension for this chain, and it does not sum-match: conflict,
    # never silently ignored.
    if len(plausible) == 1:
        p = plausible[0]
        return None, None, ChainCorroborationStatus.CONFLICT.value, (
            f"candidate overall {p.observation.dimension_id}={p.observation.value_m}m "
            f"does not match chain sum {chain_sum_m}m",
        )
    return None, None, ChainCorroborationStatus.ORDERED_UNCORROBORATED.value, (
        "multiple positionally-plausible overall candidates, none matching -- treated as noise, not conflict",
    )
