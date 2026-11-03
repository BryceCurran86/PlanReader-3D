"""An authenticated RCP mark cannot monetize reused floor-room area.

Source-neutral contract regressions only. Real source acceptance requires the
separate original RCP ceiling-zone geometry and numeric measurement issuer.
"""
from dataclasses import replace

import pytest

from pb_ceiling_independent_customer_metric_gate import (
    independently_sourced_ceiling_customer_metric as eligible,
)
from pb_live_ceiling_area_customer_projection import (
    project_live_ceiling_area_customer_rows,
)
from pb_live_ceiling_area_quantity_publication import (
    publish_live_ceiling_area_quantities,
)
from tests.test_live_ceiling_area_quantity_publication import (
    _result,
    _ceiling,
)
from pb_geometry_takeoff_model import MeasurementAuthorityType


def _legacy_source(authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value):
    ceiling = (
        _ceiling()
        if authority == MeasurementAuthorityType.DOCUMENTED_DIMENSION.value
        else _ceiling(
            authority=MeasurementAuthorityType.PDF_SCALED.value,
            physical_scale_record_id="physical-scale-1",
            figured_dimension_ids=(),
        )
    )
    result = _result(ceiling=ceiling)
    source = publish_live_ceiling_area_quantities(result)
    assert len(source) == 1
    return result, source[0]


@pytest.mark.parametrize("authority", (
    MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
    MeasurementAuthorityType.PDF_SCALED.value,
))
def test_legacy_source_firm_ceiling_reissue_is_not_independent_customer_metric(
    authority,
):
    result, quantity = _legacy_source(authority)
    assert quantity.status == "firm"
    assert quantity.value == 9.05352
    assert quantity.metadata["commercial_projection_allowed"] is False
    assert quantity.metadata["quantity_handoff_only"] is True
    assert not eligible(quantity)
    assert project_live_ceiling_area_customer_rows(
        result, workspace_id=1, project_id="source-neutral",
    ) == ()


@pytest.mark.parametrize("mutation", (
    {"commercial_projection_allowed": False},
    {"commercial_projection_allowed": None},
    {"commercial_projection_allowed": "true"},
    {"commercial_projection_allowed": 1},
    {"quantity_handoff_only": True},
    {"shadow_only": True},
    {"independent_rcp_ceiling_area_quantity_id": "room-area-qty-1"},
    {"independent_rcp_ceiling_area_quantity_id": ""},
    {"independent_rcp_ceiling_area_quantity_id": 123},
    {"independent_rcp_ceiling_area_evidence_id": "unowned-original-rcp"},
    {"independent_rcp_ceiling_area_page_id": "7"},
    {"independent_rcp_ceiling_area_viewport_id": "floor-vp"},
))
def test_independent_ceiling_customer_metric_requires_original_source_issuer_receipts(
    mutation,
):
    _, source = _legacy_source()
    original = {
        **source.metadata,
        "commercial_projection_allowed": True,
        "quantity_handoff_only": False,
        "independent_rcp_ceiling_area_quantity_id": "ceiling-area-qty-1",
        "independent_rcp_ceiling_area_evidence_id": "area-rcp-evidence",
        "independent_rcp_ceiling_area_page_id": "9",
        "independent_rcp_ceiling_area_viewport_id": "rcp-vp",
        "support_page_id": "9",
        "support_viewport_id": "rcp-vp",
    }
    source = replace(
        source,
        formula="authenticated_independent_rcp_ceiling_area_from_original_figures",
        evidence_ids=(*source.evidence_ids, "area-rcp-evidence"),
        metadata={**original, **mutation},
    )
    assert not eligible(source)


def test_independent_metric_source_receipt_contract_does_not_need_floor_area_reuse():
    _, source = _legacy_source()
    independently_issued = replace(
        source,
        formula="authenticated_independent_rcp_ceiling_area_from_original_figures",
        evidence_ids=(*source.evidence_ids, "area-rcp-evidence"),
        metadata={
            **source.metadata,
            "commercial_projection_allowed": True,
            "quantity_handoff_only": False,
            "independent_rcp_ceiling_area_quantity_id": "ceiling-area-qty-1",
            "independent_rcp_ceiling_area_evidence_id": "area-rcp-evidence",
            "independent_rcp_ceiling_area_page_id": "9",
            "independent_rcp_ceiling_area_viewport_id": "rcp-vp",
            "support_page_id": "9",
            "support_viewport_id": "rcp-vp",
        },
    )
    # This tests the CONTRACT, not a claim that the original issuer exists.
    assert eligible(independently_issued)
    assert not eligible(source)
    assert source.metadata["commercial_projection_allowed"] is False
