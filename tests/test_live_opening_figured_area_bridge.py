from __future__ import annotations

import pytest

from pb_live_physical_opening_void_composition import _canonical_opening_area
from pb_opening_label_dimension_authority import OpeningLabelDimensionEvidence


def _evidence(*, area_m2, axis_order_resolved=False):
    return OpeningLabelDimensionEvidence(
        evidence_id="label-evidence-1",
        opening_record_id="opening-1",
        page_id="1",
        viewport_id="viewport-1",
        source_text_observation_ids=("text-1",),
        raw_text="1200 - 1810 asw",
        dimension_values_mm=(1200.0, 1810.0),
        semantic_kind="window",
        area_m2=area_m2,
        axis_order_resolved=axis_order_resolved,
    )


def test_unordered_figured_pair_can_publish_area_without_width_or_height() -> None:
    area, basis, record_id = _canonical_opening_area(
        width_m=None,
        height_m=None,
        figured_label_evidence=_evidence(area_m2=2.172),
    )
    assert area == pytest.approx(2.172)
    assert basis == "figured_opening_label"
    assert record_id == "label-evidence-1"


def test_complete_resolved_geometry_is_not_overwritten_by_label_pair() -> None:
    area, basis, record_id = _canonical_opening_area(
        width_m=1.0,
        height_m=2.1,
        figured_label_evidence=_evidence(area_m2=9.99),
    )
    assert area == pytest.approx(2.1)
    assert basis == "resolved_opening_geometry"
    # The label remains provenance even when it does not replace resolved geometry.
    assert record_id == "label-evidence-1"


def test_single_axis_label_never_manufactures_area() -> None:
    evidence = OpeningLabelDimensionEvidence(
        evidence_id="single-label",
        opening_record_id="opening-1",
        page_id="1",
        viewport_id="viewport-1",
        source_text_observation_ids=("text-1",),
        raw_text="870 cs",
        dimension_values_mm=(870.0,),
        semantic_kind="door",
        area_m2=None,
        axis_order_resolved=False,
    )
    area, basis, record_id = _canonical_opening_area(
        width_m=None,
        height_m=None,
        figured_label_evidence=evidence,
    )
    assert area is None
    assert basis is None
    assert record_id == "single-label"


def test_axis_order_claim_without_resolved_geometry_does_not_publish_pair_area() -> None:
    area, basis, _record_id = _canonical_opening_area(
        width_m=None,
        height_m=None,
        figured_label_evidence=_evidence(
            area_m2=2.172,
            axis_order_resolved=True,
        ),
    )
    assert area is None
    assert basis is None
