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
inputs (see OpeningInstanceEvidenceBundle), and it discovers each instance's
bound mark from that replay -- callers never assert which mark an instance
belongs to.

PHYSICAL IDENTITY FOR COUNTING. Dedup among instances proven to exist for
one mark uses PhysicalOpeningAuthority.compare_identity() (re-derives G17
existence for both selectors and compares deterministic record ids) --
strictly stronger than candidate-layer OpeningIdentityResolver.compare_candidates(),
which remains upstream/diagnostic only and is never the final commercial
identity proposition here. The full pairwise identity graph is evaluated,
never greedily: an internally inconsistent graph (A SAME B, B SAME C, A
DISTINCT C) blocks the mark rather than silently collapsing to any count.

MARK-SCOPED COMMERCIAL SELECTOR. The published proposition is keyed by
(document_id, revision_id, source_sha256, snapshot_id, decision_scope_id,
normalized_mark) -- an explicit selector, like every other authority in
this codebase, not an arbitrary page number. Pages/viewports contribute
evidence; the decision scope defines the proposition. Callers name which
marks are in scope for a `publish_scope()` call (mirroring
OpeningScheduleCountAuthority and every other selector-resolved authority
here) -- this module discovers each candidate instance's mark via replay,
but does not invent which marks are worth deciding.

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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

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
COMMERCIAL_COUNT_RECORD_UNAVAILABLE = "commercial_instance_count_record_unavailable"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RecordKey = tuple[str, str, str, str, str, str]


def _require_nonempty(value: object, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be a non-empty string")
    return clean


def _normalized_mark(raw: object) -> str:
    normalized = normalize_opening_tag(str(raw))
    return normalized.tag if normalized is not None else str(raw).strip()


def _record_key(
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    decision_scope_id: str,
    normalized_mark: str,
) -> _RecordKey:
    return (
        str(document_id),
        str(revision_id),
        str(source_sha256),
        str(snapshot_id),
        str(decision_scope_id),
        str(normalized_mark),
    )


@dataclass(frozen=True)
class OpeningCommercialInstanceSelector:
    """Read-only lookup key supplied by ordinary consumers."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    normalized_mark: str

    def __post_init__(self) -> None:
        for name in (
            "document_id", "revision_id", "source_sha256", "snapshot_id",
            "decision_scope_id", "normalized_mark",
        ):
            _require_nonempty(getattr(self, name), name)


@dataclass(frozen=True)
class OpeningInstanceEvidenceBundle:
    """Raw, unauthenticated evidence for one candidate physical opening
    instance that might bind to some mark.

    This module independently re-derives both G17 physical existence
    (via `existence_selector`) and tag-binding identity from the remaining
    fields by calling OpeningIdentityResolver.resolve_tag_binding() itself
    -- it never accepts a pre-computed positive OpeningTagBindingResult as
    sufficient evidence, and it discovers whichever mark (if any) the
    replay proves rather than trusting a caller-asserted mark.
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
    mark: str
    existence_selector: ObservationSelector
    existence_record_id: str
    tag_observation_id: str


def _evaluate_instance_bundle(
    bundle: OpeningInstanceEvidenceBundle,
    *,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    physical_opening_authority: PhysicalOpeningAuthority,
) -> _EligibleInstance | None:
    """Gate 1 (existence) then a full replayed tag-binding resolution.

    Returns None when any independent check fails -- exclusion, not an
    error: an instance that cannot prove existence, cannot prove a bound
    mark, or whose pieces of evidence do not authenticatedly refer to the
    same physical thing in the same scope simply does not contribute to any
    mark's physical_count. The mark itself is discovered from the replay
    (`binding.bound_mark`), never taken from the caller.
    """
    # prove_existence()/resolve_tag_binding() each validate internal
    # consistency of what they're given, but neither knows about the scope
    # `publish_scope()` was actually called for -- a bundle smuggled in from
    # an unrelated document/revision/snapshot must never silently count
    # (especially since a lone such instance never reaches the pairwise
    # compare_identity() step, which is the only other place a scope
    # mismatch would otherwise surface).
    if (
        bundle.existence_selector.document_id != document_id
        or bundle.existence_selector.revision_id != revision_id
        or bundle.existence_selector.source_sha256 != source_sha256
        or bundle.existence_selector.snapshot_id != snapshot_id
        or bundle.candidate.document_id != document_id
        or bundle.candidate.revision_id != revision_id
        or bundle.candidate.source_sha256 != source_sha256
        or bundle.candidate.snapshot_id != snapshot_id
    ):
        return None

    existence = physical_opening_authority.prove_existence(bundle.existence_selector)
    if (
        existence.status != EvidenceResolutionStatus.CORROBORATED
        or existence.proposition != PHYSICAL_OPENING_EXISTS
        or existence.existence_record is None
    ):
        return None

    # existence_selector and candidate are two independent proofs joined
    # only by sitting on one caller-supplied bundle -- nothing about calling
    # both on the same bundle proves they describe the same physical
    # opening. Require the candidate's own lineage to genuinely trace back
    # to (at least one of) the same source observations the G17 existence
    # record used: the same "shared lineage" test
    # OpeningIdentityResolver.compare_candidates() already uses for the
    # analogous same-instance question.
    existence_lineage = set(existence.existence_record.source_observation_ids) | set(
        existence.existence_record.source_lineage_root_ids
    )
    candidate_lineage = set(bundle.candidate.source_observation_ids) | set(
        bundle.candidate.source_lineage_root_ids
    )
    if not (existence_lineage & candidate_lineage):
        return None

    # A genuine CORROBORATED viewport decision for one viewport must not
    # authenticate a candidate/tag pair that itself claims a different,
    # never-independently-authenticated viewport_id.
    viewport_authenticated = (
        bundle.viewport_decision.status == EvidenceResolutionStatus.CORROBORATED
        and bundle.viewport_decision.selector is not None
        and bundle.viewport_decision.selector.viewport_id == bundle.candidate.viewport_id
    )
    binding = OpeningIdentityResolver.resolve_tag_binding(
        candidate=bundle.candidate,
        nearby_tags=bundle.nearby_tags,
        binding_evidences=bundle.binding_evidences,
        expected_semantic_family=bundle.expected_semantic_family,
        viewport_authenticated=viewport_authenticated,
        # Already independently verified above against publish_scope()'s own
        # revision_id (not a rubber stamp) -- resolve_tag_binding() has no
        # separate revision-currency authority of its own to call instead.
        revision_authenticated=True,
        source_observation_authority=bundle.source_observation_authority,
    )
    if (
        binding.status != EvidenceResolutionStatus.CORROBORATED
        or binding.identity_state != IdentityState.PROVEN_SAME
        or not binding.bound_mark
        or binding.tag_observation_id is None
        or normalize_opening_tag(binding.bound_mark) is None
    ):
        return None

    return _EligibleInstance(
        key=bundle.existence_selector.observation_id,
        mark=binding.bound_mark,
        existence_selector=bundle.existence_selector,
        existence_record_id=existence.existence_record.record_id,
        tag_observation_id=binding.tag_observation_id,
    )


def _resolve_physical_identity_count(
    eligible: Sequence[_EligibleInstance],
    *,
    physical_opening_authority: PhysicalOpeningAuthority,
) -> tuple[tuple[_EligibleInstance, ...] | None, EvidenceResolutionStatus, tuple[str, ...]]:
    """All-pairs G17 identity comparison -- never greedy, never transitive
    shortcuts. Returns (representatives, status, reason_codes): exactly one
    _EligibleInstance per distinct physical instance.

    Deduplicates by `.key` (existence_selector.observation_id) FIRST, before
    any comparison -- if `eligible` ever contains two entries for the same
    key (e.g. instance_evidence carried a duplicate bundle), returning one
    representative per distinct key, rather than counting distinct union-find
    roots over a raw possibly-duplicated list, keeps the published evidence
    arrays (built from these representatives downstream) impossible to
    desync from the count derived from them -- there is only one place that
    number comes from.

    representatives is None when any pair cannot be affirmatively resolved,
    OR when the resolved SAME/DISTINCT graph is internally inconsistent
    (e.g. A SAME B, B SAME C, A DISTINCT C) -- the whole mark blocks rather
    than silently collapsing to any particular count.
    """
    by_key: dict[str, _EligibleInstance] = {}
    for instance in eligible:
        by_key.setdefault(instance.key, instance)
    keys = sorted(by_key)
    if not keys:
        return (), EvidenceResolutionStatus.CORROBORATED, ()

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

    representative_key_by_root: dict[str, str] = {}
    for key in keys:
        root = uf.find(key)
        if root not in representative_key_by_root:
            representative_key_by_root[root] = key
    representatives = tuple(
        by_key[representative_key_by_root[root]]
        for root in sorted(representative_key_by_root)
    )
    return representatives, EvidenceResolutionStatus.CORROBORATED, ()


class OpeningCommercialInstanceAuthority:
    """Read-only selector resolver for producer-owned commercial counts."""

    def __init__(
        self,
        results: Mapping[_RecordKey, CommercialInstanceCountResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise ValueError(
                "OpeningCommercialInstanceAuthority must be obtained from "
                "OpeningCommercialInstanceProducer.authority()"
            )
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: OpeningCommercialInstanceSelector) -> CommercialInstanceCountResult:
        if not isinstance(selector, OpeningCommercialInstanceSelector):
            raise TypeError("selector must be OpeningCommercialInstanceSelector")
        key = _record_key(
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.decision_scope_id,
            selector.normalized_mark,
        )
        result = self._results.get(key)
        if result is not None:
            return result
        return CommercialInstanceCountResult(
            mark=selector.normalized_mark,
            status=EvidenceResolutionStatus.ABSTAINED,
            count=None,
            physical_count=None,
            schedule_count=None,
            reason_codes=(COMMERCIAL_COUNT_RECORD_UNAVAILABLE,),
        )


class OpeningCommercialInstanceProducer:
    """Trusted writer reconciling replayed physical evidence against
    explicit schedule counts, one decision scope at a time."""

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "OpeningCommercialInstanceProducer must be obtained from create()"
            )
        self._results: dict[_RecordKey, CommercialInstanceCountResult] = {}

    @classmethod
    def create(cls) -> OpeningCommercialInstanceProducer:
        return cls(_seal=_PRODUCER_SEAL)

    def publish_scope(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        decision_scope_id: str,
        marks: Sequence[str],
        instance_evidence: Sequence[OpeningInstanceEvidenceBundle],
        physical_opening_authority: PhysicalOpeningAuthority,
        universe_completeness_authority: OpeningUniverseCompletenessAuthority,
        schedule_count_authority: OpeningScheduleCountAuthority,
    ) -> tuple[CommercialInstanceCountResult, ...]:
        """Publish one result per mark in `marks` for this decision scope.

        `marks` is caller-supplied -- the decision scope defines which
        commercial propositions are being decided; evidence only
        contributes to them. `instance_evidence` may contain bundles that
        turn out to belong to a mark not in `marks`, or that never resolve
        at all -- both are silently excluded, not treated as errors.
        """
        normalized_marks = sorted({_normalized_mark(m) for m in marks if str(m).strip()})

        completeness = universe_completeness_authority.resolve(
            OpeningUniverseSelector(
                document_id=document_id,
                revision_id=revision_id,
                source_sha256=source_sha256,
                snapshot_id=snapshot_id,
                decision_scope_id=decision_scope_id,
            )
        )
        universe_complete = completeness.status == EvidenceResolutionStatus.CORROBORATED
        completeness_record_id = (
            completeness.record.record_id if completeness.record is not None else None
        )

        # Gate 2 must guard evidence evaluation itself, not just which status
        # gets reported: instance_evidence is never touched when the scope
        # isn't complete, exactly like the single-mark version this replaced.
        # Replaying every bundle unconditionally would mean one malformed
        # OpeningInstanceEvidenceBundle (nearby_tags containing something
        # other than a TagObservation, which nothing here validates at
        # construction) raises out of resolve_tag_binding() and takes down
        # every mark in this call, even ones whose gate already says ABSTAIN.
        eligible_by_mark: dict[str, list[_EligibleInstance]] = {}
        if universe_complete:
            for bundle in instance_evidence:
                instance = _evaluate_instance_bundle(
                    bundle,
                    document_id=document_id,
                    revision_id=revision_id,
                    source_sha256=source_sha256,
                    snapshot_id=snapshot_id,
                    physical_opening_authority=physical_opening_authority,
                )
                if instance is not None:
                    eligible_by_mark.setdefault(instance.mark, []).append(instance)

        produced: list[CommercialInstanceCountResult] = []
        for mark in normalized_marks:
            if not universe_complete:
                result = CommercialInstanceCountResult(
                    mark=mark,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    count=None,
                    physical_count=None,
                    schedule_count=None,
                    reason_codes=(COMMERCIAL_COUNT_UNIVERSE_INCOMPLETE, *completeness.reason_codes),
                )
            else:
                result = self._reconcile_mark(
                    mark=mark,
                    eligible=eligible_by_mark.get(mark, []),
                    document_id=document_id,
                    revision_id=revision_id,
                    source_sha256=source_sha256,
                    snapshot_id=snapshot_id,
                    decision_scope_id=decision_scope_id,
                    physical_opening_authority=physical_opening_authority,
                    schedule_count_authority=schedule_count_authority,
                    completeness_record_id=completeness_record_id,
                )
            key = _record_key(
                document_id, revision_id, source_sha256, snapshot_id, decision_scope_id, mark
            )
            existing = self._results.get(key)
            if existing is not None and existing != result:
                raise RuntimeError("opening commercial instance producer equivocation")
            self._results[key] = result
            produced.append(result)
        return tuple(produced)

    def _reconcile_mark(
        self,
        *,
        mark: str,
        eligible: Sequence[_EligibleInstance],
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        decision_scope_id: str,
        physical_opening_authority: PhysicalOpeningAuthority,
        schedule_count_authority: OpeningScheduleCountAuthority,
        completeness_record_id: str | None,
    ) -> CommercialInstanceCountResult:
        representatives, identity_status, identity_reasons = _resolve_physical_identity_count(
            eligible, physical_opening_authority=physical_opening_authority
        )
        if representatives is None:
            return CommercialInstanceCountResult(
                mark=mark,
                status=identity_status,
                count=None,
                physical_count=None,
                schedule_count=None,
                reason_codes=identity_reasons,
            )
        physical_count = len(representatives)

        schedule_result = schedule_count_authority.resolve(
            OpeningScheduleCountSelector(
                document_id=document_id,
                revision_id=revision_id,
                source_sha256=source_sha256,
                snapshot_id=snapshot_id,
                decision_scope_id=decision_scope_id,
                normalized_mark=mark,
            )
        )
        if schedule_result.status == EvidenceResolutionStatus.CONFLICT:
            return CommercialInstanceCountResult(
                mark=mark,
                status=EvidenceResolutionStatus.CONFLICT,
                count=None,
                physical_count=physical_count,
                schedule_count=None,
                reason_codes=(COMMERCIAL_COUNT_AMBIGUOUS_SCHEDULE_ROWS, *schedule_result.reason_codes),
            )
        if schedule_result.status != EvidenceResolutionStatus.CORROBORATED or schedule_result.record is None:
            return CommercialInstanceCountResult(
                mark=mark,
                status=EvidenceResolutionStatus.ABSTAINED,
                count=None,
                physical_count=physical_count,
                schedule_count=None,
                reason_codes=(COMMERCIAL_COUNT_NO_SCHEDULE_ROW, *schedule_result.reason_codes),
            )
        schedule_count = schedule_result.record.explicit_count

        if physical_count == 0:
            return CommercialInstanceCountResult(
                mark=mark,
                status=EvidenceResolutionStatus.CONFLICT,
                count=None,
                physical_count=0,
                schedule_count=schedule_count,
                reason_codes=(COMMERCIAL_COUNT_NO_PHYSICAL_INSTANCES,),
            )

        if physical_count != schedule_count:
            return CommercialInstanceCountResult(
                mark=mark,
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
            "mark": mark,
            "document_id": document_id,
            "revision_id": revision_id,
            "source_sha256": source_sha256,
            "snapshot_id": snapshot_id,
            "decision_scope_id": decision_scope_id,
            "commercial_count": physical_count,
            "physical_existence_record_ids": sorted(e.existence_record_id for e in representatives),
            "bound_tag_observation_ids": sorted(e.tag_observation_id for e in representatives),
            "schedule_count_record_id": schedule_result.record.record_id,
        }
        record = CommercialInstanceCountRecord(
            record_id=stable_contract_id("commercial_instance_count", payload, digest_chars=32),
            mark=mark,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            snapshot_id=snapshot_id,
            decision_scope_id=decision_scope_id,
            commercial_count=physical_count,
            physical_existence_record_ids=tuple(sorted(e.existence_record_id for e in representatives)),
            bound_tag_observation_ids=tuple(sorted(e.tag_observation_id for e in representatives)),
            schedule_count_record_id=schedule_result.record.record_id,
            universe_completeness_record_id=completeness_record_id,
        )
        return CommercialInstanceCountResult(
            mark=mark,
            status=EvidenceResolutionStatus.CORROBORATED,
            count=physical_count,
            physical_count=physical_count,
            schedule_count=schedule_count,
            reason_codes=(COMMERCIAL_COUNT_RESOLVED,),
            record=record,
        )

    def authority(self) -> OpeningCommercialInstanceAuthority:
        return OpeningCommercialInstanceAuthority(
            MappingProxyType(dict(self._results)), _seal=_AUTHORITY_SEAL
        )


__all__ = [
    "COMMERCIAL_COUNT_AMBIGUOUS_IDENTITY",
    "COMMERCIAL_COUNT_AMBIGUOUS_SCHEDULE_ROWS",
    "COMMERCIAL_COUNT_INCONSISTENT_IDENTITY_GRAPH",
    "COMMERCIAL_COUNT_NO_PHYSICAL_INSTANCES",
    "COMMERCIAL_COUNT_NO_SCHEDULE_ROW",
    "COMMERCIAL_COUNT_RECORD_UNAVAILABLE",
    "COMMERCIAL_COUNT_RESOLVED",
    "COMMERCIAL_COUNT_SCHEDULE_PHYSICAL_MISMATCH",
    "COMMERCIAL_COUNT_UNIVERSE_INCOMPLETE",
    "COMMERCIAL_INSTANCE_SCHEMA_VERSION",
    "CommercialInstanceCountRecord",
    "CommercialInstanceCountResult",
    "OpeningCommercialInstanceAuthority",
    "OpeningCommercialInstanceProducer",
    "OpeningCommercialInstanceSelector",
    "OpeningInstanceEvidenceBundle",
]
