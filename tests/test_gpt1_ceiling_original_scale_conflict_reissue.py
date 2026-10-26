"""Source-negative physical scale evidence cannot be laundered into FIRM ceiling m².

These are producer→actual canonical issuer→source seal→customer tests, not
original PDF or frozen V2 score tests.
"""
from dataclasses import replace

import pytest

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_live_ceiling_area_quantity_publication import publish_live_ceiling_area_quantities
from pb_live_ceiling_area_source_closed_export import seal_live_ceiling_area_run
from pb_live_ceiling_area_customer_projection import project_live_ceiling_area_customer_rows
from tests.test_live_ceiling_area_quantity_publication import _ceiling, _result, _shadow_quantity


def _scaled_case(extra_source_metadata):
    ceiling = _ceiling(
        authority=MeasurementAuthorityType.PDF_SCALED.value,
        physical_scale_record_id="physical-scale-1",
        figured_dimension_ids=(),
    )
    original = _shadow_quantity()
    shadow = replace(
        original,
        metadata={**dict(original.metadata), **extra_source_metadata},
    )
    return _result(ceiling=ceiling, shadow=shadow)


@pytest.mark.parametrize("source_negative", [
    {"scale_status": "conflicted"},
    {"scale_status": "provisional"},
    {"scale_status": "resolved "},
    {"scale_status": True},
    {"scale_status": None},
    {"scale_conflicts": ("original-viewport-rival",)},
    {"scale_conflicts": ["foreign-scale"]},
    {"scale_conflicts": "hidden-original-conflict"},
    {"scale_conflicts": None},
    {"resolved_scale_id": "foreign-scale"},
    {"resolved_scale_id": " physical-scale-1"},
    {"resolved_scale_id": True},
    {"physical_scale_record_id": "foreign-scale"},
    {"physical_scale_record_id": True},
])
def test_negative_original_scale_cannot_reissue_or_reach_customer(source_negative):
    result = _scaled_case(source_negative)
    snapshot = tuple(quantity.to_dict() for quantity in result.quantity_evidence)
    assert publish_live_ceiling_area_quantities(result) == ()
    # Both commercial consumers must remain empty, never seal a contradicted
    # numeric FIRM ceiling or synthesize a clean scale from its canonical ID.
    assert project_live_ceiling_area_customer_rows(
        result, workspace_id=7, project_id="source-project",
    ) == ()
    assert len(seal_live_ceiling_area_run(
        result, workspace_id=7, project_id="source-project",
    ).quantities) == 0
    assert tuple(quantity.to_dict() for quantity in result.quantity_evidence) == snapshot


@pytest.mark.parametrize("source_status", ["resolved", "verified"])
def test_clean_explicit_original_scale_status_survives_real_customer(source_status):
    result = _scaled_case({
        "scale_status": source_status,
        "scale_conflicts": (),
        "resolved_scale_id": "physical-scale-1",
        "physical_scale_record_id": "physical-scale-1",
    })
    issued = publish_live_ceiling_area_quantities(result)
    assert len(issued) == 1
    assert issued[0].metadata["scale_status"] == source_status
    assert issued[0].metadata["scale_conflicts"] == ()
    sealed = seal_live_ceiling_area_run(
        result, workspace_id=7, project_id="source-project",
    )
    rows = project_live_ceiling_area_customer_rows(
        result, workspace_id=7, project_id="source-project",
    )
    assert len(sealed.quantities) == len(rows) == 1
    assert rows[0]["quantity_id"] == issued[0].quantity_id
    assert rows[0]["scale_status"] == source_status
    assert rows[0]["resolved_scale_id"] == "physical-scale-1"


def test_legacy_unannotated_scale_positive_remains_unchanged():
    result = _scaled_case({})
    issued = publish_live_ceiling_area_quantities(result)
    assert len(issued) == 1
    assert "scale_status" not in issued[0].metadata
    rows = project_live_ceiling_area_customer_rows(
        result, workspace_id=7, project_id="source-project",
    )
    assert len(rows) == 1
    assert rows[0]["measurement_method"] == "scaled_geometry"
