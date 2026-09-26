"""Shadow local opening-host authority for incomplete page wall scopes.

The legacy opening host authority requires whole-scope completeness before it
will even evaluate the opening-local host band.  That is correct for global
publication but can be stronger than necessary for the local proposition
"this physical opening belongs to this physical wall".

This shadow authority permits a locally complete host proof only when:
- physical opening existence/identity is producer-owned and corroborated;
- the wall scope is the producer-owned *page* scope (all page primitives have
  been ingested; viewport-cropped scopes are not accepted here);
- wall records and physical-wall equivalence are available;
- exact opening geometry is reconstructable from its source observations;
- the existing host-band resolver returns exactly one band;
- all its existing ambiguity/equivalence/center checks pass.

Global scope completeness is retained as provenance and is never upgraded.
No quantity, deduction, net-wall, finish, or live commercial output is
published by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_host_binding_authority import (
    HOST_BINDING_RESOLVED,
    OpeningHostBindingRecord,
    _opening_geometry,
    _resolve_host_bands,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PHYSICAL_OPENING_IDENTITY_RESOLVED,
    PhysicalOpeningAuthority,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateSelector,
)
from pb_source_observation_authority import ObservationSelector


OPENING_LOCAL_HOST_SCHEMA_VERSION = "1.0.0"
OPENING_LOCAL_HOST_RESOLVED = "opening_local_host_resolved"
OPENING_LOCAL_HOST_UNAVAILABLE = "opening_local_host_unavailable"
OPENING_LOCAL_HOST_PAGE_SCOPE_REQUIRED = "opening_local_host_page_scope_required"
OPENING_LOCAL_HOST_WALL_SCOPE_UNAVAILABLE = "opening_local_host_wall_scope_unavailable"
OPENING_LOCAL_HOST_GEOMETRY_UNAVAILABLE = "opening_local_host_geometry_unavailable"
OPENING_LOCAL_HOST_AMBIGUOUS = "opening_local_host_ambiguous"

_RECORD_SEAL = object()


@dataclass(frozen=True)
class OpeningLocalHostBindingRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    opening_identity_id: str
    host_wall_id: str
    member_wall_candidate_ids: tuple[str, ...]
    member_candidate_identity_ids: tuple[str, ...]
    member_equivalence_groups: tuple[tuple[str, ...], ...]
    source_wall_scope_complete: bool
    source_wall_scope_reason_codes: tuple[str, ...]
    schema_version: str = OPENING_LOCAL_HOST_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("OpeningLocalHostBindingRecord is producer-owned")
        if not self.host_wall_id or not self.member_wall_candidate_ids:
            raise ValueError("positive local host binding requires host members")


@dataclass(frozen=True)
class OpeningLocalHostBindingResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[OpeningLocalHostBindingRecord] = None
    schema_version: str = OPENING_LOCAL_HOST_SCHEMA_VERSION


def _blocked(reason: str, *extra: str, status=EvidenceResolutionStatus.ABSTAINED):
    return OpeningLocalHostBindingResult(
        status=status,
        reason_codes=tuple(dict.fromkeys((reason, *extra))),
        record=None,
    )


def _resolve_local_band_from_page_scope(scope, opening_geometry):
    """Narrow pure helper used by producer and adversarial tests."""
    if getattr(scope, "status", None) is not EvidenceResolutionStatus.CORROBORATED:
        return _blocked(OPENING_LOCAL_HOST_WALL_SCOPE_UNAVAILABLE)
    if str(getattr(scope, "scope_kind", "") or "") != "page":
        return _blocked(OPENING_LOCAL_HOST_PAGE_SCOPE_REQUIRED)
    records = tuple(getattr(scope, "records", ()) or ())
    equivalence = getattr(scope, "equivalence", None)
    if not records or equivalence is None:
        return _blocked(OPENING_LOCAL_HOST_WALL_SCOPE_UNAVAILABLE)

    resolution = _resolve_host_bands(records, opening_geometry, equivalence)
    if resolution.status is not EvidenceResolutionStatus.CORROBORATED:
        return _blocked(
            OPENING_LOCAL_HOST_AMBIGUOUS,
            *resolution.reason_codes,
            status=resolution.status,
        )
    if len(resolution.bands) != 1:
        return _blocked(
            OPENING_LOCAL_HOST_AMBIGUOUS,
            "multiple_authenticated_host_wall_bands"
            if len(resolution.bands) > 1
            else "no_authenticated_host_wall_band",
        )
    return resolution.bands[0]


def prove_local_opening_host(
    *,
    physical_opening_authority: PhysicalOpeningAuthority,
    physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
    opening_selector: ObservationSelector,
    wall_selector: PhysicalWallCandidateSelector,
) -> OpeningLocalHostBindingResult:
    if type(physical_opening_authority) is not PhysicalOpeningAuthority:
        raise TypeError("physical_opening_authority must be producer-owned")
    if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
        raise TypeError("physical_wall_candidate_authority must be producer-owned")
    if type(opening_selector) is not ObservationSelector:
        raise TypeError("opening_selector must be ObservationSelector")
    if type(wall_selector) is not PhysicalWallCandidateSelector:
        raise TypeError("wall_selector must be PhysicalWallCandidateSelector")

    existence = physical_opening_authority.prove_existence(opening_selector)
    identity = physical_opening_authority.compare_identity(
        opening_selector,
        opening_selector,
    )
    opening = existence.existence_record
    if (
        existence.status is not EvidenceResolutionStatus.CORROBORATED
        or existence.proposition != PHYSICAL_OPENING_EXISTS
        or opening is None
        or identity.status is not EvidenceResolutionStatus.CORROBORATED
        or identity.proven_same is not True
        or PHYSICAL_OPENING_IDENTITY_RESOLVED not in identity.reason_codes
    ):
        return _blocked("authenticated_physical_opening_identity_required")

    if (
        wall_selector.document_id != opening.document_id
        or wall_selector.revision_id != opening.revision_id
        or wall_selector.source_sha256 != opening.source_sha256
        or wall_selector.snapshot_id != opening.snapshot_id
        or wall_selector.page_id != opening.page_id
    ):
        return _blocked("opening_host_scope_mismatch")

    geometry = _opening_geometry(physical_opening_authority, opening)
    if geometry is None:
        return _blocked(OPENING_LOCAL_HOST_GEOMETRY_UNAVAILABLE)

    scope = physical_wall_candidate_authority.resolve_scope(wall_selector)
    band = _resolve_local_band_from_page_scope(scope, geometry)
    if isinstance(band, OpeningLocalHostBindingResult):
        return band

    host_wall_id = stable_contract_id(
        "opening_local_host_wall",
        {
            "document_id": opening.document_id,
            "revision_id": opening.revision_id,
            "source_sha256": opening.source_sha256,
            "snapshot_id": opening.snapshot_id,
            "page_id": opening.page_id,
            "decision_scope_id": wall_selector.decision_scope_id,
            "opening_identity_id": opening.record_id,
            "member_wall_candidate_ids": band.member_ids,
            "member_candidate_identity_ids": band.member_candidate_identity_ids,
            "member_equivalence_groups": band.member_equivalence_groups,
        },
        digest_chars=32,
    )
    record = OpeningLocalHostBindingRecord(
        record_id=stable_contract_id(
            "opening_local_host_binding",
            {
                "opening_identity_id": opening.record_id,
                "host_wall_id": host_wall_id,
                "decision_scope_id": wall_selector.decision_scope_id,
            },
            digest_chars=32,
        ),
        document_id=opening.document_id,
        revision_id=opening.revision_id,
        source_sha256=opening.source_sha256,
        snapshot_id=opening.snapshot_id,
        page_id=opening.page_id,
        decision_scope_id=wall_selector.decision_scope_id,
        opening_identity_id=opening.record_id,
        host_wall_id=host_wall_id,
        member_wall_candidate_ids=band.member_ids,
        member_candidate_identity_ids=band.member_candidate_identity_ids,
        member_equivalence_groups=band.member_equivalence_groups,
        source_wall_scope_complete=bool(scope.scope_complete),
        source_wall_scope_reason_codes=tuple(scope.reason_codes),
        _seal=_RECORD_SEAL,
    )
    return OpeningLocalHostBindingResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(OPENING_LOCAL_HOST_RESOLVED,),
        record=record,
    )


__all__ = [
    "OPENING_LOCAL_HOST_AMBIGUOUS",
    "OPENING_LOCAL_HOST_GEOMETRY_UNAVAILABLE",
    "OPENING_LOCAL_HOST_PAGE_SCOPE_REQUIRED",
    "OPENING_LOCAL_HOST_RESOLVED",
    "OPENING_LOCAL_HOST_SCHEMA_VERSION",
    "OPENING_LOCAL_HOST_UNAVAILABLE",
    "OPENING_LOCAL_HOST_WALL_SCOPE_UNAVAILABLE",
    "OpeningLocalHostBindingRecord",
    "OpeningLocalHostBindingResult",
    "prove_local_opening_host",
]
