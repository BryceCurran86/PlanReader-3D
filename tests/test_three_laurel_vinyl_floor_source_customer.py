"""Tests for genuine source-owned 3Laurel vinyl floor finish customer authority.

Tasks 17-18 in the 20-task queue:
3 vinyl floor surfaces:
- Media room vinyl floor: 4200 x 3130 mm = 13.1460 m2
- Bed 2 vinyl floor: 3000 x 4200 mm = 12.6000 m2
- Bed 3 vinyl floor: 3000 x 4200 mm = 12.6000 m2
Total vinyl floor area = 38.3460 m2.
"""
from __future__ import annotations

from pathlib import Path
import pytest

from pb_customer_output_verification import verify_sealed_customer_output
from pb_three_laurel_vinyl_floor_customer import (
    FLOOR_BED2_OBJECT_REF,
    FLOOR_BED3_OBJECT_REF,
    FLOOR_MEDIA_OBJECT_REF,
    VINYL_FLOOR_OBJECT_REFS,
    issue_original_three_laurel_vinyl_floor_customer_quantities,
)
from tests.original_source_3laurel import require_original_3laurel


@pytest.fixture
def three_laurel_pdf_path() -> Path:
    return require_original_3laurel()


def test_three_laurel_vinyl_floor_full_takeoff(three_laurel_pdf_path):
    res = issue_original_three_laurel_vinyl_floor_customer_quantities(
        three_laurel_pdf_path, workspace_id=1,
    )
    assert res.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert len(res.quantities) == 3
    assert len(res.customer_rows) == 3
    assert res.sealed_run is not None

    qty_by_ref = {q.metadata["object_ref"]: q for q in res.quantities}
    assert qty_by_ref[FLOOR_MEDIA_OBJECT_REF].value == pytest.approx(13.1460)
    assert qty_by_ref[FLOOR_BED2_OBJECT_REF].value == pytest.approx(12.6000)
    assert qty_by_ref[FLOOR_BED3_OBJECT_REF].value == pytest.approx(12.6000)

    total_area = sum(q.value for q in res.quantities)
    assert total_area == pytest.approx(38.3460)

    for q in res.quantities:
        assert q.family == "floor_finish_area"
        assert q.unit == "m2"
        assert q.status == "firm"
        assert q.confidence == 1.0
        assert q.metadata["finish_code"] == "VINYL"
        assert q.metadata["semantic_finish"] == "VINYL"

    verify_sealed_customer_output(res.sealed_run, res.customer_rows)


@pytest.mark.parametrize("floor_ref, expected_val", [
    (FLOOR_MEDIA_OBJECT_REF, 13.1460),
    (FLOOR_BED2_OBJECT_REF, 12.6000),
    (FLOOR_BED3_OBJECT_REF, 12.6000),
])
def test_three_laurel_vinyl_floor_individual_ref(three_laurel_pdf_path, floor_ref, expected_val):
    res = issue_original_three_laurel_vinyl_floor_customer_quantities(
        three_laurel_pdf_path, workspace_id=1, floor_ref=floor_ref,
    )
    assert res.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert len(res.quantities) == 1
    assert len(res.customer_rows) == 1
    assert res.quantities[0].value == pytest.approx(expected_val)
    verify_sealed_customer_output(res.sealed_run, res.customer_rows)


def test_three_laurel_vinyl_floor_fail_closed(three_laurel_pdf_path, tmp_path):
    # Invalid workspace
    r1 = issue_original_three_laurel_vinyl_floor_customer_quantities(
        three_laurel_pdf_path, workspace_id=0,
    )
    assert r1.status == "ABSTAIN"
    assert "authenticated_workspace_unavailable" in r1.reason_codes

    # Unrecognized floor ref
    r2 = issue_original_three_laurel_vinyl_floor_customer_quantities(
        three_laurel_pdf_path, workspace_id=1, floor_ref="3laurel:surface:floor:unknown",
    )
    assert r2.status == "ABSTAIN"
    assert "unrecognized_vinyl_floor_ref" in r2.reason_codes

    # Missing PDF path
    r3 = issue_original_three_laurel_vinyl_floor_customer_quantities(
        tmp_path / "nonexistent.pdf", workspace_id=1,
    )
    assert r3.status == "ABSTAIN"
    assert "source_path_unavailable" in r3.reason_codes

    # Foreign SHA PDF
    foreign_pdf = tmp_path / "foreign.pdf"
    foreign_pdf.write_bytes(b"%PDF-1.4 foreign content dummy")
    r4 = issue_original_three_laurel_vinyl_floor_customer_quantities(
        foreign_pdf, workspace_id=1,
    )
    assert r4.status == "ABSTAIN"
    assert "three_laurel_source_sha_mismatch" in r4.reason_codes
