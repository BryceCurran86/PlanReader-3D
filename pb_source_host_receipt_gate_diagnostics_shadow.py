"""Which gate stops an opening getting a producer-issued host receipt (read-only, donor piece C').

The two functions come from the closed 3Laurel stack's host-rebind module
(donor commit e01626e2c), without its single-host nomination, which the owner's
two-wall opening rule withdrew. They only read results and traces: they bind no
host, write no record and publish nothing.
"""
from __future__ import annotations

from collections.abc import Sequence

from pb_live_physical_opening_void_composition import LiveCanonicalOpeningObject
from pb_live_wall_opening_authority_composition import LiveOpeningHostTrace
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import OpeningHostBindingResult


def first_failing_host_publish_gate(result: OpeningHostBindingResult | None) -> str:
    """Empty when the result is a corroborated producer receipt; else the first reason it is not."""
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
    """The first gate of the opening's own live host trace; a trace is never itself a receipt."""
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
