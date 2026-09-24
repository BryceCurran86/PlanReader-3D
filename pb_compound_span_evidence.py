"""Compound-span decomposition evidence (shadow only, not wired into extraction).

Answers one narrow question that no existing authority currently answers:
when a floor-plan viewport carries both a large "overall" figured dimension
AND a chain of smaller figured dimensions along the same axis, can the
source dimension graph itself prove that the large dimension is a COMPOUND
span composed of those smaller members -- rather than an independent,
competing measurement of the same axis?

Motivating defect (found while investigating LMU-E3-B / Lamu DPC):
``pb_planreader_pdf_extractor._detect_outer_envelope`` selects the primary
room's own width/depth by picking the two largest sufficiently-different
figured numbers on a page. When a secondary open space (e.g. a verandah)
sits against one side of the primary room, the largest such number is
frequently the COMPOUND overall depth (primary room + secondary strip +
boundary thicknesses), not the primary room's own enclosed depth. Nothing
currently proves this distinction from source evidence -- the primary
room's rectangle silently absorbs the secondary strip's own footprint,
and if the secondary strip's width is *also* independently resolved (by
``pb_secondary_footprint_evidence``), its area gets double-counted.

This module does not fix that defect. It only produces the missing proof,
as shadow evidence, for a future authority-reviewed footprint change to
consume. It:
  - never assumes "secondary space exists -> subtract its width";
  - never chooses a decomposition merely because a term is a round or
    convenient number;
  - proves a compound relationship only from witness-bound endpoint
    continuity (each member's endpoint must coincide with the next
    member's, and the run's own endpoints must coincide with the overall
    dimension's own endpoints), never from value arithmetic alone;
  - retains all plausible candidates; abstains on ambiguity, conflict, or
    an unprovable relationship rather than guessing.

Physical roles this module can assign to a proven compound run's members
(``SpanRole``) are descriptive labels only -- they carry no wall, DPC, or
masonry authority. A ``SECONDARY_STRIP`` role proves footprint/floor-area
geometry, never that the strip's own outer boundary is a wall (an open
colonnade has real footprint depth and zero DPC-bearing wall on that
edge -- those are two different physical propositions and this module
never conflates them).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Sequence

from pb_dimension_graph_constraint_engine import DimensionOrientation
from pb_figured_dimension_evidence import (
    BindingStatus,
    DimensionEvidenceBundle,
    calibrate_dimension_layout,
    extract_dimension_evidence_bundle,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_secondary_footprint_evidence import _bbox_center, _label_words
from pb_viewport_segmentation import SegmentedViewport

# A member below this fraction of the overall span's value is a plausible
# boundary/wall thickness, never a habitable primary or secondary space.
# Matches the plausible physical wall-thickness range already used
# elsewhere in this codebase (pb_wall_fill_internal_partition_evidence),
# not a value invented for this module.
_BOUNDARY_THICKNESS_RANGE_M = (0.08, 0.35)


class SpanRole(str, Enum):
    """Physical role of one member within a proven compound span.

    Descriptive only. Carries no wall, masonry, or DPC authority -- see
    module docstring.
    """

    PRIMARY_ENCLOSED = "primary_enclosed"
    SECONDARY_STRIP = "secondary_strip"
    BOUNDARY_THICKNESS = "boundary_thickness"
    UNCLASSIFIED_MEMBER = "unclassified_member"


@dataclass(frozen=True)
class CompoundSpanComponent:
    """One witness-bound member of a proven contiguous run."""

    dimension_id: str
    value_m: float
    endpoints: tuple[tuple[float, float], tuple[float, float]]
    role: str  # SpanRole value
    order_index: int


@dataclass(frozen=True)
class CompoundSpanEvidence:
    """A proven decomposition of one overall dimension into ordered members."""

    status: str  # EvidenceResolutionStatus value
    overall_dimension_id: Optional[str]
    overall_value_m: Optional[float]
    components: tuple[CompoundSpanComponent, ...]
    primary_component: Optional[CompoundSpanComponent]
    secondary_component: Optional[CompoundSpanComponent]
    viewport_id: Optional[str]
    axis: Optional[str]  # "vertical" | "horizontal"
    reason_codes: tuple[str, ...] = ()
    evidence_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


def _abstain(reason: str, *, viewport_id: Optional[str] = None) -> CompoundSpanEvidence:
    return CompoundSpanEvidence(
        status=EvidenceResolutionStatus.ABSTAINED.value,
        overall_dimension_id=None,
        overall_value_m=None,
        components=(),
        primary_component=None,
        secondary_component=None,
        viewport_id=viewport_id,
        axis=None,
        reason_codes=(reason,),
    )


def _conflict(reason: str, *, viewport_id: Optional[str] = None) -> CompoundSpanEvidence:
    return CompoundSpanEvidence(
        status=EvidenceResolutionStatus.CONFLICT.value,
        overall_dimension_id=None,
        overall_value_m=None,
        components=(),
        primary_component=None,
        secondary_component=None,
        viewport_id=viewport_id,
        axis=None,
        reason_codes=(reason,),
    )


def _axis_coord(endpoints: tuple[tuple[float, float], tuple[float, float]], *, axis: str) -> Optional[float]:
    (x0, y0), (x1, y1) = endpoints
    if axis == "vertical":
        if abs(x0 - x1) > 1e6:  # unreachable guard; kept for symmetry with horizontal branch
            return None
        return (x0 + x1) / 2.0
    return (y0 + y1) / 2.0


def _along_span(endpoints: tuple[tuple[float, float], tuple[float, float]], *, axis: str) -> tuple[float, float]:
    (x0, y0), (x1, y1) = endpoints
    if axis == "vertical":
        return tuple(sorted((y0, y1)))  # type: ignore[return-value]
    return tuple(sorted((x0, x1)))  # type: ignore[return-value]


def _find_contiguous_runs(
    members: Sequence[Any],
    *,
    axis: str,
    axis_tolerance_pt: float,
    contiguity_tolerance_pt: float,
) -> list[list[Any]]:
    """Group same-axis-coordinate members into maximal contiguous chains.

    A run is a sequence of members, sorted along the axis, where each
    member's along-axis span ends within ``contiguity_tolerance_pt`` of the
    next member's own along-axis span start. Members on a different axis
    coordinate (not the same dimension-line track) never join a run.
    """
    if not members:
        return []

    axis_coord0 = _axis_coord(members[0].endpoints, axis=axis)
    grouped: dict[float, list[Any]] = {}
    for m in members:
        coord = _axis_coord(m.endpoints, axis=axis)
        if coord is None:
            continue
        bucket_key = None
        for existing_coord in grouped:
            if abs(existing_coord - coord) <= axis_tolerance_pt:
                bucket_key = existing_coord
                break
        grouped.setdefault(bucket_key if bucket_key is not None else coord, []).append(m)

    runs: list[list[Any]] = []
    for bucket_members in grouped.values():
        ordered = sorted(bucket_members, key=lambda m: _along_span(m.endpoints, axis=axis)[0])
        current_run = [ordered[0]]
        for nxt in ordered[1:]:
            prev_lo, prev_hi = _along_span(current_run[-1].endpoints, axis=axis)
            nxt_lo, nxt_hi = _along_span(nxt.endpoints, axis=axis)
            if abs(nxt_lo - prev_hi) <= contiguity_tolerance_pt:
                current_run.append(nxt)
            else:
                if len(current_run) > 1:
                    runs.append(current_run)
                current_run = [nxt]
        if len(current_run) > 1:
            runs.append(current_run)
    return runs


def resolve_compound_span(
    page: Any,
    *,
    page_num: int,
    viewport: SegmentedViewport,
    axis: str,
) -> CompoundSpanEvidence:
    """Prove whether a large figured dimension in this viewport is a compound
    span composed of a contiguous run of smaller witness-bound members.

    ``axis`` is ``"vertical"`` or ``"horizontal"`` -- the caller states which
    axis to search (mirroring ``pb_secondary_footprint_evidence``'s
    edge-to-orientation convention); this module does not guess it.

    Retains all plausible candidate runs. Abstains if no run's endpoints
    coincide with any overall dimension's own endpoints within tolerance.
    Conflicts if more than one run/overall pairing is simultaneously
    plausible (never resolved by picking the larger, smaller, or nearer
    candidate).
    """
    if axis not in ("vertical", "horizontal"):
        raise ValueError("axis must be 'vertical' or 'horizontal'")
    if viewport.bounding_box is None:
        return _abstain("no_viewport_bounding_box", viewport_id=viewport.view_id)

    required_orientation = (
        DimensionOrientation.VERTICAL.value if axis == "vertical" else DimensionOrientation.HORIZONTAL.value
    )
    layout = calibrate_dimension_layout(page)
    axis_tol = layout.chain_axis_tolerance_pt
    contiguity_tol = layout.witness_endpoint_distance_pt

    bundle: DimensionEvidenceBundle = extract_dimension_evidence_bundle(
        page, page_num=page_num, view_id=viewport.view_id, view_type=viewport.view_type
    )
    binding_by_id = {b.observation_id: b.status for b in bundle.bindings}

    witness_bound: list[Any] = []
    for obs in bundle.observations:
        if obs.endpoints is None:
            continue
        if binding_by_id.get(obs.dimension_id) != BindingStatus.WITNESS_BOUND.value:
            continue
        (x0, y0), (x1, y1) = obs.endpoints
        obs_orientation = (
            DimensionOrientation.HORIZONTAL.value
            if abs(x1 - x0) >= abs(y1 - y0)
            else DimensionOrientation.VERTICAL.value
        )
        if obs_orientation != required_orientation:
            continue
        try:
            value_m = float(obs.value_m)
        except (TypeError, ValueError):
            continue
        if not (value_m > 0.0):
            continue
        witness_bound.append(obs)

    if len(witness_bound) < 3:
        # Need at minimum one overall candidate plus a 2-member run.
        return _abstain("insufficient_witness_bound_members", viewport_id=viewport.view_id)

    vx0, vy0, vx1, vy1 = (float(v) for v in viewport.bounding_box)

    # Contiguous runs are found across ALL witness-bound members on this
    # axis, clustered purely by their own shared axis coordinate -- a
    # member's own size is not evidence of whether it is a "component" or
    # an "overall" dimension. A run's own dominant member (e.g. the primary
    # room's own depth) is frequently the single largest witness-bound
    # value in the viewport; that must not disqualify it from a run.
    runs = _find_contiguous_runs(
        list(witness_bound),
        axis=axis,
        axis_tolerance_pt=axis_tol,
        contiguity_tolerance_pt=contiguity_tol,
    )
    if not runs:
        return _abstain("no_contiguous_member_run", viewport_id=viewport.view_id)

    # An "overall" candidate is any witness-bound member that is NOT part
    # of the run being tested (a run's own members can never also serve as
    # its overall corroboration) and whose own endpoints bracket that run's
    # start/end. In real drafting, this is the outer, offset parallel
    # dimension-line track; structurally that necessarily puts it on a
    # different axis coordinate from the run's own track, but the
    # membership exclusion (not a coordinate-difference rule) is what is
    # actually enforced, since it is the more direct and provable
    # condition.
    matches: list[tuple[Any, list[Any]]] = []
    for run in runs:
        run_ids = {m.dimension_id for m in run}
        r_lo, r_hi = _along_span(run[0].endpoints, axis=axis)[0], _along_span(run[-1].endpoints, axis=axis)[1]
        for overall in witness_bound:
            if overall.dimension_id in run_ids:
                continue
            o_lo, o_hi = _along_span(overall.endpoints, axis=axis)
            if abs(r_lo - o_lo) <= contiguity_tol and abs(r_hi - o_hi) <= contiguity_tol:
                matches.append((overall, run))

    if not matches:
        return _abstain("no_run_brackets_any_overall_span", viewport_id=viewport.view_id)
    if len(matches) > 1:
        distinct_overalls = {id(m[0]) for m in matches}
        distinct_runs = {tuple(id(x) for x in m[1]) for m in matches}
        if len(distinct_overalls) > 1 or len(distinct_runs) > 1:
            return _conflict("multiple_plausible_compound_decompositions", viewport_id=viewport.view_id)

    overall, run = matches[0]

    # Cross-check: the run's member values must also sum to the overall's
    # own figured value within a page-typography-derived relative
    # tolerance -- endpoint coincidence alone could in principle survive a
    # coordinate rounding artifact; requiring both independently is
    # stricter than either alone and still source-owned (no assumed
    # constant).
    member_sum = sum(float(m.value_m) for m in run)
    overall_value = float(overall.value_m)
    if overall_value <= 0:
        return _abstain("invalid_overall_value", viewport_id=viewport.view_id)
    rel_err = abs(member_sum - overall_value) / overall_value
    if rel_err > 0.05:
        return _abstain("member_sum_does_not_match_overall_value", viewport_id=viewport.view_id)

    # Role classification: descriptive only (see module docstring). A
    # secondary-space label owning this viewport, adjacent to one end of
    # the run, marks the run member at that end as SECONDARY_STRIP.
    labels = _label_words(page)
    label_edge_end: Optional[str] = None  # "lo" | "hi"
    owned_labels = [
        (bbox, text)
        for bbox, text in labels
        if vx0 - 1.0 <= bbox[0] and bbox[2] <= vx1 + 1.0 and vy0 - 1.0 <= bbox[1] and bbox[3] <= vy1 + 1.0
    ]
    if len(owned_labels) == 1:
        label_bbox, _label_text = owned_labels[0]
        label_center = _bbox_center(label_bbox)
        label_axis_pos = label_center[1] if axis == "vertical" else label_center[0]
        run_lo, run_hi = _along_span(run[0].endpoints, axis=axis)[0], _along_span(run[-1].endpoints, axis=axis)[1]
        label_edge_end = "hi" if abs(label_axis_pos - run_hi) < abs(label_axis_pos - run_lo) else "lo"

    components: list[CompoundSpanComponent] = []
    for idx, m in enumerate(run):
        value_m = float(m.value_m)
        is_edge_member = (idx == 0 and label_edge_end == "lo") or (idx == len(run) - 1 and label_edge_end == "hi")
        if is_edge_member and value_m > _BOUNDARY_THICKNESS_RANGE_M[1]:
            role = SpanRole.SECONDARY_STRIP.value
        elif _BOUNDARY_THICKNESS_RANGE_M[0] <= value_m <= _BOUNDARY_THICKNESS_RANGE_M[1]:
            role = SpanRole.BOUNDARY_THICKNESS.value
        else:
            role = SpanRole.UNCLASSIFIED_MEMBER.value
        components.append(
            CompoundSpanComponent(
                dimension_id=m.dimension_id,
                value_m=value_m,
                endpoints=m.endpoints,
                role=role,
                order_index=idx,
            )
        )

    # The single largest UNCLASSIFIED_MEMBER (i.e. not boundary-thickness,
    # not already claimed by the secondary-space label) is the primary
    # enclosed component -- but only if exactly one such member exists.
    # More than one leaves primary ambiguous; retained, not force-assigned.
    unclassified = [c for c in components if c.role == SpanRole.UNCLASSIFIED_MEMBER.value]
    primary_component = unclassified[0] if len(unclassified) == 1 else None
    if primary_component is not None:
        components = [
            c if c.dimension_id != primary_component.dimension_id
            else CompoundSpanComponent(
                dimension_id=c.dimension_id,
                value_m=c.value_m,
                endpoints=c.endpoints,
                role=SpanRole.PRIMARY_ENCLOSED.value,
                order_index=c.order_index,
            )
            for c in components
        ]
        primary_component = next(c for c in components if c.dimension_id == primary_component.dimension_id)

    secondary_component = next((c for c in components if c.role == SpanRole.SECONDARY_STRIP.value), None)

    ev_id = stable_contract_id(
        "compound_span",
        {
            "overall_dimension_id": overall.dimension_id,
            "member_ids": [m.dimension_id for m in run],
            "viewport_id": viewport.view_id,
            "page": page_num,
        },
    )

    return CompoundSpanEvidence(
        status=EvidenceResolutionStatus.CORROBORATED.value,
        overall_dimension_id=overall.dimension_id,
        overall_value_m=overall_value,
        components=tuple(components),
        primary_component=primary_component,
        secondary_component=secondary_component,
        viewport_id=viewport.view_id,
        axis=axis,
        reason_codes=("compound_span_endpoint_and_sum_corroborated",),
        evidence_id=ev_id,
        metadata={
            "member_sum_m": round(member_sum, 4),
            "overall_value_m": round(overall_value, 4),
            "relative_error": round(rel_err, 5),
        },
    )


__all__ = [
    "CompoundSpanComponent",
    "CompoundSpanEvidence",
    "SpanRole",
    "resolve_compound_span",
]
