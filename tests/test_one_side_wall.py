"""A compass side names one wall only when that side has one wall."""
import json

from pb_opening_geometry_v137 import attach_openings


class _App:
    def __init__(self, openings):
        self.openings = openings
        self.saved = None

    def workspace_setting(self, _wid, _key, _default):
        return json.dumps(self.openings)

    def set_workspace_setting(self, _wid, _key, value):
        self.saved = value


def test_one_north_wall_stays_and_two_north_walls_do_not() -> None:
    opening = {"wall_ref": "North", "kind": "window", "width_m": 1.2, "height_m": 1.2, "quantity": 1}
    one = attach_openings(_App([opening]), 1, [{"wall_ref": "W1", "side": "North", "length_m": 4}])
    assert one[0]["resolved_wall_ref"] == "W1"
    two = attach_openings(
        _App([opening]),
        1,
        [
            {"wall_ref": "W1", "side": "North", "length_m": 8},
            {"wall_ref": "W2", "side": "North", "length_m": 3},
        ],
    )
    assert two[0]["resolved_wall_ref"] == ""
