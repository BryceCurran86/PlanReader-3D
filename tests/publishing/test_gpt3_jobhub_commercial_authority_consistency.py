"""Commercial JobHub payloads cannot promote forged row publishability.

These are source-neutral downstream consumer tests. They do not authenticate
an original PDF, sign a quantity or assert any frozen V2 score improvement.
"""
from __future__ import annotations

import pytest

from pb_geometry_takeoff_model import AuthorityStatus
from pb_planreader_jobhub_publish_contract import (
    PlanReaderJobHubQuantityRow,
    PublishMode,
    build_jobhub_payload,
    run_jobhub_publish_preflight,
)
from pb_takeoff_output_authority import TakeoffSourceType


IDENTITY = {"project_id": "synthetic-job-1", "identity_confirmed": True}
REVISION = {"revision_hash": "synthetic-revision-1"}


def _row(**overrides):
    row = PlanReaderJobHubQuantityRow(
        quantity_id="Q-1",
        description="Synthetic documented lining",
        value=12.0,
        unit="m²",
        trade="painting",
        source_type=TakeoffSourceType.DOCUMENTED_DIMENSION.value,
        authority_status=AuthorityStatus.FIRM.value,
        source_page=1,
        dimension_text_id="synthetic-dimension",
        revision_hash=REVISION["revision_hash"],
        is_publishable=True,
    )
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def _preflight(rows, mode=PublishMode.COMMERCIAL_PUBLISH):
    return run_jobhub_publish_preflight(
        rows=rows,
        project_identity=IDENTITY,
        drawing_revision=REVISION,
        mode=mode,
    )


@pytest.mark.parametrize("status", [
    AuthorityStatus.PROVISIONAL.value,
    AuthorityStatus.REVIEW_REQUIRED.value,
    AuthorityStatus.BLOCKED.value,
    AuthorityStatus.EXCLUDED.value,
    AuthorityStatus.REFERENCE_ONLY.value,
    "unrecognised_authority",
])
def test_forged_publishable_flag_cannot_promote_nonfirm_authority(status):
    row = _row(authority_status=status)
    assert row.is_publishable
    result = _preflight([row])
    assert not result.is_valid
    assert result.publishable_row_count == 0
    assert result.blocked_row_count == 1
    with pytest.raises(ValueError, match="Cannot build commercial payload"):
        build_jobhub_payload([row], IDENTITY, REVISION)


@pytest.mark.parametrize("source_type", [
    TakeoffSourceType.EXCLUDED.value,
    TakeoffSourceType.REFERENCE_ONLY.value,
    TakeoffSourceType.BLOCKED.value,
    "unknown_source",
])
def test_forged_publishable_flag_cannot_promote_excluded_or_unknown_source(source_type):
    row = _row(source_type=source_type)
    result = _preflight([row])
    assert not result.is_valid
    assert result.blocked_row_count == 1
    with pytest.raises(ValueError, match="Cannot build commercial payload"):
        build_jobhub_payload([row], IDENTITY, REVISION)


@pytest.mark.parametrize("source_type", [
    TakeoffSourceType.PDF_SCALED.value,
    TakeoffSourceType.AI_DETECTED.value,
    TakeoffSourceType.MANUAL.value,
])
def test_raw_scaled_ai_or_manual_source_cannot_self_promote_even_with_approval(source_type):
    row = _row(source_type=source_type, approved_by="Estimator A")
    result = _preflight([row])
    assert not result.is_valid
    with pytest.raises(ValueError, match="Cannot build commercial payload"):
        build_jobhub_payload([row], IDENTITY, REVISION)


@pytest.mark.parametrize("source_type", [
    TakeoffSourceType.MODEL_DERIVED.value,
    TakeoffSourceType.USER_CORRECTED.value,
    TakeoffSourceType.USER_APPROVED.value,
])
def test_approval_requiring_source_cannot_self_promote_without_estimator(source_type):
    row = _row(source_type=source_type, approved_by=None)
    result = _preflight([row])
    assert not result.is_valid
    assert "approval" in " ".join(result.blocking_reasons).lower()


@pytest.mark.parametrize("field", ["source_page", "dimension_text_id"])
def test_documented_firm_source_requires_page_and_figured_dimension_trace(field):
    row = _row()
    setattr(row, field, None)
    assert not _preflight([row]).is_valid


def test_user_approved_without_named_approver_is_blocked():
    row = _row(
        source_type=TakeoffSourceType.USER_APPROVED.value,
        authority_status=AuthorityStatus.USER_APPROVED.value,
        approved_by="  ",
    )
    assert not _preflight([row]).is_valid


def test_explicit_source_blocker_overrides_forged_publishable_flag():
    row = _row(blocking_reasons=["stale_after_geometry_correction"])
    result = _preflight([row])
    assert not result.is_valid
    assert result.blocked_row_count == 1
    with pytest.raises(ValueError, match="Cannot build commercial payload"):
        build_jobhub_payload([row], IDENTITY, REVISION)



@pytest.mark.parametrize("bad_field", ["authority_status", "source_type"])
@pytest.mark.parametrize("bad_value", [None, "", "   "])
def test_blank_serialized_authority_metadata_does_not_default_to_firm(bad_field, bad_value):
    raw = _row().to_dict()
    raw[bad_field] = bad_value
    result = _preflight([raw])
    assert not result.is_valid
    with pytest.raises(ValueError, match="Cannot build commercial payload"):
        build_jobhub_payload([raw], IDENTITY, REVISION)


@pytest.mark.parametrize("bad_value", ["false", "true", 1, None])
def test_serialized_publishability_must_be_explicit_boolean(bad_value):
    raw = _row().to_dict()
    raw["is_publishable"] = bad_value
    result = _preflight([raw])
    assert not result.is_valid
    assert result.blocked_row_count == 1


def test_typed_publishability_string_cannot_bypass_final_consumer():
    row = _row(is_publishable="false")
    assert not _preflight([row]).is_valid

def test_empty_commercial_payload_cannot_be_marked_ready():
    result = _preflight([])
    assert not result.is_valid
    assert any("at least one" in reason for reason in result.blocking_reasons)
    with pytest.raises(ValueError, match="Cannot build commercial payload"):
        build_jobhub_payload([], IDENTITY, REVISION)


def test_valid_documented_and_issuer_user_approved_rows_reach_consumer():
    documented = _row()
    approved_row = _row(
        quantity_id="Q-2",
        source_type=TakeoffSourceType.USER_APPROVED.value,
        authority_status=AuthorityStatus.USER_APPROVED.value,
        approved_by="Estimator A",
    )
    result = _preflight([documented, approved_row])
    assert result.is_valid
    assert result.publishable_row_count == 2
    payload = build_jobhub_payload(
        [documented, approved_row], IDENTITY, REVISION,
        created_by="Estimator A",
    )
    assert payload.is_commercial_ready is True
    assert {q.quantity_id for q in payload.quantities} == {"Q-1", "Q-2"}


def test_draft_keeps_provisional_row_with_explicit_noncommercial_warning():
    row = _row(
        authority_status=AuthorityStatus.PROVISIONAL.value,
        source_type=TakeoffSourceType.PDF_SCALED.value,
        is_publishable=False,
    )
    result = _preflight([row], PublishMode.DRAFT_PUBLISH)
    assert result.is_valid
    assert result.provisional_row_count == 1
    payload = build_jobhub_payload(
        [row], IDENTITY, REVISION, publish_mode=PublishMode.DRAFT_PUBLISH,
    )
    assert not payload.is_commercial_ready
    assert any("draft" in warning.lower() for warning in payload.warnings)
