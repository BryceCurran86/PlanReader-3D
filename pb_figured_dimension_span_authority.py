"""pb_figured_dimension_span_authority.py — Exact Figured-Dimension Span Authority.

SHADOW-ONLY. Nothing in this module is imported by any production/quantity
publishing path. It exists to answer one question the existing figured-
dimension pipeline cannot yet answer: *given a target physical entity and a
specific kind of physical quantity (a wall run, a room clear span, a wall
thickness, an opening width...), which single figured dimension, if any, is
genuinely and exclusively authoritative for it?*

Repository audit (see PR description for the full table) found the pipeline
already owns every lower layer this module needs, so none of it is
reinvented here:

  - ``pb_dimension_graph_constraint_engine.DimensionObservation`` / the F.13
    engine already carry raw figured-dimension text, value, orientation and
    conflict/authority vocabulary.
  - ``pb_figured_dimension_evidence`` already extracts native text, vector
    dimension/witness lines, and binds one to the other
    (``DimensionAnchorBinding`` / ``BindingStatus``), producing endpoints and
    same-axis chains from real page geometry.
  - ``pb_viewport_dimension_binding`` already scopes that extraction to one
    owned viewport so a sibling view's linework can never leak in.
  - ``pb_figured_dimension_authority.resolve_measurement_authority`` already
    encodes figured-beats-scaled precedence and numeric-delta review.
  - ``pb_measurement_input_authority.resolve_linear_measurement_input``
    already binds ONE evidence atom to exact document/revision/page/viewport/
    entity ownership and returns FIRM only when every ownership and scale
    check passes.

What none of those layers do, and what this module adds:

  1. A typed **semantic span kind** (``SemanticSpanKind``) so a wall run, a
     room clear dimension, a wall thickness, an opening width, a grid
     spacing and an overall building dimension are never treated as
     interchangeable just because they share a value or a target.
  2. A typed **endpoint reference** (``EndpointReference``) so "where a
     dimension terminates" is identified by (kind, target entity,
     sub-reference) — never by raw floating-point coordinate alone. Two
     dimensions that happen to land on the same pixel are only the same
     endpoint if they reference the same semantic thing.
  3. A **complete-universe resolver** (``resolve_figured_dimension_span_
     authority``) that consumes every eligible competing
     ``DimensionSpanCandidate`` for one target+kind at once, rather than the
     single caller-selected atom ``resolve_linear_measurement_input`` takes.
     A caller cannot make a competing, conflicting, or semantically
     different dimension disappear by simply not passing it in — passing an
     incomplete universe is itself a modelled failure mode (see
     ``DiscoveryCompletenness`` below) which callers are expected NOT to
     trigger by pre-filtering with a bounding box.

Explicit non-goals of this PR (fail-closed, not fail-silent, scope limits):

  - This module does not parse PDF bytes, vector paths, or OCR images. It
    operates on already-classified ``DimensionSpanCandidate`` records, the
    same scope-limiting posture ``pb_dimension_graph_constraint_engine``
    already documents for ``DimensionObservation``. Classifying a raw
    ``DimensionAnchorBinding`` into a semantic span kind and a target
    physical entity (e.g. "this witness-bound dimension's endpoints are
    this wall's two end nodes") requires the canonical wall/room topology
    that PR #286 introduced and Cursor's wall-length authority bridge owns
    integrating; wiring that classifier is explicitly future work, not this
    PR.
  - This module never calls ``resolve_linear_measurement_input`` with more
    than the single evidence atom the completeness proof below identifies
    as the sole surviving, non-conflicting, correctly-scoped candidate. It
    delegates the actual FIRM/BLOCKED decision for that one atom entirely to
    the existing authority chain rather than re-implementing precedence,
    ownership, or scale-freshness logic.
  - Nothing here is wired into any quantity provider, publisher, or
    commercial gate. See ``tests/test_figured_dimension_span_authority_
    adversarial.py`` for a regression guard asserting that.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Dict, Mapping, Optional, Sequence, Tuple

from pb_geometry_takeoff_model import AuthorityStatus
from pb_measurement_input_authority import (
    MeasurementInputResolution,
    resolve_linear_measurement_input,
)
from pb_migration_contracts import (
    DocumentEvidence,
    EntityEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    ViewportEvidence,
    canonical_contract_json,
)
from pb_migration_provider_envelope import ProviderContext

SPAN_AUTHORITY_SCHEMA_VERSION = "1.0.0"

# A physical span's numeric value must agree with another candidate for the
# *same* endpoint pair within this fraction before they are treated as one
# corroborating measurement rather than a numeric conflict. Reuses the same
# order of magnitude as pb_measurement_input_authority's own default
# max_delta_ratio (0.05) — not a new, independently-tuned tolerance.
_DEFAULT_VALUE_AGREEMENT_RATIO = 0.05


class SemanticSpanKind(str, Enum):
    """A physical quantity a figured dimension can represent. Two spans of
    the same numeric value but different kinds are never interchangeable —
    a door width is not a wall run merely because both read "900"."""

    WALL_RUN = "wall_run"
    ROOM_CLEAR_SPAN = "room_clear_span"
    WALL_THICKNESS = "wall_thickness"
    OPENING_WIDTH = "opening_width"
    OPENING_HEIGHT = "opening_height"
    GRID_SPACING = "grid_spacing"
    OVERALL_BUILDING_DIMENSION = "overall_building_dimension"
    SETOUT_DIMENSION = "setout_dimension"


class EndpointReferenceKind(str, Enum):
    """What kind of physical thing a dimension endpoint terminates on."""

    CENTERLINE = "centerline"
    FACE = "face"
    CORNER = "corner"
    JAMB = "jamb"
    GRID = "grid"
    DATUM = "datum"
    EXPLICIT_NODE = "explicit_node"


@dataclass(frozen=True)
class EndpointReference:
    """Identity of one dimension endpoint.

    Identity is ``(kind, target_id, subreference)`` ONLY. ``coordinate`` is
    carried for traceability/diagnostics but is explicitly NOT part of
    equality or the hash — two endpoints at the same pixel that reference
    different physical things (e.g. one wall's face vs. an unrelated grid
    line that happens to cross the same point) must never compare equal,
    and reusing raw floating-point location as identity was the exact
    mistake this module is written to avoid (see module docstring point 2
    and ``pb_wall_room_topology_wall_identity_v2`` for the same lesson
    already learned once for wall identity).
    """

    kind: EndpointReferenceKind
    target_id: str
    subreference: Optional[str] = None
    coordinate: Optional[Tuple[float, float]] = None

    def __post_init__(self) -> None:
        if not str(self.target_id or "").strip():
            raise ValueError("EndpointReference.target_id must be non-empty")

    @property
    def identity_key(self) -> Tuple[str, str, Optional[str]]:
        return (self.kind.value, self.target_id, self.subreference)

    def to_dict(self) -> Dict[str, object]:
        return {
            "kind": self.kind.value,
            "target_id": self.target_id,
            "subreference": self.subreference,
        }


def _unordered_endpoint_pair_key(
    a: EndpointReference, b: EndpointReference
) -> Tuple[Tuple[str, str, Optional[str]], Tuple[str, str, Optional[str]]]:
    """Order-independent identity for an endpoint pair (a span read A->B is
    the same span as B->A — reversed dimension-line orientation must not
    create a second, spurious semantic-competition group)."""
    ka, kb = a.identity_key, b.identity_key
    return (ka, kb) if ka <= kb else (kb, ka)


@dataclass(frozen=True)
class DimensionSpanCandidate:
    """One fully-typed, ownership-bound figured-dimension span candidate.

    This is the unit ``resolve_figured_dimension_span_authority`` consumes.
    Producing one from raw PDF evidence (native text + vector witness/
    terminator geometry + endpoint-to-entity classification) is explicitly
    out of scope for this PR — see module docstring.
    """

    candidate_id: str
    document_id: str
    page_id: str
    viewport_id: str
    revision_id: Optional[str]

    dimension_system_id: str
    """Identity of the whole dimension system (text + dimension line +
    witness/extension lines) this candidate came from. Two candidates that
    disagree in every other field but share a ``dimension_system_id`` are
    the same physical drawing object read twice, not two independent
    corroborating measurements."""

    text_evidence_id: str
    dimension_line_id: Optional[str]
    witness_line_ids: Tuple[str, ...]

    endpoint_a: Optional[EndpointReference]
    endpoint_b: Optional[EndpointReference]

    target_entity_id: str
    semantic_span_kind: SemanticSpanKind

    value_m: float
    evidence_status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE

    source_segment_ids: Tuple[str, ...] = ()
    """Raw geometry ids this candidate's witness/terminator chain rests on.
    Used only to detect the same physical dimension graphics represented
    twice under two different candidate_ids (adversarial test #9)."""

    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.candidate_id or "").strip():
            raise ValueError("candidate_id must be non-empty")
        if not str(self.dimension_system_id or "").strip():
            raise ValueError("dimension_system_id must be non-empty")
        if not str(self.target_entity_id or "").strip():
            raise ValueError("target_entity_id must be non-empty")
        if not math.isfinite(self.value_m) or self.value_m <= 0.0:
            raise ValueError(f"value_m must be finite and positive, got {self.value_m!r}")
        object.__setattr__(self, "witness_line_ids", tuple(self.witness_line_ids))
        object.__setattr__(self, "source_segment_ids", tuple(self.source_segment_ids))

    @property
    def has_both_endpoints_resolved(self) -> bool:
        return self.endpoint_a is not None and self.endpoint_b is not None

    @property
    def is_witness_bound(self) -> bool:
        """A complete text -> dimension-line -> witness -> endpoint chain.
        Anything less (line-bound, partial-witness, ambiguous, unsupported
        in ``pb_figured_dimension_evidence.BindingStatus`` terms) is
        evidence, but not a complete enough chain to anchor a physical
        endpoint identity."""
        return (
            self.has_both_endpoints_resolved
            and self.dimension_line_id is not None
            and len(self.witness_line_ids) >= 2
        )

    def endpoint_pair_key(self):
        if not self.has_both_endpoints_resolved:
            return None
        return _unordered_endpoint_pair_key(self.endpoint_a, self.endpoint_b)

    def fingerprint(self) -> str:
        import hashlib

        payload = {
            "candidate_id": self.candidate_id,
            "document_id": self.document_id,
            "page_id": self.page_id,
            "viewport_id": self.viewport_id,
            "revision_id": self.revision_id,
            "dimension_system_id": self.dimension_system_id,
            "target_entity_id": self.target_entity_id,
            "semantic_span_kind": self.semantic_span_kind.value,
            "endpoint_a": self.endpoint_a.to_dict() if self.endpoint_a else None,
            "endpoint_b": self.endpoint_b.to_dict() if self.endpoint_b else None,
            "value_m": self.value_m,
        }
        return hashlib.sha256(canonical_contract_json(payload).encode("utf-8")).hexdigest()


class SpanClassification(str, Enum):
    DUPLICATE_CORROBORATING = "duplicate_corroborating"
    NUMERIC_CONFLICT = "numeric_conflict"
    SEMANTIC_COMPETITION = "semantic_competition"
    DISTINCT_SPAN = "distinct_span"
    NON_APPLICABLE = "non_applicable"


def classify_candidate_pair(
    a: DimensionSpanCandidate,
    b: DimensionSpanCandidate,
    *,
    value_agreement_ratio: float = _DEFAULT_VALUE_AGREEMENT_RATIO,
) -> SpanClassification:
    """Classify the relationship between two candidates per the authority
    contract's conflict-completeness taxonomy. Never resolves anything —
    purely descriptive, used by the resolver below to build its
    discovery-completeness proof."""
    if a.target_entity_id != b.target_entity_id:
        return SpanClassification.DISTINCT_SPAN
    if a.semantic_span_kind != b.semantic_span_kind:
        # Same target, different physical quantity (e.g. this wall's run
        # vs. this wall's thickness) — a valid dimension, wrong consumer.
        return SpanClassification.NON_APPLICABLE
    pair_a, pair_b = a.endpoint_pair_key(), b.endpoint_pair_key()
    if pair_a is None or pair_b is None:
        return SpanClassification.NON_APPLICABLE
    if pair_a != pair_b:
        # Same physical span, different semantic interpretation (e.g.
        # centerline-to-centerline vs. face-to-face for the same wall run).
        return SpanClassification.SEMANTIC_COMPETITION
    ratio = abs(a.value_m - b.value_m) / max(a.value_m, b.value_m)
    if ratio <= value_agreement_ratio:
        return SpanClassification.DUPLICATE_CORROBORATING
    return SpanClassification.NUMERIC_CONFLICT


@dataclass(frozen=True)
class DiscoveryCompleteness:
    """Answers the mandate's four completeness questions for one resolution."""

    dimension_systems_enumerated: Tuple[str, ...]
    dimension_systems_applicable: Tuple[str, ...]
    dimension_systems_rejected: Tuple[Tuple[str, str], ...]  # (dimension_system_id, reason)
    dimension_systems_unresolved_potentially_applicable: Tuple[str, ...]

    @property
    def is_exhaustive_and_clean(self) -> bool:
        return not self.dimension_systems_unresolved_potentially_applicable


@dataclass(frozen=True)
class DimensionSpanAuthorityResult:
    """QuantityEvidence-shaped result for one target+kind span resolution."""

    target_entity_id: str
    semantic_span_kind: SemanticSpanKind
    status: str  # AuthorityStatus value, plus "semantic_competition"/"numeric_conflict" reason codes below
    value_m: Optional[float]
    contributing_candidate_ids: Tuple[str, ...]
    measurement_input: Optional[MeasurementInputResolution]
    completeness: DiscoveryCompleteness
    blocking_reasons: Tuple[str, ...] = ()
    notes: str = ""
    schema_version: str = SPAN_AUTHORITY_SCHEMA_VERSION

    @property
    def abstained(self) -> bool:
        return self.value_m is None


def _abstain(
    *,
    target_entity_id: str,
    semantic_span_kind: SemanticSpanKind,
    completeness: DiscoveryCompleteness,
    reasons: Tuple[str, ...],
    contributing_candidate_ids: Tuple[str, ...] = (),
    notes: str = "",
) -> DimensionSpanAuthorityResult:
    return DimensionSpanAuthorityResult(
        target_entity_id=target_entity_id,
        semantic_span_kind=semantic_span_kind,
        status=AuthorityStatus.BLOCKED.value,
        value_m=None,
        contributing_candidate_ids=contributing_candidate_ids,
        measurement_input=None,
        completeness=completeness,
        blocking_reasons=reasons,
        notes=notes,
    )


def resolve_figured_dimension_span_authority(
    *,
    target_entity_id: str,
    semantic_span_kind: SemanticSpanKind,
    candidates: Sequence[DimensionSpanCandidate],
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    entity: EntityEvidence,
    page_no: int,
    evidence_atoms_by_id: Mapping[str, EvidenceAtom],
    value_agreement_ratio: float = _DEFAULT_VALUE_AGREEMENT_RATIO,
) -> DimensionSpanAuthorityResult:
    """Resolve the single authoritative figured dimension for one physical
    quantity from the COMPLETE eligible candidate universe.

    ``candidates`` must be the full set of dimension-span candidates
    discovered for this document/page — not a caller-pre-filtered subset.
    Pre-filtering by a bounding box around the expected span is exactly the
    "one span bounding box" failure mode the authority contract forbids;
    this function does the filtering itself, transparently, and records
    what it rejected and why in the returned ``completeness`` report so a
    caller can never silently hide a competing dimension.
    """
    all_ids = tuple(sorted({c.dimension_system_id for c in candidates}))

    rejected: list[Tuple[str, str]] = []
    unresolved_potentially_applicable: list[str] = []
    applicable: list[DimensionSpanCandidate] = []

    current_revision = context.current_revision_id

    for candidate in candidates:
        same_target_and_kind = (
            candidate.target_entity_id == target_entity_id
            and candidate.semantic_span_kind == semantic_span_kind
        )
        same_target_only = candidate.target_entity_id == target_entity_id

        if candidate.document_id != document.document_id:
            if same_target_and_kind:
                rejected.append((candidate.dimension_system_id, "document_mismatch"))
            continue
        if candidate.page_id != viewport.page_id:
            if same_target_and_kind:
                rejected.append((candidate.dimension_system_id, "page_mismatch"))
            continue
        if candidate.viewport_id != viewport.viewport_id:
            if same_target_and_kind:
                rejected.append((candidate.dimension_system_id, "sibling_viewport_evidence"))
            continue
        if candidate.revision_id != current_revision:
            if same_target_and_kind:
                rejected.append((candidate.dimension_system_id, "stale_revision"))
            continue

        if not same_target_only:
            # A different physical entity entirely. Coordinates or value
            # matching this query's target is not relevant — never a
            # conflict, never tracked as unresolved-potentially-applicable.
            continue

        if candidate.semantic_span_kind != semantic_span_kind:
            # Right entity, wrong physical quantity (valid dimension, wrong
            # consumer) — explicitly not a blocker for THIS resolution.
            rejected.append((candidate.dimension_system_id, "non_applicable_semantic_kind"))
            continue

        if candidate.evidence_status == EvidenceResolutionStatus.CONFLICT:
            unresolved_potentially_applicable.append(candidate.dimension_system_id)
            continue

        if not candidate.has_both_endpoints_resolved:
            unresolved_potentially_applicable.append(candidate.dimension_system_id)
            continue

        if not candidate.is_witness_bound:
            unresolved_potentially_applicable.append(candidate.dimension_system_id)
            continue

        applicable.append(candidate)

    completeness = DiscoveryCompleteness(
        dimension_systems_enumerated=all_ids,
        dimension_systems_applicable=tuple(sorted({c.dimension_system_id for c in applicable})),
        dimension_systems_rejected=tuple(rejected),
        dimension_systems_unresolved_potentially_applicable=tuple(
            sorted(set(unresolved_potentially_applicable))
        ),
    )

    if not applicable:
        return _abstain(
            target_entity_id=target_entity_id,
            semantic_span_kind=semantic_span_kind,
            completeness=completeness,
            reasons=("no_applicable_dimension_evidence",),
        )

    if completeness.dimension_systems_unresolved_potentially_applicable:
        # An unresolved-but-potentially-applicable system exists: NO FIRM,
        # even if the applicable set alone already agrees.
        return _abstain(
            target_entity_id=target_entity_id,
            semantic_span_kind=semantic_span_kind,
            completeness=completeness,
            reasons=("unresolved_potentially_applicable_dimension_system",),
            contributing_candidate_ids=tuple(sorted(c.candidate_id for c in applicable)),
        )

    # Deduplicate identical dimension-system representations (same physical
    # drawing graphics counted twice under two candidate_ids) before
    # grouping, so a duplicate cannot silently masquerade as independent
    # corroboration nor as a competing group.
    seen_systems: Dict[str, DimensionSpanCandidate] = {}
    for candidate in sorted(applicable, key=lambda c: c.candidate_id):
        seen_systems.setdefault(candidate.dimension_system_id, candidate)
    deduped = list(seen_systems.values())

    groups: Dict[object, list[DimensionSpanCandidate]] = {}
    for candidate in deduped:
        groups.setdefault(candidate.endpoint_pair_key(), []).append(candidate)

    if len(groups) > 1:
        return _abstain(
            target_entity_id=target_entity_id,
            semantic_span_kind=semantic_span_kind,
            completeness=completeness,
            reasons=("semantic_competition_unresolved",),
            contributing_candidate_ids=tuple(sorted(c.candidate_id for c in deduped)),
            notes=(
                f"{len(groups)} distinct endpoint-reference bases compete for the same "
                f"target/kind ({target_entity_id}/{semantic_span_kind.value})"
            ),
        )

    (_, group), = groups.items()
    values = [c.value_m for c in group]
    spread_ratio = (max(values) - min(values)) / max(values)
    if spread_ratio > value_agreement_ratio:
        return _abstain(
            target_entity_id=target_entity_id,
            semantic_span_kind=semantic_span_kind,
            completeness=completeness,
            reasons=("numeric_conflict_within_same_span",),
            contributing_candidate_ids=tuple(sorted(c.candidate_id for c in group)),
            notes=f"values disagree: {sorted(round(v, 4) for v in values)}",
        )

    # Exactly one surviving semantic basis, internally agreeing: hand the
    # single canonical evidence atom to the EXISTING authority chain for the
    # real FIRM/BLOCKED decision (ownership, ambiguity, ...). Candidates are
    # sorted by candidate_id so the choice of "canonical" representative is
    # deterministic and independent of input order.
    canonical = sorted(group, key=lambda c: c.candidate_id)[0]
    figured_atom = evidence_atoms_by_id.get(canonical.text_evidence_id)
    if figured_atom is None:
        return _abstain(
            target_entity_id=target_entity_id,
            semantic_span_kind=semantic_span_kind,
            completeness=completeness,
            reasons=("figured_evidence_atom_not_found",),
            contributing_candidate_ids=(canonical.candidate_id,),
        )

    measurement_input = resolve_linear_measurement_input(
        context=context,
        document=document,
        viewport=viewport,
        entity=entity,
        page_no=page_no,
        figured_evidence=figured_atom,
    )

    if measurement_input.abstained:
        return DimensionSpanAuthorityResult(
            target_entity_id=target_entity_id,
            semantic_span_kind=semantic_span_kind,
            status=AuthorityStatus.BLOCKED.value,
            value_m=None,
            contributing_candidate_ids=(canonical.candidate_id,),
            measurement_input=measurement_input,
            completeness=completeness,
            blocking_reasons=measurement_input.blocking_reasons,
            notes=measurement_input.notes,
        )

    return DimensionSpanAuthorityResult(
        target_entity_id=target_entity_id,
        semantic_span_kind=semantic_span_kind,
        status=AuthorityStatus.FIRM.value,
        value_m=measurement_input.value_m,
        contributing_candidate_ids=(canonical.candidate_id,),
        measurement_input=measurement_input,
        completeness=completeness,
        notes=measurement_input.notes,
    )
