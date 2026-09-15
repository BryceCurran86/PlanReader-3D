"""Canonical opening identity/universe authority contracts.

This module deliberately does *not* manufacture authority from local query results or
caller metadata.  At the current main-line trust boundary there is no independently
queryable immutable source-atom/graph universe, and there is no independently
inspectable opening-observation lineage producer.  The canonical implementation
therefore exposes that absence as a typed fail-closed state.

The missing upstream capability is a producer which can, for a provenance-bound
scope, independently inspect the immutable source evidence and:

* enumerate every eligible opening/source atom before local radius/filtering;
* enumerate every eligible host candidate before local radius/filtering; and
* resolve observation lineage/identity from traceable evidence IDs.

The producer must bind source SHA, revision, evidence snapshot, graph snapshot,
page, viewport and target evidence/observation IDs.  A local candidate list,
``complete=True`` flag, tag, dimensions, proximity, bbox overlap, confidence,
schedule row, caller identity flag, self-hash or caller lineage claim is not such a
producer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE = (
    "AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE"
)


class IdentityRelation(str, Enum):
    """Authoritative relation between two physical-opening observations."""

    PROVEN_SAME = "PROVEN_SAME"
    PROVEN_DISTINCT = "PROVEN_DISTINCT"
    AMBIGUOUS = "AMBIGUOUS"


class UpstreamUniverseState(str, Enum):
    """Availability of an independently bounded canonical candidate universe."""

    AVAILABLE = "AVAILABLE"
    AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE = (
        AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE
    )


class HostBindingRelation(str, Enum):
    """Authoritative physical relation between an opening and a host."""

    PROVEN_BOUND = "PROVEN_BOUND"
    PROVEN_NOT_BOUND = "PROVEN_NOT_BOUND"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class AuthorityScope:
    """Provenance boundary required for identity/universe decisions."""

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
    """Observation descriptor; caller correlation fields are non-authoritative."""

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
    """Diagnostic/local query result that is explicitly not a completeness proof."""

    scope: AuthorityScope
    candidate_ids: tuple[str, ...]
    caller_complete: bool = False
    radius_mm: float | None = None
    filters: tuple[str, ...] = ()


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
    source itself.  Implementations must not derive completeness from a list supplied
    by the local caller which is asking the completeness question.
    """

    def resolve_identity(
        self, left: OpeningObservation, right: OpeningObservation
    ) -> IdentityDecision:
        """Resolve physical identity from independently inspectable lineage evidence."""

    def enumerate_openings(self, scope: AuthorityScope) -> CandidateUniverseDecision:
        """Enumerate all eligible openings in the independently bounded scope."""

    def enumerate_hosts(
        self, opening: OpeningObservation, scope: AuthorityScope
    ) -> CandidateUniverseDecision:
        """Enumerate all eligible hosts in the independently bounded scope."""

    def bind_host(
        self, opening: OpeningObservation, host_id: str, scope: AuthorityScope
    ) -> HostAuthorityDecision:
        """Prove or reject a host relation from upstream evidence."""


class _UnavailableCanonicalOpeningAuthorityProducer:
    """Current-main implementation: expose the missing trust source, fail closed."""

    _unavailable = (AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE,)

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
        universe = self.enumerate_hosts(opening, scope)
        return HostAuthorityDecision(
            universe=universe,
            binding=HostBindingRelation.AMBIGUOUS,
            authoritative_host_id=None,
            authoritative=False,
            blockers=universe.blockers,
        )


# Intentionally module-owned.  Public quantity/readiness callers cannot inject a
# caller-created producer and thereby move the trust boundary back into themselves.
_CURRENT_CANONICAL_PRODUCER: CanonicalOpeningAuthorityProducer = (
    _UnavailableCanonicalOpeningAuthorityProducer()
)


def combine_identity_relations(
    relations: tuple[IdentityRelation, ...],
) -> IdentityRelation:
    """Combine independently obtained identity relations monotonically.

    Ambiguity or contradiction is absorbing.  Adding evidence therefore cannot turn
    an already ambiguous/contradictory relation into PROVEN_SAME.
    """

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
    """Resolve identity using only the canonical current-main trust source."""

    return _CURRENT_CANONICAL_PRODUCER.resolve_identity(left, right)


def assess_current_opening_universe(
    query: LocalCandidateQuery,
) -> CandidateUniverseDecision:
    """Assess completeness without trusting the local candidate query itself."""

    return _CURRENT_CANONICAL_PRODUCER.enumerate_openings(query.scope)


def assess_current_host_authority(
    opening: OpeningObservation, query: LocalCandidateQuery
) -> HostAuthorityDecision:
    """Assess host universe/binding; local spatial candidates remain nominations."""

    universe = _CURRENT_CANONICAL_PRODUCER.enumerate_hosts(opening, query.scope)
    blockers = list(universe.blockers)
    if not universe.complete:
        blockers.append("opening_host_universe_incomplete")
    return HostAuthorityDecision(
        universe=universe,
        binding=HostBindingRelation.AMBIGUOUS,
        authoritative_host_id=None,
        authoritative=False,
        blockers=tuple(dict.fromkeys(blockers)),
    )


def assess_current_physical_void_authority(
    *,
    opening: OpeningObservation,
    width_mm: float | None,
    height_mm: float | None,
    host_query: LocalCandidateQuery,
    commercial_applicability: bool | None = None,
) -> PhysicalVoidAuthorityDecision:
    """Fail-closed physical-void gate for the current canonical producer.

    ``commercial_applicability`` is accepted solely to make the separation explicit;
    it never participates in physical-geometry authority.
    """

    del commercial_applicability
    blockers: list[str] = []

    if not opening.provenance_complete:
        blockers.append("opening_existence_provenance_incomplete")

    # A physical-identity producer is absent.  Caller identity flags/hashes/lineage
    # metadata on ``opening`` cannot replace it.
    blockers.append("opening_physical_identity_unproven")

    host = assess_current_host_authority(opening, host_query)
    blockers.extend(host.blockers)
    if host.binding is not HostBindingRelation.PROVEN_BOUND:
        blockers.append("opening_host_binding_unproven")

    if width_mm is None or height_mm is None or width_mm <= 0 or height_mm <= 0:
        blockers.append("opening_dimensions_unproven")

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return PhysicalVoidAuthorityDecision(
            firm=False,
            area_m2=None,
            blockers=tuple(blockers),
        )

    # Unreachable with the current canonical producer.  Kept as the dimensional
    # formula only; reaching it requires replacing the module-owned producer with a
    # genuinely independent upstream implementation in a future scoped workstream.
    assert width_mm is not None and height_mm is not None
    return PhysicalVoidAuthorityDecision(
        firm=True,
        area_m2=(width_mm / 1000.0) * (height_mm / 1000.0),
        blockers=(),
    )


def assess_current_physical_net_authority(
    *,
    gross_area_m2: float | None,
    gross_is_firm: bool,
    opening_query: LocalCandidateQuery,
    resolved_void_areas_m2: tuple[float, ...],
) -> PhysicalNetAuthorityDecision:
    """Fail closed until the relevant opening universe is independently complete."""

    blockers: list[str] = []
    if not gross_is_firm or gross_area_m2 is None or gross_area_m2 < 0:
        blockers.append("gross_wall_area_not_firm")

    universe = assess_current_opening_universe(opening_query)
    blockers.extend(universe.blockers)
    if not universe.complete:
        blockers.append("relevant_opening_universe_incomplete")

    if any(area < 0 for area in resolved_void_areas_m2):
        blockers.append("invalid_physical_void_area")

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return PhysicalNetAuthorityDecision(
            firm=False,
            net_area_m2=None,
            gross_preserved=bool(gross_is_firm and gross_area_m2 is not None),
            blockers=tuple(blockers),
        )

    assert gross_area_m2 is not None
    net_area = gross_area_m2 - sum(resolved_void_areas_m2)
    if net_area < 0:
        return PhysicalNetAuthorityDecision(
            firm=False,
            net_area_m2=None,
            gross_preserved=True,
            blockers=("physical_voids_exceed_gross_wall_area",),
        )
    return PhysicalNetAuthorityDecision(
        firm=True,
        net_area_m2=net_area,
        gross_preserved=True,
        blockers=(),
    )
