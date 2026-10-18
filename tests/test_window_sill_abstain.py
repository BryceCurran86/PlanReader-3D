"""An unprinted window sill is not 0.9 m, and a missing count is not one."""
import pytest

from pb_opening_deductions_v134 import normalise_opening, opening_area_m2
from pb_opening_evidence_v170 import from_v134_record, to_v134_record


def test_printed_sill_and_count_stay_and_missing_ones_do_not() -> None:
    window = from_v134_record(
        {"kind": "Window", "width_m": 1.2, "height_m": 1.2, "quantity": 2, "sill_m": 0.9}
    )
    assert window.quantity == 2
    assert window.sill_m == 0.9
    assert window.area_m2 == 2.88
    omitted = from_v134_record({"kind": "Window", "width_m": 1.2, "height_m": 1.2})
    assert omitted.quantity == 0
    assert omitted.sill_m is None
    assert omitted.area_m2 is None
    door = from_v134_record({"kind": "Door", "width_m": 0.9, "height_m": 2.1, "quantity": 1})
    assert door.sill_m == 0.0


def test_explicit_zero_and_known_window_sill_roundtrip() -> None:
    observed = from_v134_record({"kind": "Window", "sill_m": 0.0, "quantity": 1})
    assert observed.sill_m == 0.0
    known = from_v134_record({"kind": "Window", "sill_m": 1.25, "quantity": 1})
    assert to_v134_record(known)["sill_m"] == 1.25
    assert normalise_opening(to_v134_record(known))["sill_m"] == 1.25
    assert from_v134_record(normalise_opening(to_v134_record(known))).sill_m == 1.25


@pytest.mark.parametrize("invalid", [True, False, "nan", "inf", -1, "-0.5", "nonsense"])
def test_malformed_sill_is_not_a_measured_zero(invalid) -> None:
    record = {"kind": "Window", "sill_m": invalid, "quantity": 1}
    assert from_v134_record(record).sill_m is None
    assert normalise_opening(record)["sill_m"] is None


@pytest.mark.parametrize("invalid", [None, "", True, False, 1.25, "1.5", "1e3", -2, 0])
def test_invalid_or_missing_manual_count_does_not_create_area(invalid) -> None:
    record = {"kind": "Window", "width_m": 1.2, "height_m": 1.5, "quantity": invalid}
    assert from_v134_record(record).area_m2 is None
    assert normalise_opening(record)["quantity"] == 0
    assert opening_area_m2(record) == 0.0
