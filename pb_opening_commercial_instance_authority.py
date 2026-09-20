"""pb_opening_commercial_instance_authority.py -- Item 35 / Phase C.

Producer-owned COMMERCIAL COUNT RECONCILIATION AUTHORITY. This is not "turn a
tag-bound candidate into a commercial instance": a CORROBORATED,
PROVEN_SAME OpeningTagBindingResult proves only a tag relationship, never
physical existence. The full required chain is:

    complete physical opening universe
    -> independently proven physical existence (G17 PhysicalOpeningAuthority)
    -> physical identity (G17 PhysicalOpeningAuthority.compare_identity)
    -> authenticated tag binding (replayed, never trusted from a caller)
    -> unique explicit schedule-row count (OpeningScheduleCountAuthority)
    -> count reconciliation
    -> commercial quantity

Two hard gates, checked before any count comparison is even attempted:

1. PHYSICAL EXISTENCE. PhysicalOpeningCandidateRecord is deliberately
   CANDIDATE-only. This module never treats one as a physical commercial
   instance on its own -- every instance must independently re-prove
   PHYSICAL_OPENING_EXISTS via PhysicalOpeningAuthority.prove_existence()
   against its own G17 seed ObservationSelector. Schedule/OCR evidence can
   never manufacture physical existence. This means Phase C will NOT
   automatically unlock raster-only pages (e.g. Murera) -- that requires a
   separate, lawful raster physical-existence producer feeding
   PhysicalOpeningAuthority, which is out of scope here. Weakening
   PhysicalOpeningAuthority itself to pass a raster case is never acceptable.

2. UNIVERSE COMPLETENESS. Require OpeningUniverseCompletenessAuthority to
   resolve CORROBORATED (decision_scope_complete=True) for the exact
   decision scope. If the universe is incomplete, unknown, abstained, or
   conflicted, no commercial count publishes -- not even when
   physical_count == schedule_count by coincidence. Coincidental equality is
   not proof.

TAG-BINDING TRUST BOUNDARY. OpeningTagBindingResult carries no seal (unlike
TagObservation/TagBindingEvidence) -- a caller could otherwise construct a
fake CORROBORATED/PROVEN_SAME result and mint a count from it. This module
never accepts a pre-computed OpeningTagBindingResult as evidence: it always
replays OpeningIdentityResolver.resolve_tag_binding() itself from raw
candidate/TagObservation/TagBindingEvidence/SourceObservationAuthority
inputs (see OpeningInstanceEvidenceBundle).

PHYSICAL IDENTITY FOR COUNTING. Dedup among instances proven to exist for
one mark uses PhysicalOpeningAuthority.compare_identity() (re-derives G17
existence for both selectors and compares deterministic record ids) --
strictly stronger than candidate-layer OpeningIdentityResolver.compare_candidates(),
which remains upstream/diagnostic only and is never the final commercial
identity proposition here. The full pairwise identity graph is evaluated,
never greedily: an internally inconsistent graph (A SAME B, B SAME C, A
DISTINCT C) blocks the mark rather than silently collapsing to any count.

Reconciliation table (mark-scoped; `physical_count` = number of distinct,
G17-identity-proven instances independently bound to the mark;
`schedule_count` = the one explicit count OpeningScheduleCountAuthority
resolves for the mark):

  A. COMPLETE universe + physical_count == schedule_count (both > 0)
     + identity graph resolved                          -> CORROBORATED
  B. COMPLETE universe + physical_count >  schedule_count -> CONFLICT
  C. COMPLETE universe + physical_count <  schedule_count -> CONFLICT
  D. COMPLETE universe + explicit schedule_count > 0
     + physical_count == 0                                -> CONFLICT
  E. INCOMPLETE/unknown universe                           -> ABSTAINED
     (this also covers "schedule/OCR evidence only, no
     independently proven physical existence": a raster-only
     scope fails universe completeness for the same reason
     it fails existence, so it never reaches a false CONFLICT)
  F. COMPLETE universe + physical_count > 0
     + no explicit schedule count                          -> ABSTAINED
  H. any unresolved/conflicting pairwise physical identity  -> ABSTAINED/CONFLICT

NEVER min(schedule_count, physical_count). NEVER max(...).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_schedule_count_authority import (
    OpeningScheduleCountAuthority,
    OpeningScheduleCountSelector,
)
from pb_opening_tag_normalization import normalize_opening_tag
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseSelector,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PHYSICAL_OPENING_IDENTITIES_DISTINCT,
    PhysicalOpeningAuthority,
)
from pb_source_observation_authority import (
    ObservationSelector,
    SourceObservationAuthority,
)
from pb_source_opening_candidate_authority import (
    AuthenticatedViewportDecision,
    IdentityState,
    OpeningIdentityResolver,
    PhysicalOpeningCandidateRecord,
    TagBindingEvidence,
    TagObservation,
)

COMMERCIAL_INSTANCE_SCHEMA_VERSION = "1.0.0"

COMMERCIAL_COUNT_RESOLVED = "commercial_instance_count_resolved"
COMMERCIAL_COUNT_UNIVERSE_INCOMPLETE = "commercial_instance_count_universe_incomplete"
COMMERCIAL_COUNT_NO_SCHEDULE_ROW = "commercial_instance_count_no_explicit_schedule_count"
COMMERCIAL_COUNT_AMBIGUOUS_SCHEDULE_ROWS = "commercial_instance_count_ambiguous_schedule_rows"
COMMERCIAL_COUNT_NO_PHYSICAL_INSTANCES = "commercial_instance_count_no_physical_instances"
COMMERCIAL_COUNT_AMBIGUOUS_IDENTITY = "commercial_instance_count_ambiguous_physical_identity"
COMMERCIAL_COUNT_INCONSISTENT_IDENTITY_GRAPH = "commercial_instance_count_inconsistent_identity_graph"
COMMERCIAL_COUNT_SCHEDULE_PHYSICAL_MISMATCH = "commercial_instance_count_schedule_physical_mismatch"


@dataclass(frozen=True)
class OpeningInstanceEvidenceBundle:
    """Raw, unauthenticated evidence for one candidate physical opening
    instance that might bind to a given mark.

    This module independently re-derives both G17 physical existence
    (via `existence_selector`) and tag-binding identity from the remaining
    fields by calling OpeningIdentityResolver.resolve_tag_binding() itself
    -- it never accepts a pre-computed positive OpeningTagBindingResult as
    sufficient evidence.
    """

    existence_selector: ObservationSelector
    candidate: PhysicalOpeningCandidateRecord
    nearby_tags: tuple[TagObservation, ...]
    binding_evidences: tuple[TagBindingEvidence, ...]
    viewport_decision: AuthenticatedViewportDecision
    expected_semantic_family: str
    source_observation_authority: SourceObservationAuthority


@dataclass(frozen=True)
class CommercialInstanceCountRecord:
    """Immutable, replayable evidence trail for one mark's resolved count."""

    record_id: str
    mark: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    commercial_count: int
    physical_existence_record_ids: tuple[str, ...]
    bound_tag_observation_ids: tuple[str, ...]
    schedule_count_record_id: str
    universe_completeness_record_id: str | None
    schema_version: str = COMMERCIAL_INSTANCE_SCHEMA_VERSION


@dataclass(frozen=True)
class CommercialInstanceCountResult:
    """Fail-closed result for one opening tag mark's commercial count."""

    mark: str
    status: EvidenceResolutionStatus
    count: int | None
    physical_count: int | None
    schedule_count: int | None
    reason_codes: tuple[str, ...]
    record: CommercialInstanceCountRecord | None = None
    schema_version: str = COMMERCIAL_INSTANCE_SCHEMA_VERSION


class _UnionFind:
    def __init__(self, items: Sequence[str]) -> None:
        self._parent = {item: item for item in items}

    def find(self, item: str) -> str:
        while self._parent[item] != item:
            self._parent[item] = self._parent[self._parent[item]]
            item = self._parent[item]
        return item

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self._parent[right_root] = left_root


@dataclass(frozen=True)
class _EligibleInstance:
    key: str
    existence_selector: ObservationSelector
    existence_record_id: str
    tag_observation_id: str


def _evaluate_instance_bundle(
    bundle: OpeningInstanceEvidenceBundle,
    *,
    normalized_mark: str,
    physical_opening_authority: PhysicalOpeningAuthority,
) -> _EligibleInstance | None:
    """Gate 1 (existence) then a full replayed tag-binding resolution.

    Returns None when either independently fails -- exclusion, not an
    error: an instance that cannot prove existence or cannot prove a bound
    mark simply does not contribute to this mark's physical_count.
    """
    existence = physical_opening_authority.prove_existence(bundle.existence_selector)
    if (
        existence.status != EvidenceResolutionStatus.CORROBORATED
        or existence.proposition != PHYSICAL_OPENING_EXISTS
        or existence.existence_record is None
    ):
        return None

    viewport_authenticated = (
        bundle.viewport_decision.status == EvidenceResolutionStatus.CORROBORATED
    )
    binding = OpeningIdentityResolver.resolve_tag_binding(
        candidate=bundle.candidate,
        nearby_tags=bundle.nearby_tags,
        binding_evidences=bundle.binding_evidences,
        expected_semantic_family=bundle.expected_semantic_family,
        viewport_authenticated=viewport_authenticated,
        revision_authenticated=True,
        source_observation_authority=bundle.source_observation_authority,
    )
    if (
        binding.status != EvidenceResolutionStatus.CORROBORATED
        or binding.identity_state != IdentityState.PROVEN_SAME
        or binding.bound_mark != normalized_mark
        or binding.tag_observation_id is None
    ):
        return None

    return _EligibleInstance(
        key=bundle.existence_selector.observation_id,
        existence_selector=bundle.existence_selector,
        existence_record_id=existence.existence_record.record_id,
        tag_observation_id=binding.tag_observation_id,
    )


def _resolve_physical_identity_count(
    eligible: Sequence[_EligibleInstance],
    *,
    physical_opening_authority: PhysicalOpeningAuthority,
) -> tuple[int | None, EvidenceResolutionStatus, tuple[str, ...]]:
    """All-pairs G17 identity comparison -- never greedy, never transitive
    shortcuts. Returns (physical_count, status, reason_codes).

    physical_count is None when any pair cannot be affirmatively resolved,
    OR when the resolved SAME/DISTINCT graph is internally inconsistent
    (e.g. A SAME B, B SAME C, A DISTINCT C) -- the whole mark blocks rather
    than silently collapsing to any particular count.
    """
    if not eligible:
        return 0, EvidenceResolutionStatus.CORROBORATED, ()

    keys = sorted(e.key for e in eligible)
    by_key = {e.key: e for e in eligible}
    same_pairs: list[tuple[str, str]] = []
    distinct_pairs: list[tuple[str, str]] = []

    for i, left in enumerate(keys):
        for right in keys[i + 1:]:
            comparison = physical_opening_authority.compare_identity(
                by_key[left].existence_selector, by_key[right].existence_selector
            )
            if comparison.proven_same:
                same_pairs.append((left, right))
            elif (
                comparison.status == EvidenceResolutionStatus.CORROBORATED
                and comparison.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
            ):
                distinct_pairs.append((left, right))
            else:
                return (
                    None,
                    comparison.status,
                    (COMMERCIAL_COUNT_AMBIGUOUS_IDENTITY, *comparison.reason_codes),
                )

    uf = _UnionFind(keys)
    for left, right in same_pairs:
        uf.union(left, right)

    for left, right in distinct_pairs:
        if uf.find(left) == uf.find(right):
            return (
                None,
                EvidenceResolutionStatus.CONFLICT,
                (COMMERCIAL_COUNT_INCONSISTENT_IDENTITY_GRAPH,),
            )

    distinct_roots = {uf.find(key) for key in keys}
    return len(distinct_roots), EvidenceResolutionStatus.CORROBORATED, ()


def resolve_opening_commercial_instance_count(
    *,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    decision_scope_id: str,
    mark: str,
    instance_evidence: Sequence[OpeningInstanceEvidenceBundle],
    physical_opening_authority: PhysicalOpeningAuthority,
    universe_completeness_authority: OpeningUniverseCompletenessAuthority,
    schedule_count_authority: OpeningScheduleCountAuthority,
) -> CommercialInstanceCountResult:
    """Resolve one mark's commercial count in one decision scope.

    `instance_evidence` may contain bundles for other marks or for
    instances that never resolve at all -- both are silently excluded
    rather than treated as errors, exactly like every other candidate
    filtering step elsewhere in this codebase.
    """
    normalized = normalize_opening_tag(mark)
    normalized_mark = normalized.tag if normalized is not None else str(mark).strip()

    completeness = universe_completeness_authority.resolve(
        OpeningUniverseSelector(
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            snapshot_id=snapshot_id,
            decision_scope_id=decision_scope_id,
        )
    )
    if completeness.status != EvidenceResolutionStatus.CORROBORATED:
        return CommercialInstanceCountResult(
            mark=normalized_mark,
            status=EvidenceResolutionStatus.ABSTAINED,
            count=None,
            physical_count=None,
            schedule_count=None,
            reason_codes=(COMMERCIAL_COUNT_UNIVERSE_INCOMPLETE, *completeness.reason_codes),
        )
    completeness_record_id = (
        completeness.record.record_id if completeness.record is not None else None
    )

    eligible = [
        instance
        for bundle in instance_evidence
        if (
            instance := _evaluate_instance_bundle(
                bundle,
                normalized_mark=normalized_mark,
                physical_opening_authority=physical_opening_authority,
            )
        )
        is not None
    ]

    physical_count, identity_status, identity_reasons = _resolve_physical_identity_count(
        eligible, physical_opening_authority=physical_opening_authority
    )
    if physical_count is None:
        return CommercialInstanceCountResult(
            mark=normalized_mark,
            status=identity_status,
            count=None,
            physical_count=None,
            schedule_count=None,
            reason_codes=identity_reasons,
        )

    schedule_result = schedule_count_authority.resolve(
        OpeningScheduleCountSelector(
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            snapshot_id=snapshot_id,
            decision_scope_id=decision_scope_id,
            normalized_mark=normalized_mark,
        )
    )
    if schedule_result.status == EvidenceResolutionStatus.CONFLICT:
        return CommercialInstanceCountResult(
            mark=normalized_mark,
            status=EvidenceResolutionStatus.CONFLICT,
            count=None,
            physical_count=physical_count,
            schedule_count=None,
            reason_codes=(COMMERCIAL_COUNT_AMBIGUOUS_SCHEDULE_ROWS, *schedule_result.reason_codes),
        )
    if schedule_result.status != EvidenceResolutionStatus.CORROBORATED or schedule_result.record is None:
        return CommercialInstanceCountResult(
            mark=normalized_mark,
            status=EvidenceResolutionStatus.ABSTAINED,
            count=None,
            physical_count=physical_count,
            schedule_count=None,
            reason_codes=(COMMERCIAL_COUNT_NO_SCHEDULE_ROW, *schedule_result.reason_codes),
        )
    schedule_count = schedule_result.record.explicit_count

    if physical_count == 0:
        return CommercialInstanceCountResult(
            mark=normalized_mark,
            status=EvidenceResolutionStatus.CONFLICT,
            count=None,
            physical_count=0,
            schedule_count=schedule_count,
            reason_codes=(COMMERCIAL_COUNT_NO_PHYSICAL_INSTANCES,),
        )

    if physical_count != schedule_count:
        return CommercialInstanceCountResult(
            mark=normalized_mark,
            status=EvidenceResolutionStatus.CONFLICT,
            count=None,
            physical_count=physical_count,
            schedule_count=schedule_count,
            reason_codes=(
                COMMERCIAL_COUNT_SCHEDULE_PHYSICAL_MISMATCH,
                f"physical_{physical_count}_vs_schedule_{schedule_count}",
            ),
        )

    payload = {
        "schema_version": COMMERCIAL_INSTANCE_SCHEMA_VERSION,
        "mark": normalized_mark,
        "document_id": document_id,
        "revision_id": revision_id,
        "source_sha256": source_sha256,
        "snapshot_id": snapshot_id,
        "decision_scope_id": decision_scope_id,
        "commercial_count": physical_count,
        "physical_existence_record_ids": sorted(e.existence_record_id for e in eligible),
        "bound_tag_observation_ids": sorted(e.tag_observation_id for e in eligible),
        "schedule_count_record_id": schedule_result.record.record_id,
    }
    record = CommercialInstanceCountRecord(
        record_id=stable_contract_id("commercial_instance_count", payload, digest_chars=32),
        mark=normalized_mark,
        document_id=document_id,
        revision_id=revision_id,
        source_sha256=source_sha256,
        snapshot_id=snapshot_id,
        decision_scope_id=decision_scope_id,
        commercial_count=physical_count,
        physical_existence_record_ids=tuple(sorted(e.existence_record_id for e in eligible)),
        bound_tag_observation_ids=tuple(sorted(e.tag_observation_id for e in eligible)),
        schedule_count_record_id=schedule_result.record.record_id,
        universe_completeness_record_id=completeness_record_id,
    )
    return CommercialInstanceCountResult(
        mark=normalized_mark,
        status=EvidenceResolutionStatus.CORROBORATED,
        count=physical_count,
        physical_count=physical_count,
        schedule_count=schedule_count,
        reason_codes=(COMMERCIAL_COUNT_RESOLVED,),
        record=record,
    )


__all__ = [
    "COMMERCIAL_COUNT_AMBIGUOUS_IDENTITY",
    "COMMERCIAL_COUNT_AMBIGUOUS_SCHEDULE_ROWS",
    "COMMERCIAL_COUNT_INCONSISTENT_IDENTITY_GRAPH",
    "COMMERCIAL_COUNT_NO_PHYSICAL_INSTANCES",
    "COMMERCIAL_COUNT_NO_SCHEDULE_ROW",
    "COMMERCIAL_COUNT_RESOLVED",
    "COMMERCIAL_COUNT_SCHEDULE_PHYSICAL_MISMATCH",
    "COMMERCIAL_COUNT_UNIVERSE_INCOMPLETE",
    "COMMERCIAL_INSTANCE_SCHEMA_VERSION",
    "CommercialInstanceCountRecord",
    "CommercialInstanceCountResult",
    "OpeningInstanceEvidenceBundle",
    "resolve_opening_commercial_instance_count",
]
