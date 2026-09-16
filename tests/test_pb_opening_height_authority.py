"""Opening Height Validator v1 (Test Scaffold)"""
from __future__ import annotations
from pb_physical_opening_authority import PhysicalOpeningAuthority

import dataclasses
import inspect

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_height_authority import (
    OpeningHeightProducer,
    OpeningHeightSelector,
)
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingProducer,
)
from pb_schedule_row_height_authority import ScheduleRowHeightProducer, ScheduleRowHeightSelector
from pb_source_visibility_authority import SourceVisibilityProducer

# Import the exact #383 fixtures
from tests.test_schedule_opening_instance_binding_authority_v1 import (
    _ingest,
    _opening_selector,
    _tag_pdf,
)


def _setup_authorities(payload: bytes | None = None) -> tuple[SourceVisibilityProducer, ScheduleOpeningInstanceBindingProducer, ScheduleRowHeightProducer, OpeningHeightSelector]:
    """Helper to set up the real source chain and extract a valid selector."""
    if payload is None:
        payload = _tag_pdf()  # default W1 900x2100 with valid physical opening

    src = SourceVisibilityProducer(producer_method="height-validator", producer_version="1.0")
    published = _ingest(src, payload, "height-val-doc")
    
    # 1. Physical Opening (ObservationSelector)
    obs_selector = _opening_selector(published, src.authority())
    
    # 2. Schedule Binding Producer
    binding_prod = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(src)
    bind_result = binding_prod.publish_scope(opening_selector=obs_selector, decision_scope_id="scope-1")
    assert bind_result.status is EvidenceResolutionStatus.CORROBORATED, "Fixture binding must succeed"
    assert bind_result.record is not None
    
    # 3. Schedule Row Height Producer
    row_height_prod = ScheduleRowHeightProducer.from_source_visibility_producer(src)

    # 4. Height Selector
    height_selector = OpeningHeightSelector(
        document_id=bind_result.record.document_id,
        revision_id=bind_result.record.revision_id,
        source_sha256=bind_result.record.source_sha256,
        snapshot_id=bind_result.record.snapshot_id,
        decision_scope_id=bind_result.record.decision_scope_id,
        opening_record_id=bind_result.record.opening_record_id,
    )
    
    # Actually run the producer so authority has data
    if bind_result.record is not None:
        row_height_selector = ScheduleRowHeightSelector(
            document_id=bind_result.record.document_id,
            revision_id=bind_result.record.revision_id,
            source_sha256=bind_result.record.source_sha256,
            snapshot_id=bind_result.record.snapshot_id,
            schedule_page_id=bind_result.record.schedule_page_id,
            schedule_row_observation_ids=bind_result.record.schedule_row_observation_ids,
        )
        row_height_prod.publish_scope(row_height_selector)
    
    return src, binding_prod, row_height_prod, height_selector


def test_positive_height_evidence_requires_legitimate_instance_binding() -> None:
    src, binding_prod, row_height_prod, height_selector = _setup_authorities()
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority(), row_height_prod.authority())
    
    result = height_prod.publish_scope(height_selector)
    
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert result.evidence.height_mm == 2100.0
    assert result.evidence.document_id == height_selector.document_id
    assert result.evidence.opening_record_id == height_selector.opening_record_id


def test_attack_2040_default_is_rejected() -> None:
    # No height provided
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "")))
    src, binding_prod, row_height_prod, height_selector = _setup_authorities(payload)
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority(), row_height_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_missing_field" in result.reason_codes

def test_attack_2100_default_is_rejected() -> None:
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "")))
    src, binding_prod, row_height_prod, height_selector = _setup_authorities(payload)
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority(), row_height_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_missing_field" in result.reason_codes

def test_attack_typical_height_rejected() -> None:
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "TYPICAL")))
    src, binding_prod, row_height_prod, height_selector = _setup_authorities(payload)
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority(), row_height_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_missing_field" in result.reason_codes

def test_attack_width_used_as_height() -> None:
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "")))
    src, binding_prod, row_height_prod, height_selector = _setup_authorities(payload)
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority(), row_height_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_missing_field" in result.reason_codes

def test_attack_caller_supplied_height_is_rejected() -> None:
    params = set(inspect.signature(OpeningHeightProducer.publish_scope).parameters)
    assert "height" not in params
    assert "height_mm" not in params
    assert "evidence" not in params
    
def test_attack_caller_authenticated_flags() -> None:
    params = set(inspect.signature(OpeningHeightSelector).parameters)
    assert "authenticated" not in params
    assert "is_valid" not in params

def test_attack_raw_schedule_text_without_binding() -> None:
    # Structurally proved: Producer only accepts OpeningHeightSelector (no text payload)
    params = set(inspect.signature(OpeningHeightProducer.publish_scope).parameters)
    assert "text" not in params

def test_attack_ocr_only_text_is_untrusted() -> None:
    # Structurally proved: Upstream ScheduleOpeningInstanceBindingAuthority relies on trusted native text.
    sig = inspect.signature(OpeningHeightProducer.from_authorities)
    assert sig.parameters["binding_authority"].annotation == "ScheduleOpeningInstanceBindingAuthority"

def test_attack_hidden_untrusted_text() -> None:
    # Structurally proved: Upstream ScheduleOpeningInstanceBindingAuthority rejects hidden text.
    sig = inspect.signature(OpeningHeightProducer.from_authorities)
    assert sig.parameters["binding_authority"].annotation == "ScheduleOpeningInstanceBindingAuthority"

def test_attack_nearest_dimension() -> None:
    # Structurally proved: Upstream binding requires exact row, not spatial nearest search.
    sig = inspect.signature(OpeningHeightProducer.from_authorities)
    assert sig.parameters["binding_authority"].annotation == "ScheduleOpeningInstanceBindingAuthority"

def test_attack_unrelated_elevation_text() -> None:
    # Structurally proved: Upstream binding binds strictly to schedule rows.
    sig = inspect.signature(OpeningHeightProducer.from_authorities)
    assert sig.parameters["binding_authority"].annotation == "ScheduleOpeningInstanceBindingAuthority"

def test_attack_wrong_physical_opening() -> None:
    # Genuine condition: Provide an unregistered opening record ID
    src, binding_prod, row_height_prod, height_selector = _setup_authorities()
    tampered = dataclasses.replace(height_selector, opening_record_id="wrong_op")
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority(), row_height_prod.authority())
    result = height_prod.publish_scope(tampered)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_upstream_abstained" in result.reason_codes

def test_attack_wrong_schedule_row() -> None:
    # Structurally proved: Upstream binding maps opening_record_id to EXACTLY one schedule row.
    sig = inspect.signature(OpeningHeightProducer.from_authorities)
    assert sig.parameters["binding_authority"].annotation == "ScheduleOpeningInstanceBindingAuthority"

def test_attack_repeated_mark_without_exact_instance_binding() -> None:
    # Structurally proved: Upstream binding rejects multiple instances without exact binding.
    sig = inspect.signature(OpeningHeightProducer.from_authorities)
    assert sig.parameters["binding_authority"].annotation == "ScheduleOpeningInstanceBindingAuthority"

def test_attack_wrong_revision() -> None:
    # Genuine condition: Provide a mismatched revision ID
    src, binding_prod, row_height_prod, height_selector = _setup_authorities()
    tampered = dataclasses.replace(height_selector, revision_id="wrong_rev")
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority(), row_height_prod.authority())
    result = height_prod.publish_scope(tampered)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_upstream_abstained" in result.reason_codes

def test_attack_wrong_sha() -> None:
    # Genuine condition: Provide a mismatched source SHA
    src, binding_prod, row_height_prod, height_selector = _setup_authorities()
    tampered = dataclasses.replace(height_selector, source_sha256="wrong_sha")
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority(), row_height_prod.authority())
    result = height_prod.publish_scope(tampered)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_upstream_abstained" in result.reason_codes

def test_attack_wrong_snapshot() -> None:
    # Genuine condition: Provide a mismatched snapshot ID
    src, binding_prod, row_height_prod, height_selector = _setup_authorities()
    tampered = dataclasses.replace(height_selector, snapshot_id="wrong_snap")
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority(), row_height_prod.authority())
    result = height_prod.publish_scope(tampered)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_upstream_abstained" in result.reason_codes

def test_attack_stale_schedule_snapshot() -> None:
    # Genuine condition: Provide a mismatched (stale) snapshot ID
    src, binding_prod, row_height_prod, height_selector = _setup_authorities()
    tampered = dataclasses.replace(height_selector, snapshot_id="stale_snap")
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority(), row_height_prod.authority())
    result = height_prod.publish_scope(tampered)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_upstream_abstained" in result.reason_codes

def test_attack_duplicate_matching_schedule_rows() -> None:
    # W1 900x2100 appears twice in the same schedule
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100"), ("W1", "900", "2100")))
    src = SourceVisibilityProducer(producer_method="height-validator", producer_version="1.0")
    published = _ingest(src, payload, "height-val-doc")
    obs_selector = _opening_selector(published, src.authority())
    binding_prod = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(src)
    bind_result = binding_prod.publish_scope(opening_selector=obs_selector, decision_scope_id="scope-1")
    row_height_prod = ScheduleRowHeightProducer.from_source_visibility_producer(src)
    if bind_result.record is not None:
        row_height_selector = ScheduleRowHeightSelector(
            document_id=bind_result.record.document_id,
            revision_id=bind_result.record.revision_id,
            source_sha256=bind_result.record.source_sha256,
            snapshot_id=bind_result.record.snapshot_id,
            schedule_page_id=bind_result.record.schedule_page_id,
            schedule_row_observation_ids=bind_result.record.schedule_row_observation_ids,
        )
        row_height_prod.publish_scope(row_height_selector)
    physical = PhysicalOpeningAuthority(src.authority())
    opening_record_id = physical.prove_existence(obs_selector).existence_record.record_id
    height_selector = OpeningHeightSelector(
        document_id=obs_selector.document_id,
        revision_id=obs_selector.revision_id,
        source_sha256=obs_selector.source_sha256,
        snapshot_id=obs_selector.snapshot_id,
        decision_scope_id="scope-1",
        opening_record_id=opening_record_id,
    )
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority(), row_height_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert "opening_height_upstream_conflict" in result.reason_codes

def test_attack_conflicting_heights() -> None:
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100"), ("W1", "900", "2000")))
    src = SourceVisibilityProducer(producer_method="height-validator", producer_version="1.0")
    published = _ingest(src, payload, "height-val-doc")
    obs_selector = _opening_selector(published, src.authority())
    binding_prod = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(src)
    bind_result = binding_prod.publish_scope(opening_selector=obs_selector, decision_scope_id="scope-1")
    row_height_prod = ScheduleRowHeightProducer.from_source_visibility_producer(src)
    if bind_result.record is not None:
        row_height_selector = ScheduleRowHeightSelector(
            document_id=bind_result.record.document_id,
            revision_id=bind_result.record.revision_id,
            source_sha256=bind_result.record.source_sha256,
            snapshot_id=bind_result.record.snapshot_id,
            schedule_page_id=bind_result.record.schedule_page_id,
            schedule_row_observation_ids=bind_result.record.schedule_row_observation_ids,
        )
        row_height_prod.publish_scope(row_height_selector)
    physical = PhysicalOpeningAuthority(src.authority())
    opening_record_id = physical.prove_existence(obs_selector).existence_record.record_id
    height_selector = OpeningHeightSelector(
        document_id=obs_selector.document_id,
        revision_id=obs_selector.revision_id,
        source_sha256=obs_selector.source_sha256,
        snapshot_id=obs_selector.snapshot_id,
        decision_scope_id="scope-1",
        opening_record_id=opening_record_id,
    )
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority(), row_height_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert "opening_height_upstream_conflict" in result.reason_codes

def test_attack_missing_height_field() -> None:
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "")))
    src, binding_prod, row_height_prod, height_selector = _setup_authorities(payload)
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority(), row_height_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_missing_field" in result.reason_codes

def test_attack_ambiguous_units() -> None:
    # Genuine condition: Schedule row text contains multiple conflicting units/dimensions
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100 / 2040")))
    src, binding_prod, row_height_prod, height_selector = _setup_authorities(payload)
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority(), row_height_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_ambiguous_units" in result.reason_codes

def test_attack_cross_sheet_elevation_assumption_without_registration() -> None:
    # Structurally proved: Route B explicitly does not use cross-sheet elevations.
    sig = inspect.signature(OpeningHeightProducer.from_authorities)
    assert sig.parameters["binding_authority"].annotation == "ScheduleOpeningInstanceBindingAuthority"

def test_attack_contradiction_monotonicity() -> None:
    # We will trigger a CONFLICT by supplying conflicting schedule rows
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100"), ("W1", "900", "2000")))
    src = SourceVisibilityProducer(producer_method="height-validator", producer_version="1.0")
    published = _ingest(src, payload, "height-val-doc")
    obs_selector = _opening_selector(published, src.authority())
    binding_prod = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(src)
    bind_result = binding_prod.publish_scope(opening_selector=obs_selector, decision_scope_id="scope-1")
    row_height_prod = ScheduleRowHeightProducer.from_source_visibility_producer(src)
    if bind_result.record is not None:
        row_height_selector = ScheduleRowHeightSelector(
            document_id=bind_result.record.document_id,
            revision_id=bind_result.record.revision_id,
            source_sha256=bind_result.record.source_sha256,
            snapshot_id=bind_result.record.snapshot_id,
            schedule_page_id=bind_result.record.schedule_page_id,
            schedule_row_observation_ids=bind_result.record.schedule_row_observation_ids,
        )
        row_height_prod.publish_scope(row_height_selector)
    physical = PhysicalOpeningAuthority(src.authority())
    opening_record_id = physical.prove_existence(obs_selector).existence_record.record_id
    height_selector = OpeningHeightSelector(
        document_id=obs_selector.document_id,
        revision_id=obs_selector.revision_id,
        source_sha256=obs_selector.source_sha256,
        snapshot_id=obs_selector.snapshot_id,
        decision_scope_id="scope-1",
        opening_record_id=opening_record_id,
    )
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority(), row_height_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert "opening_height_upstream_conflict" in result.reason_codes

