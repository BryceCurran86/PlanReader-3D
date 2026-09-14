"""Canonical quantity shadow provider (Canonical Shadow Integration).

Gold-free, non-commercial, observability-only. This module NEVER touches
`pred_dict`, never imports anything from the benchmark gold/scoring path, and
never mutates any object the live `GenericPlanReaderExtractor` path owns.

WHY THIS FILE EXISTS
Phase 1's trace confirmed that every newer fail-closed authority module for
wall length/height/gross-area/net-area/opening-deduction has ZERO live
callers -- `GenericPlanReaderExtractor` still produces every commercial
quantity through legacy ad hoc geometry/regex paths, with exactly one live
hard-coded height default (`GenericPlanReaderExtractor.default_ceiling_height_m
= 2.80`, `pb_planreader_pdf_extractor.py:68`). This provider runs the
*disconnected* canonical authority chain end-to-end, per physical wall, on a
real drawing, and reports what it can and cannot prove -- without inventing
any new detection algorithm and without changing what the live path returns.

DEPENDENCY CHAIN (each stage keeps its own status; never collapsed to a
single boolean -- see `dependency_states` on every record, and
DEPENDENCY_STAGE_KEYS / the controlled `_DependencyStatus` vocabulary):

    canonical wall candidates -> physical identity -> existence -> equivalence
    -> FIRM wall length -> FIRM wall height -> gross wall area
    -> physical opening universe -> opening identity -> host resolution
    -> opening dimensions -> deduction readiness -> net wall area
    -> wall role -> finish applicability

KNOWN, TRACKED DEBT -- NOT FIXED HERE, NOT THIS MODULE'S TO FIX
`pb_wall_height_authority`'s own ownership check (`_validate_owned_evidence`)
verifies document/entity membership, page/viewport identity, and
CORROBORATED status -- but it does NOT itself verify that an evidence atom's
revision/snapshot/source-SHA match the current context. This shadow module
adds its OWN independent freshness gate (`_height_evidence_is_fresh`) as a
protective boundary in front of that weaker upstream check. That gate does
NOT mean the underlying authority module is fixed -- it still lacks
revision/snapshot/source-SHA verification and needs separate remediation
upstream (tracked as a known blocker, not addressed in this file; do not
report "height freshness fixed globally" on the strength of this shadow-side
gate alone).

CONSTRAINT: FRESHNESS MUST NOT BE MANUFACTURED
Provenance (revision_id/evidence_snapshot_id/source_sha256) is stamped onto
a level-marker evidence atom EXACTLY ONCE, in `_stamp_level_marker_atoms`,
called only from `_build_canonical_wall_universe` immediately after
`find_level_markers` runs -- i.e. using the context that was genuinely
active at the actual moment of extraction from the actual PDF. Every later
consumer (`_attempt_wall_height`, called once per wall, well after
extraction) only ever READS an already-stamped atom and verifies it against
whatever context is active at ITS OWN call time; it never re-stamps, and it
never accepts a bare `LevelMarker` and manufactures fresh-looking metadata
for it on the spot. This is deliberate: retroactively stamping "current"
context onto an atom of unknown origin would prove nothing (an old,
unbound atom would pass just as easily as a genuinely fresh one) --
freshness only means anything if the stamp was fixed at a DIFFERENT, EARLIER
moment than the check, so a mismatch is actually possible to observe. See
`test_evidence_cannot_become_fresh_merely_by_being_restamped_with_current_context`.

CONSTRAINT: AN INCOMPLETE HOST-WALL UNIVERSE NEVER AUTHORIZES A HOST-DEPENDENT
QUANTITY, EVEN WHEN THE GEOMETRIC BINDER SAYS "bound"
`bind_hosted_opening_to_walls` is always called against the FULL region-
clipped wall list (never a single-wall shortcut), but that list itself is
never proven to be the complete relevant universe (this diagnostic clips to
a small window, not the whole drawing). So even a "bound" result never
becomes host AUTHORITY here: `hosted_opening_binding.canonical_status` is
unconditionally "BLOCKED", carrying `regional_clip_wall_universe_not_proven_
complete` in blocking_reasons -- the raw binder finding ("bound"/"ambiguous"/
"unbound") is preserved separately in `candidate_result` rather than
discarded, precisely so a future, independently-proven completeness contract
can promote it later without recomputing any geometry. opening_deduction_
readiness and net_wall_area both inherit this same unconditional BLOCKED
host state; a "bound" candidate can never make either of them FIRM here.

CONSTRAINT: OPENING COMPLETENESS IS NEVER CLAIMED, EVER
This module never constructs, accepts, or trusts an `opening_set_complete`-
kind evidence atom, and never calls `build_opening_deduction_quantity` /
`build_net_wall_area_quantity` at all -- there is no code path here through
which a caller-supplied completeness claim (real or fabricated) could reach
either function. net_wall_area is unconditionally BLOCKED.

WHAT IS REUSED, UNCHANGED, FROM THE EXISTING #288 SHADOW SCRIPT
The existence/equivalence/entity construction pipeline mirrors
`scripts/wall_linear_authority_real_drawing_shadow.py` exactly (same
functions, same call order). That script returns only a summary dict; this
module needs the underlying objects so later authority calls (height, gross
area) can be layered on the same wall universe -- so the pipeline is
reconstructed here rather than imported, but it is not modified.

NOT WIRED IN THIS PASS (reported honestly via dependency_states, not
attempted):
- Opening tag/schedule identity (`pb_opening_provenance_graph`) -- exists,
  runs live, is discarded live (Phase 1 finding), but is not yet wired into
  THIS shadow provider either.
- Wall role (`pb_wall_boundary_role_authority`) -- lives only on the
  separate, not-yet-merged `claude/wall-role-authority-integration-v1`
  branch; this provider is built on bare `origin/main` and cannot import a
  module that does not exist there.
- Internal wall length promotion beyond NOT_EVIDENCED, and any external
  render/cladding producer.

SCOPE MISMATCH, STATED EXPLICITLY
Canonical authority publishes per physical wall. The live legacy path
publishes one whole-drawing/whole-page aggregate (`perimeter_walling` etc.).
`comparison` is populated only on whole-drawing AGGREGATE_SUBJECT_ID rows
(sum of FIRM per-wall values vs. the legacy figure, gated on family, unit
compatibility, and tolerance -- see `_comparison_status`); individual wall
rows leave it None rather than forcing a misleading verdict onto them.

This module is intentionally free of consumer/benchmark dependencies beyond
what it observes. It does not import or modify pb_wall_boundary_role_authority.py,
pb_physical_wall_existence_authority.py (beyond calling its public function),
pb_wall_height_authority.py (beyond calling its public function -- its
freshness gap is this module's problem to defend against, not to patch),
pb_completeness_manifest.py, pb_cross_view_registration.py, or the legacy
pb_vector_geometry_v130.solve_scale. No new dependency.
"""
from __future__ import annotations

import dataclasses
import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Optional, Sequence

import fitz

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pb_canonical_wall_room_evidence_model import resolve_wall_physical_evidence
from pb_dimension_graph_constraint_engine import HeightResolution, LevelMarker, resolve_wall_height
from pb_hosted_opening_geometry import resolve_hosted_opening_spans
from pb_hosted_opening_wall_binding import bind_hosted_opening_to_walls
from pb_level_datum_extraction import find_level_markers
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_physical_wall_existence_authority import adapt_wall_candidate_to_entity_evidence
from pb_physical_wall_identity import collect_physical_wall_identities, resolve_physical_wall_equivalence
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_vector_geometry_v130 import detect_wall_pairs, extract_native_page
from pb_wall_gross_area_quantity import build_gross_wall_area_quantity
from pb_wall_height_authority import WALL_HEIGHT_FAMILY, build_wall_height_quantity
from pb_wall_length_quantity import build_wall_length_quantity
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_opening_host_binding import detect_opening_host_candidates
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_typed_negative_evidence import GRAPH_ATOMS_KEY, attach_typed_semantic_evidence
from pb_wall_room_topology_wall_assembly import assemble_wall_candidates

SHADOW_PROVIDER_SCHEMA_VERSION = "3.0.0"

ComparisonStatus = Literal["SAME", "DIFFERENT", "LEGACY_ONLY", "SHADOW_ONLY", "BOTH_BLOCKED"]
DependencyStatus = Literal["FIRM", "BLOCKED", "CONFLICT", "AMBIGUOUS", "NOT_EVALUATED", "NOT_REQUIRED"]

AGGREGATE_SUBJECT_ID = "__whole_drawing_aggregate__"

_ALLOWED_DEPENDENCY_STATUSES: frozenset[str] = frozenset(
    {"FIRM", "BLOCKED", "CONFLICT", "AMBIGUOUS", "NOT_EVALUATED", "NOT_REQUIRED"}
)

# family -> (legacy prediction tag treated as its approximate reference, expected legacy unit)
# None means legacy has no comparable decomposition at all (it only ever
# publishes a combined figure) -- reported as SHADOW_ONLY, not guessed at
# via some other tag.
_FAMILY_TO_LEGACY_TAG: dict[str, Optional[str]] = {
    "wall_length": None,
    "wall_height": None,
    "gross_wall_area": "perimeter_walling",
    "net_wall_area": "perimeter_walling",
}
_CANONICAL_UNIT_FOR_FAMILY = {"wall_length": "m", "wall_height": "m", "gross_wall_area": "m2", "net_wall_area": "m2"}
# Units this codebase's legacy extractor actually emits (pb_planreader_pdf_extractor.py
# ExtractedPrediction.unit: "NO"/"SM"/"M"/"M3") that are dimensionally
# compatible with a given canonical unit -- comparison requires this match
# before SAME/DIFFERENT is even considered (point 8: compatible units).
_UNIT_COMPATIBLE_WITH_CANONICAL = {"m": {"M"}, "m2": {"SM"}, "m3": {"M3"}}
# perimeter_walling is mutated in place to the NET value by
# GenericOpeningDeductionPipeline.propagate_to_predictions whenever any
# opening prediction exists on the page (pb_opening_deduction_pipeline.py
# :262-334) -- when it does, gross_wall_area's legacy comparison below is
# against an already-net figure, not a clean gross one. Surfaced as a note
# on every ShadowDrawingReport rather than silently assumed away.
_COMPARISON_RELATIVE_TOLERANCE = 0.01  # reporting-only heuristic for SAME/DIFFERENT; not an authority tolerance_policy

# marker_type -> (allowed EvidenceAtom kind, "upper" or "lower" datum role).
# "ceiling" is deliberately absent: pb_dimension_graph_constraint_engine.
# _ROOF_LIKE = {"roof", "ceiling", "beam"} treats a ceiling marker
# identically to a roof marker for its own clear-height computation, but a
# room's ceiling (possibly dropped/suspended) is not independently proven
# to coincide with the bounding wall's own height -- room/ceiling height
# must never automatically become wall height (see _WALL_HEIGHT_MARKER_TYPES
# and _attempt_wall_height, which excludes "ceiling" from the levels it
# ever hands to resolve_wall_height, not merely from this mapping, so a
# ceiling marker can never masquerade as resolve_wall_height's own
# "roof_level_m" either).
_MARKER_TYPE_TO_DATUM_KIND: dict[str, tuple[str, str]] = {
    "roof": ("elevation_datum", "upper"),
    "beam": ("elevation_datum", "upper"),
    "floor": ("floor_level_datum", "lower"),
    "ground": ("floor_level_datum", "lower"),
}
# marker_type values resolve_wall_height is ever allowed to see when
# resolving WALL height specifically -- excludes "ceiling" for the same
# reason. A caller-facing constant rather than an inline filter so the
# exclusion is visible without reading _attempt_wall_height's body.
_WALL_HEIGHT_ELIGIBLE_MARKER_TYPES: frozenset[str] = frozenset({"roof", "beam", "floor", "ground"})

# Fixed dependency-chain stages every ShadowQuantityRecord reports against,
# so a reviewer can see exactly which upstream stage blocked any given
# claim -- not just that "something" was abstained.
DEPENDENCY_STAGE_KEYS: tuple[str, ...] = (
    "existence",
    "identity",
    "scale",
    "length",
    "height",
    "host",
    "opening_dimension",
    "gross_area",
    "net_area",
    "role",
    "finish",
)

_EVIDENCE_RESOLUTION_TO_DEPENDENCY: dict[str, str] = {
    "raw": "NOT_EVALUATED",
    "candidate": "NOT_EVALUATED",
    "corroborated": "FIRM",
    "conflict": "CONFLICT",
    "abstained": "BLOCKED",
}
_IDENTITY_TO_DEPENDENCY: dict[str, str] = {
    "same_or_representative": "FIRM",
    "distinct": "FIRM",
    "ambiguous": "AMBIGUOUS",
    "abstained": "BLOCKED",
}
_QUANTITY_STATUS_TO_DEPENDENCY: dict[str, str] = {
    "firm": "FIRM",
    "conflict": "CONFLICT",
    "blocked": "BLOCKED",
    "abstained": "BLOCKED",
    "provisional": "NOT_EVALUATED",
    "review_required": "NOT_EVALUATED",
}


def _evidence_status_to_dependency(value: Optional[str]) -> str:
    return _EVIDENCE_RESOLUTION_TO_DEPENDENCY.get(str(value), "BLOCKED")


def _identity_status_to_dependency(value: Optional[str]) -> str:
    return _IDENTITY_TO_DEPENDENCY.get(str(value), "BLOCKED")


def _quantity_status_to_dependency(qty) -> str:
    if qty.abstained:
        return "BLOCKED"
    return _QUANTITY_STATUS_TO_DEPENDENCY.get(str(qty.status).lower(), "BLOCKED")


def _dependency_states(**overrides: str) -> dict[str, str]:
    """Every record gets the full fixed key set; stages not relevant to
    that particular record's family default to NOT_REQUIRED (never
    omitted, so the shape is always uniform). Every supplied value must be
    one of the controlled DependencyStatus values -- arbitrary free-text
    status strings are rejected at construction, not merely discouraged."""
    states = {key: "NOT_REQUIRED" for key in DEPENDENCY_STAGE_KEYS}
    for key, value in overrides.items():
        if key not in states:
            raise ValueError(f"unknown dependency stage {key!r}")
        if value not in _ALLOWED_DEPENDENCY_STATUSES:
            raise ValueError(
                f"dependency stage {key!r} got non-controlled status {value!r}; "
                f"must be one of {sorted(_ALLOWED_DEPENDENCY_STATUSES)}"
            )
        states[key] = value
    return states


@dataclass(frozen=True)
class ShadowQuantityRecord:
    """One observability row. Never overwrites or feeds commercial output;
    this is the whole point of the object -- read-only reporting.

    candidate_result preserves a raw, ungated geometric/binder finding
    (e.g. "bound", "ambiguous") separately from canonical_status (the
    GATED authority verdict) -- useful, non-authoritative geometry is never
    thrown away just because it isn't promotion-ready yet.

    legacy_value/legacy_unit/comparison are populated only for whole-drawing
    AGGREGATE rows (subject_id == AGGREGATE_SUBJECT_ID) -- comparing one
    individual wall's canonical value against a whole-page legacy figure is
    not a sound comparison, so per-wall rows leave all three None.
    """

    quantity_family: str
    subject_id: str
    canonical_value: Optional[float]
    canonical_unit: Optional[str]
    canonical_status: str
    evidence_ids: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    dependency_states: Mapping[str, str] = field(default_factory=_dependency_states)
    candidate_result: Optional[str] = None
    legacy_value: Optional[float] = None
    legacy_unit: Optional[str] = None
    comparison: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "quantity_family": self.quantity_family,
            "subject_id": self.subject_id,
            "canonical_value": self.canonical_value,
            "canonical_unit": self.canonical_unit,
            "canonical_status": self.canonical_status,
            "evidence_ids": list(self.evidence_ids),
            "blocking_reasons": list(self.blocking_reasons),
            "dependency_states": dict(self.dependency_states),
            "candidate_result": self.candidate_result,
            "legacy_value": self.legacy_value,
            "legacy_unit": self.legacy_unit,
            "comparison": self.comparison,
        }


def _comparison_status(
    shadow_value: Optional[float],
    legacy_value: Optional[float],
    *,
    canonical_unit: Optional[str] = None,
    legacy_unit: Optional[str] = None,
) -> ComparisonStatus:
    """SAME requires more than numeric closeness (point 8): compatible
    units too. Family/subject-scope agreement is the caller's
    responsibility (this is only ever invoked per-family, per-aggregate-row
    -- see call site), so it is not re-checked here, but unit compatibility
    is checked here because it is cheap, always available, and exactly the
    kind of accidental-numeric-coincidence risk an incompatible-unit
    mismatch would otherwise hide."""
    if shadow_value is None and legacy_value is None:
        return "BOTH_BLOCKED"
    if shadow_value is None:
        return "LEGACY_ONLY"
    if legacy_value is None:
        return "SHADOW_ONLY"
    if canonical_unit is not None and legacy_unit is not None:
        compatible = _UNIT_COMPATIBLE_WITH_CANONICAL.get(canonical_unit, set())
        if legacy_unit not in compatible:
            return "DIFFERENT"
    tolerance = max(1e-6, _COMPARISON_RELATIVE_TOLERANCE * abs(legacy_value))
    return "SAME" if abs(shadow_value - legacy_value) <= tolerance else "DIFFERENT"


@dataclass(frozen=True)
class ShadowDrawingReport:
    label: str
    canonical_walls_considered: int
    canonical_records: tuple[ShadowQuantityRecord, ...]
    opening_host_candidates_observed: int
    opening_host_statuses_observed: tuple[str, ...]
    legacy_aggregate: dict[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "canonical_walls_considered": self.canonical_walls_considered,
            "canonical_records": [r.to_dict() for r in self.canonical_records],
            "opening_host_candidates_observed": self.opening_host_candidates_observed,
            "opening_host_statuses_observed": list(self.opening_host_statuses_observed),
            "legacy_aggregate": self.legacy_aggregate,
            "notes": list(self.notes),
        }


def _record(qty, *, family: str, subject_id: str, dependency_states: Mapping[str, str]) -> ShadowQuantityRecord:
    value = None if qty.abstained else qty.value
    unit = qty.unit if not qty.abstained else None
    return ShadowQuantityRecord(
        quantity_family=family,
        subject_id=subject_id,
        canonical_value=value,
        canonical_unit=unit,
        canonical_status=qty.status,
        evidence_ids=tuple(qty.evidence_ids),
        blocking_reasons=tuple(qty.blocking_reasons),
        dependency_states=dependency_states,
    )


def _stamp_level_marker_atoms(
    levels: Sequence[LevelMarker], *, document_id: str, page_id: str, extraction_context: ProviderContext
) -> dict[str, EvidenceAtom]:
    """Stamps provenance EXACTLY ONCE, at the moment of extraction -- see
    the module docstring's "CONSTRAINT: FRESHNESS MUST NOT BE MANUFACTURED"
    section for why this must never be called again later, per-wall, from
    _attempt_wall_height."""
    atoms: dict[str, EvidenceAtom] = {}
    for marker in levels:
        mapping = _MARKER_TYPE_TO_DATUM_KIND.get(marker.marker_type)
        if mapping is None:
            continue
        kind, _role = mapping
        atoms[marker.marker_id] = EvidenceAtom(
            evidence_id=f"leveldatum-{marker.marker_id}",
            document_id=document_id,
            page_id=page_id,
            kind=kind,
            method="text_level_marker",
            viewport_id=marker.view_id or None,
            raw_text=marker.raw_text,
            normalized_value=marker.level_m,
            unit="m",
            confidence=1.0,
            status=EvidenceResolutionStatus.CORROBORATED,
            metadata={
                "marker_type": marker.marker_type,
                "source_page": marker.source_page,
                "revision_id": extraction_context.current_revision_id,
                "evidence_snapshot_id": extraction_context.evidence_snapshot_id,
                "source_sha256": extraction_context.source_sha256,
            },
        )
    return atoms


def _height_evidence_is_fresh(atom: EvidenceAtom, *, context: ProviderContext) -> bool:
    """Constraint: verify the ALREADY-STAMPED evidence belongs to the
    CURRENT revision/snapshot/source-SHA, independent of
    build_wall_height_quantity's own (weaker) ownership check, which never
    inspects these three fields at all."""
    meta = atom.metadata or {}
    return (
        meta.get("revision_id") == context.current_revision_id
        and meta.get("evidence_snapshot_id") == context.evidence_snapshot_id
        and meta.get("source_sha256") == context.source_sha256
    )


def _freshness_blocked_height(*, wall_id: str, evidence_ids: tuple[str, ...]) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=f"blocked-height-freshness-{wall_id}",
        family=WALL_HEIGHT_FAMILY,
        semantic_key=f"wall_height:{wall_id}",
        value=None,
        unit="m",
        authority="none",
        status="blocked",
        abstained=True,
        blocking_reasons=("height_evidence_freshness_unproven",),
        evidence_ids=evidence_ids,
    )


def _attempt_wall_height(
    *,
    wall_id: str,
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    entity,
    levels: Sequence[LevelMarker],
    level_atoms: Mapping[str, EvidenceAtom],
) -> QuantityEvidence:
    """`level_atoms` must already be stamped (see `_stamp_level_marker_atoms`,
    called once in `_build_canonical_wall_universe`) -- this function never
    constructs a new atom from a raw LevelMarker itself; it only looks one
    up by marker_id and verifies it, so an atom's freshness can only ever
    reflect the context that was active when it was ORIGINALLY stamped, not
    whatever context happens to be passed to this call.

    Ceiling markers are excluded from what resolve_wall_height is even
    allowed to see (not merely from the atom-construction mapping) -- a
    ceiling+floor pair must resolve exactly like a missing roof marker,
    never like a proven wall-height pair. Room/ceiling height is not
    independently proven to equal this wall's own height; a dropped or
    suspended ceiling would make that false.
    """
    wall_height_eligible_levels = tuple(m for m in levels if m.marker_type in _WALL_HEIGHT_ELIGIBLE_MARKER_TYPES)
    resolution: HeightResolution = resolve_wall_height(wall_height_eligible_levels, scope_id=None)
    lower_evidence: Optional[EvidenceAtom] = None
    upper_evidence: Optional[EvidenceAtom] = None
    if resolution.status == "fully_constrained" and resolution.clear_height_m is not None:
        roof_value = resolution.sources.get("roof_level_m")
        floor_value = resolution.sources.get("floor_level_m")
        for marker in wall_height_eligible_levels:
            if marker.scope_id is not None:
                continue
            mapping = _MARKER_TYPE_TO_DATUM_KIND.get(marker.marker_type)
            if mapping is None:
                continue
            _kind, role = mapping
            if role == "upper" and upper_evidence is None and marker.level_m == roof_value:
                upper_evidence = level_atoms.get(marker.marker_id)
            elif role == "lower" and lower_evidence is None and marker.level_m == floor_value:
                lower_evidence = level_atoms.get(marker.marker_id)

    candidate_evidence = tuple(e for e in (lower_evidence, upper_evidence) if e is not None)
    if candidate_evidence and not all(_height_evidence_is_fresh(e, context=context) for e in candidate_evidence):
        return _freshness_blocked_height(
            wall_id=wall_id, evidence_ids=tuple(e.evidence_id for e in candidate_evidence)
        )

    # build_wall_height_quantity's ownership check requires each datum
    # evidence_id to be a member of BOTH document.evidence_ids AND
    # entity.evidence_ids. Extending both (never replacing/shrinking) is
    # the correct move: this is still the same document and the same
    # corroborated physical wall, now with an additional, independent kind
    # of evidence attached, exactly as a real accumulating evidence bundle
    # should behave.
    new_ids = {e.evidence_id for e in candidate_evidence}
    if new_ids:
        entity = dataclasses.replace(
            entity, evidence_ids=tuple(dict.fromkeys((*entity.evidence_ids, *sorted(new_ids))))
        )
        document = dataclasses.replace(
            document, evidence_ids=tuple(dict.fromkeys((*document.evidence_ids, *sorted(new_ids))))
        )

    return build_wall_height_quantity(
        wall_id=wall_id,
        context=context,
        document=document,
        viewport=viewport,
        entity=entity,
        lower_datum_evidence=lower_evidence,
        upper_datum_evidence=upper_evidence,
    )


def _hosted_opening_bindings(
    *, evidence, resolved, viewport_id: str, page_no: int
) -> list[ShadowQuantityRecord]:
    """Wires pb_hosted_opening_geometry + pb_hosted_opening_wall_binding --
    a genuinely different, hatch/fill-gap-based detection mechanism from W7's
    dangling-end-based pb_wall_room_topology_opening_host_binding, with
    richer status semantics ("bound" is reachable, not just "ambiguous").
    Called with the FULL region-clipped wall candidate list every time --
    never a single-wall shortcut.

    Host AUTHORITY (`canonical_status`) is unconditionally "BLOCKED" here,
    regardless of what the binder found -- see the module docstring's
    "incomplete host-wall universe" constraint. The binder's own raw
    finding is preserved in `candidate_result`, never discarded.

    No scale_authority is passed (none is proven anywhere in this shadow
    yet, same honesty as wall_length's scale_bindings=()), so every
    HostedOpeningSpan carries width_m=None -- opening width/height/deduction
    readiness are correctly left unattempted here, not guessed at.

    Note: pb_opening_deduction_readiness.build_opening_deduction_quantity
    takes host: OpeningHostCandidate (the OLD W7 type), not
    HostedOpeningWallBinding (this module's type) -- the two "opening host"
    representations are not interchangeable. That gap is reported, not
    bridged; bridging it is a real design decision for a human to make, not
    something to paper over here.
    """
    records: list[ShadowQuantityRecord] = []
    if evidence.status != "found":
        records.append(
            ShadowQuantityRecord(
                quantity_family="hosted_opening_binding",
                subject_id=f"vp-{page_no}",
                canonical_value=None,
                canonical_unit=None,
                canonical_status="BLOCKED",
                evidence_ids=(),
                blocking_reasons=(f"hosted_opening_evidence_{evidence.status}:{evidence.reason}",),
                dependency_states=_dependency_states(existence="NOT_EVALUATED"),
            )
        )
        return records

    for span in evidence.openings:
        binding = bind_hosted_opening_to_walls(span, list(resolved), viewport_id=viewport_id)
        if binding.status == "bound":
            candidate_result = "bound"
            reason = "regional_clip_wall_universe_not_proven_complete"
        else:
            candidate_result = binding.status  # "ambiguous" / "unbound"
            reason = f"hosted_opening_{binding.status}:{binding.reason}"

        # Host authority is unconditionally BLOCKED -- see docstring. The
        # controlled dependency vocabulary has no "bound" value; the raw
        # finding lives only in candidate_result, never in dependency_states.
        opening_deps = _dependency_states(existence="FIRM", identity="NOT_EVALUATED", host="BLOCKED")
        records.append(
            ShadowQuantityRecord(
                quantity_family="hosted_opening_binding",
                subject_id=binding.binding_id,
                canonical_value=None,  # binding never carries a quantity -- see module docstring
                canonical_unit=None,
                canonical_status="BLOCKED",
                evidence_ids=(),
                blocking_reasons=(reason,),
                candidate_result=candidate_result,
                dependency_states=opening_deps,
            )
        )
        dim_deps = _dependency_states(
            existence="FIRM", identity="NOT_EVALUATED", host="BLOCKED", scale="NOT_EVALUATED",
            opening_dimension="BLOCKED",
        )
        records.append(
            ShadowQuantityRecord(
                quantity_family="hosted_opening_width",
                subject_id=binding.binding_id,
                canonical_value=None,
                canonical_unit=None,
                canonical_status="BLOCKED",
                evidence_ids=(),
                blocking_reasons=("no_scale_authority_wired_in_this_shadow",),
                candidate_result=f"width_candidate_m={span.width_m}" if span.width_m is not None else None,
                dependency_states=dim_deps,
            )
        )
        records.append(
            ShadowQuantityRecord(
                quantity_family="hosted_opening_height",
                subject_id=binding.binding_id,
                canonical_value=None,
                canonical_unit=None,
                canonical_status="BLOCKED",
                evidence_ids=(),
                blocking_reasons=("plan_geometry_never_shows_height",),
                dependency_states=dim_deps,
            )
        )
        records.append(
            ShadowQuantityRecord(
                quantity_family="opening_deduction_readiness",
                subject_id=binding.binding_id,
                canonical_value=None,
                canonical_unit=None,
                canonical_status="BLOCKED",
                evidence_ids=(),
                blocking_reasons=(
                    "opening_deduction_readiness_requires_OpeningHostCandidate_not_HostedOpeningWallBinding",
                ),
                dependency_states=_dependency_states(
                    existence="FIRM", identity="NOT_EVALUATED", host="BLOCKED",
                    opening_dimension="BLOCKED", net_area="BLOCKED",
                ),
            )
        )
    return records


def _build_canonical_wall_universe(
    *, pdf_path: Path, page_0based: int, region: tuple[float, float, float, float]
):
    """Mirrors scripts/wall_linear_authority_real_drawing_shadow.py's
    construction pipeline (same functions, same order) so height/gross-area
    authority can be layered on the same wall objects. See module docstring
    for why this is reconstructed rather than imported."""
    source_sha256 = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    document_id = f"doc-{source_sha256[:16]}"
    page_id = f"page-{page_0based}"
    viewport_id = f"vp-{page_0based}"
    page_no = page_0based + 1

    doc = fitz.open(str(pdf_path))
    try:
        page_obj = doc[page_0based]
        native = extract_native_page(page_obj)
        page_text = page_obj.get_text() or ""
        # Must run while `doc` is open -- HostedOpeningSpan objects
        # themselves are plain frozen dataclasses, safe to keep after close.
        hosted_opening_evidence = resolve_hosted_opening_spans(page_obj, viewport_bbox=region)
    finally:
        doc.close()

    def _overlaps(bbox, r):
        bx0, by0, bx1, by1 = bbox
        rx0, ry0, rx1, ry1 = r
        return not (bx1 < rx0 or bx0 > rx1 or by1 < ry0 or by0 > ry1)

    segments = [
        s
        for s in native["segments"]
        if _overlaps(
            (min(s["x1"], s["x2"]), min(s["y1"], s["y2"]), max(s["x1"], s["x2"]), max(s["y1"], s["y2"])),
            region,
        )
    ]

    graph = build_wall_graph_for_viewport(segments)
    graph = attach_typed_semantic_evidence(graph, document_id=document_id, page_id=page_id, viewport_id=viewport_id)
    junctions, relationships = classify_junctions(graph, document_id=document_id, page_id=page_id, viewport_id=viewport_id)
    walls, _edge_map = assemble_wall_candidates(graph, junctions, relationships, viewport_id=viewport_id)
    pairs = detect_wall_pairs(segments)
    resolved, minted = resolve_wall_physical_evidence(
        walls, graph=graph, document_id=document_id, page_id=page_id, paired_wall_faces=pairs
    )

    semantic_atoms = list(graph.get(GRAPH_ATOMS_KEY) or [])
    catalog = [*semantic_atoms, *minted]
    evidence_ids = tuple(
        dict.fromkeys(
            str(a.get("evidence_id") if isinstance(a, dict) else a.evidence_id)
            for a in catalog
            if (a.get("evidence_id") if isinstance(a, dict) else a.evidence_id)
        )
    )

    document = DocumentEvidence(
        document_id=document_id,
        source_sha256=source_sha256,
        page_count=1,
        page_ids=(page_id,),
        evidence_ids=evidence_ids,
    )
    viewport = ViewportEvidence(
        viewport_id=viewport_id,
        document_id=document_id,
        page_id=page_id,
        bbox=tuple(region),
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        confidence=1.0,
    )
    context = ProviderContext(
        run_id="canonical-shadow",
        workspace_id="shadow",
        project_id="shadow",
        document_id=document_id,
        source_sha256=source_sha256,
        revision_id="R1",
        current_revision_id="R1",
        selected_pages=(page_0based,),
        owned_viewport_ids=(viewport_id,),
        evidence_snapshot_id="shadow-ev",
        owned_page_numbers=(page_no,),
        viewport_page_ownership=((viewport_id, page_no),),
    )
    # Level markers are extracted HERE, and their evidence atoms are
    # stamped HERE (via _stamp_level_marker_atoms, immediately below) --
    # both using this same, genuinely-current `context` -- see the module
    # docstring's freshness constraint for why this must be the ONLY place
    # stamping happens.
    levels = find_level_markers(page_text, source_page=page_no, view_id=viewport_id)
    level_atoms = _stamp_level_marker_atoms(
        levels, document_id=document_id, page_id=page_id, extraction_context=context
    )

    physical_identities = collect_physical_wall_identities(resolved, graph)
    equivalence = resolve_physical_wall_equivalence(
        tuple(physical_identities.get(wall.candidate_id) for wall in resolved),
        walls_by_id={wall.candidate_id: wall for wall in resolved},
    )

    return {
        "resolved": resolved,
        "catalog": catalog,
        "document": document,
        "viewport": viewport,
        "context": context,
        "equivalence": equivalence,
        "levels": levels,
        "level_atoms": level_atoms,
        "page_no": page_no,
        "pdf_path": pdf_path,
        "viewport_id": viewport_id,
        "hosted_opening_evidence": hosted_opening_evidence,
    }


def _identity_state_for_wall(wall_id: str, equivalence) -> str:
    if wall_id in equivalence.representative_wall_ids:
        return "same_or_representative"
    if wall_id in equivalence.ambiguous_wall_ids:
        return "ambiguous"
    if wall_id in equivalence.abstained_wall_ids:
        return "abstained"
    return "distinct"


def run_canonical_shadow_for_drawing(spec: dict[str, Any]) -> ShadowDrawingReport:
    universe = _build_canonical_wall_universe(
        pdf_path=spec["pdf"], page_0based=spec["page_0based"], region=spec["region"]
    )
    resolved = universe["resolved"]
    catalog = universe["catalog"]
    document = universe["document"]
    viewport = universe["viewport"]
    context = universe["context"]
    equivalence = universe["equivalence"]
    levels = universe["levels"]
    level_atoms = universe["level_atoms"]
    page_no = universe["page_no"]

    records: list[ShadowQuantityRecord] = []
    length_by_wall: dict[str, Any] = {}
    height_by_wall: dict[str, Any] = {}

    for wall in resolved:
        identity_state = _identity_state_for_wall(wall.candidate_id, equivalence)
        entity = adapt_wall_candidate_to_entity_evidence(
            wall, evidence_atoms=catalog, document=document, viewport=viewport, context=context
        )
        if entity is None:
            records.append(
                ShadowQuantityRecord(
                    quantity_family="wall_length",
                    subject_id=wall.candidate_id,
                    canonical_value=None,
                    canonical_unit=None,
                    canonical_status=EvidenceResolutionStatus.ABSTAINED.value,
                    evidence_ids=(),
                    blocking_reasons=("physical_wall_entity_evidence_unavailable",),
                    dependency_states=_dependency_states(
                        existence="BLOCKED", identity=_identity_status_to_dependency(identity_state)
                    ),
                )
            )
            continue

        length_qty = build_wall_length_quantity(
            wall=wall,
            context=context,
            document=document,
            viewport=viewport,
            entity=entity,
            evidence_atoms=catalog,
            equivalence=equivalence,
            page_no=page_no,
            scale_bindings=(),
        )
        length_by_wall[wall.candidate_id] = length_qty
        records.append(
            _record(
                length_qty, family="wall_length", subject_id=wall.candidate_id,
                dependency_states=_dependency_states(
                    existence=_evidence_status_to_dependency(entity.status.value),
                    identity=_identity_status_to_dependency(identity_state),
                    scale="NOT_EVALUATED",
                    length=_quantity_status_to_dependency(length_qty),
                ),
            )
        )

        height_qty = _attempt_wall_height(
            wall_id=wall.candidate_id, context=context, document=document, viewport=viewport, entity=entity,
            levels=levels, level_atoms=level_atoms,
        )
        height_by_wall[wall.candidate_id] = height_qty
        records.append(
            _record(
                height_qty, family="wall_height", subject_id=wall.candidate_id,
                dependency_states=_dependency_states(
                    existence=_evidence_status_to_dependency(entity.status.value),
                    identity=_identity_status_to_dependency(identity_state),
                    height=_quantity_status_to_dependency(height_qty),
                ),
            )
        )

        gross_deps_base = dict(
            existence=_evidence_status_to_dependency(entity.status.value),
            identity=_identity_status_to_dependency(identity_state),
            scale="NOT_EVALUATED",
            length=_quantity_status_to_dependency(length_qty),
            height=_quantity_status_to_dependency(height_qty),
        )
        if not length_qty.abstained and not height_qty.abstained:
            gross_qty = build_gross_wall_area_quantity(
                wall_id=wall.candidate_id, wall_length=length_qty, wall_height=height_qty
            )
            records.append(
                _record(
                    gross_qty, family="gross_wall_area", subject_id=wall.candidate_id,
                    dependency_states=_dependency_states(
                        **gross_deps_base, gross_area=_quantity_status_to_dependency(gross_qty)
                    ),
                )
            )
        else:
            blockers = []
            if length_qty.abstained:
                blockers.append("wall_length_abstained")
            if height_qty.abstained:
                blockers.append("wall_height_abstained")
            records.append(
                ShadowQuantityRecord(
                    quantity_family="gross_wall_area",
                    subject_id=wall.candidate_id,
                    canonical_value=None,
                    canonical_unit=None,
                    canonical_status=EvidenceResolutionStatus.ABSTAINED.value,
                    evidence_ids=(),
                    blocking_reasons=tuple(blockers),
                    dependency_states=_dependency_states(**gross_deps_base, gross_area="BLOCKED"),
                )
            )

    # Net area / opening deduction (W7 path): real host-candidate detection
    # on the real wall universe, not fabricated. See module docstring --
    # net_wall_area is unconditionally BLOCKED, never gated on host-candidate
    # count or status, because opening-set completeness is never claimed.
    host_candidates = detect_opening_host_candidates(list(resolved))
    observed_statuses = tuple(sorted({h.host_status for h in host_candidates}))
    for wall in resolved:
        if wall.candidate_id not in length_by_wall:
            continue
        records.append(
            ShadowQuantityRecord(
                quantity_family="net_wall_area",
                subject_id=wall.candidate_id,
                canonical_value=None,
                canonical_unit=None,
                canonical_status=EvidenceResolutionStatus.ABSTAINED.value,
                evidence_ids=(),
                blocking_reasons=("opening_completeness_not_independently_proven",),
                dependency_states=_dependency_states(
                    existence=_quantity_status_to_dependency(length_by_wall[wall.candidate_id]),
                    length=_quantity_status_to_dependency(length_by_wall[wall.candidate_id]),
                    height=_quantity_status_to_dependency(height_by_wall[wall.candidate_id]),
                    host="BLOCKED", net_area="BLOCKED",
                ),
            )
        )

    # Newer hosted-opening geometry + wall-binding path -- a genuinely
    # different mechanism from W7, wired for real, kept distinct.
    records.extend(
        _hosted_opening_bindings(
            evidence=universe["hosted_opening_evidence"],
            resolved=resolved,
            viewport_id=universe["viewport_id"],
            page_no=page_no,
        )
    )

    # Internal wall length: pb_wall_fill_internal_partition_evidence already
    # computes a genuine internal-partition length from real solid-fill
    # geometry, but only for a whole-envelope length_m/width_m this region-
    # scoped shadow does not independently derive -- reported NOT_EVIDENCED.
    # Must independently pass existence+identity+role+length+scope-
    # completeness before any promotion; none of those are proven here.
    records.append(
        ShadowQuantityRecord(
            quantity_family="internal_wall_length",
            subject_id=AGGREGATE_SUBJECT_ID,
            canonical_value=None,
            canonical_unit=None,
            canonical_status="not_evidenced",
            evidence_ids=(),
            blocking_reasons=("requires_whole_envelope_length_width_not_derived_in_this_shadow",),
            dependency_states=_dependency_states(
                existence="NOT_EVALUATED", identity="NOT_EVALUATED", length="NOT_EVALUATED",
                role="NOT_EVALUATED",
            ),
        )
    )

    # External render / cladding: no finish-identity/applicable-scope
    # authority exists anywhere in this shadow (or, per Phase 1's trace,
    # anywhere live) -- reported NOT_EVIDENCED, never fabricated.
    for family in ("external_render", "cladding"):
        records.append(
            ShadowQuantityRecord(
                quantity_family=family,
                subject_id=AGGREGATE_SUBJECT_ID,
                canonical_value=None,
                canonical_unit=None,
                canonical_status="not_evidenced",
                evidence_ids=(),
                blocking_reasons=("no_finish_identity_or_applicable_scope_authority_implemented",),
                dependency_states=_dependency_states(finish="NOT_EVALUATED", net_area="BLOCKED"),
            )
        )

    legacy_aggregate: dict[str, Any] = {}
    try:
        extractor = GenericPlanReaderExtractor()
        predictions = extractor.extract_from_pdf(str(spec["pdf"]), pages=[spec["page_0based"]])
        for pred in predictions:
            d = pred.to_dict()
            tag = d.get("tag") or d.get("item_id") or d.get("label")
            if tag:
                legacy_aggregate[str(tag)] = {"quantity": d.get("quantity"), "unit": d.get("unit")}
    except Exception as exc:  # noqa: BLE001 -- observability only, must not raise
        legacy_aggregate = {"error": f"{type(exc).__name__}: {exc}"}

    # Family-aggregate comparison rows: the only granularity at which a
    # canonical-vs-legacy comparison is sound. Sums only FIRM per-wall
    # values.
    def _firm_sum(by_wall: dict[str, Any]) -> Optional[float]:
        firm_values = [q.value for q in by_wall.values() if not q.abstained and q.value is not None]
        return round(sum(firm_values), 6) if firm_values else None

    gross_by_wall = {
        r.subject_id: r for r in records if r.quantity_family == "gross_wall_area" and r.subject_id in length_by_wall
    }
    aggregate_inputs = {
        "wall_length": _firm_sum(length_by_wall),
        "wall_height": _firm_sum(height_by_wall),
        "gross_wall_area": round(sum(r.canonical_value for r in gross_by_wall.values() if r.canonical_value is not None), 6)
        if any(r.canonical_value is not None for r in gross_by_wall.values())
        else None,
        "net_wall_area": None,  # never attempted this run -- opening completeness never proven
    }
    for family, shadow_total in aggregate_inputs.items():
        legacy_tag = _FAMILY_TO_LEGACY_TAG[family]
        legacy_entry = legacy_aggregate.get(legacy_tag) if legacy_tag else None
        legacy_value = legacy_entry.get("quantity") if legacy_entry else None
        legacy_unit = legacy_entry.get("unit") if legacy_entry else None
        canonical_unit = _CANONICAL_UNIT_FOR_FAMILY[family] if shadow_total is not None else None
        # Net area is BLOCKED unconditionally -- if legacy still shows a
        # numeric figure, that is LEGACY_ONLY with the canonical blocker
        # retained (point 8), not a comparison collapsing into "same".
        blocking = () if family != "net_wall_area" else ("opening_completeness_not_independently_proven",)
        records.append(
            ShadowQuantityRecord(
                quantity_family=family,
                subject_id=AGGREGATE_SUBJECT_ID,
                canonical_value=shadow_total,
                canonical_unit=canonical_unit,
                canonical_status="aggregate_of_firm_walls" if shadow_total is not None else "aggregate_none_firm",
                evidence_ids=(),
                blocking_reasons=blocking,
                dependency_states=_dependency_states(
                    length="FIRM" if family != "wall_height" and shadow_total is not None else "NOT_REQUIRED",
                    height="FIRM" if family in ("wall_height", "gross_wall_area", "net_wall_area") and shadow_total is not None else "NOT_REQUIRED",
                    gross_area="FIRM" if family in ("gross_wall_area", "net_wall_area") and shadow_total is not None else "NOT_REQUIRED",
                    net_area="BLOCKED" if family == "net_wall_area" else "NOT_REQUIRED",
                ),
                legacy_value=legacy_value,
                legacy_unit=legacy_unit,
                comparison=_comparison_status(
                    shadow_total, legacy_value, canonical_unit=canonical_unit, legacy_unit=legacy_unit
                ),
            )
        )

    return ShadowDrawingReport(
        label=spec["label"],
        canonical_walls_considered=len(resolved),
        canonical_records=tuple(records),
        opening_host_candidates_observed=len(host_candidates),
        opening_host_statuses_observed=observed_statuses,
        legacy_aggregate=legacy_aggregate,
        notes=(
            "Canonical per-wall records are per-physical-wall; comparison "
            "is populated only on the AGGREGATE_SUBJECT_ID rows (sum of FIRM "
            "per-wall values vs. the legacy whole-page figure, gated on unit "
            "compatibility) -- individual wall rows are not compared against "
            "a whole-page legacy value.",
            "perimeter_walling (the legacy reference for gross/net_wall_area) "
            "is mutated in place to the NET value by GenericOpeningDeductionPipeline "
            "whenever any opening prediction exists on this page -- this "
            "comparison does not disambiguate gross vs. net on the legacy side.",
            "Region-scoped diagnostic window only, not a whole-building "
            "perimeter claim -- every hosted_opening_binding row is BLOCKED "
            "for exactly this reason regardless of the underlying binder's "
            "own finding, which is preserved in candidate_result.",
            "pb_wall_height_authority's own ownership check does not verify "
            "revision/snapshot/source-SHA freshness at all -- this module's "
            "_height_evidence_is_fresh gate is a shadow-side protective "
            "boundary, not a fix to that module, which still needs separate "
            "remediation upstream.",
        ),
    )
