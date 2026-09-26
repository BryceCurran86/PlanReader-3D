"""An AI draft imports whole or not at all (pb_planreader_3d_app.import_ai_result).

The import wrote the summary, each take-off row, register item, mass and
opening under its own commit. Drafts from a provider without a response
schema (the Gemini path requests JSON only) can carry values SQLite cannot
store: a nested notes object failed the import after the summary and the
first take-off row were committed, and the other rows, register items and
masses were silently missing.
"""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pb_planreader_3d_app as app_mod
import pb_takeoff_accuracy_v125 as accuracy

DRAFT = {
    "executive_summary": "Two-storey house",
    "takeoff_rows": [
        {"section": "Internal", "element": "Walls", "location": "Lounge", "substrate": "Plasterboard", "quantity": 42.0, "unit": "m²"},
        {"section": "Internal", "element": "Ceilings", "location": "Lounge", "substrate": "Plasterboard", "quantity": 20.0, "unit": "m²"},
        {"section": "External", "element": "Cladding", "location": "North", "substrate": "Fibre cement", "quantity": 55.0, "unit": "m²"},
    ],
    "register_items": [{"register_name": "clarifications", "title": "Confirm ceiling height"}],
    "model_masses": [{"label": "House", "width": 12, "depth": 9, "height": 5.4}],
    "model_openings": [{"mass_label": "House", "label": "Door D01", "opening_type": "Door", "face": "Front"}],
}


def _unstorable_draft():
    draft = copy.deepcopy(DRAFT)
    draft["takeoff_rows"][1]["notes"] = {"text": "check bulkhead"}  # nested object, as an unschematised reply may send
    return draft


class AiDraftImportTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._patch = patch.object(app_mod, "DB_PATH", Path(self._tmp.name) / "planreader.db")
        self._patch.start()
        app_mod.init_local_db()
        self.ws = app_mod.create_standalone_workspace("PB-AI", "AI import", "b", "")

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def _workspace(self):
        return {
            "takeoff": app_mod.lquery("SELECT section,element,location,quantity FROM takeoff_rows WHERE workspace_id=? ORDER BY id", (self.ws,)),
            "registers": app_mod.lquery("SELECT title FROM register_items WHERE workspace_id=? ORDER BY id", (self.ws,)),
            "masses": app_mod.lquery("SELECT label FROM model_masses WHERE workspace_id=?", (self.ws,)),
            "openings": app_mod.lquery("SELECT label,mass_id FROM model_openings WHERE workspace_id=?", (self.ws,)),
            "summary": app_mod.lquery("SELECT executive_summary FROM workspaces WHERE id=?", (self.ws,))[0]["executive_summary"],
        }

    def test_a_valid_draft_imports_everything(self):
        counts = app_mod.import_ai_result(self.ws, copy.deepcopy(DRAFT))
        state = self._workspace()
        self.assertEqual(counts, {"takeoff": 3, "registers": 1, "masses": 1, "openings": 1})
        self.assertEqual([r["location"] for r in state["takeoff"]], ["Lounge", "Lounge", "North"])
        self.assertEqual(state["summary"], "Two-storey house")
        mass_id = app_mod.lquery("SELECT id FROM model_masses WHERE workspace_id=?", (self.ws,))[0]["id"]
        self.assertEqual(state["openings"], [{"label": "Door D01", "mass_id": mass_id}])

    def test_an_unstorable_value_imports_nothing(self):
        before = self._workspace()
        with self.assertRaises(Exception):
            app_mod.import_ai_result(self.ws, _unstorable_draft())
        self.assertEqual(self._workspace(), before)

    def test_production_import_wrapper_imports_whole_or_nothing(self):
        # pb_takeoff_accuracy_v125 wraps the import at startup to stamp AI provenance on the created rows.
        run = accuracy.import_ai(app_mod, app_mod.import_ai_result)
        before = self._workspace()
        with self.assertRaises(Exception):
            run(self.ws, _unstorable_draft())
        self.assertEqual(self._workspace(), before)

        run(self.ws, copy.deepcopy(DRAFT))
        rows = app_mod.lquery("SELECT location,ai_baseline_quantity FROM takeoff_rows WHERE workspace_id=? ORDER BY id", (self.ws,))
        self.assertEqual([(r["location"], r["ai_baseline_quantity"]) for r in rows],
                         [("Lounge", 42.0), ("Lounge", 20.0), ("North", 55.0)])


if __name__ == "__main__":
    unittest.main()
