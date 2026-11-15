"""Nominated swing hosts bill only after OpeningHostBindingProducer.publish."""
from __future__ import annotations

from dataclasses import replace

from pb_live_opening_area_quantity_publication import _opening_quantity
from pb_live_wall_opening_authority_composition import LiveOpeningHostTrace
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import (
    OpeningHostBindingRecord,
    OpeningHostBindingResult,
)
from pb_source_issued_host_binding_rebind_shadow import (
    apply_issued_opening_host_binding_receipts,
    first_failing_host_publish_gate,
    first_failing_live_host_trace_gate,
    observation_selector_for_opening,
)
from pb_source_unique_swing_opening_host_shadow import apply_source_unique_swing_opening_hosts
from tests.test_live_opening_area_quantity_publication import _composition
from tests.test_source_quarter_swing_opening_kind_shadow import (
    _hosted,
    _quarter_swing_drawings,
)
from tests.test_source_unique_swing_opening_host_shadow import _unhosted


def _issued_result(*, opening_id: str) -> OpeningHostBindingResult:
    record = OpeningHostBindingRecord(
        record_id="opening_host_binding_v3_issuedreceipt000000000000001",
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="a" * 64,
        snapshot_id="snap-1",
        page_id="3",
        decision_scope_id="wall-source:page-3",
        opening_identity_id=opening_id,
        host_wall_id="physical-wall-issued",
        member_wall_candidate_ids=("wall-member-1",),
        member_candidate_identity_ids=("candidate-1",),
        member_equivalence_groups=(("candidate-1",),),
        source_observation_ids=("source-observation-1",),
    )
    return OpeningHostBindingResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("opening_host_binding_resolved",),
        record=record,
    )


def test_blocked_publish_keeps_the_nomination_unbilled() -> None:
    opening = _unhosted(geom=(49.2, 50.0, 52.5, 50.0), kind="door")
    nominated = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
    )
    blocked = OpeningHostBindingResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("authenticated_physical_opening_identity_required",),
    )
    rebound = apply_issued_opening_host_binding_receipts(
        nominated,
        {nominated.canonical_openings[0].physical_opening_id: blocked},
    )
    updated = rebound.canonical_openings[0]
    assert updated.host_wall_id.startswith("opening_host_binding_group_")
    assert updated.host_binding_record_id not in updated.evidence_ids
    assert first_failing_host_publish_gate(blocked) == (
        "authenticated_physical_opening_identity_required"
    )
    billed = replace(
        updated,
        area_m2=1.827,
        area_basis="figured_opening_label",
        figured_area_record_id="figured-1",
    )
    assert _opening_quantity(billed) is None


def test_issued_publish_receipt_replaces_the_nomination() -> None:
    opening = _unhosted(geom=(49.2, 50.0, 52.5, 50.0), kind="door")
    nominated = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
    )
    issued = _issued_result(opening_id=opening.canonical_opening_id)
    rebound = apply_issued_opening_host_binding_receipts(
        nominated,
        {nominated.canonical_openings[0].physical_opening_id: issued},
    )
    updated = rebound.canonical_openings[0]
    assert updated.host_wall_id == "physical-wall-issued"
    assert updated.host_binding_record_id == issued.record.record_id
    assert issued.record.record_id in updated.evidence_ids
    assert first_failing_host_publish_gate(issued) == ""
    selector = observation_selector_for_opening(updated)
    assert selector.observation_id == updated.representative_observation_id
    billed = replace(
        updated,
        area_m2=1.827,
        area_basis="figured_opening_label",
        figured_area_record_id="figured-1",
        evidence_ids=tuple(
            dict.fromkeys((*updated.evidence_ids, "figured-1"))
        ),
    )
    quantity = _opening_quantity(billed)
    assert quantity is not None
    assert quantity.value == 1.827


def test_live_host_trace_reports_the_first_failing_publish_gate() -> None:
    opening = _hosted(geom=(49.2, 50.0, 52.5, 50.0), opening_id="opening-1")
    trace = LiveOpeningHostTrace(
        opening_identity_id=opening.physical_opening_id,
        representative_observation_id=opening.representative_observation_id,
        page_id="3",
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("opening_two_face_wall_lineage_unmapped",),
        record_id=None,
        host_wall_id=None,
        member_wall_candidate_ids=(),
    )
    assert first_failing_live_host_trace_gate(opening, (trace,)) == (
        "opening_two_face_wall_lineage_unmapped"
    )
