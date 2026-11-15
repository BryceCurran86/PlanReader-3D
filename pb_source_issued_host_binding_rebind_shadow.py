"""Replace unique-swing host nominations with OpeningHostBindingProducer receipts.

Generated ``opening_host_binding_group_*`` / ``opening_host_binding_v3_*``
strings are nominations. Quantity publication already refuses them unless the
issued record_id is on evidence. This helper resolves the sealed
``OpeningHostBindingAuthority`` with a complete target selector, keeps the
producer receipt unchanged, and puts that record_id on evidence_ids. Caller
maps, reconstructed traces, and foreign/forged records stay nominations; they
never become quantities.
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
    OpeningHostBindingAuthority,
    OpeningHostBindingProducer,
    OpeningHostBindingRecord,
    OpeningHostBindingResult,
    OpeningHostBindingSelector,
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
    page_id = str(opening.page_id or "").strip()
    observation_id = str(opening.representative_observation_id or "").strip()
    for trace in traces:
        if str(trace.opening_identity_id or "") != physical_id:
            continue
        if str(trace.page_id or "").strip() != page_id:
            return "opening_host_trace_page_mismatch"
        if str(trace.representative_observation_id or "").strip() != observation_id:
            return "opening_host_trace_observation_mismatch"
        if (
            trace.status is EvidenceResolutionStatus.CORROBORATED
            and str(trace.record_id or "").strip()
            and str(trace.host_wall_id or "").strip()
        ):
            return "opening_host_trace_not_producer_receipt"
        if trace.reason_codes:
            return str(trace.reason_codes[0])
        return "opening_host_binding_unavailable"
    return "opening_host_trace_missing"


def binding_selector_for_opening(
    opening: LiveCanonicalOpeningObject,
) -> OpeningHostBindingSelector:
    """Complete target scope already owned by the canonical opening."""
    if type(opening) is not LiveCanonicalOpeningObject:
        raise TypeError("opening must be LiveCanonicalOpeningObject")
    physical_id = str(opening.physical_opening_id or "").strip()
    if not physical_id:
        raise ValueError("physical_opening_id required")
    return OpeningHostBindingSelector(
        document_id=str(opening.document_id),
        revision_id=str(opening.revision_id),
        source_sha256=str(opening.source_sha256),
        snapshot_id=str(opening.snapshot_id),
        page_id=str(opening.page_id),
        decision_scope_id=f"wall-source:page-{opening.page_id}",
        opening_identity_id=physical_id,
    )


def _receipt_matches_opening(
    record: OpeningHostBindingRecord,
    opening: LiveCanonicalOpeningObject,
) -> bool:
    opening_ids = {
        str(opening.physical_opening_id or "").strip(),
        str(opening.canonical_opening_id or "").strip(),
    }
    opening_ids.discard("")
    if str(record.opening_identity_id) not in opening_ids:
        return False
    if (
        str(record.document_id) != str(opening.document_id)
        or str(record.revision_id) != str(opening.revision_id)
        or str(record.source_sha256) != str(opening.source_sha256)
        or str(record.snapshot_id) != str(opening.snapshot_id)
        or str(record.page_id) != str(opening.page_id)
        or str(record.decision_scope_id) != f"wall-source:page-{opening.page_id}"
    ):
        return False
    record_obs = {
        str(item).strip() for item in record.source_observation_ids if str(item).strip()
    }
    opening_obs = {
        str(item).strip() for item in opening.source_observation_ids if str(item).strip()
    }
    representative = str(opening.representative_observation_id or "").strip()
    if representative:
        opening_obs.add(representative)
    if not record_obs or record_obs.isdisjoint(opening_obs):
        return False
    if not tuple(record.member_wall_candidate_ids):
        return False
    if not tuple(record.member_candidate_identity_ids):
        return False
    if not tuple(record.member_equivalence_groups):
        return False
    return True


def _selector_matches_opening(
    selector: OpeningHostBindingSelector,
    opening: LiveCanonicalOpeningObject,
) -> bool:
    try:
        expected = binding_selector_for_opening(opening)
    except ValueError:
        return False
    return selector == expected


def apply_corroborated_live_host_traces(
    composition: LivePhysicalOpeningVoidComposition,
    traces: Sequence[LiveOpeningHostTrace],
    *,
    authority: OpeningHostBindingAuthority | None = None,
    binding_selectors: Mapping[str, OpeningHostBindingSelector] | None = None,
) -> LivePhysicalOpeningVoidComposition:
    """Install already-published host receipts. Trace strings are not issuance."""
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("composition must be LivePhysicalOpeningVoidComposition")
    if traces is not None and not isinstance(traces, Sequence):
        raise TypeError("traces must be a sequence")
    if authority is None:
        return composition
    if type(authority) is not OpeningHostBindingAuthority:
        raise TypeError("authority must be OpeningHostBindingAuthority")
    return apply_issued_opening_host_binding_receipts(
        composition,
        authority,
        binding_selectors=binding_selectors,
    )


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
    authority: OpeningHostBindingAuthority,
    *,
    binding_selectors: Mapping[str, OpeningHostBindingSelector] | None = None,
) -> LivePhysicalOpeningVoidComposition:
    """Install producer-issued host receipts; leave blocked nominations unbilled."""
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("composition must be LivePhysicalOpeningVoidComposition")
    if type(authority) is not OpeningHostBindingAuthority:
        raise TypeError("authority must be OpeningHostBindingAuthority")
    updated: dict[str, LiveCanonicalOpeningObject] = {}
    for opening in composition.canonical_openings:
        try:
            selector = binding_selector_for_opening(opening)
        except ValueError:
            continue
        if binding_selectors:
            mapped = binding_selectors.get(opening.physical_opening_id)
            if mapped is None:
                mapped = binding_selectors.get(opening.canonical_opening_id)
            if mapped is not None and not _selector_matches_opening(mapped, opening):
                continue
        result = authority.resolve(selector)
        if first_failing_host_publish_gate(result):
            continue
        assert result is not None and result.record is not None
        record = result.record
        if not _receipt_matches_opening(record, opening):
            continue
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
    Issued receipts are then resolved from producer.authority(), never from a
    caller-keyed result map.
    """
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("composition must be LivePhysicalOpeningVoidComposition")
    if type(producer) is not OpeningHostBindingProducer:
        raise TypeError("producer must be OpeningHostBindingProducer")
    for opening in composition.canonical_openings:
        host_wall_id = str(opening.host_wall_id or "")
        if not host_wall_id.startswith(NOMINATED_HOST_WALL_PREFIX):
            continue
        if not str(opening.representative_observation_id or "").strip():
            continue
        selector = observation_selector_for_opening(opening)
        producer.publish(
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
    return apply_issued_opening_host_binding_receipts(
        composition,
        producer.authority(),
    )
