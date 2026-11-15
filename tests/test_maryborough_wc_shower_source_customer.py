"""Tests for genuine source-owned Maryborough WC & Shower floor and ceiling chains.

Tasks 8 and 10 in the 20-task queue:
- Task 8: Deliver the three Maryborough WC/shower FT2 floors (D07 North, D08 Middle, D09 South)
  Each 2935 x 1620 mm = 4.7547 m2
- Task 10: Deliver the three Maryborough WC/shower WFPB 2400 ceilings (D07, D08, D09)
  Each 2935 x 1620 mm = 4.7547 m2
"""
from __future__ import annotations

import os
from pathlib import Path
import pytest

import pb_maryborough_customer_authority as floor_auth
import pb_maryborough_ceiling_customer as ceiling_auth
from pb_customer_output_verification import verify_sealed_customer_output


@pytest.fixture
def maryborough_pdf_path() -> Path:
    path = Path(
        os.environ.get(
            "PLANREADER_ORIGINAL_MARYBOROUGH",
            "C:/Users/bryce/PlanReader-3D-dimarea/documents/sources/Arch_Combined_Maryborough_Service_Station.pdf",
        )
    )
    if not path.is_file():
        pytest.skip("private original Maryborough PDF unavailable in test environment")
    return path


@pytest.mark.parametrize("door, expected_fid", [
    ("D07", floor_auth.WC_SHOWER_NORTH_PHYSICAL_FLOOR_ID),
    ("D08", floor_auth.WC_SHOWER_MIDDLE_PHYSICAL_FLOOR_ID),
    ("D09", floor_auth.WC_SHOWER_SOUTH_PHYSICAL_FLOOR_ID),
])
def test_wc_shower_floor_chain(maryborough_pdf_path, door, expected_fid):
    res = floor_auth.issue_original_maryborough_wc_shower_customer_quantities(
        maryborough_pdf_path, door_callout=door, workspace_id=1,
    )
    assert res.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert len(res.quantities) == 1
    assert len(res.customer_rows) == 1
    assert res.sealed_run is not None

    q = res.quantities[0]
    assert q.family == "floor_finish_area"
    assert q.value == 4.7547
    assert q.unit == "m2"
    assert expected_fid in q.input_entity_ids

    row = res.customer_rows[0]
    assert row["quantity"] == 4.7547
    assert row["finish_system"] == "TILED"
    verify_sealed_customer_output(res.sealed_run, res.customer_rows)


@pytest.mark.parametrize("door, expected_cid", [
    ("D07", ceiling_auth.WC_SHOWER_NORTH_PHYSICAL_CEILING_ID),
    ("D08", ceiling_auth.WC_SHOWER_MIDDLE_PHYSICAL_CEILING_ID),
    ("D09", ceiling_auth.WC_SHOWER_SOUTH_PHYSICAL_CEILING_ID),
])
def test_wc_shower_ceiling_chain(maryborough_pdf_path, door, expected_cid):
    res = ceiling_auth.issue_original_maryborough_wc_shower_ceiling_customer_quantities(
        maryborough_pdf_path, door_callout=door, workspace_id=1,
    )
    assert res.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert len(res.quantities) == 1
    assert len(res.customer_rows) == 1
    assert res.sealed_run is not None

    q = res.quantities[0]
    assert q.family == "ceiling_lining"
    assert q.value == 4.7547
    assert q.unit == "m2"
    assert expected_cid in q.input_entity_ids

    row = res.customer_rows[0]
    assert row["quantity"] == 4.7547
    assert row["finish_system"] == "WET AREA FLUSHSET PLASTERBOARD"
    verify_sealed_customer_output(res.sealed_run, res.customer_rows)


def test_wc_shower_fail_closed_regressions(maryborough_pdf_path):
    # Unknown door
    r1 = floor_auth.issue_original_maryborough_wc_shower_customer_quantities(
        maryborough_pdf_path, door_callout="D99", workspace_id=1,
    )
    assert r1.status == "ABSTAIN"
    assert r1.quantities == ()

    # Invalid workspace
    r2 = ceiling_auth.issue_original_maryborough_wc_shower_ceiling_customer_quantities(
        maryborough_pdf_path, door_callout="D07", workspace_id=-1,
    )
    assert r2.status == "ABSTAIN"
    assert r2.quantities == ()
