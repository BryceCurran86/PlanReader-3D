"""Unknown legacy publishing modes must never gain draft publication authority.

Synthetic quantities exercise real legacy preflight -> full payload builder.
No original PDF or frozen V2 measurement authority is granted.
"""
import pytest

from pb_planreader_jobhub_publish_contract import (
    PublishMode, build_jobhub_payload, run_jobhub_publish_preflight,
)
from pb_takeoff_output_authority import TakeoffSourceType, create_takeoff_output_row
from test_planreader_jobhub_preflight_gate import (
    _valid_approved_row, _valid_project_identity, _valid_drawing_revision,
)


def _provisional():
    return create_takeoff_output_row(
        quantity_id="draft-unverified-floor-1",
        description="Unconfirmed draft floor",
        value=12.5,
        unit="m²",
        source_type=TakeoffSourceType.PDF_SCALED,
        source_page=1,
        source_sheet="A101",
    )


@pytest.mark.parametrize("invalid", [
    "commercial_publish ", " commercial_publish", "draft_publish ",
    " published", "publish", "commercial", "draft", "", " ",
    "unknown", None, False, True, 0, 1, ["commercial_publish"],
])
def test_unsupported_mode_cannot_gain_preflight_draft_permission(invalid):
    verdict = run_jobhub_publish_preflight(
        [_provisional()], _valid_project_identity(),
        _valid_drawing_revision(), mode=invalid,
    )
    assert not verdict.is_valid
    assert any("Unsupported JobHub publishing mode" in reason
               for reason in verdict.blocking_reasons)
    assert verdict.publish_mode not in {
        PublishMode.DRAFT_PUBLISH.value,
        PublishMode.COMMERCIAL_PUBLISH.value,
    }


@pytest.mark.parametrize("invalid", [
    "commercial_publish ", " commercial_publish", "draft_publish ",
    "published", "unknown", "", None, False, True, 0, 1,
])
def test_unsupported_mode_cannot_construct_customer_payload(invalid):
    with pytest.raises(ValueError, match="Unsupported JobHub publishing mode"):
        build_jobhub_payload(
            rows=[_provisional()],
            project_identity=_valid_project_identity(),
            drawing_revision=_valid_drawing_revision(),
            publish_mode=invalid,
        )


@pytest.mark.parametrize("valid", [
    PublishMode.COMMERCIAL_PUBLISH,
    PublishMode.COMMERCIAL_PUBLISH.value,
    "COMMERCIAL_PUBLISH",
])
def test_existing_commercial_modes_keep_their_exact_source_gates(valid):
    preflight = run_jobhub_publish_preflight(
        [_valid_approved_row()],
        _valid_project_identity(), _valid_drawing_revision(), mode=valid,
    )
    assert preflight.is_valid
    assert preflight.publish_mode == PublishMode.COMMERCIAL_PUBLISH.value
    package = build_jobhub_payload(
        rows=[_valid_approved_row()],
        project_identity=_valid_project_identity(),
        drawing_revision=_valid_drawing_revision(),
        publish_mode=valid,
    )
    assert package.publish_mode == PublishMode.COMMERCIAL_PUBLISH.value
    assert package.is_commercial_ready


@pytest.mark.parametrize("valid", [
    PublishMode.DRAFT_PUBLISH,
    PublishMode.DRAFT_PUBLISH.value,
    "DRAFT_PUBLISH",
])
def test_existing_explicit_draft_modes_preserve_provisional_warnings(valid):
    preflight = run_jobhub_publish_preflight(
        [_provisional()],
        _valid_project_identity(), _valid_drawing_revision(), mode=valid,
    )
    assert preflight.is_valid
    assert preflight.publish_mode == PublishMode.DRAFT_PUBLISH.value
    assert preflight.provisional_row_count == 1
    assert preflight.warnings
    package = build_jobhub_payload(
        rows=[_provisional()],
        project_identity=_valid_project_identity(),
        drawing_revision=_valid_drawing_revision(),
        publish_mode=valid,
    )
    assert package.publish_mode == PublishMode.DRAFT_PUBLISH.value
    assert package.is_commercial_ready is False
    assert package.warnings
