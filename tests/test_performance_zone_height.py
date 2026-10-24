"""The batched zone refresh does not invent a 2.7 m Ground mass."""
import sqlite3
import tempfile
from pathlib import Path

from pb_performance_v1215 import refresh_zone_masses_batched


class _App:
    def __init__(self, path, zones):
        self.path = path
        self.zones = zones

    def local_connect(self):
        return sqlite3.connect(self.path)

    def lquery(self, sql, params=()):
        if "mapped_zones" in sql:
            return list(self.zones)
        return []

    @staticmethod
    def now_stamp():
        return "now"


def test_printed_height_stays_and_a_missing_height_is_skipped() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "masses.db"
        conn = sqlite3.connect(path)
        conn.execute(
            """CREATE TABLE model_masses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER, label TEXT, level_name TEXT, x REAL, y REAL, z REAL,
                width REAL, depth REAL, height REAL, finish TEXT, source_reference TEXT,
                confidence TEXT, notes TEXT, created_at TEXT
            )"""
        )
        conn.commit()
        conn.close()
        zone = {
            "id": 1,
            "name": "Living",
            "x_px": 100,
            "y_px": 50,
            "w_px": 800,
            "h_px": 400,
            "px_per_m": 100,
            "wall_height_m": 3.0,
            "level_name": "Level 2",
            "quantity_status": "Measured",
        }
        assert refresh_zone_masses_batched(_App(path, [zone]), 1) == 1
        check = sqlite3.connect(path)
        row = check.execute("SELECT level_name, height FROM model_masses").fetchone()
        check.close()
        assert row == ("Level 2", 3.0)
        bare = dict(zone)
        del bare["wall_height_m"]
        assert refresh_zone_masses_batched(_App(path, [bare]), 1) == 0
