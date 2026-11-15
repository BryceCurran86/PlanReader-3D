"""Nominated swing hosts bill only after OpeningHostBindingProducer.publish."""
from __future__ import annotations

from dataclasses import replace

from pb_live_opening_area_quantity_publication import _opening_quantity
from pb_live_wall_opening_authority_composition import LiveOpeningHostTrace
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import (
    OpeningHostBindingAuthority,
    OpeningHostBindingProducer,
    OpeningHostBindingRecord,
    OpeningHostBindingResult,
    OpeningHostBindingSelector,
)
from pb_source_issued_host_binding_rebind_shadow import (
    apply_corroborated_live_host_traces,
    apply_issued_opening_host_binding_receipts,
    binding_selector_for_opening,
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

GARAGE_PHYSICAL_ID = "physical_opening_existence_7220ac0bd0217f3dbd2508939d4dc1b3"
GARAGE_RECORD_ID = "opening_host_binding_v3_ced53157aaaaaaaaaaaaaaaaaaaaaaaa"


def _issued_result(*, opening_id: str, **overrides: object) -> OpeningHostBindingResult:
    payload = dict(
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
    payload.update(overrides)
    record = OpeningHostBindingRecord(**payload)
    return OpeningHostBindingResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("opening_host_binding_resolved",),
        record=record,
    )


def _authority_for(
    opening,
    result: OpeningHostBindingResult,
) -> OpeningHostBindingAuthority:
    selector = binding_selector_for_opening(opening)
    producer = object.__new__(OpeningHostBindingProducer)
    producer._results = {
        (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.page_id,
            selector.decision_scope_id,
            selector.opening_identity_id,
        ): result
    }
    return producer.authority()


def _billed(opening):
    return replace(
        opening,
        area_m2=1.827,
        area_basis="figured_opening_label",
        figured_area_record_id="figured-1",
        evidence_ids=tuple(dict.fromkeys((*opening.evidence_ids, "figured-1"))),
    )


def test_blocked_publish_keeps_the_nomination_unbilled() -> None:
    opening = _unhosted(geom=(49.2, 50.0, 52.5, 50.0), kind="door")
    nominated = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
        drawing_viewport_id_by_page_id={"3": "vp-floor-1"},
    )
    blocked = OpeningHostBindingResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("authenticated_physical_opening_identity_required",),
    )
    rebound = apply_issued_opening_host_binding_receipts(
        nominated,
        _authority_for(nominated.canonical_openings[0], blocked),
    )
    updated = rebound.canonical_openings[0]
    assert updated.host_wall_id.startswith("opening_host_binding_group_")
    assert updated.host_binding_record_id not in updated.evidence_ids
    assert first_failing_host_publish_gate(blocked) == (
        "authenticated_physical_opening_identity_required"
    )
    assert _opening_quantity(_billed(updated)) is None


def test_issued_publish_receipt_replaces_the_nomination() -> None:
    opening = _unhosted(geom=(49.2, 50.0, 52.5, 50.0), kind="door")
    nominated = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
        drawing_viewport_id_by_page_id={"3": "vp-floor-1"},
    )
    target = nominated.canonical_openings[0]
    issued = _issued_result(opening_id=target.physical_opening_id)
    rebound = apply_issued_opening_host_binding_receipts(
        nominated,
        _authority_for(target, issued),
    )
    updated = rebound.canonical_openings[0]
    assert updated.host_wall_id == "physical-wall-issued"
    assert updated.host_binding_record_id == issued.record.record_id
    assert issued.record.record_id in updated.evidence_ids
    assert first_failing_host_publish_gate(issued) == ""
    selector = observation_selector_for_opening(updated)
    assert selector.observation_id == updated.representative_observation_id
    quantity = _opening_quantity(_billed(updated))
    assert quantity is not None
    assert quantity.value == 1.827


def test_foreign_document_receipt_stays_unbilled() -> None:
    opening = _unhosted(geom=(49.2, 50.0, 52.5, 50.0), kind="door")
    nominated = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
        drawing_viewport_id_by_page_id={"3": "vp-floor-1"},
    )
    target = nominated.canonical_openings[0]
    foreign = _issued_result(
        opening_id=target.physical_opening_id,
        document_id="other-document",
        revision_id="other-revision",
        source_sha256="b" * 64,
        snapshot_id="other-snap",
        page_id="19",
        decision_scope_id="wall-source:page-19",
        opening_identity_id="physical_opening_existence_other",
        host_wall_id="foreign-wall",
    )
    rebound = apply_issued_opening_host_binding_receipts(
        nominated,
        _authority_for(target, foreign),
    )
    updated = rebound.canonical_openings[0]
    assert updated.host_wall_id.startswith("opening_host_binding_group_")
    assert foreign.record.record_id not in updated.evidence_ids
    assert _opening_quantity(_billed(updated)) is None


def test_foreign_selector_does_not_install_a_target_receipt() -> None:
    opening = _unhosted(geom=(49.2, 50.0, 52.5, 50.0), kind="door")
    nominated = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
        drawing_viewport_id_by_page_id={"3": "vp-floor-1"},
    )
    target = nominated.canonical_openings[0]
    issued = _issued_result(opening_id=target.physical_opening_id)
    foreign_selector = OpeningHostBindingSelector(
        document_id="other-document",
        revision_id="other-revision",
        source_sha256="b" * 64,
        snapshot_id="other-snap",
        page_id="19",
        decision_scope_id="wall-source:page-19",
        opening_identity_id="physical_opening_existence_other",
    )
    rebound = apply_issued_opening_host_binding_receipts(
        nominated,
        _authority_for(target, issued),
        binding_selectors={target.physical_opening_id: foreign_selector},
    )
    updated = rebound.canonical_openings[0]
    assert updated.host_wall_id.startswith("opening_host_binding_group_")
    assert issued.record.record_id not in updated.evidence_ids
    assert _opening_quantity(_billed(updated)) is None


def test_trace_only_host_strings_stay_unbilled() -> None:
    opening = _unhosted(geom=(49.2, 50.0, 52.5, 50.0), kind="door")
    nominated = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
        drawing_viewport_id_by_page_id={"3": "vp-floor-1"},
    )
    issued = _issued_result(opening_id=nominated.canonical_openings[0].physical_opening_id)
    trace = LiveOpeningHostTrace(
        opening_identity_id=nominated.canonical_openings[0].physical_opening_id,
        representative_observation_id=nominated.canonical_openings[0].representative_observation_id,
        page_id="3",
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("opening_host_binding_resolved",),
        record_id=issued.record.record_id,
        host_wall_id=issued.record.host_wall_id,
        member_wall_candidate_ids=issued.record.member_wall_candidate_ids,
    )
    rebound = apply_corroborated_live_host_traces(nominated, (trace,))
    updated = rebound.canonical_openings[0]
    assert updated.host_wall_id.startswith("opening_host_binding_group_")
    assert issued.record.record_id not in updated.evidence_ids
    assert first_failing_live_host_trace_gate(
        nominated.canonical_openings[0], (trace,)
    ) == "opening_host_trace_not_producer_receipt"
    assert _opening_quantity(_billed(updated)) is None


def test_wrong_page_trace_is_not_a_receipt() -> None:
    opening = _unhosted(geom=(49.2, 50.0, 52.5, 50.0), kind="door")
    nominated = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
        drawing_viewport_id_by_page_id={"3": "vp-floor-1"},
    )
    target = nominated.canonical_openings[0]
    trace = LiveOpeningHostTrace(
        opening_identity_id=target.physical_opening_id,
        representative_observation_id="other-observation",
        page_id="19",
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("opening_host_binding_resolved",),
        record_id="opening_host_binding_v3_forged",
        host_wall_id="forged-wall",
        member_wall_candidate_ids=("forged-member",),
    )
    assert first_failing_live_host_trace_gate(target, (trace,)) == (
        "opening_host_trace_page_mismatch"
    )
    rebound = apply_corroborated_live_host_traces(nominated, (trace,))
    assert rebound.canonical_openings[0].host_wall_id.startswith(
        "opening_host_binding_group_"
    )


def test_empty_member_lineage_receipt_stays_unbilled() -> None:
    opening = _unhosted(geom=(49.2, 50.0, 52.5, 50.0), kind="door")
    nominated = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
        drawing_viewport_id_by_page_id={"3": "vp-floor-1"},
    )
    target = nominated.canonical_openings[0]
    reconstructed = _issued_result(
        opening_id=target.physical_opening_id,
        member_candidate_identity_ids=(),
        member_equivalence_groups=(),
        source_observation_ids=tuple(target.source_observation_ids),
    )
    rebound = apply_issued_opening_host_binding_receipts(
        nominated,
        _authority_for(target, reconstructed),
    )
    updated = rebound.canonical_openings[0]
    assert reconstructed.record.record_id not in updated.evidence_ids
    assert _opening_quantity(_billed(updated)) is None


def test_garage_source_positive_receipt_bills() -> None:
    opening = replace(
        _unhosted(geom=(49.2, 50.0, 52.5, 50.0), kind="door", opening_id=GARAGE_PHYSICAL_ID),
        figured_single_axis_mm=870.0,
    )
    nominated = apply_source_unique_swing_opening_hosts(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
        drawing_viewport_id_by_page_id={"3": "vp-floor-1"},
    )
    target = nominated.canonical_openings[0]
    issued = _issued_result(
        opening_id=GARAGE_PHYSICAL_ID,
        record_id=GARAGE_RECORD_ID,
        host_wall_id="physical-wall-garage-host",
    )
    rebound = apply_issued_opening_host_binding_receipts(
        nominated,
        _authority_for(target, issued),
    )
    updated = rebound.canonical_openings[0]
    assert updated.host_wall_id == "physical-wall-garage-host"
    assert GARAGE_RECORD_ID in updated.evidence_ids
    quantity = _opening_quantity(_billed(updated))
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
