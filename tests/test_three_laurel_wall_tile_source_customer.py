"""Tests for genuine source-owned 3Laurel wall tile finish customer authority.

Task 16 in the 20-task queue:
8 wall tile finish surfaces:
- Laundry D skirting: 3080 x 190 mm = 0.5852 m2
- Bathroom C shower net: 900 x 2100 mm = 1.8900 m2
- Ensuite B shower return net: 900 x 2700 mm = 2.4300 m2
- Ensuite D shower return net: 900 x 2700 mm = 2.4300 m2
- GF Ensuite B shower return net: 900 x 2700 mm = 2.4300 m2
- GF Ensuite D shower return net: 900 x 2700 mm = 2.4300 m2
- Ensuite rear flat after niche: 1680 x 2700 - 600 x 400 mm = 4.2960 m2
- GF Ensuite rear flat after niche: 1870 x 2700 - 600 x 400 mm = 4.8090 m2
Total wall tile area = 21.3002 m2.
"""
from __future__ import annotations

from pathlib import Path
import pytest

from pb_customer_output_verification import verify_sealed_customer_output
from pb_three_laurel_wall_tile_customer import (
    WALL_TILE_BATHROOM_C_SHOWER_NET_REF,
    WALL_TILE_ENSUITE_B_RETURN_NET_REF,
    WALL_TILE_ENSUITE_D_RETURN_NET_REF,
    WALL_TILE_ENSUITE_REAR_FLAT_REF,
    WALL_TILE_GF_ENSUITE_B_RETURN_NET_REF,
    WALL_TILE_GF_ENSUITE_D_RETURN_NET_REF,
    WALL_TILE_GF_ENSUITE_REAR_FLAT_REF,
    WALL_TILE_LAUNDRY_D_SKIRTING_REF,
    WALL_TILE_OBJECT_REFS,
    issue_original_three_laurel_wall_tile_customer_quantities,
)
from tests.original_source_3laurel import require_original_3laurel


@pytest.fixture
def three_laurel_pdf_path() -> Path:
    return require_original_3laurel()


def test_three_laurel_wall_tile_full_takeoff(three_laurel_pdf_path):
    res = issue_original_three_laurel_wall_tile_customer_quantities(
        three_laurel_pdf_path, workspace_id=1,
    )
    assert res.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert len(res.quantities) == 8
    assert len(res.customer_rows) == 8
    assert res.sealed_run is not None

    qty_by_ref = {q.metadata["object_ref"]: q for q in res.quantities}
    assert qty_by_ref[WALL_TILE_LAUNDRY_D_SKIRTING_REF].value == pytest.approx(0.5852)
    assert qty_by_ref[WALL_TILE_BATHROOM_C_SHOWER_NET_REF].value == pytest.approx(1.8900)
    assert qty_by_ref[WALL_TILE_ENSUITE_B_RETURN_NET_REF].value == pytest.approx(2.4300)
    assert qty_by_ref[WALL_TILE_ENSUITE_D_RETURN_NET_REF].value == pytest.approx(2.4300)
    assert qty_by_ref[WALL_TILE_GF_ENSUITE_B_RETURN_NET_REF].value == pytest.approx(2.4300)
    assert qty_by_ref[WALL_TILE_GF_ENSUITE_D_RETURN_NET_REF].value == pytest.approx(2.4300)
    assert qty_by_ref[WALL_TILE_ENSUITE_REAR_FLAT_REF].value == pytest.approx(4.2960)
    assert qty_by_ref[WALL_TILE_GF_ENSUITE_REAR_FLAT_REF].value == pytest.approx(4.8090)

    total_area = sum(q.value for q in res.quantities)
    assert total_area == pytest.approx(21.3002)

    for q in res.quantities:
        assert q.family == "wall_finish_area"
        assert q.unit == "m2"
        assert q.status == "firm"
        assert q.confidence == 1.0
        assert q.metadata["finish_code"] == "TILES"
        assert q.metadata["semantic_finish"] == "TILED"

    verify_sealed_customer_output(res.sealed_run, res.customer_rows)


@pytest.mark.parametrize("wall_tile_ref, expected_val", [
    (WALL_TILE_LAUNDRY_D_SKIRTING_REF, 0.5852),
    (WALL_TILE_BATHROOM_C_SHOWER_NET_REF, 1.8900),
    (WALL_TILE_ENSUITE_B_RETURN_NET_REF, 2.4300),
    (WALL_TILE_ENSUITE_D_RETURN_NET_REF, 2.4300),
    (WALL_TILE_GF_ENSUITE_B_RETURN_NET_REF, 2.4300),
    (WALL_TILE_GF_ENSUITE_D_RETURN_NET_REF, 2.4300),
    (WALL_TILE_ENSUITE_REAR_FLAT_REF, 4.2960),
    (WALL_TILE_GF_ENSUITE_REAR_FLAT_REF, 4.8090),
])
def test_three_laurel_wall_tile_individual_ref(three_laurel_pdf_path, wall_tile_ref, expected_val):
    res = issue_original_three_laurel_wall_tile_customer_quantities(
        three_laurel_pdf_path, workspace_id=1, wall_tile_ref=wall_tile_ref,
    )
    assert res.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert len(res.quantities) == 1
    assert len(res.customer_rows) == 1
    assert res.quantities[0].value == pytest.approx(expected_val)
    verify_sealed_customer_output(res.sealed_run, res.customer_rows)


def test_three_laurel_wall_tile_fail_closed(three_laurel_pdf_path, tmp_path):
    # Invalid workspace
    r1 = issue_original_three_laurel_wall_tile_customer_quantities(
        three_laurel_pdf_path, workspace_id=0,
    )
    assert r1.status == "ABSTAIN"
    assert "authenticated_workspace_unavailable" in r1.reason_codes

    # Unrecognized wall tile ref
    r2 = issue_original_three_laurel_wall_tile_customer_quantities(
        three_laurel_pdf_path, workspace_id=1, wall_tile_ref="3laurel:surface:wall_tile:unknown",
    )
    assert r2.status == "ABSTAIN"
    assert "unrecognized_wall_tile_ref" in r2.reason_codes

    # Missing PDF path
    r3 = issue_original_three_laurel_wall_tile_customer_quantities(
        tmp_path / "nonexistent.pdf", workspace_id=1,
    )
    assert r3.status == "ABSTAIN"
    assert "source_path_unavailable" in r3.reason_codes

    # Foreign SHA PDF
    foreign_pdf = tmp_path / "foreign.pdf"
    foreign_pdf.write_bytes(b"%PDF-1.4 foreign content dummy")
    r4 = issue_original_three_laurel_wall_tile_customer_quantities(
        foreign_pdf, workspace_id=1,
    )
    assert r4.status == "ABSTAIN"
    assert "three_laurel_source_sha_mismatch" in r4.reason_codes
