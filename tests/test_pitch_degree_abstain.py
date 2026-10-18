"""A pitched ceiling without a printed degree stays at its flat area."""
from pb_paintable_surface_v176 import calculate_pitched_surface_area


def test_a_supplied_pitch_expands_and_zero_does_not() -> None:
    assert round(calculate_pitched_surface_area(100.0, 30.0), 2) == 115.47
    assert calculate_pitched_surface_area(100.0, 0.0) == 100.0
