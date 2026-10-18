"""A missing opening count is not one window."""
import pb_opening_deductions_v134 as openings


def test_supplied_count_stays_and_a_missing_count_has_no_area() -> None:
    measured = openings.normalise_opening(
        {"kind": "Window", "width_m": 1.2, "height_m": 1.5, "quantity": 2, "wall_ref": "W1"}
    )
    assert measured["quantity"] == 2
    assert openings.opening_area_m2(measured) == 3.6
    omitted = openings.normalise_opening({"width_m": 1.2, "height_m": 1.5})
    assert omitted["quantity"] == 0
    assert omitted["kind"] == ""
    assert omitted["wall_ref"] == ""
    assert openings.opening_area_m2(omitted) == 0.0
