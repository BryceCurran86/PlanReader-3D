"""Default-off, read-only correspondence of a callout-identified glazing strip to whole-opening aperture records, SHADOW.

A nominator (the plan callout to glazing strip shadow) names a glazing strip, by immutable visible-ink ids, for the
callout that corresponds to it. `StructuralWholeOpeningApertureProducer` independently reports whole-opening aperture
records and the internal glazing subdivisions it discriminated. This module answers one narrow question: does exactly
one structurally proven whole-opening aperture record have the extent of that strip, with no unaccounted rival?

It never edits or reinterprets the aperture authority. Its source adapter hands that authority only strokes the
producer authenticates (a visible observation joined to the producer's own primitive of the same id, with matching
geometry and drawing sequence), runs it unchanged, and relates records to strips by extent. Every record that
could be a different reading of the same ink (nested inside the strip, containing it, or partly overlapping it) is
RETAINED as a rival. A nested record is set aside only when the authority itself discriminated an internal glazing
subdivision of exactly that span; nothing else, no distance, size or label, removes a rival.

Issues only CANDIDATE / ABSTAINED / CONFLICT. It grants no physical opening, host, kind, frame, scale, count or
quantity, and it is wired to nothing. Its standing limits are typed and always present.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, fields
from typing import Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_structural_whole_opening_aperture_authority import (
    AMBIGUOUS_MULTI_LAYER_OFFSET,
    AMBIGUOUS_STRUCTURAL_BOUNDARY,
    APERTURE_EXTENT_INCOMPLETE,
    FILL_MASK_BOUNDARY_UNPROVEN,
    HOST_WALL_CONTINUITY_PROVEN,
    STRUCTURAL_TERMINAL_JAMB_PROVEN,
    TERMINAL_ROLE_UNPROVEN,
    WALL_CONTINUITY_MISSING,
    ApertureSourceStroke,
    GlazingSubdivisionDiscriminationRecord,
    StructuralWholeOpeningApertureProducer,
    WholeOpeningApertureRecord,
)

WHOLE_APERTURE_CORRESPONDENCE_SCHEMA_VERSION = "1.0.0"
WHOLE_APERTURE_CORRESPONDENCE_METHOD = "callout_strip_whole_aperture_correspondence_shadow"
PRODUCER_INPUT_PROVENANCE = "producer_owned_source_visibility_authenticated_strokes"
PRODUCER_INPUT_PROVENANCE_BACKDROP_WITHHELD = (
    "producer_owned_source_visibility_authenticated_strokes_backdrop_fills_withheld_by_paint_order")
BACKDROP_FILL_EDGES_WITHHELD = "backdrop_fill_edges_withheld_by_paint_order"

# relations of an aperture record to a strip's whole frame extent
RELATION_EQUAL = "equal_extent"
RELATION_NESTED = "nested_inside_strip_extent"
RELATION_CONTAINING = "contains_strip_extent"
RELATION_OVERLAPPING = "partly_overlaps_strip_extent"

LINKAGE_OBSERVATION_IDENTITY = "aperture_record_names_strip_ink_by_observation_id"
LINKAGE_SPAN_EQUALITY_ONLY = "aperture_record_related_by_span_equality_only"

# the only new strings: reasons of this correspondence, never atom kinds
WHOLE_APERTURE_CORRESPONDED = "equal_extent_whole_aperture_unique"
NO_EQUAL_EXTENT_APERTURE = "no_equal_extent_whole_aperture_record"
DUPLICATE_EQUAL_EXTENT_APERTURES = "duplicate_equal_extent_whole_aperture_records"
EQUAL_EXTENT_STRUCTURE_NOT_PROVEN = "equal_extent_whole_aperture_structure_not_proven"
EQUAL_EXTENT_BAND_NOT_WITHIN_STRIP_BAND = "equal_extent_aperture_band_not_within_strip_band"
APERTURE_RECORD_IDS_NOT_UNIQUE = "aperture_authority_record_ids_not_unique"
NESTED_APERTURES_NOT_VETOED = "nested_aperture_candidates_not_vetoed"
CONTAINING_APERTURES_NOT_VETOED = "containing_aperture_candidates_not_vetoed"
OVERLAPPING_APERTURES_NOT_VETOED = "overlapping_aperture_candidates_not_vetoed"
APERTURE_LINKS_DIFFERENT_GLAZING = "aperture_record_links_different_glazing_strip"
STRIP_NOMINATION_INVALID = "strip_nomination_invalid"
STRIP_EXTENT_INCOMPLETE = "strip_extent_incomplete"
STRIP_CLAIMED_BY_MULTIPLE_CALLOUTS = "strip_claimed_by_multiple_callouts"
STRIP_INK_NOT_IN_STROKE_INVENTORY = "strip_ink_not_in_stroke_inventory"
UNADMITTED_INK_IN_STRIP_REGION = "unadmitted_source_ink_in_strip_region"
PAGE_STROKE_INVENTORY_INCOMPLETE = "page_stroke_inventory_incomplete"
APERTURE_RECORD_OWNERSHIP_MISMATCH = "aperture_record_ownership_mismatch"
APERTURE_RECORD_INVALID = "aperture_record_invalid_or_colliding"
APERTURE_BUDGET_EXCEEDED_CODE = "aperture_budget_exceeded"
WHOLE_APERTURE_CORRESPONDENCE_DISABLED = "whole_aperture_correspondence_disabled"
VISIBLE_SOURCE_AUTHORITY_REQUIRED = "visible_source_authority_required"
SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE = "snapshot_observation_integrity_failure"

# the aperture authority's own words that mean "not structurally established"
_UNPROVEN_REASONS = frozenset({
    AMBIGUOUS_MULTI_LAYER_OFFSET, AMBIGUOUS_STRUCTURAL_BOUNDARY, APERTURE_EXTENT_INCOMPLETE,
    FILL_MASK_BOUNDARY_UNPROVEN, TERMINAL_ROLE_UNPROVEN, WALL_CONTINUITY_MISSING,
})
_POSITIVE = (EvidenceResolutionStatus.CANDIDATE, EvidenceResolutionStatus.CORROBORATED)

# standing limits: always present, never a grant
STANDING_LIMITS = (
    "equal_extent_is_location_not_identity_of_a_physical_opening",
    "aperture_authority_does_not_link_records_to_glazing_strips",
    "aperture_authority_does_not_decide_whole_versus_nested_apertures",
    "aperture_authority_jamb_threshold_between_observed_stroke_widths_cannot_prove_a_jamb_alone",
    "opening_kind_host_wall_binding_and_quantity_not_established",
    "withholding_backdrop_fills_is_a_paint_order_inference_the_aperture_authority_did_not_make",
)

_MAX_STRIPS = 512
_MAX_RECORDS = 200_000
_MAX_UNADMITTED = 400_000
_EQ_FRACTION = 4.0          # the callout shadow's equality tolerance: a quarter of the coordinate quantum

_GRANT_FLAGS = (
    "physical_opening_granted", "host_granted", "opening_kind_granted", "frame_granted",
    "scale_granted", "metric_granted", "count_granted", "quantity_granted",
    "wall_binding_granted", "commercial_projection_allowed", "customer_publication_granted",
)

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
CONF = EvidenceResolutionStatus.CONFLICT


# --------------------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ApertureOwnership:
    document_id: str
    revision_id: str
    snapshot_id: str
    source_sha256: str
    page_id: str


@dataclass(frozen=True)
class CalloutClaim:
    """One callout that the nominator corresponded to the strip. Its identity is the nominator's, not this module's."""

    tag_mark: str
    tag_observation_id: str
    correspondence_record_id: str


@dataclass(frozen=True)
class StripNomination:
    strip_id: str
    axis: str
    band: tuple[float, float]
    frame_along: tuple[float, float]
    extent_complete: bool
    ink_ids: tuple[str, ...]
    plan_viewport_id: Optional[str]
    claims: tuple[CalloutClaim, ...]


@dataclass(frozen=True)
class InkItem:
    """A native segment of the page: where it is, where it falls in the content stream's paint order, whether stroked."""

    box: tuple[float, float, float, float]
    sequence: Optional[int]
    stroked: bool


@dataclass(frozen=True)
class StrokeInventory:
    """What the producer authenticated on the page and what it did not."""

    complete: bool
    admitted_observation_ids: frozenset
    admitted_ink: tuple[InkItem, ...]
    unadmitted_ink: tuple[InkItem, ...]
    counts: tuple[tuple[str, int], ...]
    reason_codes: tuple[str, ...] = ()


# --------------------------------------------------------------------------------------
# outputs
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ApertureRelation:
    record_key: str
    record_id: str
    relation: str
    authority_status: EvidenceResolutionStatus
    structural_role: str
    authority_reason_codes: tuple[str, ...]
    span_along: tuple[float, float]
    wall_band_across: tuple[float, float]
    shared_strip_ink_ids: tuple[str, ...]
    vetoed_by_subdivision_ids: tuple[str, ...]
    end_offsets: tuple[float, float]       # (record low - strip low, record high - strip high): a diagnostic, never a tolerance


@dataclass(frozen=True)
class StripApertureCorrespondence:
    strip_id: str
    claims: tuple[CalloutClaim, ...]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    equal_record_ids: tuple[str, ...]
    unvetoed_rival_record_ids: tuple[str, ...]
    vetoed_rival_record_ids: tuple[str, ...]
    relations: tuple[ApertureRelation, ...]
    linkage_basis: Optional[str]
    record_id: str

    def __post_init__(self) -> None:
        if self.status is CAND and (
            len(self.equal_record_ids) != 1 or self.unvetoed_rival_record_ids
            or self.linkage_basis is None or self.reason_codes != (WHOLE_APERTURE_CORRESPONDED,)
        ):
            raise ValueError("a CANDIDATE needs one equal-extent record, no unvetoed rival and a stated linkage")


@dataclass(frozen=True)
class WholeApertureCorrespondenceShadow:
    ownership: Optional[ApertureOwnership]
    correspondences: tuple[StripApertureCorrespondence, ...]
    page_reason_codes: tuple[str, ...]
    standing_limits: tuple[str, ...]
    aperture_record_count: int
    subdivision_record_count: int
    stroke_counts: tuple[tuple[str, int], ...]
    input_provenance: str
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
    schema_version: str = WHOLE_APERTURE_CORRESPONDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.shadow_only is not True:
            raise ValueError("shadow receipt cannot leave shadow mode")
        for name in _GRANT_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError(f"shadow receipt cannot grant {name}")
        if not set(_GRANT_FLAGS) <= {f.name for f in fields(self)}:
            raise ValueError("grant flag set is out of date")
        if self.standing_limits != STANDING_LIMITS:
            raise ValueError("standing limits are fixed")


# --------------------------------------------------------------------------------------
# bridge from the nominator's receipt (duck-typed so that this module imports no nominator)
# --------------------------------------------------------------------------------------
def nominations_from_callout_receipt(receipt) -> tuple[StripNomination, ...]:
    """One nomination per strip that at least one CANDIDATE callout correspondence names (all claims kept)."""
    strips = {s.strip_id: s for s in receipt.strips}
    if len(strips) != len(receipt.strips):
        raise ValueError("strip ids must be unique")
    claims: dict[str, list[CalloutClaim]] = {}
    for c in receipt.correspondences:
        if c.status is CAND and c.strip_id is not None:
            claims.setdefault(c.strip_id, []).append(CalloutClaim(c.tag_mark, c.tag_observation_id, c.record_id))
    out = []
    for strip_id in sorted(claims):
        s = strips[strip_id]
        out.append(StripNomination(
            strip_id=strip_id, axis=s.axis, band=tuple(s.band), frame_along=tuple(s.frame_along),
            extent_complete=s.extent_complete, ink_ids=tuple(s.ink_ids), plan_viewport_id=s.plan_viewport_id,
            claims=tuple(sorted(claims[strip_id], key=lambda k: (k.tag_observation_id, k.correspondence_record_id)))))
    return tuple(out)


# --------------------------------------------------------------------------------------
# pure core
# --------------------------------------------------------------------------------------
def _real(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and abs(value) < 1e12


def _pair(value) -> bool:
    return (type(value) in (tuple, list) and len(value) == 2 and all(_real(v) for v in value)
            and value[0] < value[1])


def _overlap(a, b) -> float:
    return min(a[1], b[1]) - max(a[0], b[0])


def _within(inner, outer, eq: float) -> bool:
    return inner[0] >= outer[0] - eq and inner[1] <= outer[1] + eq


def _ownership_matches(record, ownership: ApertureOwnership) -> bool:
    return (record.document_id == ownership.document_id and record.revision_id == ownership.revision_id
            and record.snapshot_id == ownership.snapshot_id and record.source_sha256 == ownership.source_sha256
            and str(record.page_id) == ownership.page_id)


def _valid_nomination(nom: StripNomination) -> bool:
    return (type(nom) is StripNomination and type(nom.strip_id) is str and nom.strip_id
            and nom.axis in ("H", "V") and _pair(nom.band) and _pair(nom.frame_along)
            and type(nom.extent_complete) is bool
            and type(nom.ink_ids) is tuple and all(type(i) is str and i for i in nom.ink_ids)
            and len(set(nom.ink_ids)) == len(nom.ink_ids) and nom.ink_ids
            and type(nom.claims) is tuple and nom.claims
            and all(type(c) is CalloutClaim for c in nom.claims))


def _record_valid(record) -> bool:
    return (type(record) is WholeOpeningApertureRecord and record.axis in ("H", "V")
            and _pair(record.aperture_span_along) and _pair(record.wall_band_across)
            and type(record.record_id) is str and bool(record.record_id)
            and type(record.reason_codes) is tuple and type(record.glazing_strip_ids) is tuple
            and type(record.terminal_jamb_lo_ids) is tuple and type(record.terminal_jamb_hi_ids) is tuple
            and type(record.host_face_ids) is tuple and type(record.discriminated_subdivision_ids) is tuple)


def _subdivision_valid(sub) -> bool:
    return (type(sub) is GlazingSubdivisionDiscriminationRecord and sub.axis in ("H", "V")
            and _pair(sub.subdivision_span_along) and type(sub.record_id) is str and bool(sub.record_id)
            and type(sub.is_internal_subdivision) is bool)


def _distinct(records: Sequence) -> tuple[tuple, int]:
    """Identical repeats collapse. The aperture authority derives a record id from document, page, span and axis
    alone, so two different records (another glass band, status or jamb set) can share one id: every such record is
    kept as its own reading and the number of ids that name more than one is counted."""
    unique = tuple(dict.fromkeys(records))
    by_id: dict[str, int] = {}
    for record in unique:
        by_id[record.record_id] = by_id.get(record.record_id, 0) + 1
    return unique, sum(1 for n in by_id.values() if n > 1)


def _record_key(record: WholeOpeningApertureRecord) -> str:
    return stable_contract_id("shadow_aperture_record_reading", {
        "id": record.record_id, "span": tuple(record.aperture_span_along), "band": tuple(record.wall_band_across),
        "status": record.status.value, "role": record.structural_role, "reasons": tuple(record.reason_codes),
        "lo": tuple(record.terminal_jamb_lo_ids), "hi": tuple(record.terminal_jamb_hi_ids),
        "host": tuple(record.host_face_ids), "glazing": tuple(record.glazing_strip_ids),
        "subdivisions": tuple(record.discriminated_subdivision_ids),
    }, digest_chars=20)


def _structurally_proven(record: WholeOpeningApertureRecord) -> bool:
    reasons = set(record.reason_codes)
    return (record.status in _POSITIVE and STRUCTURAL_TERMINAL_JAMB_PROVEN in reasons
            and HOST_WALL_CONTINUITY_PROVEN in reasons and not (reasons & _UNPROVEN_REASONS))


def _classify(record: WholeOpeningApertureRecord, nom: StripNomination, eq: float) -> Optional[str]:
    """None when the record cannot be a different reading of this strip's ink."""
    if record.axis != nom.axis:
        return None
    if _overlap(record.aperture_span_along, nom.frame_along) <= eq:
        return None
    if _overlap(record.wall_band_across, nom.band) <= eq:
        return None
    lo, hi = record.aperture_span_along
    flo, fhi = nom.frame_along
    if abs(lo - flo) <= eq and abs(hi - fhi) <= eq:
        return RELATION_EQUAL
    if lo >= flo - eq and hi <= fhi + eq:
        return RELATION_NESTED
    if lo <= flo + eq and hi >= fhi - eq:
        return RELATION_CONTAINING
    return RELATION_OVERLAPPING


def _vetoing_subdivisions(record, equal, subdivisions_by_id, ownership, eq: float) -> tuple[str, ...]:
    """Ids of the equal-extent record's own discriminated internal subdivisions that cut this nested record's ends.

    The authority discriminated those subdivisions (posts) as NOT wall openings inside the equal-extent record. A
    nested record whose two ends each lie on that record's outer edge or on an edge of one of those subdivisions
    is a run of the same frame, not an opening of its own. Anything else stays an unvetoed rival."""
    if equal is None:
        return ()
    cuts: list[tuple[float, Optional[str]]] = [
        (equal.aperture_span_along[0], None), (equal.aperture_span_along[1], None)]
    for sub_id in equal.discriminated_subdivision_ids:
        sub = subdivisions_by_id.get(sub_id)
        if (sub is None or not sub.is_internal_subdivision or sub.status not in _POSITIVE
                or sub.axis != record.axis or not _ownership_matches(sub, ownership)
                or not _within(sub.subdivision_span_along, equal.aperture_span_along, eq)):
            continue
        cuts.extend([(sub.subdivision_span_along[0], sub_id), (sub.subdivision_span_along[1], sub_id)])
    used: list[str] = []
    for end in record.aperture_span_along:
        hits = [sub_id for at, sub_id in cuts if abs(at - end) <= eq]
        if not hits:
            return ()
        used.extend(h for h in hits if h is not None)
    return tuple(sorted(set(used)))


def _in_region(item: InkItem, axis: str, along, across, eq: float) -> bool:
    x0, y0, x1, y1 = item.box
    box_along, box_across = ((x0, x1), (y0, y1)) if axis == "H" else ((y0, y1), (x0, x1))
    return _overlap(box_along, along) >= -eq and _overlap(box_across, across) >= -eq


def _region_has_unadmitted_ink(nom: StripNomination, wall_band, inventory: StrokeInventory, eq: float) -> bool:
    """True when source ink the producer could not admit lies in the strip's region and could have hidden or added to it.

    Only one kind of unadmitted ink is cleared, by the content stream's own paint order: an unstroked fill that is
    painted before every admitted STROKE of the region cannot cover any of them (an admitted fill, such as a page
    background, is not a stroke the aperture authority reads). A stroked item, an unstroked fill painted at or after
    an admitted stroke, one with no readable sequence, or a region with no admitted stroke all block."""
    across = (min(nom.band[0], wall_band[0]), max(nom.band[1], wall_band[1]))
    along = nom.frame_along
    pending = [i for i in inventory.unadmitted_ink if _in_region(i, nom.axis, along, across, eq)]
    if not pending:
        return False
    sequences = [i.sequence for i in inventory.admitted_ink if i.stroked and _in_region(i, nom.axis, along, across, eq)]
    if not sequences or any(type(q) is not int for q in sequences):
        return True
    earliest = min(sequences)
    return any(i.stroked or type(i.sequence) is not int or i.sequence >= earliest for i in pending)


def _correspondence_id(ownership, nom, status, reasons, equal_ids, unvetoed, vetoed, linkage) -> str:
    return stable_contract_id("shadow_strip_whole_aperture_correspondence", {
        "ownership": (ownership.document_id, ownership.revision_id, ownership.snapshot_id,
                      ownership.source_sha256, ownership.page_id),
        "strip": nom.strip_id, "claims": tuple((c.tag_observation_id, c.correspondence_record_id) for c in nom.claims),
        "status": status.value, "reasons": tuple(reasons), "equal": tuple(equal_ids),
        "unvetoed": tuple(unvetoed), "vetoed": tuple(vetoed), "linkage": linkage,
    }, digest_chars=24)


def _blocked_nomination(ownership, nom, code) -> StripApertureCorrespondence:
    strip_id = nom.strip_id if type(getattr(nom, "strip_id", None)) is str else "invalid"
    claims = nom.claims if type(getattr(nom, "claims", None)) is tuple else ()
    record_id = stable_contract_id("shadow_strip_whole_aperture_correspondence", {
        "ownership": (ownership.document_id, ownership.revision_id, ownership.snapshot_id,
                      ownership.source_sha256, ownership.page_id),
        "strip": strip_id, "reasons": (code,)}, digest_chars=24)
    return StripApertureCorrespondence(strip_id, claims, ABST, (code,), (), (), (), (), None, record_id)


def correspond_strip(
    nom: StripNomination, records: Sequence[WholeOpeningApertureRecord],
    subdivisions_by_id: dict, inventory: StrokeInventory,
    ownership: ApertureOwnership, eq: float,
) -> StripApertureCorrespondence:
    """The pure decision for one nominated strip. `records` and the subdivisions are already ownership-checked."""
    if not _valid_nomination(nom):
        return _blocked_nomination(ownership, nom, STRIP_NOMINATION_INVALID)
    blockers: list[tuple[EvidenceResolutionStatus, str]] = []
    if not nom.extent_complete:
        blockers.append((ABST, STRIP_EXTENT_INCOMPLETE))
    if len({(c.tag_observation_id) for c in nom.claims}) > 1:
        blockers.append((ABST, STRIP_CLAIMED_BY_MULTIPLE_CALLOUTS))
    if not inventory.complete:
        blockers.append((ABST, PAGE_STROKE_INVENTORY_INCOMPLETE))
    if not set(nom.ink_ids) <= inventory.admitted_observation_ids:
        blockers.append((ABST, STRIP_INK_NOT_IN_STROKE_INVENTORY))

    related = []
    for record in records:
        relation = _classify(record, nom, eq)
        if relation is not None:
            related.append((relation, record))
    equal = [r for rel, r in related if rel == RELATION_EQUAL]
    sole = equal[0] if len(equal) == 1 else None
    key_of = {id(r): _record_key(r) for _, r in related}

    if not equal:
        blockers.append((ABST, NO_EQUAL_EXTENT_APERTURE))
    elif len(equal) > 1:
        blockers.append((CONF, DUPLICATE_EQUAL_EXTENT_APERTURES))
    if sole is not None:
        if sole.status is CONF:
            blockers.append((CONF, EQUAL_EXTENT_STRUCTURE_NOT_PROVEN))
        elif not _structurally_proven(sole):
            blockers.append((ABST, EQUAL_EXTENT_STRUCTURE_NOT_PROVEN))
        if not _within(sole.wall_band_across, nom.band, eq):
            blockers.append((ABST, EQUAL_EXTENT_BAND_NOT_WITHIN_STRIP_BAND))
        linked = set(sole.glazing_strip_ids)
        if linked and not (linked & set(nom.ink_ids)):
            blockers.append((ABST, APERTURE_LINKS_DIFFERENT_GLAZING))
    wall_band = sole.wall_band_across if sole is not None else nom.band
    if _region_has_unadmitted_ink(nom, wall_band, inventory, eq):
        blockers.append((ABST, UNADMITTED_INK_IN_STRIP_REGION))

    relations: list[ApertureRelation] = []
    unvetoed: list[str] = []
    vetoed: list[str] = []
    positive_unvetoed = False
    not_vetoed_reason = {
        RELATION_NESTED: NESTED_APERTURES_NOT_VETOED, RELATION_CONTAINING: CONTAINING_APERTURES_NOT_VETOED,
        RELATION_OVERLAPPING: OVERLAPPING_APERTURES_NOT_VETOED,
    }
    for relation, record in sorted(related, key=lambda p: (p[1].aperture_span_along, key_of[id(p[1])])):
        vetoes: tuple[str, ...] = ()
        if relation == RELATION_NESTED:
            vetoes = _vetoing_subdivisions(record, sole, subdivisions_by_id, ownership, eq)
        if relation != RELATION_EQUAL:
            if vetoes:
                vetoed.append(key_of[id(record)])
            else:
                unvetoed.append(key_of[id(record)])
                positive_unvetoed = positive_unvetoed or record.status in _POSITIVE
                blockers.append((ABST, not_vetoed_reason[relation]))
        shared = tuple(sorted(
            set(nom.ink_ids) & (set(record.glazing_strip_ids) | set(record.terminal_jamb_lo_ids)
                                | set(record.terminal_jamb_hi_ids) | set(record.host_face_ids))))
        relations.append(ApertureRelation(
            key_of[id(record)], record.record_id, relation, record.status, record.structural_role, tuple(record.reason_codes),
            tuple(record.aperture_span_along), tuple(record.wall_band_across), shared, vetoes,
            (round(record.aperture_span_along[0] - nom.frame_along[0], 3),
             round(record.aperture_span_along[1] - nom.frame_along[1], 3))))
    if positive_unvetoed:
        blockers = [(CONF if reason in not_vetoed_reason.values() else status, reason) for status, reason in blockers]

    equal_ids = tuple(sorted(key_of[id(r)] for r in equal))
    if blockers:
        status = CONF if any(s is CONF for s, _ in blockers) else ABST
        reasons = tuple(sorted({reason for _, reason in blockers}))
        linkage = None
    else:
        status, reasons = CAND, (WHOLE_APERTURE_CORRESPONDED,)
        linkage = (LINKAGE_OBSERVATION_IDENTITY if sole.glazing_strip_ids else LINKAGE_SPAN_EQUALITY_ONLY)
    unvetoed_ids, vetoed_ids = tuple(sorted(set(unvetoed))), tuple(sorted(set(vetoed)))
    return StripApertureCorrespondence(
        nom.strip_id, nom.claims, status, reasons, equal_ids, unvetoed_ids, vetoed_ids, tuple(relations), linkage,
        _correspondence_id(ownership, nom, status, reasons, equal_ids, unvetoed_ids, vetoed_ids, linkage))


def evaluate_whole_aperture_correspondence(
    ownership: ApertureOwnership, nominations: Sequence[StripNomination],
    apertures: Sequence[WholeOpeningApertureRecord], subdivisions: Sequence[GlazingSubdivisionDiscriminationRecord],
    inventory: StrokeInventory, *, coordinate_quantum_pt: float, input_provenance: str = PRODUCER_INPUT_PROVENANCE,
    page_reason_codes: Sequence[str] = (),
) -> WholeApertureCorrespondenceShadow:
    """Pure: no source, no producer. Records of other pages are ignored; a record of this page that is not
    owned by this document, revision, snapshot and hash makes the whole result abstain."""
    if (not _real(coordinate_quantum_pt) or coordinate_quantum_pt <= 0 or type(ownership) is not ApertureOwnership
            or type(inventory) is not StrokeInventory or isinstance(nominations, (str, bytes))):
        raise ValueError("a positive finite coordinate quantum, ownership and inventory are required")
    eq = coordinate_quantum_pt / _EQ_FRACTION
    nominations = tuple(nominations)
    if len(set(getattr(n, "strip_id", id(n)) for n in nominations)) != len(nominations):
        raise ValueError("a strip is nominated once")
    page_reasons = list(page_reason_codes)

    def finish(correspondences, n_records, n_subs):
        return WholeApertureCorrespondenceShadow(
            ownership, tuple(correspondences), tuple(sorted(set(page_reasons))), STANDING_LIMITS, n_records, n_subs,
            inventory.counts, input_provenance)

    def abstain_all(code, n_records=0, n_subs=0):
        page_reasons.append(code)
        return finish([_blocked_nomination(ownership, n, code) for n in nominations], n_records, n_subs)

    if len(nominations) > _MAX_STRIPS:
        return abstain_all(APERTURE_BUDGET_EXCEEDED_CODE)
    if len(apertures) > _MAX_RECORDS or len(subdivisions) > _MAX_RECORDS:
        return abstain_all(APERTURE_BUDGET_EXCEEDED_CODE)
    page_records = [r for r in apertures if str(getattr(r, "page_id", None)) == ownership.page_id]
    page_subs = [s for s in subdivisions if str(getattr(s, "page_id", None)) == ownership.page_id]
    if any(not _ownership_matches(r, ownership) for r in page_records + page_subs
           if hasattr(r, "document_id")) or any(not hasattr(r, "document_id") for r in page_records + page_subs):
        return abstain_all(APERTURE_RECORD_OWNERSHIP_MISMATCH, len(page_records), len(page_subs))
    if not all(_record_valid(r) for r in page_records) or not all(_subdivision_valid(s) for s in page_subs):
        return abstain_all(APERTURE_RECORD_INVALID, len(page_records), len(page_subs))
    records, collisions = _distinct(page_records)
    subs, sub_collisions = _distinct(page_subs)
    if sub_collisions:
        return abstain_all(APERTURE_RECORD_INVALID, len(records), len(subs))   # a post that two ids name is not a cut
    if collisions:
        page_reasons.append(APERTURE_RECORD_IDS_NOT_UNIQUE)
    page_reasons.extend(inventory.reason_codes)
    subs_by_id = {s.record_id: s for s in subs}
    correspondences = [correspond_strip(n, records, subs_by_id, inventory, ownership, eq) for n in nominations]
    return finish(correspondences, len(records), len(subs))


# --------------------------------------------------------------------------------------
# producer-owned source adapter
# --------------------------------------------------------------------------------------
def _finite_box(values) -> Optional[tuple[float, float, float, float]]:
    if type(values) not in (tuple, list) or len(values) != 4 or any(type(v) not in (int, float) for v in values):
        return None
    try:
        box = tuple(float(v) for v in values)
    except OverflowError:
        return None
    return box if all(math.isfinite(v) and abs(v) < 1e12 for v in box) else None


@dataclass(frozen=True)
class FillPath:
    """One unstroked filled path whose every edge the producer admitted: its extent and its place in the paint order."""

    path_index: int
    sequence: Optional[int]
    box: tuple[float, float, float, float]


_GRID_CELL_PT = 64.0


def _touches(a, b, eq: float) -> bool:
    return (min(a[2], b[2]) - max(a[0], b[0]) >= -eq) and (min(a[3], b[3]) - max(a[1], b[1]) >= -eq)


def backdrop_fill_paths(fills: Sequence[FillPath], strokes: Sequence[InkItem], eq: float) -> frozenset:
    """Path indices of unstroked fills that no admitted stroke they could cover precedes in the paint order.

    A filled path covers only what it overlaps and only what was painted before it. A fill is a backdrop when at
    least one admitted stroke touches its extent and every admitted stroke that does is painted AFTER it
    (a stroke with an unreadable position counts as before). A fill with no readable position is never a backdrop.
    The result depends only on extents and positions: not on colour, size, page position or any drawing constant."""
    grid: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for i, item in enumerate(strokes):
        if not item.stroked:
            continue
        x0, y0, x1, y1 = item.box
        position = item.sequence if type(item.sequence) is int else -1
        for cx in range(int((x0 - eq) // _GRID_CELL_PT), int((x1 + eq) // _GRID_CELL_PT) + 1):
            for cy in range(int((y0 - eq) // _GRID_CELL_PT), int((y1 + eq) // _GRID_CELL_PT) + 1):
                grid.setdefault((cx, cy), []).append((position, i))
    for cell in grid.values():
        cell.sort()
    result = set()
    for fill in fills:
        if type(fill.sequence) is not int:
            continue
        x0, y0, x1, y1 = fill.box
        seen: set[int] = set()
        earlier = later = False
        for cx in range(int((x0 - eq) // _GRID_CELL_PT), int((x1 + eq) // _GRID_CELL_PT) + 1):
            for cy in range(int((y0 - eq) // _GRID_CELL_PT), int((y1 + eq) // _GRID_CELL_PT) + 1):
                for position, i in grid.get((cx, cy), ()):
                    if i in seen or not _touches(strokes[i].box, fill.box, eq):
                        continue
                    seen.add(i)
                    if position <= fill.sequence:
                        earlier = True
                        break
                    later = True
                    break                     # the rest of this position-sorted cell is later still
                if earlier:
                    break
            if earlier:
                break
        if later and not earlier:
            result.add(fill.path_index)
    return frozenset(result)


def _sequence(segment) -> Optional[int]:
    value = segment.get("sequence_number")
    return value if type(value) is int and not isinstance(value, bool) else None


class StripWholeApertureCorrespondenceShadow:
    """Opt-in census. `enabled` must be an explicit bool; the default is off and off touches nothing."""

    def __init__(self, source, *, enabled: bool = False, withhold_backdrop_fills: bool = False):
        if type(enabled) is not bool or type(withhold_backdrop_fills) is not bool:
            raise TypeError("enabled and withhold_backdrop_fills must be explicit bools")
        self._source = source
        self._enabled = enabled
        self._withhold = withhold_backdrop_fills

    @staticmethod
    def _backdrop_paths(segments, fill_edge_paths, admitted_segments, admitted_ink, eq: float) -> frozenset:
        by_path: dict[int, list] = {}
        for segment_id, segment in segments.items():
            path_index = segment.get("path_index")
            if type(path_index) is int:
                by_path.setdefault(path_index, []).append((str(segment_id), segment))
        fills = []
        for path_index in sorted({p for p in fill_edge_paths if p is not None}):
            edges = by_path.get(path_index, [])
            boxes = [_finite_box([segment.get(k) for k in ("x1", "y1", "x2", "y2")]) for _, segment in edges]
            positions = {_sequence(segment) for _, segment in edges}
            if (not edges or any(box is None for box in boxes) or len(positions) != 1
                    or any(segment_id not in admitted_segments for segment_id, _ in edges)
                    or any(segment.get("stroke_present") for _, segment in edges)):
                continue                  # a fill with an edge the producer did not admit has an unproven extent
            fills.append(FillPath(path_index, next(iter(positions)), (
                min(min(b[0], b[2]) for b in boxes), min(min(b[1], b[3]) for b in boxes),
                max(max(b[0], b[2]) for b in boxes), max(max(b[1], b[3]) for b in boxes))))
        return backdrop_fill_paths(fills, admitted_ink, eq)

    def _abstain(self, ownership, nominations, code) -> WholeApertureCorrespondenceShadow:
        empty = StrokeInventory(False, frozenset(), (), (), ())
        if ownership is None:
            return WholeApertureCorrespondenceShadow(
                None, (), (code,), STANDING_LIMITS, 0, 0, (), PRODUCER_INPUT_PROVENANCE)
        return WholeApertureCorrespondenceShadow(
            ownership, tuple(_blocked_nomination(ownership, n, code) for n in nominations), (code,),
            STANDING_LIMITS, 0, 0, empty.counts, PRODUCER_INPUT_PROVENANCE)

    def audit(self, *, revision_id: str, plan_page_id: int, nominations: Sequence[StripNomination],
              coordinate_quantum_pt: float) -> WholeApertureCorrespondenceShadow:
        if not self._enabled:
            return self._abstain(None, (), WHOLE_APERTURE_CORRESPONDENCE_DISABLED)
        if (type(revision_id) is not str or type(plan_page_id) is not int or isinstance(plan_page_id, bool)
                or isinstance(nominations, (str, bytes))):
            raise ValueError("revision id, integer page id and StripNomination records required")
        nominations = tuple(nominations)
        if not _real(coordinate_quantum_pt) or coordinate_quantum_pt <= 0:
            raise ValueError("a positive finite coordinate quantum is required")

        import fitz

        from pb_source_observation_authority import ObservationSelector
        from pb_source_visibility_authority import VISIBLE_SOURCE_OBSERVATION_EXISTS
        from pb_vector_geometry_v130 import extract_native_page

        source = self._source
        published = source.published_snapshot_for_revision(revision_id)
        if published is None:
            return self._abstain(None, nominations, VISIBLE_SOURCE_AUTHORITY_REQUIRED)
        document_id = published.revision.document_id
        ownership = ApertureOwnership(
            document_id, revision_id, published.snapshot.snapshot_id, published.revision.source_sha256,
            str(plan_page_id))
        if (plan_page_id not in tuple(int(v) for v in published.coverage.decoded_pages)
                or plan_page_id in tuple(int(v) for v in published.coverage.failed_pages)
                or source._producer.current_revision_id(document_id) != revision_id):
            return self._abstain(ownership, nominations, VISIBLE_SOURCE_AUTHORITY_REQUIRED)
        source_bytes = source._producer._store.source_bytes_by_revision.get(revision_id)
        if source_bytes is None or hashlib.sha256(source_bytes).hexdigest() != ownership.source_sha256:
            return self._abstain(ownership, nominations, SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE)

        with fitz.open(stream=bytes(source_bytes), filetype="pdf") as document:
            page = document[plan_page_id - 1]
            drawings = page.get_drawings()
            segments = {s["id"]: s for s in extract_native_page(page)["segments"]}

        visibility = source.authority()
        strokes: list[ApertureSourceStroke] = []
        admitted_ink: list[InkItem] = []
        fill_edge_paths: list[Optional[int]] = []       # aligned with `strokes`: the path of an unstroked fill edge
        admitted_segments: set[str] = set()
        counts: dict[str, int] = {}
        reasons: list[str] = []
        complete = True
        seed = None
        seen: set[str] = set()

        def count(name: str) -> None:
            counts[name] = counts.get(name, 0) + 1

        for observation_id in published.visible_observation_ids:
            if type(observation_id) is not str or not observation_id or observation_id in seen:
                complete = False
                count("duplicate_or_malformed_observation_id")
                continue
            seen.add(observation_id)
            result = visibility.resolve_visible(ObservationSelector(
                document_id, revision_id, ownership.source_sha256, ownership.snapshot_id, observation_id))
            observation = result.observation
            if (result.status is not EvidenceResolutionStatus.CORROBORATED
                    or result.proposition != VISIBLE_SOURCE_OBSERVATION_EXISTS or observation is None
                    or observation.observation_id != observation_id or observation.document_id != document_id
                    or observation.revision_id != revision_id or observation.source_sha256 != ownership.source_sha256
                    or observation.snapshot_id != ownership.snapshot_id):
                complete = False
                count("visible_observation_unresolved")
                continue
            if str(observation.page_id) != ownership.page_id:
                continue
            geometry = _finite_box(observation.geometry)
            primitive = segments.get(str(observation.source_primitive_ref).removeprefix("visible:segment:"))
            if geometry is None or primitive is None or _finite_box(
                    [primitive.get(k) for k in ("x1", "y1", "x2", "y2")]) != geometry:
                complete = False
                count("primitive_join_failed")
                continue
            path_index = primitive.get("path_index")
            if type(path_index) is not int or not 0 <= path_index < len(drawings) or (
                    drawings[path_index].get("seqno") != primitive.get("sequence_number")):
                complete = False
                count("drawing_join_failed")
                continue
            drawing = drawings[path_index]
            stroked = bool(primitive.get("stroke_present") and primitive.get("width_present"))
            width = primitive.get("width")
            opacity = drawing.get("stroke_opacity")
            rgb = primitive.get("stroke")
            if stroked and not (type(width) in (int, float) and math.isfinite(width) and width > 0):
                complete = False
                count("stroke_width_unresolved")
                continue
            if stroked and rgb is not None and not (
                    type(rgb) in (tuple, list) and all(type(v) in (int, float) and math.isfinite(v) for v in rgb)):
                complete = False
                count("stroke_colour_unresolved")
                continue
            if seed is None:
                seed = observation
            admitted_segments.add(str(primitive["id"]))
            admitted_ink.append(InkItem(
                (min(geometry[0], geometry[2]), min(geometry[1], geometry[3]),
                 max(geometry[0], geometry[2]), max(geometry[1], geometry[3])), _sequence(primitive), stroked))
            count("stroked" if stroked else "fill_only")
            strokes.append(ApertureSourceStroke(
                observation_id=observation_id, geometry=geometry,
                stroke_width=float(width) if stroked else 0.0,
                stroke_rgb=tuple(float(v) for v in rgb) if stroked and rgb else None,
                stroke_opacity=float(opacity) if stroked and type(opacity) in (int, float) and math.isfinite(opacity)
                else 0.0,
                dashes=str(primitive.get("dashes", "")) if stroked else "[] 0",
                is_fill_mask=not stroked, is_clipped=False))
            fill_edge_paths.append(None if stroked else path_index)

        unadmitted: list[InkItem] = []
        for segment_id, segment in segments.items():
            if str(segment_id) in admitted_segments:
                continue
            box = _finite_box([segment.get(k) for k in ("x1", "y1", "x2", "y2")])
            if box is None:
                complete = False
                count("native_segment_geometry_unreadable")
                continue
            count("native_segment_not_admitted")
            unadmitted.append(InkItem(
                (min(box[0], box[2]), min(box[1], box[3]), max(box[0], box[2]), max(box[1], box[3])),
                _sequence(segment), bool(segment.get("stroke_present"))))
        if len(unadmitted) > _MAX_UNADMITTED:
            complete = False
            reasons.append(APERTURE_BUDGET_EXCEEDED_CODE)
            unadmitted = []

        if seed is None or not strokes:
            return self._abstain(ownership, nominations, VISIBLE_SOURCE_AUTHORITY_REQUIRED)
        page_reasons: list[str] = []
        if self._withhold:
            backdrop = self._backdrop_paths(segments, fill_edge_paths, admitted_segments, admitted_ink,
                                            coordinate_quantum_pt / _EQ_FRACTION)
            kept = [stroke for stroke, path in zip(strokes, fill_edge_paths) if path is None or path not in backdrop]
            if len(kept) != len(strokes):
                counts["backdrop_fill_edge_withheld"] = len(strokes) - len(kept)
                page_reasons.append(BACKDROP_FILL_EDGES_WITHHELD)
            strokes = kept
        inventory = StrokeInventory(
            complete, frozenset(s.observation_id for s in strokes), tuple(admitted_ink), tuple(unadmitted),
            tuple(sorted(counts.items())), tuple(reasons))
        producer = StructuralWholeOpeningApertureProducer.create()
        discovered = producer.analyze_page(seed, strokes)         # every reading, not the id-keyed dictionary
        authority = producer.authority()
        return evaluate_whole_aperture_correspondence(
            ownership, nominations, discovered, authority.all_discriminated_subdivisions(), inventory,
            coordinate_quantum_pt=coordinate_quantum_pt, page_reason_codes=page_reasons,
            input_provenance=PRODUCER_INPUT_PROVENANCE_BACKDROP_WITHHELD if self._withhold else PRODUCER_INPUT_PROVENANCE)
