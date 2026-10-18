"""An unprinted window sill is not 0.9 m, and a missing count is not one."""
from pb_opening_evidence_v170 import from_v134_record


def test_printed_sill_and_count_stay_and_missing_ones_do_not() -> None:
    window = from_v134_record(
        {"kind": "Window", "width_m": 1.2, "height_m": 1.2, "quantity": 2, "sill_m": 0.9}
    )
    assert window.quantity == 2
    assert window.sill_m == 0.9
    assert window.area_m2 == 2.88
    omitted = from_v134_record({"kind": "Window", "width_m": 1.2, "height_m": 1.2})
    assert omitted.quantity == 0
    assert omitted.sill_m == 0.0
    assert omitted.area_m2 is None
    door = from_v134_record({"kind": "Door", "width_m": 0.9, "height_m": 2.1, "quantity": 1})
    assert door.sill_m == 0.0
