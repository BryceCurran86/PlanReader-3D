"""Strict approval Boolean preservation at legacy JobHub serialized trust boundary.

Real legacy preflight and builder controls; synthetic approved source rows only.
No original PDF, signed FIRM or frozen V2 score evidence is asserted.
"""
from __future__ import annotations

import pytest

from pb_planreader_jobhub_publish_contract import (
    PlanReaderJobHubPayload,
    PlanReaderJobHubQuantityRow,
    PublishMode,
    build_jobhub_payload,
    run_jobhub_publish_preflight,
)
from test_planreader_jobhub_preflight_gate import (
    _valid_approved_row,
    _valid_drawing_revision,
    _valid_project_identity,
)


@pytest.mark.parametrize("forged", [
    "false", "true", "False", "TRUE", "0", "1", " ",
    None, 0, 1, 0.0, 1.0, [], {}, ["false"],
])
def test_forged_legacy_row_publishability_cannot_hydrate_as_true(forged):
    original = PlanReaderJobHubQuantityRow.from_takeoff_output_row(
        _valid_approved_row()
    )
    assert original.is_publishable is True
    raw = original.to_dict()
    raw["is_publishable"] = forged
    with pytest.raises(ValueError, match="is_publishable must be an explicit Boolean"):
        PlanReaderJobHubQuantityRow.from_dict(raw)


@pytest.mark.parametrize("forged", [
    "false", "true", "False", "TRUE", "0", "1", " ",
    None, 0, 1, 0.0, 1.0, [], {}, ["false"],
])
def test_forged_top_level_customer_ready_cannot_hydrate_as_true(forged):
    original = build_jobhub_payload(
        [_valid_approved_row()], _valid_project_identity(),
        _valid_drawing_revision(), publish_mode=PublishMode.COMMERCIAL_PUBLISH,
        created_by="Source Estimator",
    )
    assert original.is_commercial_ready is True
    raw = original.to_dict()
    raw["is_commercial_ready"] = forged
    with pytest.raises(ValueError, match="is_commercial_ready must be an explicit Boolean"):
        PlanReaderJobHubPayload.from_dict(raw)


def test_missing_row_flag_remains_unapproved_through_legacy_preflight():
    raw = PlanReaderJobHubQuantityRow.from_takeoff_output_row(
        _valid_approved_row()
    ).to_dict()
    raw.pop("is_publishable")
    row = PlanReaderJobHubQuantityRow.from_dict(raw)
    assert row.is_publishable is False
    preflight = run_jobhub_publish_preflight(
        [row], _valid_project_identity(), _valid_drawing_revision(),
        mode=PublishMode.COMMERCIAL_PUBLISH,
    )
    assert not preflight.is_valid
    with pytest.raises(ValueError, match="Cannot build commercial payload"):
        build_jobhub_payload(
            [row], _valid_project_identity(), _valid_drawing_revision(),
            publish_mode=PublishMode.COMMERCIAL_PUBLISH,
        )


def test_missing_top_level_flag_remains_noncommercial_after_hydration():
    original = build_jobhub_payload(
        [_valid_approved_row()], _valid_project_identity(),
        _valid_drawing_revision(), publish_mode=PublishMode.COMMERCIAL_PUBLISH,
    )
    raw = original.to_dict()
    raw.pop("is_commercial_ready")
    parsed = PlanReaderJobHubPayload.from_dict(raw)
    assert parsed.is_commercial_ready is False
    assert parsed.quantities[0].is_publishable is True


@pytest.mark.parametrize(("mode", "expected_ready"), [
    (PublishMode.COMMERCIAL_PUBLISH, True),
    (PublishMode.DRAFT_PUBLISH, False),
])
def test_explicit_approved_and_draft_wire_booleans_keep_real_pipeline(
    mode, expected_ready,
):
    original = build_jobhub_payload(
        [_valid_approved_row()], _valid_project_identity(),
        _valid_drawing_revision(), publish_mode=mode,
        created_by="Source Estimator",
    )
    assert original.is_commercial_ready is expected_ready
    original_dict = original.to_dict()
    restored = PlanReaderJobHubPayload.from_dict(original_dict)
    assert type(restored.is_commercial_ready) is bool
    assert restored.is_commercial_ready is expected_ready
    assert restored.quantities[0].is_publishable is True
    assert restored.publish_mode == mode.value
    assert restored.payload_fingerprint == original.payload_fingerprint
    assert restored.to_dict() == original_dict
    preflight = run_jobhub_publish_preflight(
        restored.quantities, _valid_project_identity(),
        _valid_drawing_revision(), mode=mode,
    )
    assert preflight.is_valid
    assert preflight.publishable_row_count == 1


def test_explicit_false_row_flag_preserves_draft_not_commercial():
    original = PlanReaderJobHubQuantityRow.from_takeoff_output_row(
        _valid_approved_row()
    )
    raw = original.to_dict()
    raw["is_publishable"] = False
    restored = PlanReaderJobHubQuantityRow.from_dict(raw)
    assert restored.is_publishable is False
    result = run_jobhub_publish_preflight(
        [restored], _valid_project_identity(), _valid_drawing_revision(),
        mode=PublishMode.COMMERCIAL_PUBLISH,
    )
    assert not result.is_valid
