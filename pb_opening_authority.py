"""Canonical opening identity/universe authority contracts.

This module deliberately does not manufacture authority from local query results or
caller metadata. Current main has provenance identifiers, but no independently
queryable immutable source-atom/graph universe and no independently inspectable
opening-observation lineage producer. The canonical implementation therefore
exposes that absence as a typed fail-closed state.

The missing upstream capability is a producer which can, for a provenance-bound
scope, independently inspect immutable source evidence and:

* prove an opening observation exists in that source scope;
* resolve observation lineage/physical identity from traceable evidence IDs;
* prove opening dimensions from traceable source evidence;
* enumerate every eligible opening before local radius/filtering;
* enumerate every eligible host before local radius/filtering; and
* prove host identity and host binding independently of spatial nomination.

It must bind source SHA, revision, evidence snapshot, graph snapshot, page, viewport,
evidence IDs and target observations. A local candidate list, ``complete=True``,
tag, dimensions, proximity, bbox overlap, confidence, schedule row, caller identity
flag, caller lineage claim or caller-created self-hash is not authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE = (
    "AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE"
)


class IdentityRelation(str, Enum):
    PROVEN_SAME = "PROVEN_SAME"
    PROVEN_DISTINCT = "PROVEN_DISTINCT"
    AMBIGUOUS = "AMBIGUOUS"


class UpstreamUniverseState(str, Enum):
    AVAILABLE = "AVAILABLE"
    AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE = (
        AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE
    )


class HostBindingRelation(str, Enum):
    PROVEN_BOUND = "PROVEN_BOUND"
    PROVEN_NOT_BOUND = "PROVEN_NOT_BOUND"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class AuthorityScope:
    source_sha256: str
    source_revision_id: str
    evidence_snapshot_id: str
    canonical_graph_snapshot_id: str
    page_index: int
    viewport_id: str

    @property
    def provenance_complete(self) -> bool:
        return bool(
            self.source_sha256
            and self.source_revision_id
            and self.evidence_snapshot_id
            and self.canonical_graph_snapshot_id
            and self.page_index >= 0
            and self.viewport_id
        )


@dataclass(frozen=True)
class OpeningObservation:
    """Observation descriptor; correlation fields remain non-authoritative."""

    observation_id: str
    scope: AuthorityScope
    evidence_ids: tuple[str, ...]
    tag: str | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    x: float | None = None
    y: float | None = None
    caller_identity_proven: bool = False
    caller_self_hash: str | None = None
    caller_lineage_ids: tuple[str, ...] = ()

    @property
    def provenance_complete(self) -> bool:
        return bool(
            self.observation_id
            and self.scope.provenance_complete
            and self.evidence_ids
            and all(self.evidence_ids)
        )


@dataclass(frozen=True)
class LocalCandidateQuery:
    """Diagnostic/local query result; never a completeness proof."""

    scope: AuthorityScope
    candidate_ids: tuple[str, ...]
    caller_complete: bool = False
    radius_mm: float | None = None
    filters: tuple[str, ...] = ()


@dataclass(frozen=True)
class OpeningExistenceDecision:
    proven: bool
    authoritative_observation_id: str | None = None
    evidence_ids: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class OpeningDimensionsDecision:
    proven: bool
    width_mm: float | None = None
    height_mm: float | None = None
    evidence_ids: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class IdentityDecision:
    relation: IdentityRelation
    authoritative: bool
    evidence_ids: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateUniverseDecision:
    state: UpstreamUniverseState
    complete: bool
    authoritative_candidate_ids: tuple[str, ...]
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class HostAuthorityDecision:
    universe: CandidateUniverseDecision
    host_identity: IdentityRelation
    binding: HostBindingRelation
    authoritative_host_id: str | None
    authoritative: bool
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class PhysicalVoidAuthorityDecision:
    firm: bool
    area_m2: float | None
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class PhysicalNetAuthorityDecision:
    firm: bool
    net_area_m2: float | None
    gross_preserved: bool
    blockers: tuple[str, ...]


class CanonicalOpeningAuthorityProducer(Protocol):
    """Required future trust-boundary interface.

    A conforming implementation must inspect an upstream immutable evidence/graph
    source itself. It must not derive completeness, identity, existence or dimensions
    from the local caller asking the question.
    """

    def prove_opening_existence(
        self, observation: OpeningObservation
    ) -> OpeningExistenceDecision:
        """Prove the observation exists in the independently bounded source scope."""

    def identify_opening(self, observation: OpeningObservation) -> IdentityDecision:
        """Relate the observation to a canonical physical opening using lineage."""

    def resolve_identity(
        self, left: OpeningObservation, right: OpeningObservation
    ) -> IdentityDecision:
        """Resolve SAME/DISTINCT/AMBIGUOUS from independently inspected evidence."""

    def prove_opening_dimensions(
        self,
        observation: OpeningObservation,
        claimed_width_mm: float | None,
        claimed_height_mm: float | None,
    ) -> OpeningDimensionsDecision:
        """Resolve dimensions from independent evidence, not caller numbers alone."""

    def enumerate_openings(self, scope: AuthorityScope) -> CandidateUniverseDecision:
        """Enumerate all eligible openings in the independently bounded scope."""

    def enumerate_hosts(
        self, opening: OpeningObservation, scope: AuthorityScope
    ) -> CandidateUniverseDecision:
        """Enumerate all eligible hosts in the independently bounded scope."""

    def bind_host(
        self, opening: OpeningObservation, host_id: str, scope: AuthorityScope
    ) -> HostAuthorityDecision:
        """Prove host identity and physical binding from upstream evidence."""


class _UnavailableCanonicalOpeningAuthorityProducer:
    """Current-main producer: expose missing upstream authority and fail closed."""

    _unavailable = (AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE,)

    def prove_opening_existence(
        self, observation: OpeningObservation
    ) -> OpeningExistenceDecision:
        blockers = list(self._unavailable)
        if not observation.provenance_complete:
            blockers.append("opening_existence_provenance_incomplete")
        return OpeningExistenceDecision(proven=False, blockers=tuple(blockers))

    def identify_opening(self, observation: OpeningObservation) -> IdentityDecision:
        blockers = list(self._unavailable)
        if not observation.provenance_complete:
            blockers.append("opening_identity_provenance_incomplete")
        return IdentityDecision(
            relation=IdentityRelation.AMBIGUOUS,
            authoritative=False,
            blockers=tuple(blockers),
        )

    def resolve_identity(
        self, left: OpeningObservation, right: OpeningObservation
    ) -> IdentityDecision:
        blockers = list(self._unavailable)
        if not left.provenance_complete or not right.provenance_complete:
            blockers.append("opening_identity_provenance_incomplete")
        return IdentityDecision(
            relation=IdentityRelation.AMBIGUOUS,
            authoritative=False,
            blockers=tuple(blockers),
        )

    def prove_opening_dimensions(
        self,
        observation: OpeningObservation,
        claimed_width_mm: float | None,
        claimed_height_mm: float | None,
    ) -> OpeningDimensionsDecision:
        blockers = list(self._unavailable)
        if not observation.provenance_complete:
            blockers.append("opening_dimension_provenance_incomplete")
        if (
            claimed_width_mm is None
            or claimed_height_mm is None
            or claimed_width_mm <= 0
            or claimed_height_mm <= 0
        ):
            blockers.append("opening_dimensions_missing_or_invalid")
        return OpeningDimensionsDecision(proven=False, blockers=tuple(blockers))

    def enumerate_openings(self, scope: AuthorityScope) -> CandidateUniverseDecision:
        blockers = list(self._unavailable)
        if not scope.provenance_complete:
            blockers.append("opening_universe_scope_provenance_incomplete")
        return CandidateUniverseDecision(
            state=UpstreamUniverseState.AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE,
            complete=False,
            authoritative_candidate_ids=(),
            blockers=tuple(blockers),
        )

    def enumerate_hosts(
        self, opening: OpeningObservation, scope: AuthorityScope
    ) -> CandidateUniverseDecision:
        blockers = list(self._unavailable)
        if not opening.provenance_complete or not scope.provenance_complete:
            blockers.append("host_universe_scope_provenance_incomplete")
        return CandidateUniverseDecision(
            state=UpstreamUniverseState.AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE,
            complete=False,
            authoritative_candidate_ids=(),
            blockers=tuple(blockers),
        )

    def bind_host(
        self, opening: OpeningObservation, host_id: str, scope: AuthorityScope
    ) -> HostAuthorityDecision:
        del host_id
        universe = self.enumerate_hosts(opening, scope)
        return HostAuthorityDecision(
            universe=universe,
            host_identity=IdentityRelation.AMBIGUOUS,
            binding=HostBindingRelation.AMBIGUOUS,
            authoritative_host_id=None,
            authoritative=False,
            blockers=universe.blockers,
        )


# Module-owned on purpose: public quantity callers cannot inject a caller-created
# producer and thereby move the trust boundary back into themselves.
_CURRENT_CANONICAL_PRODUCER: CanonicalOpeningAuthorityProducer = (
    _UnavailableCanonicalOpeningAuthorityProducer()
)


def combine_identity_relations(
    relations: tuple[IdentityRelation, ...],
) -> IdentityRelation:
    """Combine independently proven relations; ambiguity/contradiction is absorbing."""

    if not relations or IdentityRelation.AMBIGUOUS in relations:
        return IdentityRelation.AMBIGUOUS
    unique = set(relations)
    if unique == {IdentityRelation.PROVEN_SAME}:
        return IdentityRelation.PROVEN_SAME
    if unique == {IdentityRelation.PROVEN_DISTINCT}:
        return IdentityRelation.PROVEN_DISTINCT
    return IdentityRelation.AMBIGUOUS


def resolve_current_opening_identity(
    left: OpeningObservation, right: OpeningObservation
) -> IdentityDecision:
    return _CURRENT_CANONICAL_PRODUCER.resolve_identity(left, right)


def assess_current_opening_universe(
    query: LocalCandidateQuery,
) -> CandidateUniverseDecision:
    # Local candidates, filters, radius and caller_complete are deliberately excluded
    # from the canonical producer's proof inputs.
    return _CURRENT_CANONICAL_PRODUCER.enumerate_openings(query.scope)


def assess_current_host_authority(
    opening: OpeningObservation, query: LocalCandidateQuery
) -> HostAuthorityDecision:
    """Keep nomination, universe, identity and binding as separate authority axes."""

    universe = _CURRENT_CANONICAL_PRODUCER.enumerate_hosts(opening, query.scope)
    blockers = list(universe.blockers)
    if not universe.complete:
        blockers.append("opening_host_universe_incomplete")
        return HostAuthorityDecision(
            universe=universe,
            host_identity=IdentityRelation.AMBIGUOUS,
            binding=HostBindingRelation.AMBIGUOUS,
            authoritative_host_id=None,
            authoritative=False,
            blockers=tuple(dict.fromkeys(blockers)),
        )

    if len(universe.authoritative_candidate_ids) != 1:
        blockers.append("opening_host_not_unique")
        return HostAuthorityDecision(
            universe=universe,
            host_identity=IdentityRelation.AMBIGUOUS,
            binding=HostBindingRelation.AMBIGUOUS,
            authoritative_host_id=None,
            authoritative=False,
            blockers=tuple(dict.fromkeys(blockers)),
        )

    host_id = universe.authoritative_candidate_ids[0]
    return _CURRENT_CANONICAL_PRODUCER.bind_host(opening, host_id, query.scope)


def assess_current_physical_void_authority(
    *,
    opening: OpeningObservation,
    width_mm: float | None,
    height_mm: float | None,
    host_query: LocalCandidateQuery,
    commercial_applicability: bool | None = None,
) -> PhysicalVoidAuthorityDecision:
    """Physical geometry gate; commercial applicability is deliberately downstream."""

    del commercial_applicability
    blockers: list[str] = []

    opening_universe = _CURRENT_CANONICAL_PRODUCER.enumerate_openings(opening.scope)
    blockers.extend(opening_universe.blockers)
    if not opening_universe.complete:
        blockers.append("relevant_opening_universe_incomplete")

    existence = _CURRENT_CANONICAL_PRODUCER.prove_opening_existence(opening)
    blockers.extend(existence.blockers)
    if not existence.proven:
        blockers.append("opening_existence_unproven")

    identity = _CURRENT_CANONICAL_PRODUCER.identify_opening(opening)
    blockers.extend(identity.blockers)
    if not identity.authoritative or identity.relation is not IdentityRelation.PROVEN_SAME:
        blockers.append("opening_physical_identity_unproven")

    host = assess_current_host_authority(opening, host_query)
    blockers.extend(host.blockers)
    if host.host_identity is not IdentityRelation.PROVEN_SAME:
        blockers.append("opening_host_identity_unproven")
    if host.binding is not HostBindingRelation.PROVEN_BOUND:
        blockers.append("opening_host_binding_unproven")

    dimensions = _CURRENT_CANONICAL_PRODUCER.prove_opening_dimensions(
        opening,
        width_mm,
        height_mm,
    )
    blockers.extend(dimensions.blockers)
    if not dimensions.proven:
        blockers.append("opening_dimensions_unproven")

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return PhysicalVoidAuthorityDecision(False, None, tuple(blockers))

    assert dimensions.width_mm is not None and dimensions.height_mm is not None
    return PhysicalVoidAuthorityDecision(
        True,
        (dimensions.width_mm / 1000.0) * (dimensions.height_mm / 1000.0),
        (),
    )


def assess_current_physical_net_authority(
    *,
    gross_area_m2: float | None,
    gross_is_firm: bool,
    opening_query: LocalCandidateQuery,
    resolved_void_areas_m2: tuple[float, ...],
) -> PhysicalNetAuthorityDecision:
    """Preserve FIRM gross while net fails closed on incomplete opening authority."""

    blockers: list[str] = []
    if not gross_is_firm or gross_area_m2 is None or gross_area_m2 < 0:
        blockers.append("gross_wall_area_not_firm")

    universe = assess_current_opening_universe(opening_query)
    blockers.extend(universe.blockers)
    if not universe.complete:
        blockers.append("relevant_opening_universe_incomplete")

    if any(area < 0 for area in resolved_void_areas_m2):
        blockers.append("invalid_physical_void_area")

    # A safe positive net path also needs authoritative opening-id -> FIRM-void
    # coverage. A caller tuple of areas cannot prove that every material opening was
    # resolved, even after an upstream universe producer becomes available.
    if universe.complete:
        blockers.append("authoritative_void_coverage_mapping_unavailable")

    blockers = list(dict.fromkeys(blockers))
    return PhysicalNetAuthorityDecision(
        firm=False,
        net_area_m2=None,
        gross_preserved=bool(
            gross_is_firm and gross_area_m2 is not None and gross_area_m2 >= 0
        ),
        blockers=tuple(blockers),
    )
