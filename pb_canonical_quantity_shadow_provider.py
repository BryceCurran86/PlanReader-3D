"""Canonical quantity shadow provider (Canonical Shadow Integration, Phase 2/6).

Gold-free, non-commercial, observability-only. This module NEVER touches
`pred_dict`, never imports anything from the benchmark gold/scoring path, and
never mutates any object the live `GenericPlanReaderExtractor` path owns.

WHY THIS FILE EXISTS
Phase 1's trace (see conversation record, not repeated here) confirmed that
every newer fail-closed authority module for wall length/height/gross-area/
net-area/opening-deduction has ZERO live callers -- `GenericPlanReaderExtractor`
still produces every commercial quantity through legacy ad hoc geometry/regex
paths, with exactly one live hard-coded height default
(`GenericPlanReaderExtractor.default_ceiling_height_m = 2.80`,
`pb_planreader_pdf_extractor.py:68`).

This provider runs the *disconnected* canonical authority chain end-to-end,
per physical wall, on a real drawing, and reports what it can and cannot
prove -- without inventing any new detection algorithm and without changing
what the live path returns.

WHAT IS REUSED, UNCHANGED, FROM THE EXISTING #288 SHADOW SCRIPT
The existence/equivalence/entity construction pipeline below mirrors
`scripts/wall_linear_authority_real_drawing_shadow.py` exactly (same
functions, same call order: build_wall_graph_for_viewport ->
attach_typed_semantic_evidence -> classify_junctions -> assemble_wall_candidates
-> detect_wall_pairs -> resolve_wall_physical_evidence ->
collect_physical_wall_identities -> resolve_physical_wall_equivalence). That
script returns only a summary dict; this module needs the underlying
objects (WallCandidate list, ProviderContext, DocumentEvidence,
ViewportEvidence, evidence catalog, equivalence) so later authority calls
(height, gross area) can be layered on the same wall universe -- so the
pipeline is reconstructed here rather than imported, but it is not modified.

WHAT IS NEW HERE
1. Wall height: `pb_level_datum_extraction.find_level_markers` +
   `pb_dimension_graph_constraint_engine.resolve_wall_height` already run in
   the LIVE legacy path (via `pb_planreader_pdf_extractor.py:631-636`) and
   already refuse to default when unresolved -- but their output is a bare
   `HeightResolution`, never wrapped as an `EvidenceAtom` for
   `pb_wall_height_authority.build_wall_height_quantity` to consume. That
   adapter (`_level_marker_evidence_atom` / `_attempt_wall_height`) is new.
2. Gross area: mechanical (`build_gross_wall_area_quantity`) once both
   length and height are independently FIRM for the same wall_id. No new
   logic beyond calling the existing authority.
3. Net area / opening deduction: NOT attempted with fabricated inputs.
   `pb_wall_room_topology_opening_host_binding.detect_opening_host_candidates`
   is called for real (on the real WallCandidate universe, zero new
   geometry work needed -- it takes only `Sequence[WallCandidate]`) so the
   "always ambiguous_host" claim is an observed fact on this drawing, not
   an assumed one; `build_opening_deduction_quantity`/
   `build_net_wall_area_quantity` are never called with anything but real
   host candidates, so net area is reported BLOCKED with the same
   `opening_host_not_uniquely_resolved` reason those functions would
   themselves produce, rather than skipped or guessed at.

SCOPE MISMATCH, STATED EXPLICITLY
Canonical authority publishes per physical wall. The live legacy path
publishes one whole-drawing/whole-page aggregate (`perimeter_walling` etc.).
This provider does not attempt a fabricated per-wall "same/different"
comparison against that aggregate -- it reports canonical per-wall results
and the legacy whole-drawing aggregate side by side, and leaves the
granularity mismatch visible rather than papering over it.
"""
from __future__ import annotations

import dataclasses
import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional, Sequence

import fitz

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pb_canonical_wall_room_evidence_model import resolve_wall_physical_evidence
from pb_dimension_graph_constraint_engine import HeightResolution, LevelMarker, resolve_wall_height
from pb_level_datum_extraction import find_level_markers
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_physical_wall_existence_authority import adapt_wall_candidate_to_entity_evidence
from pb_hosted_opening_geometry import resolve_hosted_opening_spans
from pb_hosted_opening_wall_binding import bind_hosted_opening_to_walls
from pb_physical_wall_identity import collect_physical_wall_identities, resolve_physical_wall_equivalence
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_vector_geometry_v130 import detect_wall_pairs, extract_native_page
from pb_wall_gross_area_quantity import build_gross_wall_area_quantity
from pb_wall_height_authority import build_wall_height_quantity
from pb_wall_length_quantity import build_wall_length_quantity
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_opening_host_binding import detect_opening_host_candidates
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_typed_negative_evidence import GRAPH_ATOMS_KEY, attach_typed_semantic_evidence
from pb_wall_room_topology_wall_assembly import assemble_wall_candidates

SHADOW_PROVIDER_SCHEMA_VERSION = "1.0.0"

ComparisonStatus = Literal["SAME", "DIFFERENT", "LEGACY_ONLY", "SHADOW_ONLY", "BOTH_BLOCKED"]

# family -> legacy prediction tag treated as its (approximate) reference.
# None means legacy has no comparable decomposition at all (it only ever
# publishes a combined figure) -- that is reported as SHADOW_ONLY, not
# guessed at via some other tag.
_FAMILY_TO_LEGACY_TAG: dict[str, Optional[str]] = {
    "wall_length": None,
    "wall_height": None,
    "gross_wall_area": "perimeter_walling",
    "net_wall_area": "perimeter_walling",
}
# perimeter_walling is mutated in place to the NET value by
# GenericOpeningDeductionPipeline.propagate_to_predictions whenever any
# opening prediction exists on the page (see pb_opening_deduction_pipeline.py
# :262-334) -- when it does, gross_wall_area's legacy comparison below is
# against an already-net figure, not a clean gross one. That ambiguity is
# inherent to the legacy representation, not disambiguated here; it is
# surfaced as a note on every ShadowDrawingReport rather than silently
# assumed away.
_COMPARISON_RELATIVE_TOLERANCE = 0.01  # reporting-only heuristic for SAME/DIFFERENT; not an authority tolerance_policy

# marker_type -> (allowed EvidenceAtom kind, "upper" or "lower" datum role)
_MARKER_TYPE_TO_DATUM_KIND: dict[str, tuple[str, str]] = {
    "roof": ("elevation_datum", "upper"),
    "ceiling": ("ceiling_level_datum", "upper"),
    "beam": ("elevation_datum", "upper"),
    "floor": ("floor_level_datum", "lower"),
    "ground": ("floor_level_datum", "lower"),
}


@dataclass(frozen=True)
class ShadowQuantityRecord:
    """One Phase-6 observability row. Never overwrites or feeds commercial
    output; this is the whole point of the object -- read-only reporting.

    legacy_live_value/comparison_status are populated only for whole-drawing
    AGGREGATE rows (subject_id == AGGREGATE_SUBJECT_ID) -- comparing one
    individual wall's canonical value against a whole-page legacy figure is
    not a sound comparison, so per-wall rows leave both None rather than
    forcing a misleading verdict onto them.
    """

    quantity_family: str
    subject_id: str
    value: Optional[float]
    unit: Optional[str]
    authority_status: str
    evidence_ids: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    legacy_live_value: Optional[float] = None
    comparison_status: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "quantity_family": self.quantity_family,
            "subject_id": self.subject_id,
            "value": self.value,
            "unit": self.unit,
            "authority_status": self.authority_status,
            "evidence_ids": list(self.evidence_ids),
            "blocking_reasons": list(self.blocking_reasons),
            "legacy_live_value": self.legacy_live_value,
            "canonical_shadow_value": self.value,
            "comparison_status": self.comparison_status,
        }


AGGREGATE_SUBJECT_ID = "__whole_drawing_aggregate__"


def _comparison_status(shadow_value: Optional[float], legacy_value: Optional[float]) -> ComparisonStatus:
    if shadow_value is None and legacy_value is None:
        return "BOTH_BLOCKED"
    if shadow_value is None:
        return "LEGACY_ONLY"
    if legacy_value is None:
        return "SHADOW_ONLY"
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


def _record(qty, *, family: str, subject_id: str) -> ShadowQuantityRecord:
    value = None if qty.abstained else qty.value
    unit = qty.unit if not qty.abstained else None
    return ShadowQuantityRecord(
        quantity_family=family,
        subject_id=subject_id,
        value=value,
        unit=unit,
        authority_status=qty.status,
        evidence_ids=tuple(qty.evidence_ids),
        blocking_reasons=tuple(qty.blocking_reasons),
    )


def _level_marker_evidence_atom(
    marker: LevelMarker, *, document_id: str, page_id: str
) -> Optional[EvidenceAtom]:
    mapping = _MARKER_TYPE_TO_DATUM_KIND.get(marker.marker_type)
    if mapping is None:
        return None
    kind, _role = mapping
    return EvidenceAtom(
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
        metadata={"marker_type": marker.marker_type, "source_page": marker.source_page},
    )


def _attempt_wall_height(
    *,
    wall_id: str,
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    entity,
    levels: Sequence[LevelMarker],
):
    resolution: HeightResolution = resolve_wall_height(levels, scope_id=None)
    lower_evidence: Optional[EvidenceAtom] = None
    upper_evidence: Optional[EvidenceAtom] = None
    if resolution.status == "fully_constrained" and resolution.clear_height_m is not None:
        roof_value = resolution.sources.get("roof_level_m")
        floor_value = resolution.sources.get("floor_level_m")
        for marker in levels:
            if marker.scope_id is not None:
                continue
            mapping = _MARKER_TYPE_TO_DATUM_KIND.get(marker.marker_type)
            if mapping is None:
                continue
            _kind, role = mapping
            if role == "upper" and upper_evidence is None and marker.level_m == roof_value:
                upper_evidence = _level_marker_evidence_atom(
                    marker, document_id=document.document_id, page_id=document.page_ids[0]
                )
            elif role == "lower" and lower_evidence is None and marker.level_m == floor_value:
                lower_evidence = _level_marker_evidence_atom(
                    marker, document_id=document.document_id, page_id=document.page_ids[0]
                )

    # build_wall_height_quantity's ownership check requires each datum
    # evidence_id to be a member of BOTH document.evidence_ids AND
    # entity.evidence_ids. `entity` here is the wall's *existence* entity
    # (from adapt_wall_candidate_to_entity_evidence) and `document` was built
    # from the wall-topology catalog -- neither knows about height evidence
    # yet. Extending both (never replacing/shrinking) is the correct move:
    # this is still the same document and the same corroborated physical
    # wall, now with an additional, independent kind of evidence attached,
    # exactly as a real accumulating evidence bundle should behave. Doing
    # this here (not in the caller) keeps "where do level-marker evidence
    # ids get registered" in one place.
    new_ids = {e.evidence_id for e in (lower_evidence, upper_evidence) if e is not None}
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
                value=None,
                unit=None,
                authority_status="abstained",
                evidence_ids=(),
                blocking_reasons=(f"hosted_opening_evidence_{evidence.status}:{evidence.reason}",),
            )
        )
        return records

    for i, span in enumerate(evidence.openings):
        binding = bind_hosted_opening_to_walls(span, list(resolved), viewport_id=viewport_id)
        blocking = () if binding.status == "bound" else (f"hosted_opening_{binding.status}:{binding.reason}",)
        records.append(
            ShadowQuantityRecord(
                quantity_family="hosted_opening_binding",
                subject_id=binding.binding_id,
                value=None,  # binding never carries a quantity -- see module docstring
                unit=None,
                authority_status=binding.status,
                evidence_ids=(),
                blocking_reasons=blocking,
            )
        )
        records.append(
            ShadowQuantityRecord(
                quantity_family="hosted_opening_width",
                subject_id=binding.binding_id,
                value=span.width_m,
                unit="m" if span.width_m is not None else None,
                authority_status="abstained" if span.width_m is None else "candidate",
                evidence_ids=(),
                blocking_reasons=() if span.width_m is not None else ("no_scale_authority_wired_in_this_shadow",),
            )
        )
        records.append(
            ShadowQuantityRecord(
                quantity_family="hosted_opening_height",
                subject_id=binding.binding_id,
                value=None,
                unit=None,
                authority_status="abstained",
                evidence_ids=(),
                blocking_reasons=("plan_geometry_never_shows_height",),
            )
        )
        records.append(
            ShadowQuantityRecord(
                quantity_family="opening_deduction_readiness",
                subject_id=binding.binding_id,
                value=None,
                unit=None,
                authority_status="abstained",
                evidence_ids=(),
                blocking_reasons=(
                    "opening_deduction_readiness_requires_OpeningHostCandidate_not_HostedOpeningWallBinding",
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

    levels = find_level_markers(page_text, source_page=page_no, view_id=viewport_id)
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
        "page_no": page_no,
        "pdf_path": pdf_path,
        "viewport_id": viewport_id,
        "hosted_opening_evidence": hosted_opening_evidence,
    }


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
    page_no = universe["page_no"]

    records: list[ShadowQuantityRecord] = []
    length_by_wall: dict[str, Any] = {}
    height_by_wall: dict[str, Any] = {}

    for wall in resolved:
        entity = adapt_wall_candidate_to_entity_evidence(
            wall, evidence_atoms=catalog, document=document, viewport=viewport, context=context
        )
        if entity is None:
            records.append(
                ShadowQuantityRecord(
                    quantity_family="wall_length",
                    subject_id=wall.candidate_id,
                    value=None,
                    unit=None,
                    authority_status=EvidenceResolutionStatus.ABSTAINED.value,
                    evidence_ids=(),
                    blocking_reasons=("physical_wall_entity_evidence_unavailable",),
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
        records.append(_record(length_qty, family="wall_length", subject_id=wall.candidate_id))

        height_qty = _attempt_wall_height(
            wall_id=wall.candidate_id, context=context, document=document, viewport=viewport, entity=entity, levels=levels
        )
        height_by_wall[wall.candidate_id] = height_qty
        records.append(_record(height_qty, family="wall_height", subject_id=wall.candidate_id))

        if not length_qty.abstained and not height_qty.abstained:
            gross_qty = build_gross_wall_area_quantity(
                wall_id=wall.candidate_id, wall_length=length_qty, wall_height=height_qty
            )
            records.append(_record(gross_qty, family="gross_wall_area", subject_id=wall.candidate_id))
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
                    value=None,
                    unit=None,
                    authority_status=EvidenceResolutionStatus.ABSTAINED.value,
                    evidence_ids=(),
                    blocking_reasons=tuple(blockers),
                )
            )

    # Net area / opening deduction (W7 path): real host-candidate detection
    # on the real wall universe, not fabricated. detect_opening_host_candidates
    # only needs Sequence[WallCandidate] -- no new geometry work required.
    host_candidates = detect_opening_host_candidates(list(resolved))
    observed_statuses = tuple(sorted({h.host_status for h in host_candidates}))
    hosted_candidates = [h for h in host_candidates if h.host_status == "hosted"]
    net_area_blocked_reason = (
        "opening_host_not_uniquely_resolved" if not hosted_candidates else "net_wall_area_not_attempted"
    )
    for wall in resolved:
        if wall.candidate_id not in length_by_wall:
            continue
        records.append(
            ShadowQuantityRecord(
                quantity_family="net_wall_area",
                subject_id=wall.candidate_id,
                value=None,
                unit=None,
                authority_status=EvidenceResolutionStatus.ABSTAINED.value,
                evidence_ids=(),
                blocking_reasons=(net_area_blocked_reason,),
            )
        )

    # Newer hosted-opening geometry + wall-binding path (task 6) -- a
    # genuinely different mechanism from W7, wired for real, kept distinct.
    records.extend(
        _hosted_opening_bindings(
            evidence=universe["hosted_opening_evidence"],
            resolved=resolved,
            viewport_id=universe["viewport_id"],
            page_no=page_no,
        )
    )

    # Internal wall length (task 7): pb_wall_fill_internal_partition_evidence
    # already computes a genuine internal-partition length from real solid-
    # fill geometry, but only for a whole-envelope length_m/width_m this
    # region-scoped shadow does not independently derive (that function's
    # own contract requires the caller's already-resolved envelope scale,
    # not just wall-candidate geometry) -- reported NOT_EVIDENCED rather
    # than guessing an envelope size, per "do not promote to FIRM merely
    # because the function returns a number."
    records.append(
        ShadowQuantityRecord(
            quantity_family="internal_wall_length",
            subject_id=AGGREGATE_SUBJECT_ID,
            value=None,
            unit=None,
            authority_status="not_evidenced",
            evidence_ids=(),
            blocking_reasons=("requires_whole_envelope_length_width_not_derived_in_this_shadow",),
        )
    )

    # External render / cladding (task 8): no finish-identity/applicable-
    # scope authority exists anywhere in this shadow (or, per Phase 1's
    # trace, anywhere live) -- reported NOT_EVIDENCED, never fabricated.
    for family in ("external_render", "cladding"):
        records.append(
            ShadowQuantityRecord(
                quantity_family=family,
                subject_id=AGGREGATE_SUBJECT_ID,
                value=None,
                unit=None,
                authority_status="not_evidenced",
                evidence_ids=(),
                blocking_reasons=("no_finish_identity_or_applicable_scope_authority_implemented",),
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

    # Family-aggregate comparison rows (task 3): the only granularity at
    # which a canonical-vs-legacy comparison is sound (see class docstring
    # for why per-wall rows leave comparison_status=None). Sums only FIRM
    # per-wall values -- an abstained wall contributes 0 to the sum but is
    # separately visible via its own per-wall record's blocking_reasons, it
    # is never silently dropped from the walls-considered count.
    def _firm_sum(by_wall: dict[str, Any]) -> Optional[float]:
        firm_values = [q.value for q in by_wall.values() if not q.abstained and q.value is not None]
        return round(sum(firm_values), 6) if firm_values else None

    gross_by_wall = {
        r.subject_id: r for r in records if r.quantity_family == "gross_wall_area" and r.subject_id in length_by_wall
    }
    aggregate_inputs = {
        "wall_length": _firm_sum(length_by_wall),
        "wall_height": _firm_sum(height_by_wall),
        "gross_wall_area": round(sum(r.value for r in gross_by_wall.values() if r.value is not None), 6)
        if any(r.value is not None for r in gross_by_wall.values())
        else None,
        "net_wall_area": None,  # never attempted this run -- see net_area_blocked_reason above
    }
    _AGGREGATE_UNIT = {"wall_length": "m", "wall_height": "m", "gross_wall_area": "m2", "net_wall_area": "m2"}
    for family, shadow_total in aggregate_inputs.items():
        legacy_tag = _FAMILY_TO_LEGACY_TAG[family]
        legacy_value = legacy_aggregate.get(legacy_tag, {}).get("quantity") if legacy_tag else None
        records.append(
            ShadowQuantityRecord(
                quantity_family=family,
                subject_id=AGGREGATE_SUBJECT_ID,
                value=shadow_total,
                unit=_AGGREGATE_UNIT[family] if shadow_total is not None else None,
                authority_status="aggregate_of_firm_walls" if shadow_total is not None else "aggregate_none_firm",
                evidence_ids=(),
                blocking_reasons=(),
                legacy_live_value=legacy_value,
                comparison_status=_comparison_status(shadow_total, legacy_value),
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
            "Canonical per-wall records are per-physical-wall; comparison_status "
            "is populated only on the AGGREGATE_SUBJECT_ID rows (sum of FIRM "
            "per-wall values vs. the legacy whole-page figure) -- individual "
            "wall rows are not compared against a whole-page legacy value.",
            "perimeter_walling (the legacy reference for gross/net_wall_area) "
            "is mutated in place to the NET value by GenericOpeningDeductionPipeline "
            "whenever any opening prediction exists on this page -- this "
            "comparison does not disambiguate gross vs. net on the legacy side.",
            "Region-scoped diagnostic window only, not a whole-building "
            "perimeter claim.",
        ),
    )
