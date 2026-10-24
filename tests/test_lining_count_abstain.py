"""A lining measurement does not invent one side and one layer."""
from tradereader_plastering import calculate_measurement


def test_supplied_layers_stay_and_a_missing_count_installs_nothing() -> None:
    measured = calculate_measurement(
        {
            "element_type": "Wall lining",
            "wall_length_m": 10,
            "height_m": 2.7,
            "layers": 2,
            "sides": 1,
            "board_width_mm": 1200,
            "board_length_mm": 2400,
        }
    )
    assert measured["installed_board_area_m2"] == 54.0
    omitted = calculate_measurement(
        {
            "element_type": "Wall lining",
            "wall_length_m": 10,
            "height_m": 2.7,
            "board_width_mm": 1200,
            "board_length_mm": 2400,
        }
    )
    assert omitted["installed_board_area_m2"] == 0.0
    assert omitted["sheet_count"] == 0
