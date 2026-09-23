"""Live source-owned opening deduction composition.

Composes sealed physical-opening-void authority into source-declared deduction
applicability and opening deduction authority. target_scope_ids are addressing
only; they cannot establish target semantics, rules, host identity, geometry,
or a DEDUCT decision.

This layer intentionally stops before gross-wall geometry, net-wall Boolean
union, commercial publication, and finish propagation.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence

from pb_live_physical_opening_void_composition import LivePhysicalOpeningVoidComposition
from pb_live_wall_opening_authority_composition import LiveWallOpeningAuthorityComposition
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_deduction_applicability_authority import (
    OpeningDeductionApplicabilityAuthority,
    OpeningDeductionApplicabilityProducer,
    OpeningDeductionApplicabilitySelector,
    OpeningDeductionRuleProducer,
    OpeningDeductionTargetScopeProducer,
)
from pb_opening_deduction_authority import (
    OpeningDeductionAuthority,
    OpeningDeductionProducer,
    OpeningDeductionSelector,
)
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingProducer,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


LIVE_OPENING_DEDUCTION_SCHEMA_VERSION = "1.0.0"
LIVE_OPENING_DEDUCTION_RESOLVED = "live_opening_deduction_composition_resolved"
LIVE_OPENING_DEDUCTION_PARTIAL = "live_opening_deduction_composition_partial"
LIVE_OPENING_DEDUCTION_UNAVAILABLE = "live_opening_deduction_composition_unavailable"
LIVE_OPENING_DEDUCTION_UPSTREAM_INCOMPLETE = "live_opening_deduction_upstream_incomplete"


@dataclass(frozen=True)
class LiveOpeningDeductionTrace:
    opening_identity_id: str
    target_scope_id: str
    page_id: str
    decision_scope_id: str
    target_status: EvidenceResolutionStatus
    target_record_id: str | None
    rule_status: EvidenceResolutionStatus
    rule_record_id: str | None
    applicability_status: EvidenceResolutionStatus
    applicability_record_id: str | None
    deduction_status: EvidenceResolutionStatus
    deduction_reason_codes: tuple[str, ...]
    deduction_record_id: str | None


@dataclass(frozen=True)
class LiveOpeningDeductionComposition:
    revision_id: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    target_scope_ids: tuple[str, ...]
    traces: tuple[LiveOpeningDeductionTrace, ...]
    applicability_authorities: Mapping[str, OpeningDeductionApplicabilityAuthority]
    deduction_authorities: Mapping[str, OpeningDeductionAuthority]
    deduction_selectors: Mapping[tuple[str, str], OpeningDeductionSelector]
    schema_version: str = LIVE_OPENING_DEDUCTION_SCHEMA_VERSION


def _reasons(values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def _targets(values: Sequence[str]) -> tuple[str, ...]:
    result = tuple(sorted({str(value).strip() for value in values if str(value).strip()}))
    if not result:
        raise ValueError("target_scope_ids must contain at least one address")
    return result


def compose_live_opening_deductions(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    wall_opening_composition: LiveWallOpeningAuthorityComposition,
    physical_void_composition: LivePhysicalOpeningVoidComposition,
    target_scope_ids: Sequence[str],
) -> LiveOpeningDeductionComposition:
    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")
    if type(wall_opening_composition) is not LiveWallOpeningAuthorityComposition:
        raise TypeError("wall_opening_composition must be LiveWallOpeningAuthorityComposition")
    if type(physical_void_composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("physical_void_composition must be LivePhysicalOpeningVoidComposition")

    targets = _targets(target_scope_ids)
    revision_id = wall_opening_composition.revision_id
    if physical_void_composition.revision_id != revision_id:
        return LiveOpeningDeductionComposition(
            revision_id,
            EvidenceResolutionStatus.CONFLICT,
            (LIVE_OPENING_DEDUCTION_UPSTREAM_INCOMPLETE,),
            targets,
            (),
            MappingProxyType({}),
            MappingProxyType({}),
            MappingProxyType({}),
        )

    published = source_visibility_producer.published_snapshot_for_revision(revision_id)
    if published is None:
        return LiveOpeningDeductionComposition(
            revision_id,
            EvidenceResolutionStatus.ABSTAINED,
            (LIVE_OPENING_DEDUCTION_UNAVAILABLE,),
            targets,
            (),
            MappingProxyType({}),
            MappingProxyType({}),
            MappingProxyType({}),
        )

    schedule = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(
        source_visibility_producer
    )
    traces_by_opening = {
        trace.opening_identity_id: trace for trace in physical_void_composition.traces
    }
    for opening_id, trace in traces_by_opening.items():
        binding_selector = wall_opening_composition.binding_selectors.get(opening_id)
        if binding_selector is None:
            continue
        schedule.publish_scope(
            opening_selector=ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=trace.representative_observation_id,
            ),
            decision_scope_id=binding_selector.decision_scope_id,
        )

    selectors: list[OpeningDeductionApplicabilitySelector] = []
    for opening_id, trace in sorted(traces_by_opening.items()):
        binding_selector = wall_opening_composition.binding_selectors.get(opening_id)
        if binding_selector is None:
            continue
        for target_scope_id in targets:
            selectors.append(
                OpeningDeductionApplicabilitySelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    page_id=trace.page_id,
                    decision_scope_id=binding_selector.decision_scope_id,
                    opening_identity_id=opening_id,
                    target_scope_id=target_scope_id,
                )
            )

    if not selectors:
        return LiveOpeningDeductionComposition(
            revision_id,
            EvidenceResolutionStatus.ABSTAINED,
            (LIVE_OPENING_DEDUCTION_UNAVAILABLE, LIVE_OPENING_DEDUCTION_UPSTREAM_INCOMPLETE),
            targets,
            (),
            MappingProxyType({}),
            MappingProxyType({}),
            MappingProxyType({}),
        )

    target = OpeningDeductionTargetScopeProducer.from_authorities(
        source_visibility_producer=source_visibility_producer,
        schedule_binding_authority=schedule.authority(),
        host_binding_authority=wall_opening_composition.opening_host_binding_authority,
    )
    target_results = {selector.key: target.publish(selector) for selector in selectors}

    rule = OpeningDeductionRuleProducer.from_source_visibility_producer(
        source_visibility_producer,
        target_scope_authority=target.authority(),
    )
    rule_results = {selector.key: rule.publish(selector) for selector in selectors}

    app_producers: dict[str, OpeningDeductionApplicabilityProducer] = {}
    app_results = {}
    for selector in selectors:
        producer = app_producers.get(selector.page_id)
        if producer is None:
            void_authority = physical_void_composition.physical_opening_void_authorities.get(
                selector.page_id
            )
            if void_authority is None:
                continue
            producer = OpeningDeductionApplicabilityProducer.from_authorities(
                physical_void_authority=void_authority,
                host_binding_authority=wall_opening_composition.opening_host_binding_authority,
                target_scope_authority=target.authority(),
                rule_authority=rule.authority(),
            )
            app_producers[selector.page_id] = producer
        app_results[selector.key] = producer.publish(selector)

    app_authorities = {
        page_id: producer.authority() for page_id, producer in app_producers.items()
    }
    deduction_producers: dict[str, OpeningDeductionProducer] = {}
    deduction_results = {}
    deduction_selectors: dict[tuple[str, str], OpeningDeductionSelector] = {}

    for selector in selectors:
        app_authority = app_authorities.get(selector.page_id)
        void_authority = physical_void_composition.physical_opening_void_authorities.get(
            selector.page_id
        )
        universe_authority = (
            wall_opening_composition.opening_universe_completeness_authorities.get(
                selector.page_id
            )
        )
        if app_authority is None or void_authority is None or universe_authority is None:
            continue

        producer = deduction_producers.get(selector.page_id)
        if producer is None:
            producer = OpeningDeductionProducer.from_authorities(
                physical_void_authority=void_authority,
                host_binding_authority=wall_opening_composition.opening_host_binding_authority,
                opening_universe_authority=universe_authority,
                target_applicability_authority=app_authority,
            )
            deduction_producers[selector.page_id] = producer

        deduction_selector = OpeningDeductionSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            opening_identity_id=selector.opening_identity_id,
            target_scope_id=selector.target_scope_id,
        )
        deduction_selectors[(selector.opening_identity_id, selector.target_scope_id)] = (
            deduction_selector
        )
        deduction_results[selector.key] = producer.publish(deduction_selector)

    out_traces: list[LiveOpeningDeductionTrace] = []
    for selector in selectors:
        target_result = target_results.get(selector.key)
        rule_result = rule_results.get(selector.key)
        app_result = app_results.get(selector.key)
        deduction_result = deduction_results.get(selector.key)
        target_record = getattr(target_result, "record", None)
        rule_record = getattr(rule_result, "record", None)
        app_record = getattr(app_result, "record", None)
        deduction_record = getattr(deduction_result, "record", None)
        out_traces.append(
            LiveOpeningDeductionTrace(
                opening_identity_id=selector.opening_identity_id,
                target_scope_id=selector.target_scope_id,
                page_id=selector.page_id,
                decision_scope_id=selector.decision_scope_id,
                target_status=getattr(
                    target_result, "status", EvidenceResolutionStatus.ABSTAINED
                ),
                target_record_id=getattr(target_record, "record_id", None),
                rule_status=getattr(
                    rule_result, "status", EvidenceResolutionStatus.ABSTAINED
                ),
                rule_record_id=getattr(rule_record, "record_id", None),
                applicability_status=getattr(
                    app_result, "status", EvidenceResolutionStatus.ABSTAINED
                ),
                applicability_record_id=getattr(app_record, "record_id", None),
                deduction_status=getattr(
                    deduction_result, "status", EvidenceResolutionStatus.ABSTAINED
                ),
                deduction_reason_codes=_reasons(
                    getattr(
                        deduction_result,
                        "reason_codes",
                        ("opening_deduction_unavailable",),
                    )
                ),
                deduction_record_id=getattr(deduction_record, "record_id", None),
            )
        )

    expected_pairs = {
        (opening_id, target_scope_id)
        for opening_id in traces_by_opening
        for target_scope_id in targets
    }
    traced_pairs = {
        (trace.opening_identity_id, trace.target_scope_id) for trace in out_traces
    }
    upstream_complete = (
        physical_void_composition.status is EvidenceResolutionStatus.CORROBORATED
        and traced_pairs == expected_pairs
    )
    all_resolved = upstream_complete and all(
        trace.deduction_status is EvidenceResolutionStatus.CORROBORATED
        and trace.deduction_record_id is not None
        for trace in out_traces
    )
    has_conflict = any(
        trace.applicability_status is EvidenceResolutionStatus.CONFLICT
        or trace.deduction_status is EvidenceResolutionStatus.CONFLICT
        for trace in out_traces
    )

    if all_resolved:
        status = EvidenceResolutionStatus.CORROBORATED
        reasons = (LIVE_OPENING_DEDUCTION_RESOLVED,)
    elif has_conflict:
        status = EvidenceResolutionStatus.CONFLICT
        reasons = (
            LIVE_OPENING_DEDUCTION_PARTIAL,
            *(reason for trace in out_traces for reason in trace.deduction_reason_codes),
        )
    else:
        status = EvidenceResolutionStatus.ABSTAINED
        reasons = (
            LIVE_OPENING_DEDUCTION_PARTIAL,
            *((LIVE_OPENING_DEDUCTION_UPSTREAM_INCOMPLETE,) if not upstream_complete else ()),
            *(reason for trace in out_traces for reason in trace.deduction_reason_codes),
        )

    return LiveOpeningDeductionComposition(
        revision_id=revision_id,
        status=status,
        reason_codes=_reasons(reasons),
        target_scope_ids=targets,
        traces=tuple(out_traces),
        applicability_authorities=MappingProxyType(dict(app_authorities)),
        deduction_authorities=MappingProxyType(
            {
                page_id: producer.authority()
                for page_id, producer in deduction_producers.items()
            }
        ),
        deduction_selectors=MappingProxyType(dict(deduction_selectors)),
    )


__all__ = [
    "LIVE_OPENING_DEDUCTION_PARTIAL",
    "LIVE_OPENING_DEDUCTION_RESOLVED",
    "LIVE_OPENING_DEDUCTION_SCHEMA_VERSION",
    "LIVE_OPENING_DEDUCTION_UNAVAILABLE",
    "LIVE_OPENING_DEDUCTION_UPSTREAM_INCOMPLETE",
    "LiveOpeningDeductionComposition",
    "LiveOpeningDeductionTrace",
    "compose_live_opening_deductions",
]
