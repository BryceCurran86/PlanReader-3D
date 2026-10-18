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
