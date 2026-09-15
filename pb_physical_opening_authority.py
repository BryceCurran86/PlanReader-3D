"""G17 phase-2 physical-opening semantic authority boundary.

Phase 1 can prove that an immutable producer-owned source observation exists and
is bound to exact PDF bytes.  That is deliberately weaker than proving that the
observation denotes a physical opening in the building.

The current repository has no independent source-native physical-opening entity
producer.  Native PDF vectors/text, OCR, CV, schedules, tags, dimensions,
coordinates, proximity, hashes, candidate lists and corroboration flags are all
insufficient to bridge that semantic gap.  Consequently this module is
intentionally fail-closed: it validates the Phase-1 selector through the trusted
source-observation reader and then returns a typed upstream-capability blocker.

No positive physical-opening existence or identity path is implemented here.
Later work may replace this blocker only when a genuinely producer-owned,
inspectable semantic source is available.  Universe completeness, dimensions,
host binding, physical void and net wall area remain out of scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import (
    ObservationSelector,
    SourceObservationAuthority,
    SourceObservationAuthorityResult,
)


PHYSICAL_OPENING_EXISTENCE_UNRESOLVED = "physical_opening_existence_unresolved"
PHYSICAL_OPENING_IDENTITY_UNRESOLVED = "physical_opening_identity_unresolved"

AUTHORITATIVE_PHYSICAL_OPENING_SEMANTICS_UNAVAILABLE = (
    "authoritative_physical_opening_semantics_unavailable"
)
AUTHORITATIVE_PHYSICAL_OPENING_IDENTITY_UNAVAILABLE = (
    "authoritative_physical_opening_identity_unavailable"
)
MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY = (
    "independent source-native physical opening instance semantic producer"
)


@dataclass(frozen=True)
class PhysicalOpeningExistenceResult:
    """Fail-closed result for the physical-opening existence proposition."""

    status: EvidenceResolutionStatus
    proposition: Optional[str]
    physical_opening_existence: str
    reason_codes: tuple[str, ...]
    source_observation: Optional[SourceObservationAuthorityResult] = None
    missing_upstream_capability: Optional[str] = None


@dataclass(frozen=True)
class PhysicalOpeningIdentityResult:
    """Fail-closed result for whether two observations denote one opening."""

    status: EvidenceResolutionStatus
    physical_opening_identity: str
    proven_same: bool
    reason_codes: tuple[str, ...]
    left_source_observation: Optional[SourceObservationAuthorityResult] = None
    right_source_observation: Optional[SourceObservationAuthorityResult] = None
    missing_upstream_capability: Optional[str] = None


def _dedupe_reason_codes(*groups: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    for group in groups:
        for reason in group:
            clean = str(reason or "").strip()
            if clean and clean not in result:
                result.append(clean)
    return tuple(result)


def _source_failure_status(*results: SourceObservationAuthorityResult) -> EvidenceResolutionStatus:
    if any(result.status is EvidenceResolutionStatus.CONFLICT for result in results):
        return EvidenceResolutionStatus.CONFLICT
    return EvidenceResolutionStatus.ABSTAINED


class PhysicalOpeningAuthority:
    """Read-only Phase-2 consumer over a genuine Phase-1 authority reader.

    The constructor intentionally requires the concrete Phase-1 reader rather
    than a duck-typed object.  That prevents ordinary callers from injecting a
    fake ``resolve`` implementation that simply returns a fabricated
    ``CORROBORATED`` record.  As with Phase 1, equal-privilege Python code is not
    treated as a cryptographic security boundary.
    """

    def __init__(self, source_observation_authority: SourceObservationAuthority) -> None:
        if type(source_observation_authority) is not SourceObservationAuthority:
            raise TypeError(
                "source_observation_authority must be the concrete producer-owned "
                "SourceObservationAuthority reader"
            )
        self._source_observation_authority = source_observation_authority

    @staticmethod
    def capabilities() -> dict[str, bool]:
        """Declare the propositions this fail-closed Phase-2 slice can establish."""

        return {
            "physical_opening_existence": False,
            "physical_opening_identity": False,
            "opening_universe_complete": False,
            "opening_dimensions": False,
            "host_identity": False,
            "host_binding": False,
            "physical_void": False,
            "net_wall_area": False,
        }

    def prove_existence(self, selector: ObservationSelector) -> PhysicalOpeningExistenceResult:
        """Resolve source lineage, then abstain because physical semantics are absent."""

        if not isinstance(selector, ObservationSelector):
            raise TypeError("selector must be ObservationSelector")

        source_result = self._source_observation_authority.resolve(selector)
        if source_result.status is not EvidenceResolutionStatus.CORROBORATED:
            return PhysicalOpeningExistenceResult(
                status=_source_failure_status(source_result),
                proposition=None,
                physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                reason_codes=_dedupe_reason_codes(source_result.reason_codes),
                source_observation=source_result,
                missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
            )

        # A byte-backed source observation is necessary provenance, not semantic
        # proof that a physical opening exists.  Do not inspect text, geometry,
        # observation kind, confidence, schedule role or any caller metadata here.
        return PhysicalOpeningExistenceResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            proposition=None,
            physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
            reason_codes=(AUTHORITATIVE_PHYSICAL_OPENING_SEMANTICS_UNAVAILABLE,),
            source_observation=source_result,
            missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
        )

    def compare_identity(
        self,
        left_selector: ObservationSelector,
        right_selector: ObservationSelector,
    ) -> PhysicalOpeningIdentityResult:
        """Never infer physical identity from observation equality or similarity."""

        if not isinstance(left_selector, ObservationSelector):
            raise TypeError("left_selector must be ObservationSelector")
        if not isinstance(right_selector, ObservationSelector):
            raise TypeError("right_selector must be ObservationSelector")

        left = self._source_observation_authority.resolve(left_selector)
        right = self._source_observation_authority.resolve(right_selector)
        if (
            left.status is not EvidenceResolutionStatus.CORROBORATED
            or right.status is not EvidenceResolutionStatus.CORROBORATED
        ):
            return PhysicalOpeningIdentityResult(
                status=_source_failure_status(left, right),
                physical_opening_identity=PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
                proven_same=False,
                reason_codes=_dedupe_reason_codes(left.reason_codes, right.reason_codes),
                left_source_observation=left,
                right_source_observation=right,
                missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
            )

        # Even the exact same source observation can only prove source-observation
        # identity.  It cannot prove that the source observation corresponds to a
        # physical opening, much less establish a reusable physical-opening ID.
        return PhysicalOpeningIdentityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            physical_opening_identity=PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
            proven_same=False,
            reason_codes=(AUTHORITATIVE_PHYSICAL_OPENING_IDENTITY_UNAVAILABLE,),
            left_source_observation=left,
            right_source_observation=right,
            missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
        )


__all__ = [
    "AUTHORITATIVE_PHYSICAL_OPENING_IDENTITY_UNAVAILABLE",
    "AUTHORITATIVE_PHYSICAL_OPENING_SEMANTICS_UNAVAILABLE",
    "MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY",
    "PHYSICAL_OPENING_EXISTENCE_UNRESOLVED",
    "PHYSICAL_OPENING_IDENTITY_UNRESOLVED",
    "PhysicalOpeningAuthority",
    "PhysicalOpeningExistenceResult",
    "PhysicalOpeningIdentityResult",
]
