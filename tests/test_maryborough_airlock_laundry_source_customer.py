"""Tests for genuine source-owned Maryborough Airlock and Laundry floor and ceiling chains.

Tasks 6, 7, 9 in the 20-task queue:
- Task 6: Maryborough Airlock FT2 floor (1520 x 5044 mm = 7.66688 m2)
- Task 7: Maryborough Laundry FT2 floor (1655 x 5044 mm = 8.34782 m2)
- Task 9: Maryborough Airlock and Laundry WFPB 2400 ceilings (7.66688 m2 and 8.34782 m2)
"""
from __future__ import annotations

import os
from pathlib import Path
import fitz
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


def test_airlock_floor_chain(maryborough_pdf_path):
    res = floor_auth.issue_original_maryborough_airlock_customer_quantities(
        maryborough_pdf_path, workspace_id=1,
    )
    assert res.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert len(res.quantities) == 1
    assert len(res.customer_rows) == 1
    assert res.sealed_run is not None

    q = res.quantities[0]
    assert q.family == "floor_finish_area"
    assert q.value == 7.66688
    assert q.unit == "m2"
    assert floor_auth.AIRLOCK_PHYSICAL_FLOOR_ID in q.input_entity_ids

    row = res.customer_rows[0]
    assert row["quantity"] == 7.66688
    assert row["finish_system"] == "TILED"
    verify_sealed_customer_output(res.sealed_run, res.customer_rows)


def test_laundry_floor_chain(maryborough_pdf_path):
    res = floor_auth.issue_original_maryborough_laundry_customer_quantities(
        maryborough_pdf_path, workspace_id=1,
    )
    assert res.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert len(res.quantities) == 1
    assert len(res.customer_rows) == 1
    assert res.sealed_run is not None

    q = res.quantities[0]
    assert q.family == "floor_finish_area"
    assert q.value == 8.34782
    assert q.unit == "m2"
    assert floor_auth.LAUNDRY_PHYSICAL_FLOOR_ID in q.input_entity_ids

    row = res.customer_rows[0]
    assert row["quantity"] == 8.34782
    assert row["finish_system"] == "TILED"
    verify_sealed_customer_output(res.sealed_run, res.customer_rows)


def test_airlock_ceiling_chain(maryborough_pdf_path):
    res = ceiling_auth.issue_original_maryborough_airlock_ceiling_customer_quantities(
        maryborough_pdf_path, workspace_id=1,
    )
    assert res.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert len(res.quantities) == 1
    assert len(res.customer_rows) == 1
    assert res.sealed_run is not None

    q = res.quantities[0]
    assert q.family == "ceiling_lining"
    assert q.value == 7.66688
    assert q.unit == "m2"
    assert ceiling_auth.AIRLOCK_PHYSICAL_CEILING_ID in q.input_entity_ids

    row = res.customer_rows[0]
    assert row["quantity"] == 7.66688
    assert row["finish_system"] == "WET AREA FLUSHSET PLASTERBOARD"
    verify_sealed_customer_output(res.sealed_run, res.customer_rows)


def test_laundry_ceiling_chain(maryborough_pdf_path):
    res = ceiling_auth.issue_original_maryborough_laundry_ceiling_customer_quantities(
        maryborough_pdf_path, workspace_id=1,
    )
    assert res.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert len(res.quantities) == 1
    assert len(res.customer_rows) == 1
    assert res.sealed_run is not None

    q = res.quantities[0]
    assert q.family == "ceiling_lining"
    assert q.value == 8.34782
    assert q.unit == "m2"
    assert ceiling_auth.LAUNDRY_PHYSICAL_CEILING_ID in q.input_entity_ids

    row = res.customer_rows[0]
    assert row["quantity"] == 8.34782
    assert row["finish_system"] == "WET AREA FLUSHSET PLASTERBOARD"
    verify_sealed_customer_output(res.sealed_run, res.customer_rows)


def test_airlock_laundry_fail_closed_regressions(maryborough_pdf_path):
    # Invalid workspace
    r1 = floor_auth.issue_original_maryborough_airlock_customer_quantities(maryborough_pdf_path, workspace_id=0)
    assert r1.status == "ABSTAIN"
    assert r1.quantities == ()

    # Bad path
    r2 = ceiling_auth.issue_original_maryborough_laundry_ceiling_customer_quantities("nonexistent.pdf")
    assert r2.status == "ABSTAIN"
    assert r2.quantities == ()
