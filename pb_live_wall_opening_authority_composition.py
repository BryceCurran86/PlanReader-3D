"""Source-owned live wall/opening authority composition.

This module composes already-reviewed producer boundaries without inventing
commercial identities or quantities.  It proves page-scoped physical walls,
semantic physical openings, and exact opening->host bindings from one immutable
SourceVisibilityProducer snapshot.

It also composes the already-reviewed source-authenticated semantic opening
inventory into OpeningUniverseCompletenessAuthority. It intentionally stops
before opening voids, deduction applicability, gross wall geometry, net-wall
union, wall-role aggregation, or commercial publication. Those later
propositions remain independently fail-closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_host_binding_authority import (
    OpeningHostBindingAuthority,
    OpeningHostBindingProducer,
    OpeningHostBindingResult,
    OpeningHostBindingSelector,
    OpeningHostWallUniverseProducer,
    OpeningHostWallUniverseSelector,
)
from pb_opening_host_frame_authority import (
    OpeningHostFrameAuthority,
    OpeningHostFrameProducer,
    OpeningHostFrameSelector,
)
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseCompletenessResult,
    OpeningUniverseSelector,
)
from pb_opening_universe_completeness_source_adapter import (
    build_semantic_opening_inventory_completeness,
)
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_semantic_opening_enumeration_authority import (
    SemanticOpeningEnumerationAuthority,
    SemanticOpeningEnumerationProducer,
    SemanticOpeningEnumerationResult,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


LIVE_WALL_OPENING_COMPOSITION_SCHEMA_VERSION = "1.0.0"
LIVE_WALL_OPENING_COMPOSITION_RESOLVED = "live_wall_opening_composition_resolved"
LIVE_WALL_OPENING_COMPOSITION_PARTIAL = "live_wall_opening_composition_partial"
LIVE_WALL_OPENING_COMPOSITION_UNAVAILABLE = "live_wall_opening_composition_unavailable"


@dataclass(frozen=True)
class LiveOpeningHostTrace:
    opening_identity_id: Optional[str]
    representative_observation_id: str
    page_id: Optional[str]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record_id: Optional[str]
    host_wall_id: Optional[str]
    member_wall_candidate_ids: tuple[str, ...]


@dataclass(frozen=True)
class LiveOpeningHostFrameTrace:
    opening_identity_id: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record_id: Optional[str]
    host_wall_id: Optional[str]
    whole_wall_candidate_ids: tuple[str, ...]


@dataclass(frozen=True)
class LiveWallScopeTrace:
    page_id: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    scope_complete: bool
    wall_candidate_ids: tuple[str, ...]


@dataclass(frozen=True)
class LiveWallOpeningAuthorityComposition:
    revision_id: str
    page_ids: tuple[str, ...]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    semantic_enumeration_result: SemanticOpeningEnumerationResult
    opening_universe_result: OpeningUniverseCompletenessResult
    opening_universe_results: Mapping[str, OpeningUniverseCompletenessResult]
    wall_scopes: tuple[LiveWallScopeTrace, ...]
    opening_bindings: tuple[LiveOpeningHostTrace, ...]
    host_frames: tuple[LiveOpeningHostFrameTrace, ...]
    physical_wall_candidate_authority: PhysicalWallCandidateAuthority
    physical_opening_authority: PhysicalOpeningAuthority
    semantic_opening_enumeration_authority: SemanticOpeningEnumerationAuthority
    opening_universe_completeness_authority: OpeningUniverseCompletenessAuthority
    opening_universe_completeness_authorities: Mapping[
        str, OpeningUniverseCompletenessAuthority
    ]
    opening_host_binding_authority: OpeningHostBindingAuthority
    opening_host_frame_authority: OpeningHostFrameAuthority
    binding_selectors: Mapping[str, OpeningHostBindingSelector]
    host_frame_selectors: Mapping[str, OpeningHostFrameSelector]
    schema_version: str = LIVE_WALL_OPENING_COMPOSITION_SCHEMA_VERSION


def _clean_page_ids(page_ids: Sequence[str]) -> tuple[str, ...]:
    cleaned = tuple(
        sorted(
            {str(page_id).strip() for page_id in page_ids if str(page_id).strip()},
            key=lambda value: (0, int(value)) if value.isdigit() else (1, value),
        )
    )
    if not cleaned:
        raise ValueError("page_ids must contain at least one source page")
    return cleaned


def compose_live_wall_opening_authority(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    revision_id: str,
    page_ids: Sequence[str],
) -> LiveWallOpeningAuthorityComposition:
    """Compose exact source-owned wall/opening host authority for source pages.

    Page ids are addressing only.  Every wall, opening, equivalence relation,
    completeness state, and host proposition is re-derived by producer-owned
    authorities from the immutable source snapshot.
    """
    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")
    revision_id = str(revision_id or "").strip()
    if not revision_id:
        raise ValueError("revision_id must be non-empty")
    selected_pages = _clean_page_ids(page_ids)

    published = source_visibility_producer.published_snapshot_for_revision(revision_id)
    if published is None:
        raise ValueError(LIVE_WALL_OPENING_COMPOSITION_UNAVAILABLE)

    wall_producer = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source_visibility_producer,
        page_ids=selected_pages,
    )
    wall_authority = wall_producer.authority()
    host_universe_authority = (
        OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(
            wall_authority
        ).authority()
    )

    physical_opening_authority = PhysicalOpeningAuthority(
        source_visibility_producer.authority()
    )
    semantic_producer = (
        SemanticOpeningEnumerationProducer.from_source_visibility_producer(
            source_visibility_producer
        )
    )
    semantic_scope_id = stable_contract_id(
        "live_wall_opening_scope",
        {
            "document_id": published.revision.document_id,
            "revision_id": published.revision.revision_id,
            "source_sha256": published.revision.source_sha256,
            "snapshot_id": published.snapshot.snapshot_id,
            "page_ids": list(selected_pages),
        },
        digest_chars=24,
    )
    semantic_result = semantic_producer.publish_page_scope(
        revision_id=revision_id,
        decision_scope_id=semantic_scope_id,
        page_ids=selected_pages,
    )
    opening_universe_authority = build_semantic_opening_inventory_completeness(
        source_visibility_producer=source_visibility_producer,
        revision_id=revision_id,
        decision_scope_id=semantic_scope_id,
        page_ids=selected_pages,
    )
    opening_universe_result = opening_universe_authority.resolve(
        OpeningUniverseSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            decision_scope_id=semantic_scope_id,
        )
    )

    # PhysicalWallCandidateAuthority owns the canonical page decision scope
    # "wall-source:page-{page_id}". PhysicalOpeningVoidAuthority requires
    # completeness, host binding, and void selectors to share that exact scope
    # identity, so publish one source-authenticated semantic opening inventory
    # completeness record per selected page under the producer-owned wall scope.
    page_opening_universe_authorities: dict[
        str, OpeningUniverseCompletenessAuthority
    ] = {}
    page_opening_universe_results: dict[
        str, OpeningUniverseCompletenessResult
    ] = {}
    for page_id in selected_pages:
        page_scope_id = f"wall-source:page-{page_id}"
        page_authority = build_semantic_opening_inventory_completeness(
            source_visibility_producer=source_visibility_producer,
            revision_id=revision_id,
            decision_scope_id=page_scope_id,
            page_ids=(page_id,),
        )
        page_result = page_authority.resolve(
            OpeningUniverseSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                decision_scope_id=page_scope_id,
            )
        )
        page_opening_universe_authorities[page_id] = page_authority
        page_opening_universe_results[page_id] = page_result

    binding_producer = OpeningHostBindingProducer.from_authorities(
        physical_opening_authority=physical_opening_authority,
        host_wall_universe_authority=host_universe_authority,
    )

    wall_traces: list[LiveWallScopeTrace] = []
    for page_id in selected_pages:
        wall_result = wall_authority.resolve_scope(
            PhysicalWallCandidateSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id=page_id,
                decision_scope_id=f"wall-source:page-{page_id}",
            )
        )
        wall_traces.append(
            LiveWallScopeTrace(
                page_id=page_id,
                status=wall_result.status,
                reason_codes=tuple(wall_result.reason_codes),
                scope_complete=bool(wall_result.scope_complete),
                wall_candidate_ids=tuple(
                    record.wall_candidate_id for record in wall_result.records
                ),
            )
        )

    opening_traces: list[LiveOpeningHostTrace] = []
    binding_selectors: dict[str, OpeningHostBindingSelector] = {}
    opening_observation_selectors: dict[str, ObservationSelector] = {}
    record = semantic_result.record
    representative_ids = (
        tuple(record.representative_observation_ids)
        if record is not None
        else ()
    )
    for observation_id in representative_ids:
        obs_selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        existence = physical_opening_authority.prove_existence(obs_selector)
        opening_record = existence.existence_record
        if opening_record is None:
            opening_traces.append(
                LiveOpeningHostTrace(
                    opening_identity_id=None,
                    representative_observation_id=observation_id,
                    page_id=None,
                    status=existence.status,
                    reason_codes=tuple(existence.reason_codes),
                    record_id=None,
                    host_wall_id=None,
                    member_wall_candidate_ids=(),
                )
            )
            continue

        page_id = str(opening_record.page_id)
        if page_id not in selected_pages:
            opening_traces.append(
                LiveOpeningHostTrace(
                    opening_identity_id=opening_record.record_id,
                    representative_observation_id=observation_id,
                    page_id=page_id,
                    status=EvidenceResolutionStatus.CONFLICT,
                    reason_codes=("opening_outside_selected_source_scope",),
                    record_id=None,
                    host_wall_id=None,
                    member_wall_candidate_ids=(),
                )
            )
            continue

        universe_selector = OpeningHostWallUniverseSelector(
            document_id=opening_record.document_id,
            revision_id=opening_record.revision_id,
            source_sha256=opening_record.source_sha256,
            snapshot_id=opening_record.snapshot_id,
            page_id=page_id,
            decision_scope_id=f"wall-source:page-{page_id}",
        )
        result: OpeningHostBindingResult = binding_producer.publish(
            opening_left_selector=obs_selector,
            opening_right_selector=obs_selector,
            host_universe_selector=universe_selector,
        )
        bound_record = result.record
        opening_traces.append(
            LiveOpeningHostTrace(
                opening_identity_id=opening_record.record_id,
                representative_observation_id=observation_id,
                page_id=page_id,
                status=result.status,
                reason_codes=tuple(result.reason_codes),
                record_id=bound_record.record_id if bound_record is not None else None,
                host_wall_id=bound_record.host_wall_id if bound_record is not None else None,
                member_wall_candidate_ids=(
                    tuple(bound_record.member_wall_candidate_ids)
                    if bound_record is not None
                    else ()
                ),
            )
        )
        opening_observation_selectors[opening_record.record_id] = obs_selector
        binding_selectors[opening_record.record_id] = OpeningHostBindingSelector(
            document_id=opening_record.document_id,
            revision_id=opening_record.revision_id,
            source_sha256=opening_record.source_sha256,
            snapshot_id=opening_record.snapshot_id,
            page_id=page_id,
            decision_scope_id=universe_selector.decision_scope_id,
            opening_identity_id=opening_record.record_id,
        )

    binding_authority = binding_producer.authority()
    frame_producer = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=physical_opening_authority,
        host_binding_authority=binding_authority,
        physical_wall_candidate_authority=wall_authority,
    )
    host_frame_traces: list[LiveOpeningHostFrameTrace] = []
    host_frame_selectors: dict[str, OpeningHostFrameSelector] = {}
    for opening_identity_id, binding_selector in binding_selectors.items():
        observation_selector = opening_observation_selectors[opening_identity_id]
        frame_result = frame_producer.publish(
            opening_selector=observation_selector,
            host_binding_selector=binding_selector,
        )
        evidence = frame_result.evidence
        frame_selector = OpeningHostFrameSelector(
            document_id=binding_selector.document_id,
            revision_id=binding_selector.revision_id,
            source_sha256=binding_selector.source_sha256,
            snapshot_id=binding_selector.snapshot_id,
            page_id=binding_selector.page_id,
            decision_scope_id=binding_selector.decision_scope_id,
            opening_identity_id=binding_selector.opening_identity_id,
        )
        host_frame_selectors[opening_identity_id] = frame_selector
        host_frame_traces.append(
            LiveOpeningHostFrameTrace(
                opening_identity_id=opening_identity_id,
                status=frame_result.status,
                reason_codes=tuple(frame_result.reason_codes),
                record_id=evidence.record_id if evidence is not None else None,
                host_wall_id=evidence.host_wall_id if evidence is not None else None,
                whole_wall_candidate_ids=(
                    tuple(evidence.whole_wall_candidate_ids)
                    if evidence is not None
                    else ()
                ),
            )
        )
    host_frame_authority = frame_producer.authority()
    has_wall_failure = any(
        trace.status is not EvidenceResolutionStatus.CORROBORATED
        or not trace.scope_complete
        or not trace.wall_candidate_ids
        for trace in wall_traces
    )
    has_binding_failure = any(
        trace.status is not EvidenceResolutionStatus.CORROBORATED
        or trace.record_id is None
        for trace in opening_traces
    )
    has_frame_failure = any(
        trace.status is not EvidenceResolutionStatus.CORROBORATED
        or trace.record_id is None
        for trace in host_frame_traces
    )
    semantic_unavailable = semantic_result.record is None
    opening_universe_unavailable = any(
        result.status is not EvidenceResolutionStatus.CORROBORATED
        or result.record is None
        or not bool(result.decision_scope_complete)
        for result in page_opening_universe_results.values()
    )
    if semantic_unavailable:
        status = EvidenceResolutionStatus.ABSTAINED
        reasons = (
            LIVE_WALL_OPENING_COMPOSITION_UNAVAILABLE,
            *tuple(semantic_result.reason_codes),
        )
    elif (
        opening_universe_unavailable
        or has_wall_failure
        or has_binding_failure
        or has_frame_failure
    ):
        status = (
            EvidenceResolutionStatus.CONFLICT
            if (
                semantic_result.status is EvidenceResolutionStatus.CONFLICT
                or any(
                    result.status is EvidenceResolutionStatus.CONFLICT
                    for result in page_opening_universe_results.values()
                )
                or any(t.status is EvidenceResolutionStatus.CONFLICT for t in opening_traces)
                or any(t.status is EvidenceResolutionStatus.CONFLICT for t in wall_traces)
            )
            else EvidenceResolutionStatus.ABSTAINED
        )
        reasons = (
            LIVE_WALL_OPENING_COMPOSITION_PARTIAL,
            *tuple(semantic_result.reason_codes),
            *(
                reason
                for result in page_opening_universe_results.values()
                for reason in result.reason_codes
            ),
            *(reason for trace in wall_traces for reason in trace.reason_codes),
            *(reason for trace in opening_traces for reason in trace.reason_codes),
            *(reason for trace in host_frame_traces for reason in trace.reason_codes),
        )
    else:
        status = EvidenceResolutionStatus.CORROBORATED
        reasons = (
            LIVE_WALL_OPENING_COMPOSITION_RESOLVED,
            *tuple(semantic_result.reason_codes),
        )

    return LiveWallOpeningAuthorityComposition(
        revision_id=revision_id,
        page_ids=selected_pages,
        status=status,
        reason_codes=tuple(dict.fromkeys(reasons)),
        semantic_enumeration_result=semantic_result,
        opening_universe_result=opening_universe_result,
        opening_universe_results=MappingProxyType(
            dict(page_opening_universe_results)
        ),
        wall_scopes=tuple(wall_traces),
        opening_bindings=tuple(opening_traces),
        host_frames=tuple(host_frame_traces),
        physical_wall_candidate_authority=wall_authority,
        physical_opening_authority=physical_opening_authority,
        semantic_opening_enumeration_authority=semantic_producer.authority(),
        opening_universe_completeness_authority=opening_universe_authority,
        opening_universe_completeness_authorities=MappingProxyType(
            dict(page_opening_universe_authorities)
        ),
        opening_host_binding_authority=binding_authority,
        opening_host_frame_authority=host_frame_authority,
        binding_selectors=MappingProxyType(dict(binding_selectors)),
        host_frame_selectors=MappingProxyType(dict(host_frame_selectors)),
    )


__all__ = [
    "LIVE_WALL_OPENING_COMPOSITION_PARTIAL",
    "LIVE_WALL_OPENING_COMPOSITION_RESOLVED",
    "LIVE_WALL_OPENING_COMPOSITION_SCHEMA_VERSION",
    "LIVE_WALL_OPENING_COMPOSITION_UNAVAILABLE",
    "LiveOpeningHostFrameTrace",
    "LiveOpeningHostTrace",
    "LiveWallOpeningAuthorityComposition",
    "LiveWallScopeTrace",
    "compose_live_wall_opening_authority",
]
