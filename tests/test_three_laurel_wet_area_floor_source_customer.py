"""Tests for genuine source-owned 3Laurel wet-area floor finish customer authority.

Tasks 11-14 in the 20-task queue:
- Task 11: Main bathroom tiled floor (1880 x 2750 mm = 5.1700 m2)
- Task 12: Main WC tiled floor (1560 x 1110 mm = 1.7316 m2)
- Task 13: Laundry tiled floor (3080 x 1680 mm = 5.1744 m2)
- Task 14: GF Ensuite/Laundry tiled floor (1870 x 3470 mm = 6.4889 m2)
Total wet area floor area = 18.5649 m2.
"""
from __future__ import annotations

from pathlib import Path
import pytest

from pb_customer_output_verification import verify_sealed_customer_output
from pb_three_laurel_wet_area_floor_customer import (
    FLOOR_BATHROOM_OBJECT_REF,
    FLOOR_MAIN_WC_OBJECT_REF,
    FLOOR_LAUNDRY_OBJECT_REF,
    FLOOR_GF_ENSUITE_LAUNDRY_OBJECT_REF,
    WET_AREA_FLOOR_OBJECT_REFS,
    issue_original_three_laurel_wet_area_floor_customer_quantities,
)
from tests.original_source_3laurel import require_original_3laurel


@pytest.fixture
def three_laurel_pdf_path() -> Path:
    return require_original_3laurel()


def test_three_laurel_wet_area_floor_full_takeoff(three_laurel_pdf_path):
    res = issue_original_three_laurel_wet_area_floor_customer_quantities(
        three_laurel_pdf_path, workspace_id=1,
    )
    assert res.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert len(res.quantities) == 4
    assert len(res.customer_rows) == 4
    assert res.sealed_run is not None

    qty_by_ref = {q.metadata["object_ref"]: q for q in res.quantities}
    assert qty_by_ref[FLOOR_BATHROOM_OBJECT_REF].value == pytest.approx(5.1700)
    assert qty_by_ref[FLOOR_MAIN_WC_OBJECT_REF].value == pytest.approx(1.7316)
    assert qty_by_ref[FLOOR_LAUNDRY_OBJECT_REF].value == pytest.approx(5.1744)
    assert qty_by_ref[FLOOR_GF_ENSUITE_LAUNDRY_OBJECT_REF].value == pytest.approx(6.4889)

    total_area = sum(q.value for q in res.quantities)
    assert total_area == pytest.approx(18.5649)

    for q in res.quantities:
        assert q.unit == "m2"
        assert q.status == "firm"
        assert q.confidence == 1.0
        assert q.metadata["finish_code"] == "TILES"
        assert q.metadata["semantic_finish"] == "TILED"

    verify_sealed_customer_output(res.sealed_run, res.customer_rows)


@pytest.mark.parametrize("floor_ref, expected_val", [
    (FLOOR_BATHROOM_OBJECT_REF, 5.1700),
    (FLOOR_MAIN_WC_OBJECT_REF, 1.7316),
    (FLOOR_LAUNDRY_OBJECT_REF, 5.1744),
    (FLOOR_GF_ENSUITE_LAUNDRY_OBJECT_REF, 6.4889),
])
def test_three_laurel_wet_area_floor_individual_ref(three_laurel_pdf_path, floor_ref, expected_val):
    res = issue_original_three_laurel_wet_area_floor_customer_quantities(
        three_laurel_pdf_path, workspace_id=1, floor_ref=floor_ref,
    )
    assert res.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert len(res.quantities) == 1
    assert len(res.customer_rows) == 1
    assert res.quantities[0].value == pytest.approx(expected_val)
    verify_sealed_customer_output(res.sealed_run, res.customer_rows)


def test_three_laurel_wet_area_floor_fail_closed(three_laurel_pdf_path, tmp_path):
    # Invalid workspace
    r1 = issue_original_three_laurel_wet_area_floor_customer_quantities(
        three_laurel_pdf_path, workspace_id=0,
    )
    assert r1.status == "ABSTAIN"
    assert "authenticated_workspace_unavailable" in r1.reason_codes

    # Unrecognized floor ref
    r2 = issue_original_three_laurel_wet_area_floor_customer_quantities(
        three_laurel_pdf_path, workspace_id=1, floor_ref="3laurel:surface:floor:unknown",
    )
    assert r2.status == "ABSTAIN"
    assert "unrecognized_wet_area_floor_ref" in r2.reason_codes

    # Missing PDF path
    r3 = issue_original_three_laurel_wet_area_floor_customer_quantities(
        tmp_path / "nonexistent.pdf", workspace_id=1,
    )
    assert r3.status == "ABSTAIN"
    assert "source_path_unavailable" in r3.reason_codes

    # Foreign SHA PDF
    foreign_pdf = tmp_path / "foreign.pdf"
    foreign_pdf.write_bytes(b"%PDF-1.4 foreign content dummy")
    r4 = issue_original_three_laurel_wet_area_floor_customer_quantities(
        foreign_pdf, workspace_id=1,
    )
    assert r4.status == "ABSTAIN"
    assert "three_laurel_source_sha_mismatch" in r4.reason_codes
