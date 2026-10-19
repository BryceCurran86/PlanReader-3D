"""Commercial source line provenance changes must invalidate JobHub TOCTOU hashes."""
from __future__ import annotations

from copy import deepcopy

import pytest

from pb_jobhub_publishing_contract import (
    BenchmarkStatusPayload, ExcludedScopePayload, PublishingWarningPayload,
    validate_publishing_gate,
)
from test_commercial_identity_default_safety import _minimal_commercial_package


def _approved():
    p = _minimal_commercial_package(
        estimator="Estimator A", created_by="Estimator A",
        approved_by="Estimator A",
    )
    p.drawing_revision.source_files_hash = "a" * 64
    p.payload_hash = p.compute_payload_hash()
    return p


@pytest.mark.parametrize(("field", "value"), [
    ("source_page", "not-original-sheet-11"),
    ("geometry_ref", "not-original-wall"),
    ("approved_by", "Another Approver"),
    ("approved_at", "2026-10-19T01:23:45Z"),
    ("notes", "new exclusions without issuer signoff"),
    ("confidence", 0.51),
    ("quantity", 10.000001),
    ("rate", 1.001),
    ("total_price", 10.001),
])
def test_rehashed_old_payload_cannot_ignore_changed_source_evidence(field, value):
    p = _approved()
    original_sha = p.payload_hash
    setattr(p.quantities[0], field, value)
    assert p.compute_payload_hash() != original_sha
    result = validate_publishing_gate(p)
    assert not result.is_publishable
    assert any("TOCTOU violation" in r for r in result.blocking_reasons)


def test_preflight_snapshot_changes_invalidate_existing_commercial_hash():
    p = _approved()
    original = p.payload_hash
    p.preflight_fingerprint = "another-source-snapshot"
    assert p.compute_payload_hash() != original
    result = validate_publishing_gate(p)
    assert any("TOCTOU violation" in r for r in result.blocking_reasons)


def test_changed_customer_issuer_cannot_reuse_approved_source_hash():
    p = _approved()
    p.created_by = "Different Company Estimator"
    assert p.compute_payload_hash() != p.payload_hash
    assert not validate_publishing_gate(p).is_publishable


def test_changed_frozen_benchmark_status_invalidate_commercial_payload():
    p = _approved()
    p.benchmark_status = BenchmarkStatusPayload(
        match_status="wrong_project_source_mismatch",
        is_compatible=False,
        summary="This belongs to another construction project",
    )
    assert p.compute_payload_hash() != p.payload_hash
    assert not validate_publishing_gate(p).is_publishable


def test_deleted_or_modified_exclusions_cannot_reuse_prior_hash():
    p = _approved()
    p.excluded_items.append(ExcludedScopePayload(
        item_code="EXTERNAL", description="Roof soffit",
        reason="Explicitly excluded by source", trade="Roofing",
    ))
    assert p.compute_payload_hash() != p.payload_hash
    assert not validate_publishing_gate(p).is_publishable


def test_changed_client_scope_warning_cannot_hide_in_same_export_receipt():
    p = _approved()
    p.warnings.append(PublishingWarningPayload(
        code="SOURCE_CONFLICT", severity="Blocker",
        message="The original drawing no longer matches the source",
    ))
    assert p.compute_payload_hash() != p.payload_hash
    assert any("TOCTOU violation" in r
               for r in validate_publishing_gate(p).blocking_reasons)


def test_same_commercial_source_on_different_creation_day_deduplicates():
    a = _approved()
    b = deepcopy(a)
    a.created_at = "2026-10-19T10:00:00Z"
    b.created_at = "2026-10-20T10:00:00Z"
    assert a.compute_payload_hash() == b.compute_payload_hash()


def test_duplicate_physical_takeoff_row_identity_is_rejected_even_if_self_rehashed():
    p = _approved()
    p.quantities.append(deepcopy(p.quantities[0]))
    p.payload_hash = p.compute_payload_hash()
    outcome = validate_publishing_gate(p)
    assert not outcome.is_publishable
    assert any("Duplicate physical takeoff row IDs" in reason
               for reason in outcome.blocking_reasons)


def test_legitimate_firm_source_still_passes_when_full_hash_is_fresh():
    p = _approved()
    assert validate_publishing_gate(p).is_publishable
