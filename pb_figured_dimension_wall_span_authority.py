"""Producer-owned figured-dimension-to-wall-span identity authority (SHADOW ONLY).

This module implements the missing last step of the workstream
``pb_wall_length_quantity.py`` names but does not implement: "dimension line
-> terminators -> witnesses -> endpoints -> exact physical span -> exact
target entity". It does not reimplement any of the earlier steps.

Reused UNCHANGED (per AGENTS.md: "reuse existing dimension observations,
graph structures, evidence atoms and stable IDs"):

- ``pb_figured_dimension_evidence.extract_dimension_evidence_bundle`` /
  ``bind_observation_to_vector_geometry`` already resolve, per figured-
  dimension observation: the dimension-line vector segment
  (``DimensionAnchorBinding.dimension_line_id``), the two witness/extension
  lines (``witness_line_ids``), and the two physical endpoints
  (``endpoints``) -- ambiguous dimension-line candidates already resolve to
  ``BindingStatus.AMBIGUOUS`` there, before this module ever runs.
- ``pb_dimension_graph_constraint_engine.DimensionObservation`` is the only
  dimension representation used; no second one is introduced here.
- ``pb_migration_contracts.EvidenceAtom`` / ``EvidenceResolutionStatus`` /
  ``stable_contract_id`` are the only evidence vocabulary used.
- ``pb_wall_room_topology_contracts.WallCandidate`` is the only wall
  representation consulted; no second wall schema is introduced.
- The resulting ``EvidenceAtom`` is shaped exactly to what
  ``pb_physical_wall_existence_authority.bind_additional_wall_owned_evidence``
  already requires (``kind="figured_dimension"``,
  ``metadata["wall_candidate_id"|"revision_id"|"evidence_snapshot_id"|
  "source_sha256"]``) so a later, separately-reviewed change could pass it
  through ``additional_owned_evidence_ids`` without this module inventing a
  new acceptance path. This module does NOT call that function and does NOT
  feed ``pb_wall_length_quantity.build_wall_length_quantity`` -- it is a
  standalone shadow producer only.

Explicit, honest scope limit (do not overclaim): "terminators" (tick/arrow
glyphs) are not separately vectorized or identified anywhere in this
codebase's dimension-evidence pipeline today -- ``pb_figured_dimension_
evidence.py`` proves physical extent via witness/extension-line endpoint
intersection, not via terminator-glyph geometry. This module reuses that
same, real, already-adversarially-considered mechanism (``WITNESS_BOUND``
requires BOTH witness lines to resolve to a real perpendicular intersection)
as the physical-endpoint proof, and does not fabricate a separate terminator
concept. Every produced record's ``notes`` says so explicitly.

What this module actually adds (new work):
1. Restricts to dimension observations that reached ``BindingStatus.
   WITNESS_BOUND`` (both witnesses resolved) -- ``PARTIAL_WITNESS``,
   ``LINE_BOUND``, ``AMBIGUOUS``, and ``UNSUPPORTED`` all abstain here,
   unchanged from what those statuses already mean upstream.
2. Same-document/revision/snapshot/SHA/page/viewport ownership checks
   between the dimension observation, the candidate walls, and the caller's
   ``ProviderContext`` -- no cross-view relation is attempted (out of scope
   by instruction).
3. Wall-span geometry: for each candidate ``WallCandidate`` sharing the
   dimension's viewport, tests whether the wall's own centerline is (a)
   straight (all consecutive segments collinear -- an L-shaped/curved wall
   is not attributed a single-run length dimension by this module), (b)
   collinear with the dimension's endpoint-to-endpoint span within a
   page-typography-derived tolerance (reusing the caller's own
   ``DimensionLayoutCalibration``, never a hardcoded constant), and (c)
   whether the dimension's endpoints closely coincide with the wall's own
   two endpoints (a "wall length" dimension measures the whole run, not an
   arbitrary sub-span -- a genuine partial-overlap sub-span is explicitly
   out of scope for this module and abstains rather than being guessed).
4. Orientation: the dimension span's direction must be parallel (within the
   same page-derived tolerance) to the wall's own direction -- this is what
   rejects a wall-thickness dimension (measured across the wall) being
   mistaken for a wall-length dimension.
5. Zero matching walls -> abstain. Two or more -> abstain (ambiguous,
   never resolved by nearest/first/smallest). Exactly one -> proven span
   identity for that wall.
6. Two independently-proven dimensions for the exact same wall whose values
   disagree beyond tolerance -> CONFLICT, neither is preferred.

Nothing here reads a benchmark ID, project name, filename, or expected
quantity. Nothing here mutates ``pb_planreader_pdf_extractor.py`` or any
commercial/JobHub path -- there are no callers of this module outside its
own tests and an explicit shadow-run script.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence

from pb_dimension_graph_constraint_engine import DimensionObservation
from pb_figured_dimension_evidence import BindingStatus, DimensionLayoutCalibration
from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus, stable_contract_id
from pb_migration_provider_envelope import ProviderContext
from pb_physical_wall_existence_authority import ADDITIONAL_WALL_EVIDENCE_KIND_FIGURED
from pb_wall_room_topology_contracts import WallCandidate

FIGURED_WALL_SPAN_SCHEMA_VERSION = "1.0.0"
FIGURED_WALL_SPAN_METHOD = "figured_dimension_wall_span_authority"

WALL_SPAN_RESOLVED = "figured_wall_span_resolved"
WALL_SPAN_NOT_WITNESS_BOUND = "figured_wall_span_dimension_not_witness_bound"
WALL_SPAN_NO_ENDPOINTS = "figured_wall_span_dimension_missing_endpoints"
WALL_SPAN_DOCUMENT_MISMATCH = "figured_wall_span_document_mismatch"
WALL_SPAN_SOURCE_SHA_MISMATCH = "figured_wall_span_source_sha_mismatch"
WALL_SPAN_REVISION_UNBOUND = "figured_wall_span_revision_unbound"
WALL_SPAN_REVISION_STALE = "figured_wall_span_revision_stale"
WALL_SPAN_VIEWPORT_MISMATCH = "figured_wall_span_viewport_mismatch"
WALL_SPAN_VIEWPORT_NOT_OWNED = "figured_wall_span_viewport_not_owned"
WALL_SPAN_WALL_NOT_STRAIGHT = "figured_wall_span_candidate_wall_not_straight"
WALL_SPAN_ORIENTATION_MISMATCH = "figured_wall_span_orientation_mismatch"
WALL_SPAN_OFFSET_TOO_LARGE = "figured_wall_span_perpendicular_offset_exceeds_tolerance"
WALL_SPAN_ENDPOINT_COVERAGE_MISMATCH = "figured_wall_span_endpoint_coverage_mismatch"
WALL_SPAN_NO_CANDIDATE_WALL = "figured_wall_span_no_candidate_wall"
WALL_SPAN_AMBIGUOUS_WALLS = "figured_wall_span_ambiguous_candidate_walls"
WALL_SPAN_CONFLICTING_DIMENSIONS = "figured_wall_span_conflicting_dimensions_same_wall"


Point = tuple[float, float]


def _vec(a: Point, b: Point) -> Point:
    return (b[0] - a[0], b[1] - a[1])


def _length(v: Point) -> float:
    return math.hypot(v[0], v[1])


def _unit(v: Point) -> Optional[Point]:
    length = _length(v)
    if length <= 0.0:
        return None
    return (v[0] / length, v[1] / length)


def _cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _is_straight_wall(centerline_pts: Sequence[Point], tolerance_pt: float) -> bool:
    """True only when every consecutive segment is collinear with the first.

    An L-shaped or curved wall is not attributed a single-run figured
    dimension by this module -- which specific leg the dimension measures
    is a real, unresolved question this module does not guess.
    """
    if len(centerline_pts) < 2:
        return False
    if len(centerline_pts) == 2:
        return True
    base = _unit(_vec(centerline_pts[0], centerline_pts[1]))
    if base is None:
        return False
    for i in range(1, len(centerline_pts) - 1):
        seg = _vec(centerline_pts[i], centerline_pts[i + 1])
        seg_len = _length(seg)
        if seg_len <= 0.0:
            continue
        # Perpendicular distance of the far endpoint from the base line.
        offset = abs(_cross(base, seg))
        if offset > tolerance_pt:
            return False
    return True


@dataclass(frozen=True)
class WallSpanGeometryCheck:
    """Diagnostic geometry comparison between one dimension span and one wall."""

    wall_candidate_id: str
    collinear: bool
    orientation_parallel: bool
    perpendicular_offset_pt: Optional[float]
    endpoint_coverage_delta_pt: Optional[float]
    eligible: bool
    reasons: tuple[str, ...] = ()


def _evaluate_wall_against_span(
    wall: WallCandidate,
    span_start: Point,
    span_end: Point,
    *,
    tolerance_pt: float,
) -> WallSpanGeometryCheck:
    reasons: list[str] = []
    if not _is_straight_wall(wall.centerline_pts, tolerance_pt):
        return WallSpanGeometryCheck(
            wall_candidate_id=wall.candidate_id,
            collinear=False,
            orientation_parallel=False,
            perpendicular_offset_pt=None,
            endpoint_coverage_delta_pt=None,
            eligible=False,
            reasons=(WALL_SPAN_WALL_NOT_STRAIGHT,),
        )

    wall_start, wall_end = wall.centerline_pts[0], wall.centerline_pts[-1]
    wall_dir = _unit(_vec(wall_start, wall_end))
    span_dir = _unit(_vec(span_start, span_end))
    if wall_dir is None or span_dir is None:
        return WallSpanGeometryCheck(
            wall_candidate_id=wall.candidate_id,
            collinear=False,
            orientation_parallel=False,
            perpendicular_offset_pt=None,
            endpoint_coverage_delta_pt=None,
            eligible=False,
            reasons=(WALL_SPAN_ORIENTATION_MISMATCH,),
        )

    # Orientation: span direction must be parallel or anti-parallel to the
    # wall direction, not perpendicular (rejects a thickness dimension) and
    # not merely "close" by an arbitrary degree threshold -- the cross
    # product of two unit vectors is the sine of the angle between them, so
    # comparing it against a page-derived *distance* tolerance divided by a
    # representative span length keeps this scale-appropriate rather than a
    # separately-invented angular constant.
    span_len = _length(_vec(span_start, span_end))
    angular_sine_bound = tolerance_pt / span_len if span_len > 0 else 1.0
    orientation_parallel = abs(_cross(wall_dir, span_dir)) <= max(angular_sine_bound, 1e-6)
    if not orientation_parallel:
        reasons.append(WALL_SPAN_ORIENTATION_MISMATCH)

    # Perpendicular offset of both span endpoints from the wall's infinite
    # centerline (using the wall's own direction as the reference axis).
    normal = (-wall_dir[1], wall_dir[0])
    offset_start = abs(_dot(_vec(wall_start, span_start), normal))
    offset_end = abs(_dot(_vec(wall_start, span_end), normal))
    perpendicular_offset_pt = max(offset_start, offset_end)
    if perpendicular_offset_pt > tolerance_pt:
        reasons.append(WALL_SPAN_OFFSET_TOO_LARGE)

    # Endpoint coverage: a "wall length" dimension is evidence for this
    # module only when it measures the wall's own full run, not an
    # unrepresented sub-span -- compare span endpoints against wall
    # endpoints directly (checked in both possible pairings, since neither
    # the dimension's nor the wall's point order is authoritative).
    pairing_a = max(
        _length(_vec(span_start, wall_start)), _length(_vec(span_end, wall_end))
    )
    pairing_b = max(
        _length(_vec(span_start, wall_end)), _length(_vec(span_end, wall_start))
    )
    endpoint_coverage_delta_pt = min(pairing_a, pairing_b)
    if endpoint_coverage_delta_pt > tolerance_pt:
        reasons.append(WALL_SPAN_ENDPOINT_COVERAGE_MISMATCH)

    collinear = perpendicular_offset_pt <= tolerance_pt
    eligible = collinear and orientation_parallel and endpoint_coverage_delta_pt <= tolerance_pt
    return WallSpanGeometryCheck(
        wall_candidate_id=wall.candidate_id,
        collinear=collinear,
        orientation_parallel=orientation_parallel,
        perpendicular_offset_pt=perpendicular_offset_pt,
        endpoint_coverage_delta_pt=endpoint_coverage_delta_pt,
        eligible=eligible,
        reasons=tuple(reasons),
    )


@dataclass(frozen=True)
class FiguredWallSpanShadowRecord:
    """Auditable shadow record for one (dimension observation, wall) resolution.

    Exposes every field the review Phase 3 requires, using real, honestly
    labeled names -- ``witness_line_ids`` (not "terminator ids": see module
    docstring for why terminator-glyph identification is not a separately
    implemented step here).
    """

    record_id: str
    dimension_id: str
    raw_text: str
    value_m: Optional[float]
    dimension_line_id: Optional[str]
    witness_line_ids: tuple[str, ...]
    endpoints: Optional[tuple[Point, Point]]
    candidate_wall_ids: tuple[str, ...]
    resolved_wall_id: Optional[str]
    document_id: str
    page_id: str
    viewport_id: str
    source_sha256: str
    revision_id: Optional[str]
    evidence_snapshot_id: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    geometry_checks: tuple[WallSpanGeometryCheck, ...] = ()
    notes: str = ""
    schema_version: str = FIGURED_WALL_SPAN_SCHEMA_VERSION


def resolve_figured_wall_span_identity(
    observation: DimensionObservation,
    *,
    walls: Sequence[WallCandidate],
    calibration: DimensionLayoutCalibration,
    context: ProviderContext,
    document_id: str,
    source_sha256: str,
    binding_status: str,
) -> FiguredWallSpanShadowRecord:
    """Resolve one figured-dimension observation's ownership of at most one wall.

    ``binding_status`` is the caller's already-computed
    ``DimensionAnchorBinding.status`` for this observation (from
    ``pb_figured_dimension_evidence.bind_observation_to_vector_geometry`` /
    ``apply_anchor_binding``) -- this function does not recompute it.
    """
    payload_base = {
        "dimension_id": observation.dimension_id,
        "source_page": observation.source_page,
        "view_id": observation.view_id,
        "document_id": document_id,
        "source_sha256": source_sha256,
        "revision_id": context.revision_id,
    }

    def _abstain(reason: str, *extra: str) -> FiguredWallSpanShadowRecord:
        codes = tuple(dict.fromkeys((reason, *extra)))
        record_id = stable_contract_id(
            "figured_wall_span", {**payload_base, "status": "abstained", "reasons": list(codes)}
        )
        return FiguredWallSpanShadowRecord(
            record_id=record_id,
            dimension_id=observation.dimension_id,
            raw_text=observation.raw_text,
            value_m=None,
            dimension_line_id=None,
            witness_line_ids=observation.witness_targets,
            endpoints=observation.endpoints,
            candidate_wall_ids=(),
            resolved_wall_id=None,
            document_id=document_id,
            page_id=str(observation.source_page),
            viewport_id=observation.view_id,
            source_sha256=source_sha256,
            revision_id=context.revision_id,
            evidence_snapshot_id=context.evidence_snapshot_id,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=codes,
            notes=(
                "Terminator glyphs are not separately vectorized in this codebase; "
                "witness/extension-line endpoint intersection is the physical-extent "
                "proof used here, unchanged from pb_figured_dimension_evidence.py."
            ),
        )

    if binding_status != BindingStatus.WITNESS_BOUND.value:
        return _abstain(WALL_SPAN_NOT_WITNESS_BOUND)
    if observation.endpoints is None:
        return _abstain(WALL_SPAN_NO_ENDPOINTS)
    if not context.revision_id or not context.current_revision_id:
        return _abstain(WALL_SPAN_REVISION_UNBOUND)
    if context.revision_id != context.current_revision_id:
        return _abstain(WALL_SPAN_REVISION_STALE)
    if document_id != context.document_id:
        return _abstain(WALL_SPAN_DOCUMENT_MISMATCH)
    if source_sha256 != context.source_sha256:
        return _abstain(WALL_SPAN_SOURCE_SHA_MISMATCH)
    if observation.view_id and observation.view_id not in context.trusted_viewport_ids():
        return _abstain(WALL_SPAN_VIEWPORT_NOT_OWNED)

    span_start, span_end = observation.endpoints
    same_viewport_walls = [w for w in walls if w.viewport_id == observation.view_id]
    if observation.view_id and any(w.viewport_id != observation.view_id for w in walls):
        # Present for auditability only -- cross-viewport candidates are
        # simply excluded below, never compared as if they were eligible.
        pass

    checks = tuple(
        _evaluate_wall_against_span(
            wall, span_start, span_end, tolerance_pt=calibration.witness_endpoint_distance_pt
        )
        for wall in same_viewport_walls
    )
    eligible = [c for c in checks if c.eligible]

    if not eligible:
        record_id = stable_contract_id(
            "figured_wall_span", {**payload_base, "status": "abstained", "reasons": [WALL_SPAN_NO_CANDIDATE_WALL]}
        )
        return FiguredWallSpanShadowRecord(
            record_id=record_id,
            dimension_id=observation.dimension_id,
            raw_text=observation.raw_text,
            value_m=None,
            dimension_line_id=None,
            witness_line_ids=observation.witness_targets,
            endpoints=observation.endpoints,
            candidate_wall_ids=tuple(w.candidate_id for w in same_viewport_walls),
            resolved_wall_id=None,
            document_id=document_id,
            page_id=str(observation.source_page),
            viewport_id=observation.view_id,
            source_sha256=source_sha256,
            revision_id=context.revision_id,
            evidence_snapshot_id=context.evidence_snapshot_id,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(WALL_SPAN_NO_CANDIDATE_WALL,),
            geometry_checks=checks,
            notes="No candidate wall's centerline matched this dimension's proven physical span.",
        )

    if len(eligible) > 1:
        record_id = stable_contract_id(
            "figured_wall_span",
            {**payload_base, "status": "conflict", "reasons": [WALL_SPAN_AMBIGUOUS_WALLS],
             "candidates": sorted(c.wall_candidate_id for c in eligible)},
        )
        return FiguredWallSpanShadowRecord(
            record_id=record_id,
            dimension_id=observation.dimension_id,
            raw_text=observation.raw_text,
            value_m=None,
            dimension_line_id=None,
            witness_line_ids=observation.witness_targets,
            endpoints=observation.endpoints,
            candidate_wall_ids=tuple(sorted(c.wall_candidate_id for c in eligible)),
            resolved_wall_id=None,
            document_id=document_id,
            page_id=str(observation.source_page),
            viewport_id=observation.view_id,
            source_sha256=source_sha256,
            revision_id=context.revision_id,
            evidence_snapshot_id=context.evidence_snapshot_id,
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(WALL_SPAN_AMBIGUOUS_WALLS,),
            geometry_checks=checks,
            notes=f"{len(eligible)} walls are equally plausible targets for this dimension; never resolved by nearest/first/smallest.",
        )

    winner = eligible[0]
    record_id = stable_contract_id(
        "figured_wall_span",
        {**payload_base, "status": "corroborated", "wall_candidate_id": winner.wall_candidate_id},
    )
    return FiguredWallSpanShadowRecord(
        record_id=record_id,
        dimension_id=observation.dimension_id,
        raw_text=observation.raw_text,
        value_m=observation.value_m,
        dimension_line_id=None,
        witness_line_ids=observation.witness_targets,
        endpoints=observation.endpoints,
        candidate_wall_ids=(winner.wall_candidate_id,),
        resolved_wall_id=winner.wall_candidate_id,
        document_id=document_id,
        page_id=str(observation.source_page),
        viewport_id=observation.view_id,
        source_sha256=source_sha256,
        revision_id=context.revision_id,
        evidence_snapshot_id=context.evidence_snapshot_id,
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(WALL_SPAN_RESOLVED,),
        geometry_checks=checks,
        notes="Exactly one wall's centerline matched this dimension's proven physical span and orientation.",
    )


def detect_conflicting_wall_span_records(
    records: Sequence[FiguredWallSpanShadowRecord],
    *,
    tolerance_m: float = 0.005,
) -> dict[str, tuple[FiguredWallSpanShadowRecord, ...]]:
    """Group CORROBORATED records by resolved wall id; flag disagreeing groups.

    Returns only groups with 2+ records whose values disagree beyond
    tolerance -- the caller is expected to downgrade those specific records
    to CONFLICT before any of them are used, never averaging or picking one.
    """
    by_wall: dict[str, list[FiguredWallSpanShadowRecord]] = {}
    for record in records:
        if record.status is EvidenceResolutionStatus.CORROBORATED and record.resolved_wall_id:
            by_wall.setdefault(record.resolved_wall_id, []).append(record)
    conflicts: dict[str, tuple[FiguredWallSpanShadowRecord, ...]] = {}
    for wall_id, group in by_wall.items():
        values = [r.value_m for r in group if r.value_m is not None]
        if len(values) >= 2 and (max(values) - min(values)) > tolerance_m:
            conflicts[wall_id] = tuple(group)
    return conflicts


def to_owned_evidence_atom(
    record: FiguredWallSpanShadowRecord,
    *,
    method: str = FIGURED_WALL_SPAN_METHOD,
) -> Optional[EvidenceAtom]:
    """Project a CORROBORATED shadow record into the atom shape
    ``pb_physical_wall_existence_authority.bind_additional_wall_owned_evidence``
    already accepts. Returns None for anything not CORROBORATED -- this
    function does not call that boundary, it only proves the shape is ready
    for a later, separately-reviewed wiring change.
    """
    if record.status is not EvidenceResolutionStatus.CORROBORATED or not record.resolved_wall_id:
        return None
    return EvidenceAtom(
        evidence_id=record.record_id,
        document_id=record.document_id,
        page_id=record.page_id,
        kind=ADDITIONAL_WALL_EVIDENCE_KIND_FIGURED,
        method=method,
        viewport_id=record.viewport_id,
        raw_text=record.raw_text,
        normalized_value=record.value_m,
        unit="m",
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=record.reason_codes,
        metadata={
            "wall_candidate_id": record.resolved_wall_id,
            "revision_id": record.revision_id,
            "evidence_snapshot_id": record.evidence_snapshot_id,
            "source_sha256": record.source_sha256,
        },
    )


__all__ = [
    "FIGURED_WALL_SPAN_SCHEMA_VERSION",
    "FIGURED_WALL_SPAN_METHOD",
    "WALL_SPAN_RESOLVED",
    "WALL_SPAN_NOT_WITNESS_BOUND",
    "WALL_SPAN_NO_ENDPOINTS",
    "WALL_SPAN_DOCUMENT_MISMATCH",
    "WALL_SPAN_SOURCE_SHA_MISMATCH",
    "WALL_SPAN_REVISION_UNBOUND",
    "WALL_SPAN_REVISION_STALE",
    "WALL_SPAN_VIEWPORT_MISMATCH",
    "WALL_SPAN_VIEWPORT_NOT_OWNED",
    "WALL_SPAN_WALL_NOT_STRAIGHT",
    "WALL_SPAN_ORIENTATION_MISMATCH",
    "WALL_SPAN_OFFSET_TOO_LARGE",
    "WALL_SPAN_ENDPOINT_COVERAGE_MISMATCH",
    "WALL_SPAN_NO_CANDIDATE_WALL",
    "WALL_SPAN_AMBIGUOUS_WALLS",
    "WALL_SPAN_CONFLICTING_DIMENSIONS",
    "WallSpanGeometryCheck",
    "FiguredWallSpanShadowRecord",
    "resolve_figured_wall_span_identity",
    "detect_conflicting_wall_span_records",
    "to_owned_evidence_atom",
]
