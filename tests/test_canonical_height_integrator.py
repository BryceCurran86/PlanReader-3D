from __future__ import annotations

import logging
import pytest
from pb_canonical_height_integrator import CanonicalHeightIntegrator, CanonicalHeightResult
from pb_opening_height_authority import OpeningHeightProducer, OpeningHeightSelector
from pb_source_observation_authority import SourceObservationAuthority
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_opening_height_authority_validator_v1 import _tag_pdf, _ingest, _opening_selector
from pb_schedule_opening_instance_binding_authority import ScheduleOpeningInstanceBindingProducer
from pb_physical_opening_authority import PhysicalOpeningAuthority

def test_canonical_height_integrator_route_b_success(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    
    # 1. Setup authorities with Route B success
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")))
    src = SourceVisibilityProducer(producer_method="height-validator", producer_version="1.0")
    published = _ingest(src, payload, "test-doc")
    obs_selector = _opening_selector(published, src.authority())
    
    binding_prod = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(src)
    bind_result = binding_prod.publish_scope(opening_selector=obs_selector, decision_scope_id="scope-1")
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
    
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    obs_auth = src.authority()
    
    # 2. Run Integrator
    integrator = CanonicalHeightIntegrator(height_prod, obs_auth)
    result = integrator.resolve_height(height_selector)
    
    # 3. Compare and Verify
    assert result.height_mm == 2100.0
    assert result.source == "schedule_route_b"
    assert result.confidence == 1.0
    
    # 4. Log checks
    assert "Route B success: 2100.0 mm" in caplog.text

def test_canonical_height_integrator_route_b_fail(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    
    # 1. Setup authorities with Route B fail (duplicate schedule rows)
    payload = _tag_pdf(schedule_rows=(("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100"), ("W1", "900", "2100")))
    src = SourceVisibilityProducer(producer_method="height-validator", producer_version="1.0")
    published = _ingest(src, payload, "test-doc")
    obs_selector = _opening_selector(published, src.authority())
    
    binding_prod = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(src)
    bind_result = binding_prod.publish_scope(opening_selector=obs_selector, decision_scope_id="scope-1")
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
    
    height_prod = OpeningHeightProducer.from_authorities(src, binding_prod.authority())
    obs_auth = src.authority()
    
    # 2. Run Integrator
    integrator = CanonicalHeightIntegrator(height_prod, obs_auth)
    result = integrator.resolve_height(height_selector)
    
    # 3. Compare and Verify
    assert result.height_mm is None
    assert result.source == "unresolved"
    assert result.confidence == 0.0
    
    # 4. Log checks
    assert "Route B failed for" in caplog.text
    assert "all routes failed for" in caplog.text
