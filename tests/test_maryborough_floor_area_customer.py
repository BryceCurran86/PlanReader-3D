"""Unit tests for pb_maryborough_floor_area_customer."""
from __future__ import annotations

from pathlib import Path

import pytest

from pb_maryborough_floor_area_customer import (
    FOOD_PREP_PHYSICAL_FLOOR_ID,
    OFFICE_PHYSICAL_FLOOR_ID,
    issue_original_maryborough_floor_customer_areas,
)

PDF_PATH = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")


@pytest.mark.skipif(not PDF_PATH.is_file(), reason="Source PDF not present")
def test_maryborough_floor_customer_areas_exact_production() -> None:
    res = issue_original_maryborough_floor_customer_areas(PDF_PATH)
    assert res.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert len(res.quantities) == 2
    assert res.sealed_run is not None

    q_map = {q.input_entity_ids[0]: q for q in res.quantities}
    assert OFFICE_PHYSICAL_FLOOR_ID in q_map
    assert FOOD_PREP_PHYSICAL_FLOOR_ID in q_map

    office = q_map[OFFICE_PHYSICAL_FLOOR_ID]
    assert office.value == 9.05352
    assert office.unit == "m2"
    assert office.family == "floor_area"

    food_prep = q_map[FOOD_PREP_PHYSICAL_FLOOR_ID]
    assert food_prep.value == 13.270425
    assert food_prep.unit == "m2"
    assert food_prep.family == "floor_area"

    assert len(res.customer_rows) == 2
