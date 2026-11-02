"""A named estimator must be a real nonblank string, not a truthy value.

Production factory -> authority summary -> actual legacy preflight and payload.
Synthetic source-neutral rows only; no original-PDF FIRM or frozen V2 gain.
"""
from __future__ import annotations

import pytest

from pb_takeoff_output_authority import (
    TakeoffSourceType,
    approve_takeoff_output_row,
    create_takeoff_output_row,
    generate_takeoff_authority_summary,
)
from pb_planreader_jobhub_publish_contract import (
    PublishMode, build_jobhub_payload, run_jobhub_publish_preflight,
)
from test_planreader_jobhub_preflight_gate import (
    _valid_drawing_revision, _valid_project_identity,
)


def _source_row(source_type, approved_by=None):
    return create_takeoff_output_row(
        quantity_id="SYNTH-ESTIMATOR-1",
        description="Source-neutral estimator-approved trade quantity",
        value=17.5,
        unit="m²",
        trade="painting",
        source_type=source_type,
        source_page=2,
        source_sheet="A102",
        approved_by=approved_by,
    )


@pytest.mark.parametrize("source_type", [
    TakeoffSourceType.MODEL_DERIVED,
    TakeoffSourceType.USER_CORRECTED,
    TakeoffSourceType.USER_APPROVED,
])
@pytest.mark.parametrize("forged", [
    " ", "\t", "\n \t ", True, 1, 1.1,
    {"estimator": "Unverified"}, ["Estimator"], b"Estimator", None, "",
])
def test_truthy_nonhuman_estimator_cannot_raise_publishability_or_readiness(
    source_type, forged,
):
    row = _source_row(source_type, approved_by=forged)
    assert row.is_publishable is False
    assert row.blocking_reasons
    summary = generate_takeoff_authority_summary([row])
    assert summary["publishable_count"] == 0
    assert summary["commercial_readiness_pct"] == 0.0

    verdict = run_jobhub_publish_preflight(
        [row], _valid_project_identity(), _valid_drawing_revision(),
        mode=PublishMode.COMMERCIAL_PUBLISH,
    )
    assert not verdict.is_valid
    with pytest.raises(ValueError, match="Cannot build commercial payload"):
        build_jobhub_payload(
            [row], _valid_project_identity(), _valid_drawing_revision(),
            publish_mode=PublishMode.COMMERCIAL_PUBLISH,
        )


@pytest.mark.parametrize("source_type", [
    TakeoffSourceType.MODEL_DERIVED,
    TakeoffSourceType.USER_CORRECTED,
    TakeoffSourceType.USER_APPROVED,
])
@pytest.mark.parametrize("approver", ["Source Estimator", "  Named Estimator  "])
def test_actual_named_estimator_keeps_existing_approved_path(
    source_type, approver,
):
    row = _source_row(source_type, approved_by=approver)
    assert row.is_publishable is True
    assert row.approved_by == approver
    assert generate_takeoff_authority_summary([row])["publishable_count"] == 1
    check = run_jobhub_publish_preflight(
        [row], _valid_project_identity(), _valid_drawing_revision(),
        mode=PublishMode.COMMERCIAL_PUBLISH,
    )
    assert check.is_valid
    package = build_jobhub_payload(
        [row], _valid_project_identity(), _valid_drawing_revision(),
        publish_mode=PublishMode.COMMERCIAL_PUBLISH,
        created_by="Source Estimator",
    )
    assert package.is_commercial_ready
    assert package.quantities[0].approved_by == approver


@pytest.mark.parametrize("forged", [
    " ", "\t", True, 1, ["Estimator"], {"approver": "X"},
])
def test_approval_helper_cannot_turn_nonhuman_stamp_into_commercial_receipt(
    forged,
):
    draft = _source_row(TakeoffSourceType.MODEL_DERIVED)
    assert not draft.is_publishable
    approved = approve_takeoff_output_row(
        draft, approved_by=forged, approved_at="2026-10-29T00:00:00Z",
    )
    assert not approved.is_publishable
    assert generate_takeoff_authority_summary([approved])["publishable_count"] == 0
    assert not run_jobhub_publish_preflight(
        [approved], _valid_project_identity(), _valid_drawing_revision(),
        mode=PublishMode.COMMERCIAL_PUBLISH,
    ).is_valid


def test_real_named_approval_helper_remains_publishable():
    draft = _source_row(TakeoffSourceType.MODEL_DERIVED)
    approved = approve_takeoff_output_row(
        draft, approved_by="Source Estimator",
        approved_at="2026-10-29T00:00:00Z",
    )
    assert approved.is_publishable
    assert generate_takeoff_authority_summary([approved])["publishable_count"] == 1
