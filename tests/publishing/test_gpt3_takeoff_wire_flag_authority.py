"""Source-owned takeoff flag must not be truthiness-coerced into JobHub approval.

Synthetic rows exercise the actual legacy preflight/builder, not original PDF,
FIRM source authentication, or the frozen Full Plan V2 score.
"""
from __future__ import annotations

import pytest

from pb_takeoff_output_authority import TakeoffOutputRow
from pb_planreader_jobhub_publish_contract import (
    PublishMode, build_jobhub_payload, run_jobhub_publish_preflight,
)
from test_planreader_jobhub_preflight_gate import (
    _valid_approved_row, _valid_project_identity, _valid_drawing_revision,
)


@pytest.mark.parametrize("forged", [
    "false", "true", "0", "1", "False", "", " ", 0, 1, 0.0, 1.0, None,
    [], {}, ["true"],
])
def test_malformed_wire_flag_cannot_become_commercial_authority(forged):
    genuine = _valid_approved_row()
    assert genuine.is_publishable is True
    raw = genuine.to_dict()
    raw["is_publishable"] = forged
    with pytest.raises(ValueError, match="explicit Boolean"):
        TakeoffOutputRow.from_dict(raw)


def test_missing_wire_flag_remains_unapproved_not_default_true():
    raw = _valid_approved_row().to_dict()
    raw.pop("is_publishable")
    restored = TakeoffOutputRow.from_dict(raw)
    assert restored.is_publishable is False
    result = run_jobhub_publish_preflight(
        [restored], _valid_project_identity(), _valid_drawing_revision(),
        mode=PublishMode.COMMERCIAL_PUBLISH,
    )
    assert not result.is_valid
    with pytest.raises(ValueError, match="Cannot build commercial payload"):
        build_jobhub_payload(
            [restored], _valid_project_identity(),
            _valid_drawing_revision(), publish_mode=PublishMode.COMMERCIAL_PUBLISH,
        )


@pytest.mark.parametrize("confidence", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_source_confidence_cannot_deserialize_or_construct(confidence):
    real = _valid_approved_row()
    raw = real.to_dict()
    raw["confidence"] = confidence
    with pytest.raises(ValueError, match="Confidence must be finite"):
        TakeoffOutputRow.from_dict(raw)
    with pytest.raises(ValueError, match="Confidence must be finite"):
        TakeoffOutputRow(
            quantity_id="unsafe-confidence", description="invalid",
            value=10.0, unit="m²", confidence=confidence,
        )


def test_valid_json_boolean_true_keeps_existing_commercial_consumer_live():
    original = _valid_approved_row()
    raw = original.to_dict()
    assert type(raw["is_publishable"]) is bool and raw["is_publishable"] is True
    restored = TakeoffOutputRow.from_dict(raw)
    assert restored.is_publishable is True
    assert restored.confidence == original.confidence
    check = run_jobhub_publish_preflight(
        [restored], _valid_project_identity(), _valid_drawing_revision(),
        mode=PublishMode.COMMERCIAL_PUBLISH,
    )
    assert check.is_valid and check.publishable_row_count == 1
    package = build_jobhub_payload(
        [restored], _valid_project_identity(), _valid_drawing_revision(),
        created_by="Source Estimator", publish_mode=PublishMode.COMMERCIAL_PUBLISH,
    )
    assert package.is_commercial_ready
    assert len(package.quantities) == 1
    assert package.quantities[0].is_publishable is True


def test_valid_explicit_boolean_false_preserves_draft_not_commercial():
    raw = _valid_approved_row().to_dict()
    raw["is_publishable"] = False
    restored = TakeoffOutputRow.from_dict(raw)
    assert restored.is_publishable is False
    check = run_jobhub_publish_preflight(
        [restored], _valid_project_identity(), _valid_drawing_revision(),
        mode=PublishMode.COMMERCIAL_PUBLISH,
    )
    assert not check.is_valid
    draft = build_jobhub_payload(
        [restored], _valid_project_identity(), _valid_drawing_revision(),
        publish_mode=PublishMode.DRAFT_PUBLISH,
    )
    assert draft.is_commercial_ready is False
