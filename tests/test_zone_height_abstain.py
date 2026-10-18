"""A mapped zone without a printed height is not a 2.7 m Ground mass."""
from pb_3d_quickstart_v1213 import refresh_zone_masses


class _App:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    def lquery(self, sql, params=()):
        if "mapped_zones" in sql:
            return list(self.rows)
        return []

    def lexecute(self, sql, params=()):
        self.executed.append((sql, tuple(params)))
        return 1

    @staticmethod
    def now_stamp():
        return "now"


def _zone(**extra):
    row = {
        "id": 1,
        "name": "Living",
        "x_px": 100,
        "y_px": 50,
        "w_px": 800,
        "h_px": 400,
        "px_per_m": 100,
        "quantity_status": "Measured",
    }
    row.update(extra)
    return row


def test_printed_height_and_level_stay_and_a_missing_height_is_skipped() -> None:
    app = _App([_zone(wall_height_m=3.0, level_name="Level 2")])
    assert refresh_zone_masses(app, 1) == 1
    insert = app.executed[1][1]
    assert insert[2] == "Level 2"
    assert insert[8] == 3.0
    missing = _App([_zone()])
    assert refresh_zone_masses(missing, 1) == 0
    assert len(missing.executed) == 1
