"""Importing a take-off file appends all rows or none (pb_planreader_3d_app.import_takeoff_rows).

The import button of takeoff_import_panel inserted each parsed row under its
own commit and only appends. A failure part-way (a lock, a constraint) left
the rows before it imported, and retrying the import then duplicated them.
"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pb_planreader_3d_app as app_mod

REPO = Path(__file__).resolve().parents[1]


def _records():
    return [
        {"section": "Internal", "element": "Walls", "location": "Lounge", "substrate": "Plasterboard", "quantity": 42.0,
         "unit": "m²", "rate_per_unit": 4.5},
        {"section": "Internal", "element": "Ceilings", "location": "Lounge", "substrate": "Plasterboard", "quantity": 20.0,
         "unit": "m²", "row_role": "model_surface"},
        {"section": "", "element": "", "location": "", "source_reference": ""},  # blank line in the file
        {"section": "External", "element": "Cladding", "location": "North", "substrate": "Fibre cement", "quantity": 55.0, "unit": "m²"},
    ]


class TakeoffFileImportTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._patch = patch.object(app_mod, "DB_PATH", Path(self._tmp.name) / "planreader.db")
        self._patch.start()
        app_mod.init_local_db()
        self.ws = app_mod.create_standalone_workspace("PB-I", "Import", "b", "")

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def _rows(self):
        return app_mod.lquery("SELECT location,element,rate_per_unit,row_role FROM takeoff_rows WHERE workspace_id=? ORDER BY id", (self.ws,))

    def test_rows_import_with_the_same_rules_as_before(self):
        self.assertEqual(app_mod.import_takeoff_rows(self.ws, _records()), 3)
        rows = self._rows()
        self.assertEqual([(r["location"], r["element"]) for r in rows],
                         [("Lounge", "Walls"), ("Lounge", "Ceilings"), ("North", "Cladding")])
        self.assertEqual(rows[0]["rate_per_unit"], 4.5)
        self.assertEqual(rows[1]["row_role"], "", "only '' and floor_area survive an import")
        self.assertGreater(rows[2]["rate_per_unit"], 0, "a missing rate still takes the default rate")

    def test_a_failure_part_way_imports_nothing_and_a_retry_imports_once(self):
        app_mod.lexecute("CREATE TRIGGER fail_north BEFORE INSERT ON takeoff_rows WHEN NEW.location='North' "
                         "BEGIN SELECT RAISE(ABORT, 'database is locked'); END")
        with self.assertRaisesRegex(Exception, "database is locked"):
            app_mod.import_takeoff_rows(self.ws, _records())
        self.assertEqual(self._rows(), [])
        app_mod.lexecute("DROP TRIGGER fail_north")
        app_mod.import_takeoff_rows(self.ws, _records())
        self.assertEqual(len(self._rows()), 3, "the retry imports every row exactly once")

    def test_the_import_button_uses_the_transactional_import(self):
        tree = ast.parse((REPO / "pb_planreader_3d_app.py").read_text(encoding="utf-8-sig"))
        panel = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "takeoff_import_panel")
        calls = {n.func.id for n in ast.walk(panel) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        self.assertIn("import_takeoff_rows", calls)
        inserts = [n for n in ast.walk(panel) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                   and "INSERT INTO takeoff_rows" in n.value]
        self.assertEqual(inserts, [], "the panel must not insert rows one commit at a time")


if __name__ == "__main__":
    unittest.main()
