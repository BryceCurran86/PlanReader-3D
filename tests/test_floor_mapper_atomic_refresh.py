"""The fast floor mapper replaces a page's generated rows all or nothing.

pb_floor_mapper_v127._replace_generated_rows committed its DELETE, then
inserted each row under its own commit. A failure part-way (a lock, a
constraint, a row missing a field) left the page with only some of its
floor-area boxes: 41 m² published where the page had 70 m² before and
72 m² after.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pb_floor_mapper_v127 as floor_mapper
import pb_planreader_3d_app as app_mod


def _box(page_id, number, area):
    return {"section": "Internal", "element": "Floor area", "location": f"Box {number}", "substrate": "Other",
            "finish_system": "N/A", "quantity": area, "unit": "m²", "quantity_status": "Measured",
            "source_page": "A101", "source_reference": f"{floor_mapper.SOURCE_PREFIX} · page:{page_id} · box:{number}",
            "inclusion_status": "INCLUSION", "coats": 0, "coverage_m2_per_litre": 0, "productivity_m2_per_hour": 0,
            "rate_per_unit": 0, "confidence": "Measured", "notes": "", "row_role": "floor_area"}


class FloorMapperRefreshTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._patch = patch.object(app_mod, "DB_PATH", Path(self._tmp.name) / "planreader.db")
        self._patch.start()
        app_mod.init_local_db()
        self.ws = app_mod.create_standalone_workspace("PB-F", "Floor mapper", "b", "")
        self.app = SimpleNamespace(lexecute=app_mod.lexecute, lquery=app_mod.lquery,
                                   local_connect=app_mod.local_connect, now_stamp=app_mod.now_stamp)
        floor_mapper._replace_generated_rows(self.app, self.ws, 1, [_box(1, 1, 40.0), _box(1, 2, 30.0)])
        floor_mapper._replace_generated_rows(self.app, self.ws, 10, [_box(10, 9, 12.0)])
        app_mod.lexecute("INSERT INTO takeoff_rows(workspace_id,section,element,location,quantity,unit,source_reference,created_at,updated_at) "
                         "VALUES(?,'Internal','Walls','Kitchen',18.0,'m²','Estimator manual entry','x','x')", (self.ws,))

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def _rows(self):
        return app_mod.lquery("SELECT location,quantity FROM takeoff_rows WHERE workspace_id=? ORDER BY location", (self.ws,))

    def test_refresh_replaces_only_this_page(self):
        floor_mapper._replace_generated_rows(self.app, self.ws, 1, [_box(1, 3, 41.0), _box(1, 4, 31.0)])
        self.assertEqual(self._rows(), [{"location": "Box 3", "quantity": 41.0}, {"location": "Box 4", "quantity": 31.0},
                                        {"location": "Box 9", "quantity": 12.0}, {"location": "Kitchen", "quantity": 18.0}])

    def test_database_failure_part_way_keeps_the_page_intact(self):
        before = self._rows()
        app_mod.lexecute("CREATE TRIGGER fail_second BEFORE INSERT ON takeoff_rows WHEN NEW.location='Box 4' "
                         "BEGIN SELECT RAISE(ABORT, 'disk full'); END")
        with self.assertRaisesRegex(Exception, "disk full"):
            floor_mapper._replace_generated_rows(self.app, self.ws, 1, [_box(1, 3, 41.0), _box(1, 4, 31.0)])
        self.assertEqual(self._rows(), before)

    def test_malformed_row_fails_before_anything_is_deleted(self):
        before = self._rows()
        broken = _box(1, 4, 31.0)
        del broken["unit"]
        with self.assertRaises(KeyError):
            floor_mapper._replace_generated_rows(self.app, self.ws, 1, [_box(1, 3, 41.0), broken])
        self.assertEqual(self._rows(), before)


if __name__ == "__main__":
    unittest.main()
