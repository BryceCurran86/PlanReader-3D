"""Unit tests for pb_maryborough_customer_authority."""
from __future__ import annotations

from pathlib import Path

import pytest

from pb_maryborough_customer_authority import (
    AIRLOCK_PHYSICAL_FLOOR_ID,
    FOOD_PREP_PHYSICAL_FLOOR_ID,
    LAUNDRY_PHYSICAL_FLOOR_ID,
    OFFICE_PHYSICAL_FLOOR_ID,
    PWD_PHYSICAL_FLOOR_ID,
    issue_all_original_maryborough_customer_quantities,
)

PDF_PATH = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")


@pytest.mark.skipif(not PDF_PATH.is_file(), reason="Source PDF not present")
def test_maryborough_customer_authority_all_24_items() -> None:
    res = issue_all_original_maryborough_customer_quantities(PDF_PATH)
    assert res.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert len(res.quantities) == 24
    assert res.sealed_run is not None
    assert len(res.customer_rows) == 24
    assert len(res.identity_map_bindings) == 24

    # Verify all quantities are firm and lineage-verified
    assert all(q.status == "firm" for q in res.quantities)
    assert all(not q.abstained for q in res.quantities)
    assert all(q.confidence == 1.0 for q in res.quantities)
    assert all(q.lineage_ok for q in res.sealed_run.quantities)

    # Floor quantities verification
    q_map = {q.semantic_key: q for q in res.quantities}
    office_key = f"floor_area:{OFFICE_PHYSICAL_FLOOR_ID}:maryborough-office-ft3-floor-area"
    food_prep_key = f"floor_area:{FOOD_PREP_PHYSICAL_FLOOR_ID}:maryborough-food-prep-ft3-floor-area"
    pwd_key = f"floor_area:{PWD_PHYSICAL_FLOOR_ID}:maryborough-pwd-ft2-floor-area"
    airlock_key = f"floor_area:{AIRLOCK_PHYSICAL_FLOOR_ID}:maryborough-airlock-ft2-floor-area"
    laundry_key = f"floor_area:{LAUNDRY_PHYSICAL_FLOOR_ID}:maryborough-laundry-ft2-floor-area"

    assert office_key in q_map
    assert q_map[office_key].value == 9.05352
    assert q_map[office_key].unit == "m2"

    assert food_prep_key in q_map
    assert q_map[food_prep_key].value == 13.270425
    assert q_map[food_prep_key].unit == "m2"

    assert pwd_key in q_map
    assert q_map[pwd_key].value == 7.854
    assert q_map[pwd_key].unit == "m2"

    assert airlock_key in q_map
    assert q_map[airlock_key].value == 7.66688
    assert q_map[airlock_key].unit == "m2"

    assert laundry_key in q_map
    assert q_map[laundry_key].value == 8.34782
    assert q_map[laundry_key].unit == "m2"

    # Opening counts verification
    item_map = {b["benchmark_item_id"]: b for b in res.identity_map_bindings}
    assert "maryborough-window-tagged-count" in item_map
    assert "maryborough-door-ipf3-count" in item_map
    assert "maryborough-door-laminex-partition-count" in item_map
    assert "maryborough-door-aluminium-glazed-count" in item_map

    counts_by_item = {
        q.metadata.get("benchmark_item_id", q.semantic_key.split(":")[-1]): q.value
        for q in res.quantities
        if q.unit == "nr"
    }
    assert counts_by_item["maryborough-window-tagged-count"] == 6.0
    assert counts_by_item["maryborough-door-ipf3-count"] == 11.0
    assert counts_by_item["maryborough-door-laminex-partition-count"] == 3.0
    assert counts_by_item["maryborough-door-aluminium-glazed-count"] == 2.0
