"""Diagnostic-only anatomy of ``semantic_opening_physical_conflict`` (Item 35).

``SemanticOpeningEnumerationProducer`` marks a whole scope ``CONFLICT`` when any
visible observation lands in its ``conflict_observation_ids`` set.  The record
keeps that set (and the residual set) but not *why* each observation is in it.
This module explains it using only the authorities' PUBLIC results:

* ``SourceVisibilityAuthority.resolve_visible``     - source-observation status
* ``PhysicalOpeningAuthority.classify_disposition`` - disposition, reason codes,
                                                      candidate ids
* ``PhysicalOpeningAuthority.prove_existence``      - the support set of each
                                                      proven opening
* ``PhysicalOpeningAuthority.assess_visible_candidate_closure`` - page closure

Paths that add an observation to ``conflict_observation_ids`` in
``_publish_scope`` (pb_semantic_opening_enumeration_authority, current main):

  1. document scope: ``resolve_visible`` status is CONFLICT
                                                 -> ``source_observation_failure``
  2. observation lineage differs from the scope   -> ``lineage_mismatch``
  3. proven-opening record lineage / page differs -> ``lineage_mismatch``
  4. ``classify_disposition`` is CONFLICT
       a. ``ambiguous_physical_opening_candidates`` (observation is a member of
          more than one candidate)                 -> same label
       b. ``snapshot_observation_integrity_failure``: some observation of the
          SNAPSHOT failed to resolve, which makes EVERY observation's
          disposition a conflict            -> ``snapshot_observation_integrity_failure``
       c. anything else                            -> ``disposition_conflict_other``
  5. page candidate closure incomplete and the observation is both closure-
     unresolved and support of a proven opening   -> ``closure_unresolved_overlap_with_proven_opening``
  6. two proven-opening records share a record id but are not equal (a
     content-hash id makes this unreachable in practice).  The diagnostic does
     not try to reproduce it: such an observation is reported ``unattributed``.

The user-facing "source-observation failure" family is path 1 plus path 4b,
kept as two labels because their causes differ (one observation vs the whole
snapshot).  Closure is assessed only for pages that contain a diagnosed
observation, seeded by the smallest diagnosed observation on the page; closure
depends on the seed's page and lineage only (a test checks this).

The record does not store which path fired, so this module RE-DERIVES it by
asking the same public questions of the same producer-owned snapshot.  Nothing
is manufactured: an observation for which no path reproduces is reported as
``unattributed``, and anything the producer does not expose is listed in
``unavailable`` instead of being inferred.  In particular a candidate's member
observations and structural pattern are NOT public for an ambiguous candidate
(``prove_existence`` returns ``candidate=None`` on a conflict), so they are
reported unavailable.

Diagnostic only: every call here is read-only, the record is never altered, no
authority module is edited or monkey-patched, nothing is scored, no benchmark
gold / expected value / tolerance is read, no identity is inferred from counts,
and nothing is a commercial authority.  Production code must not import this
module.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import (
    AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES,
    PHYSICAL_OPENING_DISPOSITION_CONFLICT,
    PHYSICAL_OPENING_DISPOSITION_NO_CANDIDATE,
    PHYSICAL_OPENING_DISPOSITION_OPENING_SUPPORT,
    SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,
    PhysicalOpeningAuthority,
)
from pb_semantic_opening_enumeration_authority import (
    SemanticOpeningEnumerationProducer,
    SemanticOpeningEnumerationResult,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

SEMANTIC_CONFLICT_DIAGNOSTIC_SCHEMA_VERSION = "1.0.0"

# Conflict provenance labels (diagnostic path labels, not evidence statuses).
CONFLICT_PATH_AMBIGUOUS_CANDIDATES = AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES
CONFLICT_PATH_SOURCE_OBSERVATION_FAILURE = "source_observation_failure"
CONFLICT_PATH_SNAPSHOT_INTEGRITY_FAILURE = SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE
CONFLICT_PATH_CLOSURE_UNRESOLVED_OVERLAP = (
    "closure_unresolved_overlap_with_proven_opening"
)
CONFLICT_PATH_LINEAGE_MISMATCH = "lineage_mismatch"
CONFLICT_PATH_DISPOSITION_CONFLICT_OTHER = "disposition_conflict_other"
CONFLICT_PATH_UNATTRIBUTED = "unattributed"
CONFLICT_PATHS = (
    CONFLICT_PATH_AMBIGUOUS_CANDIDATES,
    CONFLICT_PATH_SOURCE_OBSERVATION_FAILURE,
    CONFLICT_PATH_SNAPSHOT_INTEGRITY_FAILURE,
    CONFLICT_PATH_CLOSURE_UNRESOLVED_OVERLAP,
    CONFLICT_PATH_LINEAGE_MISMATCH,
    CONFLICT_PATH_DISPOSITION_CONFLICT_OTHER,
    CONFLICT_PATH_UNATTRIBUTED,
)

# The three families the investigation asks about.  Ties are reported, never broken.
FAMILY_AMBIGUOUS_CANDIDATES = "ambiguous_physical_opening_candidates"
FAMILY_SOURCE_OBSERVATION_FAILURE = "source_observation_failure"
FAMILY_CLOSURE_UNRESOLVED_OVERLAP = "closure_unresolved_overlap_with_proven_opening"
FAMILY_OTHER = "other"
_PATH_FAMILY = {
    CONFLICT_PATH_AMBIGUOUS_CANDIDATES: FAMILY_AMBIGUOUS_CANDIDATES,
    CONFLICT_PATH_SOURCE_OBSERVATION_FAILURE: FAMILY_SOURCE_OBSERVATION_FAILURE,
    CONFLICT_PATH_SNAPSHOT_INTEGRITY_FAILURE: FAMILY_SOURCE_OBSERVATION_FAILURE,
    CONFLICT_PATH_CLOSURE_UNRESOLVED_OVERLAP: FAMILY_CLOSURE_UNRESOLVED_OVERLAP,
}

# How an ambiguous observation relates to the PROVEN openings on its page,
# derived from each proven opening's public support set.
RELATION_SHARED_BETWEEN_PROVEN_OPENINGS = "shared_between_proven_openings"
RELATION_ONE_PROVEN_OPENING_PLUS_COMPETITOR = "one_proven_opening_plus_competitor"
RELATION_NO_PROVEN_OPENING = "no_proven_opening"
RELATION_NOT_APPLICABLE = "not_applicable"
RELATION_UNAVAILABLE = "unavailable"

RESIDUAL_PATH_UNRESOLVED_DISPOSITION = "unresolved_disposition"
RESIDUAL_PATH_CLOSURE_UNRESOLVED = "closure_unresolved"
RESIDUAL_PATH_UNRESOLVED_SOURCE_OBSERVATION = "unresolved_source_observation"
RESIDUAL_PATH_UNATTRIBUTED = "unattributed"
RESIDUAL_PATHS = (
    RESIDUAL_PATH_UNRESOLVED_DISPOSITION,
    RESIDUAL_PATH_CLOSURE_UNRESOLVED,
    RESIDUAL_PATH_UNRESOLVED_SOURCE_OBSERVATION,
    RESIDUAL_PATH_UNATTRIBUTED,
)

# Information the producers do not expose publicly.  Reported, never inferred.
UNAVAILABLE_CANDIDATE_STRUCTURAL_PATTERN = (
    "candidate_structural_pattern_for_ambiguous_candidates"
)
UNAVAILABLE_CANDIDATE_MEMBER_OBSERVATIONS = (
    "candidate_member_observation_ids_for_unproven_candidates"
)
UNAVAILABLE_CONFLICT_PATH_NOT_RECORDED = (
    "conflict_path_provenance_not_recorded_in_semantic_record_rederived"
)
UNAVAILABLE_CLOSURE_CANDIDATE_ID_RELATION = (
    "relation_between_closure_candidate_ids_and_disposition_candidate_ids"
)
UNAVAILABLE_VIEW_KIND = "viewport_view_kind_not_part_of_the_semantic_layer"
STATIC_UNAVAILABLE = (
    UNAVAILABLE_CANDIDATE_STRUCTURAL_PATTERN,
    UNAVAILABLE_CANDIDATE_MEMBER_OBSERVATIONS,
    UNAVAILABLE_CONFLICT_PATH_NOT_RECORDED,
    UNAVAILABLE_CLOSURE_CANDIDATE_ID_RELATION,
    UNAVAILABLE_VIEW_KIND,
)
UNAVAILABLE_SEMANTIC_RECORD_ABSENT = "semantic_record_absent"

# Must equal the constants used by collect_item35_authority_shadow so that a
# record collected here is the same record the shadow publishes.  A test pins
# this by comparing semantic record ids.
SHADOW_PRODUCER_METHOD = "planreader_live_item35_shadow"
SHADOW_PRODUCER_VERSION = "1.0.0"

_GEOMETRY_DECIMALS = 3


def _sorted_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values}))


def _round_geometry(values: Iterable[Any]) -> tuple[float, ...]:
    return tuple(round(float(value), _GEOMETRY_DECIMALS) for value in values)


@dataclass(frozen=True)
class ObservationEvidence:
    """Source-owned facts about one visible observation (None when unavailable)."""

    observation_id: str
    page_id: Optional[str]
    viewport_id: Optional[str]
    observation_kind: Optional[str]
    source_primitive_ref: Optional[str]
    derivation_parent_ids: tuple[str, ...]
    geometry: tuple[float, ...]
    visible_status: str
    visible_reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "page_id": self.page_id,
            "viewport_id": self.viewport_id,
            "observation_kind": self.observation_kind,
            "source_primitive_ref": self.source_primitive_ref,
            "derivation_parent_ids": list(self.derivation_parent_ids),
            "geometry": list(self.geometry),
            "visible_status": self.visible_status,
            "visible_reason_codes": list(self.visible_reason_codes),
        }


@dataclass(frozen=True)
class DispositionEvidence:
    """The public ``classify_disposition`` result for one observation."""

    status: Optional[str]
    disposition: Optional[str]
    reason_codes: tuple[str, ...]
    candidate_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "disposition": self.disposition,
            "reason_codes": list(self.reason_codes),
            "candidate_ids": list(self.candidate_ids),
        }


@dataclass(frozen=True)
class ConflictObservation:
    evidence: ObservationEvidence
    disposition: DispositionEvidence
    in_opening_support: bool
    proven_opening_record_ids: tuple[str, ...]
    candidate_relation: str
    in_closure_unresolved: Optional[bool]
    paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence": self.evidence.to_dict(),
            "disposition": self.disposition.to_dict(),
            "in_opening_support": self.in_opening_support,
            "proven_opening_record_ids": list(self.proven_opening_record_ids),
            "candidate_relation": self.candidate_relation,
            "in_closure_unresolved": self.in_closure_unresolved,
            "paths": list(self.paths),
        }


@dataclass(frozen=True)
class ResidualObservation:
    evidence: ObservationEvidence
    disposition: DispositionEvidence
    in_closure_unresolved: Optional[bool]
    paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence": self.evidence.to_dict(),
            "disposition": self.disposition.to_dict(),
            "in_closure_unresolved": self.in_closure_unresolved,
            "paths": list(self.paths),
        }


@dataclass(frozen=True)
class PageClosureEvidence:
    """Public page-closure result, obtained through one seed observation."""

    page_id: str
    seed_observation_id: str
    status: str
    candidate_universe_complete: bool
    raw_candidate_count: int
    resolved_candidate_count: int
    unresolved_candidate_ids: tuple[str, ...]
    unresolved_observation_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_id": self.page_id,
            "seed_observation_id": self.seed_observation_id,
            "status": self.status,
            "candidate_universe_complete": self.candidate_universe_complete,
            "raw_candidate_count": self.raw_candidate_count,
            "resolved_candidate_count": self.resolved_candidate_count,
            "unresolved_candidate_ids": list(self.unresolved_candidate_ids),
            "unresolved_observation_ids": list(self.unresolved_observation_ids),
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True)
class RepresentativeExistenceEvidence:
    """A proven opening whose recorded representative cannot re-prove existence.

    Downstream consumers (e.g. the generic count) re-prove existence from the
    record's representative observation.  If that observation is itself in an
    ambiguous candidate set, ``prove_existence`` returns a conflict for it.
    """

    opening_record_id: str
    representative_observation_id: str
    status: str
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "opening_record_id": self.opening_record_id,
            "representative_observation_id": self.representative_observation_id,
            "status": self.status,
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True)
class ConflictCluster:
    """Ambiguous conflicting observations linked by shared candidate ids."""

    cluster_id: str
    observation_ids: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    page_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "observation_ids": list(self.observation_ids),
            "candidate_ids": list(self.candidate_ids),
            "page_ids": list(self.page_ids),
        }


_FIELD_NAMES = (
    "semantic_record_id",
    "semantic_status",
    "semantic_reason_codes",
    "document_id",
    "revision_id",
    "source_sha256",
    "snapshot_id",
    "decision_scope_id",
    "decision_scope_kind",
    "page_ids",
    "counts",
    "conflicts",
    "residuals",
    "closure_pages",
    "clusters",
    "opening_support_unresolved_count",
    "representative_existence_unresolved",
    "rederivation_consistent",
    "unavailable",
)


def _payload_from_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SEMANTIC_CONFLICT_DIAGNOSTIC_SCHEMA_VERSION,
        "semantic_record_id": fields["semantic_record_id"],
        "semantic_status": fields["semantic_status"],
        "semantic_reason_codes": list(fields["semantic_reason_codes"]),
        "document_id": fields["document_id"],
        "revision_id": fields["revision_id"],
        "source_sha256": fields["source_sha256"],
        "snapshot_id": fields["snapshot_id"],
        "decision_scope_id": fields["decision_scope_id"],
        "decision_scope_kind": fields["decision_scope_kind"],
        "page_ids": list(fields["page_ids"]),
        "counts": {name: value for name, value in fields["counts"]},
        "conflicts": [item.to_dict() for item in fields["conflicts"]],
        "residuals": [item.to_dict() for item in fields["residuals"]],
        "closure_pages": [item.to_dict() for item in fields["closure_pages"]],
        "clusters": [item.to_dict() for item in fields["clusters"]],
        "opening_support_unresolved_count": fields["opening_support_unresolved_count"],
        "representative_existence_unresolved": [
            item.to_dict() for item in fields["representative_existence_unresolved"]
        ],
        "rederivation_consistent": fields["rederivation_consistent"],
        "unavailable": list(fields["unavailable"]),
        "commercial_authority_granted": False,
    }


@dataclass(frozen=True)
class SemanticConflictDiagnostic:
    """Immutable, deterministic anatomy of one semantic-enumeration scope."""

    record_id: str
    semantic_record_id: Optional[str]
    semantic_status: Optional[str]
    semantic_reason_codes: tuple[str, ...]
    document_id: Optional[str]
    revision_id: Optional[str]
    source_sha256: Optional[str]
    snapshot_id: Optional[str]
    decision_scope_id: Optional[str]
    decision_scope_kind: Optional[str]
    page_ids: tuple[str, ...]
    counts: tuple[tuple[str, int], ...]
    conflicts: tuple[ConflictObservation, ...]
    residuals: tuple[ResidualObservation, ...]
    closure_pages: tuple[PageClosureEvidence, ...]
    clusters: tuple[ConflictCluster, ...]
    opening_support_unresolved_count: int
    representative_existence_unresolved: tuple[RepresentativeExistenceEvidence, ...]
    rederivation_consistent: bool
    unavailable: tuple[str, ...]
    commercial_authority_granted: bool = False
    schema_version: str = SEMANTIC_CONFLICT_DIAGNOSTIC_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.commercial_authority_granted is not False:
            raise ValueError("a diagnostic never grants commercial authority")
        if self.counts != tuple(sorted(self.counts)):
            raise ValueError("counts must be sorted")
        if self.record_id != stable_contract_id(
            "semantic_conflict_diagnostic", self._payload(), digest_chars=32
        ):
            raise ValueError("record_id does not match the diagnostic content")

    def _payload(self) -> dict[str, Any]:
        return _payload_from_fields({name: getattr(self, name) for name in _FIELD_NAMES})

    def counts_dict(self) -> dict[str, int]:
        return dict(self.counts)

    def to_dict(self) -> dict[str, Any]:
        payload = self._payload()
        payload["record_id"] = self.record_id
        return payload


def _build(fields: dict[str, Any]) -> SemanticConflictDiagnostic:
    fields = {**fields, "counts": tuple(sorted(fields["counts"].items()))}
    record_id = stable_contract_id(
        "semantic_conflict_diagnostic", _payload_from_fields(fields), digest_chars=32
    )
    return SemanticConflictDiagnostic(record_id=record_id, **fields)


def _selector(record: Any, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=record.document_id,
        revision_id=record.revision_id,
        source_sha256=record.source_sha256,
        snapshot_id=record.snapshot_id,
        observation_id=observation_id,
    )


def _observation_evidence(visible: Any, observation_id: str) -> ObservationEvidence:
    observation = visible.observation
    return ObservationEvidence(
        observation_id=observation_id,
        page_id=str(observation.page_id) if observation is not None else None,
        viewport_id=(
            None
            if observation is None or observation.viewport_id is None
            else str(observation.viewport_id)
        ),
        observation_kind=(
            str(observation.observation_kind) if observation is not None else None
        ),
        source_primitive_ref=(
            str(observation.source_primitive_ref) if observation is not None else None
        ),
        derivation_parent_ids=(
            tuple(str(item) for item in observation.derivation_parent_ids)
            if observation is not None
            else ()
        ),
        geometry=_round_geometry(observation.geometry) if observation is not None else (),
        visible_status=str(visible.status.value),
        visible_reason_codes=_sorted_unique(visible.reason_codes),
    )


def _disposition_evidence(result: Any) -> DispositionEvidence:
    if result is None:
        return DispositionEvidence(None, None, (), ())
    return DispositionEvidence(
        status=str(result.status.value),
        disposition=str(result.disposition),
        reason_codes=_sorted_unique(result.reason_codes),
        candidate_ids=_sorted_unique(result.candidate_ids),
    )


def _lineage_differs(observation: Any, record: Any) -> bool:
    return (
        observation.document_id != record.document_id
        or observation.revision_id != record.revision_id
        or observation.source_sha256 != record.source_sha256
        or observation.snapshot_id != record.snapshot_id
    )


def _clusters(conflicts: Sequence[ConflictObservation]) -> tuple[ConflictCluster, ...]:
    """Union ambiguous observations that share any candidate id (no thresholds)."""
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    ambiguous = [
        item
        for item in conflicts
        if CONFLICT_PATH_AMBIGUOUS_CANDIDATES in item.paths and item.disposition.candidate_ids
    ]
    first_owner: dict[str, str] = {}
    for item in sorted(ambiguous, key=lambda entry: entry.evidence.observation_id):
        observation_id = item.evidence.observation_id
        parent.setdefault(observation_id, observation_id)
        for candidate_id in item.disposition.candidate_ids:
            owner = first_owner.setdefault(candidate_id, observation_id)
            union(owner, observation_id)

    groups: dict[str, list[ConflictObservation]] = {}
    for item in ambiguous:
        groups.setdefault(find(item.evidence.observation_id), []).append(item)
    clusters = []
    for members in groups.values():
        observation_ids = _sorted_unique(m.evidence.observation_id for m in members)
        candidate_ids = _sorted_unique(c for m in members for c in m.disposition.candidate_ids)
        page_ids = _sorted_unique(m.evidence.page_id for m in members if m.evidence.page_id)
        clusters.append(
            ConflictCluster(
                cluster_id=stable_contract_id(
                    "semantic_conflict_cluster",
                    {"observation_ids": list(observation_ids)},
                    digest_chars=20,
                ),
                observation_ids=observation_ids,
                candidate_ids=candidate_ids,
                page_ids=page_ids,
            )
        )
    return tuple(sorted(clusters, key=lambda cluster: cluster.cluster_id))


def _empty_diagnostic(
    reason: str, *, status: Optional[str] = None, reason_codes: Iterable[str] = ()
) -> SemanticConflictDiagnostic:
    return _build(
        {
            "semantic_record_id": None,
            "semantic_status": status,
            "semantic_reason_codes": _sorted_unique(reason_codes),
            "document_id": None,
            "revision_id": None,
            "source_sha256": None,
            "snapshot_id": None,
            "decision_scope_id": None,
            "decision_scope_kind": None,
            "page_ids": (),
            "counts": {
                "visible": 0,
                "support": 0,
                "residual": 0,
                "conflict": 0,
                "openings": 0,
            },
            "conflicts": (),
            "residuals": (),
            "closure_pages": (),
            "clusters": (),
            "opening_support_unresolved_count": 0,
            "representative_existence_unresolved": (),
            "rederivation_consistent": True,
            "unavailable": _sorted_unique((*STATIC_UNAVAILABLE, reason)),
        }
    )


def diagnose_semantic_conflicts(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    semantic_result: SemanticOpeningEnumerationResult,
) -> SemanticConflictDiagnostic:
    """Explain the conflict and residual sets of one published semantic scope.

    Read-only.  ``semantic_result`` must have been published by a
    ``SemanticOpeningEnumerationProducer`` bound to ``source_visibility_producer``;
    the record's lineage is checked against that producer's snapshot and a
    mismatch raises ``ValueError`` (the records would not share an authenticated
    scope).
    """
    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")
    if not isinstance(semantic_result, SemanticOpeningEnumerationResult):
        raise TypeError("semantic_result must be a SemanticOpeningEnumerationResult")

    record = semantic_result.record
    if record is None:
        return _empty_diagnostic(
            UNAVAILABLE_SEMANTIC_RECORD_ABSENT,
            status=str(semantic_result.status.value),
            reason_codes=semantic_result.reason_codes,
        )

    published = source_visibility_producer.published_snapshot_for_revision(
        record.revision_id
    )
    if (
        published is None
        or published.revision.document_id != record.document_id
        or published.revision.source_sha256 != record.source_sha256
        or published.snapshot.snapshot_id != record.snapshot_id
    ):
        raise ValueError(
            "semantic record does not belong to this producer's authenticated snapshot"
        )

    visibility = source_visibility_producer.authority()
    # A private authority over the producer's own visibility authority.  Only this
    # object's memo caches are filled; no producer or shared authority is touched,
    # and a caller cannot substitute an authority over different data.
    physical = PhysicalOpeningAuthority(visibility)
    scope_kind = record.decision_scope_kind
    allowed_pages = {str(page) for page in record.page_ids}
    support_ids = set(record.opening_support_observation_ids)

    conflict_set = set(record.conflict_observation_ids)

    # Support set of every PROVEN opening.  prove_existence(record.representative)
    # is not usable for this: the representative is min(support ids) and can itself
    # be an ambiguous observation.  Instead ask the public disposition of
    # UNAMBIGUOUS support observations, whose existence_record lists the whole
    # support set, until every proven opening is recovered.
    remaining = set(record.physical_opening_record_ids)
    opening_support: dict[str, frozenset[str]] = {}
    for observation_id in sorted(support_ids - conflict_set):
        if not remaining:
            break
        result = physical.classify_disposition(_selector(record, observation_id))
        existence_record = result.existence_record
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.disposition == PHYSICAL_OPENING_DISPOSITION_OPENING_SUPPORT
            and existence_record is not None
            and existence_record.record_id in remaining
        ):
            opening_support[existence_record.record_id] = frozenset(
                existence_record.source_observation_ids
            )
            remaining.discard(existence_record.record_id)
    support_unresolved = len(remaining)
    openings_by_observation: dict[str, list[str]] = {}
    for opening_id, members in opening_support.items():
        for member in members:
            openings_by_observation.setdefault(member, []).append(opening_id)

    # Can each proven opening's recorded representative re-prove existence?
    representative_unresolved: list[RepresentativeExistenceEvidence] = []
    for opening_id, representative_id in zip(
        record.physical_opening_record_ids, record.representative_observation_ids
    ):
        existence = physical.prove_existence(_selector(record, representative_id))
        proven = (
            existence.status is EvidenceResolutionStatus.CORROBORATED
            and existence.existence_record is not None
            and existence.existence_record.record_id == opening_id
        )
        if not proven:
            representative_unresolved.append(
                RepresentativeExistenceEvidence(
                    opening_record_id=opening_id,
                    representative_observation_id=representative_id,
                    status=str(existence.status.value),
                    reason_codes=_sorted_unique(existence.reason_codes),
                )
            )

    # Resolve every diagnosed observation once.
    diagnosed = _sorted_unique(
        (*record.conflict_observation_ids, *record.residual_visible_observation_ids)
    )
    visible_by_id = {
        observation_id: visibility.resolve_visible(_selector(record, observation_id))
        for observation_id in diagnosed
    }

    # Page closure, seeded by the smallest diagnosed corroborated observation on
    # the page (closure depends on the seed's page and lineage only).
    seed_by_page: dict[str, str] = {}
    for observation_id in diagnosed:
        visible = visible_by_id[observation_id]
        if (
            visible.status is EvidenceResolutionStatus.CORROBORATED
            and visible.observation is not None
        ):
            seed_by_page.setdefault(str(visible.observation.page_id), observation_id)
    closure_by_page: dict[str, PageClosureEvidence] = {}
    for page_id in sorted(seed_by_page, key=lambda p: (0, int(p)) if p.isdigit() else (1, p)):
        seed = seed_by_page[page_id]
        closure = physical.assess_visible_candidate_closure(_selector(record, seed))
        closure_by_page[page_id] = PageClosureEvidence(
            page_id=page_id,
            seed_observation_id=seed,
            status=str(closure.status.value),
            candidate_universe_complete=bool(closure.candidate_universe_complete),
            raw_candidate_count=int(closure.raw_candidate_count),
            resolved_candidate_count=int(closure.resolved_candidate_count),
            unresolved_candidate_ids=_sorted_unique(closure.unresolved_candidate_ids),
            unresolved_observation_ids=_sorted_unique(closure.unresolved_observation_ids),
            reason_codes=_sorted_unique(closure.reason_codes),
        )

    closure_unresolved_sets = {
        page_id: frozenset(closure.unresolved_observation_ids)
        for page_id, closure in closure_by_page.items()
    }

    def in_closure_unresolved(page_id: Optional[str], observation_id: str) -> Optional[bool]:
        closure = closure_by_page.get(page_id) if page_id is not None else None
        if closure is None or closure.status != EvidenceResolutionStatus.CORROBORATED.value:
            return None
        return observation_id in closure_unresolved_sets[page_id]

    conflicts: list[ConflictObservation] = []
    for observation_id in _sorted_unique(record.conflict_observation_ids):
        visible = visible_by_id[observation_id]
        evidence = _observation_evidence(visible, observation_id)
        paths: set[str] = set()
        disposition_result = None
        corroborated = (
            visible.status is EvidenceResolutionStatus.CORROBORATED
            and visible.observation is not None
        )
        if not corroborated:
            if scope_kind == "document" and visible.status is EvidenceResolutionStatus.CONFLICT:
                paths.add(CONFLICT_PATH_SOURCE_OBSERVATION_FAILURE)
        elif _lineage_differs(visible.observation, record):
            paths.add(CONFLICT_PATH_LINEAGE_MISMATCH)
        else:
            disposition_result = physical.classify_disposition(
                _selector(record, observation_id)
            )
            if (
                disposition_result.status is EvidenceResolutionStatus.CONFLICT
                or disposition_result.disposition == PHYSICAL_OPENING_DISPOSITION_CONFLICT
            ):
                codes = set(disposition_result.reason_codes)
                if AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES in codes:
                    paths.add(CONFLICT_PATH_AMBIGUOUS_CANDIDATES)
                elif SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE in codes:
                    paths.add(CONFLICT_PATH_SNAPSHOT_INTEGRITY_FAILURE)
                else:
                    paths.add(CONFLICT_PATH_DISPOSITION_CONFLICT_OTHER)
            elif (
                disposition_result.status is EvidenceResolutionStatus.CORROBORATED
                and disposition_result.disposition
                == PHYSICAL_OPENING_DISPOSITION_OPENING_SUPPORT
                and disposition_result.existence_record is not None
            ):
                opening = disposition_result.existence_record
                if (
                    opening.document_id != record.document_id
                    or opening.revision_id != record.revision_id
                    or opening.source_sha256 != record.source_sha256
                    or opening.snapshot_id != record.snapshot_id
                    or str(opening.page_id) not in allowed_pages
                ):
                    paths.add(CONFLICT_PATH_LINEAGE_MISMATCH)

        page_id = evidence.page_id
        closure_flag = in_closure_unresolved(page_id, observation_id)
        closure = closure_by_page.get(page_id) if page_id is not None else None
        if (
            closure is not None
            and closure.status == EvidenceResolutionStatus.CORROBORATED.value
            and not closure.candidate_universe_complete
            and observation_id in closure_unresolved_sets[page_id]
            and observation_id in support_ids
        ):
            paths.add(CONFLICT_PATH_CLOSURE_UNRESOLVED_OVERLAP)
        if not paths:
            paths.add(CONFLICT_PATH_UNATTRIBUTED)

        proven = _sorted_unique(openings_by_observation.get(observation_id, ()))
        if CONFLICT_PATH_AMBIGUOUS_CANDIDATES not in paths:
            relation = RELATION_NOT_APPLICABLE
        elif support_unresolved:
            relation = RELATION_UNAVAILABLE
        elif len(proven) >= 2:
            relation = RELATION_SHARED_BETWEEN_PROVEN_OPENINGS
        elif len(proven) == 1:
            relation = RELATION_ONE_PROVEN_OPENING_PLUS_COMPETITOR
        else:
            relation = RELATION_NO_PROVEN_OPENING

        conflicts.append(
            ConflictObservation(
                evidence=evidence,
                disposition=_disposition_evidence(disposition_result),
                in_opening_support=observation_id in support_ids,
                proven_opening_record_ids=proven,
                candidate_relation=relation,
                in_closure_unresolved=closure_flag,
                paths=tuple(sorted(paths)),
            )
        )

    residuals: list[ResidualObservation] = []
    for observation_id in _sorted_unique(record.residual_visible_observation_ids):
        visible = visible_by_id[observation_id]
        evidence = _observation_evidence(visible, observation_id)
        paths = set()
        disposition_result = None
        corroborated = (
            visible.status is EvidenceResolutionStatus.CORROBORATED
            and visible.observation is not None
        )
        if not corroborated:
            paths.add(RESIDUAL_PATH_UNRESOLVED_SOURCE_OBSERVATION)
        elif not _lineage_differs(visible.observation, record):
            disposition_result = physical.classify_disposition(
                _selector(record, observation_id)
            )
            corroborated_status = (
                disposition_result.status is EvidenceResolutionStatus.CORROBORATED
            )
            is_support = (
                corroborated_status
                and disposition_result.disposition
                == PHYSICAL_OPENING_DISPOSITION_OPENING_SUPPORT
                and disposition_result.existence_record is not None
            )
            is_no_candidate = (
                corroborated_status
                and disposition_result.disposition
                == PHYSICAL_OPENING_DISPOSITION_NO_CANDIDATE
            )
            is_conflict = (
                disposition_result.status is EvidenceResolutionStatus.CONFLICT
                or disposition_result.disposition == PHYSICAL_OPENING_DISPOSITION_CONFLICT
            )
            if not (is_support or is_no_candidate or is_conflict):
                paths.add(RESIDUAL_PATH_UNRESOLVED_DISPOSITION)
        page_id = evidence.page_id
        closure_flag = in_closure_unresolved(page_id, observation_id)
        residual_closure = closure_by_page.get(page_id) if page_id is not None else None
        if (
            closure_flag
            and residual_closure is not None
            and not residual_closure.candidate_universe_complete
            and observation_id not in support_ids
        ):
            paths.add(RESIDUAL_PATH_CLOSURE_UNRESOLVED)
        if not paths:
            paths.add(RESIDUAL_PATH_UNATTRIBUTED)
        residuals.append(
            ResidualObservation(
                evidence=evidence,
                disposition=_disposition_evidence(disposition_result),
                in_closure_unresolved=closure_flag,
                paths=tuple(sorted(paths)),
            )
        )

    unattributed = sum(
        1 for item in conflicts if CONFLICT_PATH_UNATTRIBUTED in item.paths
    ) + sum(1 for item in residuals if RESIDUAL_PATH_UNATTRIBUTED in item.paths)
    unavailable = list(STATIC_UNAVAILABLE)
    if support_unresolved:
        unavailable.append("proven_opening_support_sets_unresolved")
    if representative_unresolved:
        unavailable.append("proven_opening_representative_cannot_reprove_existence")
    if unattributed:
        unavailable.append("observation_paths_not_reproduced_by_public_results")

    return _build(
        {
            "semantic_record_id": record.record_id,
            "semantic_status": str(semantic_result.status.value),
            "semantic_reason_codes": _sorted_unique(record.reason_codes),
            "document_id": record.document_id,
            "revision_id": record.revision_id,
            "source_sha256": record.source_sha256,
            "snapshot_id": record.snapshot_id,
            "decision_scope_id": record.decision_scope_id,
            "decision_scope_kind": scope_kind,
            "page_ids": tuple(str(page) for page in record.page_ids),
            "counts": {
                "visible": len(record.visible_observation_ids),
                "support": len(record.opening_support_observation_ids),
                "residual": len(record.residual_visible_observation_ids),
                "conflict": len(record.conflict_observation_ids),
                "openings": len(record.physical_opening_record_ids),
            },
            "conflicts": tuple(conflicts),
            "residuals": tuple(residuals),
            "closure_pages": tuple(closure_by_page.values()),
            "clusters": _clusters(conflicts),
            "opening_support_unresolved_count": support_unresolved,
            "representative_existence_unresolved": tuple(
                sorted(representative_unresolved, key=lambda e: e.opening_record_id)
            ),
            "rederivation_consistent": unattributed == 0 and support_unresolved == 0,
            "unavailable": _sorted_unique(unavailable),
        }
    )


def collect_semantic_scope(
    pdf_path: Path | str,
    *,
    document_id: str,
    pages: Optional[Sequence[int]] = None,
    source_bytes: Optional[bytes] = None,
) -> tuple[SourceVisibilityProducer, SemanticOpeningEnumerationResult]:
    """Publish the same semantic scope ``collect_item35_authority_shadow`` publishes.

    Mirrors the shadow's source -> semantic steps (same producer method/version,
    same scope-id formulas) so the record is identical to the shadow's; the
    completeness / view-class / count stages are not needed and not run.
    ``pages`` are 0-based indexes, as in the shadow.  ``source_bytes`` lets a
    caller that already read (and hashed) the file pass exactly those bytes, so
    the diagnosed content cannot differ from the hashed content.
    """
    path = Path(pdf_path)
    payload = source_bytes if source_bytes is not None else path.read_bytes()
    if not payload:
        raise ValueError("source PDF is empty")
    scoped_page_ids: tuple[str, ...] = ()
    if pages is not None:
        scoped_page_ids = tuple(
            str(int(page_index) + 1) for page_index in sorted({int(v) for v in pages})
        )
        if not scoped_page_ids:
            raise ValueError("pages must contain at least one page index")
    source = SourceVisibilityProducer(
        producer_method=SHADOW_PRODUCER_METHOD,
        producer_version=SHADOW_PRODUCER_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=str(path),
    )
    semantic_producer = SemanticOpeningEnumerationProducer.from_source_visibility_producer(
        source
    )
    if pages is None:
        result = semantic_producer.publish_document_scope(
            revision_id=published.revision.revision_id,
            decision_scope_id=f"item35:document:{published.revision.revision_id}",
        )
        return source, result
    published = source.augment_with_raster_visible_segments(
        published.revision.revision_id, page_ids=scoped_page_ids
    )
    result = semantic_producer.publish_page_scope(
        revision_id=published.revision.revision_id,
        decision_scope_id=(
            f"item35:pages:{published.revision.revision_id}:" + ",".join(scoped_page_ids)
        ),
        page_ids=scoped_page_ids,
    )
    return source, result


def collect_semantic_conflict_diagnostic(
    pdf_path: Path | str,
    *,
    document_id: str,
    pages: Optional[Sequence[int]] = None,
    source_bytes: Optional[bytes] = None,
) -> SemanticConflictDiagnostic:
    source, result = collect_semantic_scope(
        pdf_path, document_id=document_id, pages=pages, source_bytes=source_bytes
    )
    return diagnose_semantic_conflicts(
        source_visibility_producer=source, semantic_result=result
    )


# ---------------------------------------------------------------- aggregation
def _sorted_counts(counter: Counter) -> dict[str, int]:
    return {str(key): counter[key] for key in sorted(counter, key=str)}


def _dominant(counter: Counter) -> list[str]:
    """Every key holding the maximum count.  Ties are kept, never broken."""
    if not counter:
        return []
    top = max(counter.values())
    return sorted(str(key) for key, value in counter.items() if value == top)


def _histogram(values: Iterable[int]) -> dict[str, int]:
    counter = Counter(values)
    return {str(key): counter[key] for key in sorted(counter)}


def aggregate_semantic_conflict_diagnostics(
    diagnostics: Iterable[SemanticConflictDiagnostic],
) -> dict[str, Any]:
    """Deterministic, order-invariant tally.  Ties for the dominant path are kept."""
    items = list(diagnostics)
    if not all(isinstance(item, SemanticConflictDiagnostic) for item in items):
        raise TypeError("diagnostics must be SemanticConflictDiagnostic instances")
    ordered = sorted(items, key=lambda item: item.record_id)

    obs_paths: Counter = Counter()
    scope_paths: Counter = Counter()
    exclusive: Counter = Counter()
    combos: Counter = Counter()
    disposition_codes: Counter = Counter()
    visible_codes: Counter = Counter()
    relations: Counter = Counter()
    residual_paths: Counter = Counter()
    residual_codes: Counter = Counter()
    unavailable: Counter = Counter()
    statuses: Counter = Counter()
    record_codes: Counter = Counter()
    candidates_per_conflict: list[int] = []
    cluster_obs: list[int] = []
    cluster_cands: list[int] = []
    pair_shares: Counter = Counter()
    proven_per_conflict: Counter = Counter()
    closure_incomplete_pages = closure_pages = 0
    closure_unresolved_candidates = closure_unresolved_observations = 0
    conflicts_total = residuals_total = 0
    scopes_with_conflict = 0
    unattributed = 0
    family_counts: Counter = Counter()
    family_scope_counts: Counter = Counter()
    openings_total = 0
    representative_unresolved_total = 0
    representative_codes: Counter = Counter()

    for diag in ordered:
        statuses[str(diag.semantic_status)] += 1
        record_codes.update(diag.semantic_reason_codes)
        openings_total += diag.counts_dict().get("openings", 0)
        representative_unresolved_total += len(diag.representative_existence_unresolved)
        for item in diag.representative_existence_unresolved:
            representative_codes.update(item.reason_codes)
        unavailable.update(diag.unavailable)
        if diag.conflicts:
            scopes_with_conflict += 1
        seen_paths: set[str] = set()
        seen_families: set[str] = set()
        pair_counter: Counter = Counter()
        for item in diag.conflicts:
            conflicts_total += 1
            for path in item.paths:
                obs_paths[path] += 1
                seen_paths.add(path)
            for family in {_PATH_FAMILY.get(path, FAMILY_OTHER) for path in item.paths}:
                family_counts[family] += 1
                seen_families.add(family)
            if len(item.paths) == 1:
                exclusive[item.paths[0]] += 1
            combos["+".join(item.paths)] += 1
            disposition_codes.update(item.disposition.reason_codes)
            visible_codes.update(item.evidence.visible_reason_codes)
            if CONFLICT_PATH_AMBIGUOUS_CANDIDATES in item.paths:
                candidates_per_conflict.append(len(item.disposition.candidate_ids))
                relations[item.candidate_relation] += 1
                proven_per_conflict[len(item.proven_opening_record_ids)] += 1
                ids = item.disposition.candidate_ids
                for i, left in enumerate(ids):
                    for right in ids[i + 1 :]:
                        pair_counter[(left, right)] += 1
            if CONFLICT_PATH_UNATTRIBUTED in item.paths:
                unattributed += 1
        for path in seen_paths:
            scope_paths[path] += 1
        for family in seen_families:
            family_scope_counts[family] += 1
        pair_shares.update(pair_counter.values())
        for cluster in diag.clusters:
            cluster_obs.append(len(cluster.observation_ids))
            cluster_cands.append(len(cluster.candidate_ids))
        for item in diag.residuals:
            residuals_total += 1
            for path in item.paths:
                residual_paths[path] += 1
            if RESIDUAL_PATH_UNATTRIBUTED in item.paths:
                unattributed += 1
            residual_codes.update(item.disposition.reason_codes)
        for page in diag.closure_pages:
            closure_pages += 1
            if not page.candidate_universe_complete:
                closure_incomplete_pages += 1
            closure_unresolved_candidates += len(page.unresolved_candidate_ids)
            closure_unresolved_observations += len(page.unresolved_observation_ids)

    def stats(values: list[int]) -> dict[str, Any]:
        if not values:
            return {"count": 0, "min": None, "max": None, "total": 0, "histogram": {}}
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "total": sum(values),
            "histogram": _histogram(values),
        }

    payload: dict[str, Any] = {
        "schema_version": SEMANTIC_CONFLICT_DIAGNOSTIC_SCHEMA_VERSION,
        "scope_count": len(ordered),
        "scopes_with_conflict": scopes_with_conflict,
        "diagnostic_record_ids": [item.record_id for item in ordered],
        "semantic_status_counts": _sorted_counts(statuses),
        "semantic_record_reason_code_counts": _sorted_counts(record_codes),
        "conflict_observations_total": conflicts_total,
        "conflict_family_observation_counts": _sorted_counts(family_counts),
        "conflict_family_scope_counts": _sorted_counts(family_scope_counts),
        "dominant_conflict_families_by_observations": _dominant(family_counts),
        "dominant_conflict_families_by_scopes": _dominant(family_scope_counts),
        "conflict_path_observation_counts": _sorted_counts(obs_paths),
        "conflict_path_scope_counts": _sorted_counts(scope_paths),
        "conflict_path_exclusive_observation_counts": _sorted_counts(exclusive),
        "conflict_path_combination_counts": _sorted_counts(combos),
        "dominant_conflict_paths_by_observations": _dominant(obs_paths),
        "dominant_conflict_paths_by_scopes": _dominant(scope_paths),
        "conflict_disposition_reason_code_counts": _sorted_counts(disposition_codes),
        "conflict_visible_reason_code_counts": _sorted_counts(visible_codes),
        "ambiguous_candidates_per_conflict": stats(candidates_per_conflict),
        "ambiguous_candidate_relation_counts": _sorted_counts(relations),
        "ambiguous_proven_openings_per_observation": {
            str(key): proven_per_conflict[key] for key in sorted(proven_per_conflict)
        },
        "ambiguous_candidate_pair_shared_observations": {
            str(key): pair_shares[key] for key in sorted(pair_shares)
        },
        "conflict_clusters": {
            "count": len(cluster_obs),
            "observations_per_cluster": stats(cluster_obs),
            "candidates_per_cluster": stats(cluster_cands),
        },
        "residual_observations_total": residuals_total,
        "residual_path_counts": _sorted_counts(residual_paths),
        "residual_disposition_reason_code_counts": _sorted_counts(residual_codes),
        "closure": {
            "pages_assessed": closure_pages,
            "pages_incomplete": closure_incomplete_pages,
            "unresolved_candidates": closure_unresolved_candidates,
            "unresolved_observations": closure_unresolved_observations,
        },
        "proven_openings_total": openings_total,
        "proven_openings_with_unresolvable_representative": representative_unresolved_total,
        "unresolvable_representative_reason_code_counts": _sorted_counts(
            representative_codes
        ),
        "unattributed_observations": unattributed,
        "unavailable_scope_counts": _sorted_counts(unavailable),
        "commercial_authority_granted": False,
    }
    payload["record_id"] = stable_contract_id(
        "semantic_conflict_diagnostic_summary", payload, digest_chars=32
    )
    return payload


__all__ = [
    "CONFLICT_PATHS",
    "CONFLICT_PATH_AMBIGUOUS_CANDIDATES",
    "CONFLICT_PATH_CLOSURE_UNRESOLVED_OVERLAP",
    "CONFLICT_PATH_DISPOSITION_CONFLICT_OTHER",
    "CONFLICT_PATH_LINEAGE_MISMATCH",
    "CONFLICT_PATH_SNAPSHOT_INTEGRITY_FAILURE",
    "CONFLICT_PATH_SOURCE_OBSERVATION_FAILURE",
    "CONFLICT_PATH_UNATTRIBUTED",
    "FAMILY_AMBIGUOUS_CANDIDATES",
    "FAMILY_CLOSURE_UNRESOLVED_OVERLAP",
    "FAMILY_OTHER",
    "FAMILY_SOURCE_OBSERVATION_FAILURE",
    "ConflictCluster",
    "ConflictObservation",
    "DispositionEvidence",
    "ObservationEvidence",
    "PageClosureEvidence",
    "RELATION_NOT_APPLICABLE",
    "RELATION_NO_PROVEN_OPENING",
    "RELATION_ONE_PROVEN_OPENING_PLUS_COMPETITOR",
    "RELATION_SHARED_BETWEEN_PROVEN_OPENINGS",
    "RELATION_UNAVAILABLE",
    "RESIDUAL_PATHS",
    "RepresentativeExistenceEvidence",
    "ResidualObservation",
    "SEMANTIC_CONFLICT_DIAGNOSTIC_SCHEMA_VERSION",
    "STATIC_UNAVAILABLE",
    "SemanticConflictDiagnostic",
    "aggregate_semantic_conflict_diagnostics",
    "collect_semantic_conflict_diagnostic",
    "collect_semantic_scope",
    "diagnose_semantic_conflicts",
]
