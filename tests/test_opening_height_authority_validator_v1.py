"""Opening Height Validator v1 (Test Scaffold)"""
from __future__ import annotations

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
from pb_source_visibility_authority import SourceVisibilityProducer

# Import the exact #383 fixtures
from tests.test_schedule_opening_instance_binding_authority_v1 import (
    _ingest,
    _opening_selector,
    _tag_pdf,
)


def _setup_authorities(payload: bytes | None = None) -> tuple[SourceVisibilityProducer, ScheduleOpeningInstanceBindingProducer, OpeningHeightSelector]:
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
    
    # 3. Height Selector
    height_selector = OpeningHeightSelector(
        document_id=bind_result.record.document_id,
        revision_id=bind_result.record.revision_id,
        source_sha256=bind_result.record.source_sha256,
        snapshot_id=bind_result.record.snapshot_id,
        decision_scope_id=bind_result.record.decision_scope_id,
        opening_record_id=bind_result.record.opening_record_id,
    )
    
    return src, binding_prod, height_selector


@pytest.mark.xfail(reason="Production not yet implemented")
def test_positive_height_evidence_requires_legitimate_instance_binding() -> None:
    src, binding_prod, height_selector = _setup_authorities()
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    
    result = height_prod.publish_scope(height_selector)
    
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert result.evidence.height_mm == 2100.0
    assert result.evidence.document_id == height_selector.document_id
    assert result.evidence.opening_record_id == height_selector.opening_record_id


@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_2040_default_is_rejected() -> None:
    # No height provided
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "")))
    src, binding_prod, height_selector = _setup_authorities(payload)
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_missing_field" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_2100_default_is_rejected() -> None:
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "")))
    src, binding_prod, height_selector = _setup_authorities(payload)
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_missing_field" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_typical_height_rejected() -> None:
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "TYPICAL")))
    src, binding_prod, height_selector = _setup_authorities(payload)
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_missing_field" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_width_used_as_height() -> None:
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "")))
    src, binding_prod, height_selector = _setup_authorities(payload)
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
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

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_raw_schedule_text_without_binding() -> None:
    src, binding_prod, height_selector = _setup_authorities()
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_raw_text_no_binding" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_ocr_only_text_is_untrusted() -> None:
    src, binding_prod, height_selector = _setup_authorities()
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_ocr_untrusted" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_hidden_untrusted_text() -> None:
    src, binding_prod, height_selector = _setup_authorities()
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_hidden_text" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_nearest_dimension() -> None:
    src, binding_prod, height_selector = _setup_authorities()
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_nearest_dimension" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_unrelated_elevation_text() -> None:
    src, binding_prod, height_selector = _setup_authorities()
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_unrelated_elevation" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_wrong_physical_opening() -> None:
    src, binding_prod, height_selector = _setup_authorities()
    tampered = dataclasses.replace(height_selector, opening_record_id="wrong_op")
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(tampered)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_wrong_opening" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_wrong_schedule_row() -> None:
    src, binding_prod, height_selector = _setup_authorities()
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_wrong_row" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_repeated_mark_without_exact_instance_binding() -> None:
    src, binding_prod, height_selector = _setup_authorities()
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_repeated_mark_unbound" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_wrong_revision() -> None:
    src, binding_prod, height_selector = _setup_authorities()
    tampered = dataclasses.replace(height_selector, revision_id="wrong_rev")
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(tampered)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_lineage_mismatch" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_wrong_sha() -> None:
    src, binding_prod, height_selector = _setup_authorities()
    tampered = dataclasses.replace(height_selector, source_sha256="wrong_sha")
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(tampered)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_lineage_mismatch" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_wrong_snapshot() -> None:
    src, binding_prod, height_selector = _setup_authorities()
    tampered = dataclasses.replace(height_selector, snapshot_id="wrong_snap")
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(tampered)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_lineage_mismatch" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_stale_schedule_snapshot() -> None:
    src, binding_prod, height_selector = _setup_authorities()
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_stale_snapshot" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_duplicate_matching_schedule_rows() -> None:
    # W1 900x2100 appears twice in the same schedule
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100"), ("W1", "900", "2100")))
    src = SourceVisibilityProducer(producer_method="height-validator", producer_version="1.0")
    published = _ingest(src, payload, "height-val-doc")
    obs_selector = _opening_selector(published, src.authority())
    binding_prod = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(src)
    bind_result = binding_prod.publish_scope(opening_selector=obs_selector, decision_scope_id="scope-1")
    # Binding abstains or conflicts when rows are completely duplicated
    # In Item 1, binding conflicts if duplicate rows exist unless disambiguated.
    # We will simulate this by checking the height producer response IF it somehow gets a selector.
    # Actually, the height producer just asks binding_authority, which will CONFLICT.
    height_selector = OpeningHeightSelector(
        document_id="height-val-doc",
        revision_id="rev",
        source_sha256="sha",
        snapshot_id="snap",
        decision_scope_id="scope-1",
        opening_record_id=obs_selector.observation_id, # mock it
    )
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert "opening_height_duplicate_rows" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_conflicting_heights() -> None:
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100"), ("W1", "900", "2000")))
    src = SourceVisibilityProducer(producer_method="height-validator", producer_version="1.0")
    published = _ingest(src, payload, "height-val-doc")
    obs_selector = _opening_selector(published, src.authority())
    binding_prod = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(src)
    bind_result = binding_prod.publish_scope(opening_selector=obs_selector, decision_scope_id="scope-1")
    height_selector = OpeningHeightSelector(
        document_id="height-val-doc",
        revision_id="rev",
        source_sha256="sha",
        snapshot_id="snap",
        decision_scope_id="scope-1",
        opening_record_id=obs_selector.observation_id, # mock it
    )
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert "opening_height_conflicting_heights" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_missing_height_field() -> None:
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "")))
    src, binding_prod, height_selector = _setup_authorities(payload)
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_missing_field" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_ambiguous_units() -> None:
    # 2100mm vs 2100 inches? Actually, PlanReader usually handles this, but if it's "2100 / 2040" it's ambiguous
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100 / 2040")))
    src, binding_prod, height_selector = _setup_authorities(payload)
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_ambiguous_units" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_cross_sheet_elevation_assumption_without_registration() -> None:
    src, binding_prod, height_selector = _setup_authorities()
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "opening_height_unregistered_cross_sheet" in result.reason_codes

@pytest.mark.xfail(reason="Production not yet implemented")
def test_attack_contradiction_monotonicity() -> None:
    src, binding_prod, height_selector = _setup_authorities()
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    result = height_prod.publish_scope(height_selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert "opening_height_monotonicity" in result.reason_codes

