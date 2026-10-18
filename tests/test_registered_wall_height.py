"""A registered wall without a printed height is not 2.7 m."""
from pb_unified_building_v139 import build_figure, build_registered_walls


class _App:
    def __init__(self, walls, profiles):
        self.walls = walls
        self.profiles = profiles

    def register_elevations_v135(self, _wid):
        return {"facades": {}}

    def elevation_height_by_side_v136(self, _wid):
        return self.profiles

    def registered_wall_records_v135(self, _wid):
        return self.walls


def test_printed_height_stays_and_a_missing_height_is_not_drawn() -> None:
    walls = build_registered_walls(
        _App(
            [
                {"wall_ref": "W1", "side": "North", "length_m": 4, "height_m": 3.0},
                {"wall_ref": "W2", "side": "South", "length_m": 4},
            ],
            {},
        ),
        1,
    )
    by_ref = {wall["wall_ref"]: wall for wall in walls}
    assert by_ref["W1"]["height_m"] == 3.0
    assert by_ref["W1"]["gross_m2"] == 12.0
    assert by_ref["W2"]["height_m"] == 0.0
    assert by_ref["W2"]["gross_m2"] == 0.0
    figure = build_figure(
        [
            {"wall_ref": "W1", "a": [0, 0], "b": [4, 0], "height_m": 3.0},
            {"wall_ref": "W2", "a": [0, 0], "b": [4, 0]},
        ]
    )
    assert len(figure.data) == 1
