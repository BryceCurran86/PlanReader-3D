import pytest

import pb_opening_production_v175 as prod


def _manual(quantity=1):
    row = {
        "deduct": True,
        "wall_ref": "W1",
        "width_m": 1.0,
        "height_m": 2.0,
        "manual_override_confirmed": True,
    }
    if quantity is not None:
        row["quantity"] = quantity
    return row


def test_stated_count_deducts_its_area():
    assert prod._safe_deducted_area([_manual(2)]) == 4.0


def test_missing_count_does_not_deduct_one_opening():
    row = _manual(None)
    assert "quantity" not in row
    assert prod._safe_deducted_area([row]) == 0.0


def test_blank_count_does_not_deduct_one_opening():
    assert prod._safe_deducted_area([_manual("")]) == 0.0


def test_b5_merge_keeps_blank_count_at_zero_area():
    row = {
        "deduct": True,
        "wall_ref": "W01",
        "resolved_wall_ref": "W01",
        "width_m": 0.82,
        "height_m": 2.1,
        "quantity": "",
        "page_no": 1,
        "page_id": 5,
        "workspace_id": 7,
        "reconciliation_complete": True,
        "deduction_status": "auto_eligible",
        "deduction_decision": "deducted",
        "dimension_basis": "rough_opening",
        "geometry_confidence": 0.9,
        "dimension_confidence": 0.9,
        "association_confidence": 0.9,
    }
    merged = prod.merge_b5_authoritative([], [row])
    assert len(merged) == 1
    assert merged[0]["area_m2"] == 0.0

@pytest.mark.parametrize("bad_count", [
    True, False, 1.5, 0.5, "1.5", "1e3", "2.0", "NaN", "inf", -1, 0,
])
def test_noninteger_or_unproven_count_never_deducts_area(bad_count):
    assert prod._stated_quantity(_manual(bad_count)) == 0
    assert prod._safe_deducted_area([_manual(bad_count)]) == 0.0
    assert prod._safe_net_wall_area(10.0, [_manual(bad_count)]) == 10.0


@pytest.mark.parametrize(("stated", "expected"), [
    (1, 1), (2, 2), (2.0, 2), ("2", 2), (" 02 ", 2),
])
def test_proven_positive_integer_count_retained(stated, expected):
    assert prod._stated_quantity(_manual(stated)) == expected
    assert prod._safe_deducted_area([_manual(stated)]) == 2.0 * expected


@pytest.mark.parametrize("bad_count", [True, 1.5, "1e3", "2.0"])
def test_b5_merge_invalid_count_has_no_deduction(bad_count):
    row = {
        "deduct": True, "wall_ref": "W01", "resolved_wall_ref": "W01",
        "width_m": 0.82, "height_m": 2.1, "quantity": bad_count,
        "page_no": 1, "page_id": 5, "workspace_id": 7,
        "reconciliation_complete": True, "deduction_status": "auto_eligible",
        "deduction_decision": "deducted", "dimension_basis": "rough_opening",
        "geometry_confidence": 0.9, "dimension_confidence": 0.9,
        "association_confidence": 0.9,
    }
    merged = prod.merge_b5_authoritative([], [row])
    assert len(merged) == 1
    assert merged[0]["area_m2"] == 0.0
