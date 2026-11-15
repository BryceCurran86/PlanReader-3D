"""Tests for genuine source-owned 3Laurel primary ceiling finish customer authority.

Task 15 in the 20-task queue:
7 primary ceiling finish planes:
- Garage ceiling plane: 36.40 m2
- GF Alfresco ceiling plane: 10.50 m2
- GF Living ceiling plane: 60.00 m2
- GF Porch ceiling plane: 1.40 m2
- Main-house Alfresco ceiling plane: 13.60 m2
- Main-house Living ceiling plane: 168.10 m2
- Main-house Porch ceiling plane: 7.50 m2
Total primary ceiling plane area = 297.50 m2.
"""
from __future__ import annotations

from pathlib import Path
import pytest

from pb_customer_output_verification import verify_sealed_customer_output
from pb_three_laurel_ceiling_customer import (
    CEILING_GARAGE_OBJECT_REF,
    CEILING_GF_ALFRESCO_OBJECT_REF,
    CEILING_GF_LIVING_OBJECT_REF,
    CEILING_GF_PORCH_OBJECT_REF,
    CEILING_MAIN_ALFRESCO_OBJECT_REF,
    CEILING_MAIN_LIVING_OBJECT_REF,
    CEILING_MAIN_PORCH_OBJECT_REF,
    PRIMARY_CEILING_PLANE_REFS,
    issue_original_three_laurel_ceiling_customer_quantities,
)
from tests.original_source_3laurel import require_original_3laurel


@pytest.fixture
def three_laurel_pdf_path() -> Path:
    return require_original_3laurel()


def test_three_laurel_ceiling_full_takeoff(three_laurel_pdf_path):
    res = issue_original_three_laurel_ceiling_customer_quantities(
        three_laurel_pdf_path, workspace_id=1,
    )
    assert res.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert len(res.quantities) == 7
    assert len(res.customer_rows) == 7
    assert res.sealed_run is not None

    qty_by_ref = {q.metadata["object_ref"]: q for q in res.quantities}
    assert qty_by_ref[CEILING_GARAGE_OBJECT_REF].value == pytest.approx(36.40)
    assert qty_by_ref[CEILING_GF_ALFRESCO_OBJECT_REF].value == pytest.approx(10.50)
    assert qty_by_ref[CEILING_GF_LIVING_OBJECT_REF].value == pytest.approx(60.00)
    assert qty_by_ref[CEILING_GF_PORCH_OBJECT_REF].value == pytest.approx(1.40)
    assert qty_by_ref[CEILING_MAIN_ALFRESCO_OBJECT_REF].value == pytest.approx(13.60)
    assert qty_by_ref[CEILING_MAIN_LIVING_OBJECT_REF].value == pytest.approx(168.10)
    assert qty_by_ref[CEILING_MAIN_PORCH_OBJECT_REF].value == pytest.approx(7.50)

    total_area = sum(q.value for q in res.quantities)
    assert total_area == pytest.approx(297.50)

    for q in res.quantities:
        assert q.family == "ceiling_lining"
        assert q.unit == "m2"
        assert q.status == "firm"
        assert q.confidence == 1.0

    verify_sealed_customer_output(res.sealed_run, res.customer_rows)


@pytest.mark.parametrize("ceiling_ref, expected_val", [
    (CEILING_GARAGE_OBJECT_REF, 36.40),
    (CEILING_GF_ALFRESCO_OBJECT_REF, 10.50),
    (CEILING_GF_LIVING_OBJECT_REF, 60.00),
    (CEILING_GF_PORCH_OBJECT_REF, 1.40),
    (CEILING_MAIN_ALFRESCO_OBJECT_REF, 13.60),
    (CEILING_MAIN_LIVING_OBJECT_REF, 168.10),
    (CEILING_MAIN_PORCH_OBJECT_REF, 7.50),
])
def test_three_laurel_ceiling_individual_ref(three_laurel_pdf_path, ceiling_ref, expected_val):
    res = issue_original_three_laurel_ceiling_customer_quantities(
        three_laurel_pdf_path, workspace_id=1, ceiling_ref=ceiling_ref,
    )
    assert res.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert len(res.quantities) == 1
    assert len(res.customer_rows) == 1
    assert res.quantities[0].value == pytest.approx(expected_val)
    verify_sealed_customer_output(res.sealed_run, res.customer_rows)


def test_three_laurel_ceiling_fail_closed(three_laurel_pdf_path, tmp_path):
    # Invalid workspace
    r1 = issue_original_three_laurel_ceiling_customer_quantities(
        three_laurel_pdf_path, workspace_id=0,
    )
    assert r1.status == "ABSTAIN"
    assert "authenticated_workspace_unavailable" in r1.reason_codes

    # Unrecognized ceiling ref
    r2 = issue_original_three_laurel_ceiling_customer_quantities(
        three_laurel_pdf_path, workspace_id=1, ceiling_ref="3laurel:surface:ceiling:unknown",
    )
    assert r2.status == "ABSTAIN"
    assert "unrecognized_ceiling_ref" in r2.reason_codes

    # Missing PDF path
    r3 = issue_original_three_laurel_ceiling_customer_quantities(
        tmp_path / "nonexistent.pdf", workspace_id=1,
    )
    assert r3.status == "ABSTAIN"
    assert "source_path_unavailable" in r3.reason_codes

    # Foreign SHA PDF
    foreign_pdf = tmp_path / "foreign.pdf"
    foreign_pdf.write_bytes(b"%PDF-1.4 foreign content dummy")
    r4 = issue_original_three_laurel_ceiling_customer_quantities(
        foreign_pdf, workspace_id=1,
    )
    assert r4.status == "ABSTAIN"
    assert "three_laurel_source_sha_mismatch" in r4.reason_codes
