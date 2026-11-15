"""Replace unique-swing host nominations with OpeningHostBindingProducer receipts.

Generated ``opening_host_binding_group_*`` / ``opening_host_binding_v3_*``
strings are nominations. Quantity publication already refuses them unless the
issued record_id is on evidence. This helper copies a CORROBORATED producer
result onto the matching canonical opening and puts that record_id on
evidence_ids. Blocked publish results stay nominations; they never become
quantities.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Mapping, Sequence

from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject,
    LivePhysicalOpeningVoidComposition,
)
from pb_live_wall_opening_authority_composition import LiveOpeningHostTrace
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import (
    OpeningHostBindingProducer,
    OpeningHostBindingRecord,
    OpeningHostBindingResult,
    OpeningHostWallUniverseSelector,
)
from pb_source_observation_authority import ObservationSelector

NOMINATED_HOST_WALL_PREFIX = "opening_host_binding_group_"
HOST_PUBLISH_IDENTITY_REQUIRED = "authenticated_physical_opening_identity_required"


def first_failing_host_publish_gate(result: OpeningHostBindingResult | None) -> str:
    if result is None:
        return "opening_host_binding_producer_publish_not_called"
    if (
        result.status is EvidenceResolutionStatus.CORROBORATED
        and result.record is not None
        and str(result.record.record_id or "").strip()
        and str(result.record.host_wall_id or "").strip()
    ):
        return ""
    if result.reason_codes:
        return str(result.reason_codes[0])
    return "opening_host_binding_unavailable"


def first_failing_live_host_trace_gate(
    opening: LiveCanonicalOpeningObject,
    traces: Sequence[LiveOpeningHostTrace],
) -> str:
    if type(opening) is not LiveCanonicalOpeningObject:
        raise TypeError("opening must be LiveCanonicalOpeningObject")
    physical_id = str(opening.physical_opening_id or "").strip()
    for trace in traces:
        if str(trace.opening_identity_id or "") != physical_id:
            continue
        if (
            trace.status is EvidenceResolutionStatus.CORROBORATED
            and str(trace.record_id or "").strip()
            and str(trace.host_wall_id or "").strip()
        ):
            return ""
        if trace.reason_codes:
            return str(trace.reason_codes[0])
        return "opening_host_binding_unavailable"
    return "opening_host_trace_missing"


def _result_from_live_host_trace(
    opening: LiveCanonicalOpeningObject,
    traces: Sequence[LiveOpeningHostTrace],
) -> OpeningHostBindingResult | None:
    """Rebuild the producer receipt already on the live wall-opening trace."""
    physical_id = str(opening.physical_opening_id or "").strip()
    for trace in traces:
        if str(trace.opening_identity_id or "") != physical_id:
            continue
        if first_failing_live_host_trace_gate(opening, (trace,)):
            return None
        record_id = str(trace.record_id or "").strip()
        host_wall_id = str(trace.host_wall_id or "").strip()
        record = OpeningHostBindingRecord(
            record_id=record_id,
            document_id=str(opening.document_id),
            revision_id=str(opening.revision_id),
            source_sha256=str(opening.source_sha256),
            snapshot_id=str(opening.snapshot_id),
            page_id=str(opening.page_id),
            decision_scope_id=f"wall-source:page-{opening.page_id}",
            opening_identity_id=physical_id,
            host_wall_id=host_wall_id,
            member_wall_candidate_ids=tuple(trace.member_wall_candidate_ids or ()),
            member_candidate_identity_ids=(),
            member_equivalence_groups=(),
            source_observation_ids=tuple(opening.source_observation_ids or ()),
        )
        return OpeningHostBindingResult(
            status=trace.status,
            reason_codes=tuple(trace.reason_codes),
            record=record,
        )
    return None


def apply_corroborated_live_host_traces(
    composition: LivePhysicalOpeningVoidComposition,
    traces: Sequence[LiveOpeningHostTrace],
) -> LivePhysicalOpeningVoidComposition:
    """Install already-published host traces; do not re-call publish."""
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("composition must be LivePhysicalOpeningVoidComposition")
    issued: dict[str, OpeningHostBindingResult] = {}
    for opening in composition.canonical_openings:
        result = _result_from_live_host_trace(opening, traces)
        if first_failing_host_publish_gate(result):
            continue
        issued[str(opening.physical_opening_id)] = result
    return apply_issued_opening_host_binding_receipts(composition, issued)


def observation_selector_for_opening(
    opening: LiveCanonicalOpeningObject,
) -> ObservationSelector:
    """Document/revision/source/snapshot/observation already owned by the opening."""
    if type(opening) is not LiveCanonicalOpeningObject:
        raise TypeError("opening must be LiveCanonicalOpeningObject")
    observation_id = str(opening.representative_observation_id or "").strip()
    if not observation_id:
        raise ValueError("representative_observation_id required")
    return ObservationSelector(
        document_id=str(opening.document_id),
        revision_id=str(opening.revision_id),
        source_sha256=str(opening.source_sha256),
        snapshot_id=str(opening.snapshot_id),
        observation_id=observation_id,
    )


def apply_issued_opening_host_binding_receipts(
    composition: LivePhysicalOpeningVoidComposition,
    issued_by_physical_id: Mapping[str, OpeningHostBindingResult],
) -> LivePhysicalOpeningVoidComposition:
    """Install producer-issued host receipts; leave blocked nominations unbilled."""
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("composition must be LivePhysicalOpeningVoidComposition")
    updated: dict[str, LiveCanonicalOpeningObject] = {}
    for opening in composition.canonical_openings:
        result = issued_by_physical_id.get(opening.physical_opening_id)
        if result is None:
            result = issued_by_physical_id.get(opening.canonical_opening_id)
        if first_failing_host_publish_gate(result):
            continue
        assert result is not None and result.record is not None
        record = result.record
        evidence_ids = tuple(
            dict.fromkeys((*opening.evidence_ids, record.record_id))
        )
        updated[opening.canonical_opening_id] = replace(
            opening,
            host_wall_id=record.host_wall_id,
            host_binding_record_id=record.record_id,
            evidence_ids=evidence_ids,
        )
    if not updated:
        return composition
    return replace(
        composition,
        canonical_openings=tuple(
            updated.get(item.canonical_opening_id, item)
            for item in composition.canonical_openings
        ),
    )


def republish_nominated_hosts(
    composition: LivePhysicalOpeningVoidComposition,
    producer: OpeningHostBindingProducer,
) -> LivePhysicalOpeningVoidComposition:
    """Retry OpeningHostBindingProducer.publish on unique-swing nominations.

    Left and right selectors are the opening's own representative observation.
    The first failing reason is the producer receipt, not a generated hash.
    """
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("composition must be LivePhysicalOpeningVoidComposition")
    if type(producer) is not OpeningHostBindingProducer:
        raise TypeError("producer must be OpeningHostBindingProducer")
    issued: dict[str, OpeningHostBindingResult] = {}
    for opening in composition.canonical_openings:
        host_wall_id = str(opening.host_wall_id or "")
        if not host_wall_id.startswith(NOMINATED_HOST_WALL_PREFIX):
            continue
        if not str(opening.representative_observation_id or "").strip():
            continue
        selector = observation_selector_for_opening(opening)
        result = producer.publish(
            opening_left_selector=selector,
            opening_right_selector=selector,
            host_universe_selector=OpeningHostWallUniverseSelector(
                document_id=str(opening.document_id),
                revision_id=str(opening.revision_id),
                source_sha256=str(opening.source_sha256),
                snapshot_id=str(opening.snapshot_id),
                page_id=str(opening.page_id),
                decision_scope_id=f"wall-source:page-{opening.page_id}",
            ),
        )
        issued[str(opening.physical_opening_id)] = result
    return apply_issued_opening_host_binding_receipts(composition, issued)
