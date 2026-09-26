"""Automatic-geometry publication: re-run idempotency and failure transactions.

Representative three-sheet documents through the production wrapper chain:
a room-face plan (A101), a second floor plan (A102) and an explicit facade
substrate area (A301). The unit document publishes selected-evidence unit
floor rows; the unit-less document falls back to the context floor-area
producer, so every injected automatic row family is re-run.
"""
from __future__ import annotations

import unittest

import fitz

import pb_auto_geometry_v1219 as auto
import pb_context_floorarea_v1224 as context_floorarea
import pb_planreader_3d_app as app_mod
import pb_room_face_takeoff as room_face
from test_auto_geometry_takeoff_row_contract import (
    RENDER_ZOOM,
    _apply_production_chain,
    _workspace,
)

A101_TEXT = "GROUND FLOOR PLAN\nUNIT 1\nTOTAL AREA 85.4 m2"
A101_UNITLESS_TEXT = "GROUND FLOOR PLAN\nINTERNAL FLOOR AREA 85.4 m2"
A102_TEXT = "LEVEL 1 FLOOR PLAN\nINTERNAL FLOOR AREA 120.5 m2"
A301_TEXT = "NORTH ELEVATION\nLINEABOARD CLADDING 42.5 m2"


def _write_document(pdf_path, png_path):
    doc = fitz.open()
    mm = 72 / 25.4
    plan = doc.new_page(width=842, height=595)
    ox, oy, w, h, split = 80, 80, 100 * mm, 60 * mm, 60 * mm
    for a, b in (((ox, oy), (ox + w, oy)), ((ox + w, oy), (ox + w, oy + h)),
                 ((ox + w, oy + h), (ox, oy + h)), ((ox, oy + h), (ox, oy)),
                 ((ox + split, oy), (ox + split, oy + h))):
        plan.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1)
    plan.insert_text(fitz.Point(ox + split / 2 - 20, oy + h / 2), "LOUNGE", fontsize=9)
    plan.insert_text(fitz.Point(ox + split + (w - split) / 2 - 22, oy + h / 2), "BEDROOM", fontsize=9)
    plan.insert_text(fitz.Point(ox, oy + h + 40), "GROUND FLOOR PLAN   SCALE 1:100", fontsize=9)
    plan.get_pixmap(matrix=fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM)).save(png_path)
    for text in (A102_TEXT, A301_TEXT):
        page = doc.new_page(width=842, height=595)
        page.insert_text(fitz.Point(80, 120), text.replace("\n", "   "), fontsize=9)
    doc.save(pdf_path)
    doc.close()


def _family(reference: str) -> str:
    if room_face.SOURCE_PREFIX in reference:
        return "room_face"
    if context_floorarea.SOURCE_SUFFIX in reference:
        return "context_floor_area"
    if "v1.2.26 floor:" in reference:
        return "selected_evidence_floor"
    if "· facade:" in reference:
        return "facade"
    if "· unit:" in reference:
        return "unit"
    return "other"


def _snapshot():
    rows = app_mod.lquery(
        f"SELECT {','.join(auto.TAKEOFF_ROW_FIELDS[:-2])} FROM takeoff_rows WHERE workspace_id=1 "
        "ORDER BY source_reference, location, quantity"
    )
    masses = app_mod.lquery("SELECT id,width,depth,height,source_reference FROM model_masses WHERE workspace_id=1 ORDER BY id")
    report = auto._setting_get(_SNAPSHOT_APP, 1)
    surfaces = app_mod.workspace_setting(1, "3d_surface_editor_v1212")
    return rows, masses, report, surfaces


_SNAPSHOT_APP = None


class _PreparedWorkspace:
    def __init__(self, plan_text: str = A101_TEXT):
        self.plan_text = plan_text

    def __enter__(self):
        global _SNAPSHOT_APP
        self._ctx = _workspace()
        ws = self._ctx.__enter__()
        pdf, png = ws.root / "plans.pdf", ws.root / "plans_p1.png"
        _write_document(pdf, png)
        ws.add_document(pdf)
        ws.add_page(1, "Floor Plan", "A101", self.plan_text, image=png)
        ws.add_page(2, "Floor Plan", "A102", A102_TEXT)
        ws.add_page(3, "Elevation", "A301", A301_TEXT)
        app_mod.lexecute(
            """INSERT INTO takeoff_rows(workspace_id,section,element,location,substrate,quantity,unit,
                   quantity_status,source_reference,row_role,created_at,updated_at)
               VALUES(1,'Internal','Walls','Kitchen','Plasterboard',18.0,'m²','Measured',
                      'Estimator manual entry','','x','x')"""
        )
        _apply_production_chain(ws.app)
        _SNAPSHOT_APP = ws.app
        self.ws = ws
        return ws

    def __exit__(self, *exc):
        global _SNAPSHOT_APP
        _SNAPSHOT_APP = None
        return self._ctx.__exit__(*exc)


class RerunIdempotencyTests(unittest.TestCase):
    def test_three_runs_publish_the_same_rows_and_one_mass(self):
        documents = {
            "unit document": (A101_TEXT, {"room_face", "selected_evidence_floor", "facade"}),
            "unit-less document": (A101_UNITLESS_TEXT, {"room_face", "context_floor_area", "facade"}),
        }
        for name, (plan_text, expected_families) in documents.items():
            with self.subTest(name), _PreparedWorkspace(plan_text) as ws:
                snapshots = []
                for _run in range(3):
                    report = auto.analyse_workspace(ws.app, 1)
                    rows, masses, stored, _surfaces = _snapshot()
                    auto_rows = [r for r in rows if (r["source_reference"] or "").startswith(auto.SOURCE_PREFIX)]
                    self.assertEqual(len(auto_rows), report["auto_takeoff_rows"])
                    self.assertEqual(stored["auto_takeoff_rows"], report["auto_takeoff_rows"])
                    self.assertEqual(stored["model_mass_id"], masses[0]["id"])
                    snapshots.append((rows, masses))
                first_rows, first_masses = snapshots[0]
                families = {_family(r["source_reference"]) for r in first_rows
                            if (r["source_reference"] or "").startswith(auto.SOURCE_PREFIX)}
                self.assertTrue(expected_families <= families, families)
                self.assertNotIn("other", families)
                manual = [r for r in first_rows if r["source_reference"] == "Estimator manual entry"]
                self.assertEqual(len(manual), 1)
                self.assertEqual(len(first_masses), 1)
                for rows, masses in snapshots[1:]:
                    self.assertEqual(rows, first_rows, "re-running must replace, never accumulate or alter rows")
                    self.assertEqual(masses, first_masses)


class PublicationFailureTests(unittest.TestCase):
    def _baseline_then(self, ws, failing_run):
        auto.analyse_workspace(ws.app, 1)
        before = _snapshot()
        app_mod.lexecute("UPDATE pages SET extracted_text=? WHERE id=1", ("GROUND FLOOR PLAN\nUNIT 1\nTOTAL AREA 90.0 m2",))
        with self.assertRaises(Exception) as caught:
            failing_run()
        return before, _snapshot(), caught.exception

    def test_producer_failure_midway_publishes_nothing(self):
        with _PreparedWorkspace() as ws:
            base_facades = auto._build_facade_rows

            def broken_facades(app_obj, workspace_id, pages):
                raise RuntimeError("facade producer failed")

            def run():
                auto._build_facade_rows = broken_facades
                try:
                    auto.analyse_workspace(ws.app, 1)
                finally:
                    auto._build_facade_rows = base_facades

            before, after, error = self._baseline_then(ws, run)
        self.assertIn("facade producer failed", str(error))
        self.assertEqual(after, before)

    def test_malformed_row_publishes_nothing(self):
        with _PreparedWorkspace() as ws:
            base_units = auto._build_unit_rows

            def legacy_units(app_obj, workspace_id, pages):
                rows, summary = base_units(app_obj, workspace_id, pages)
                return rows + [tuple(range(13))], summary

            def run():
                auto._build_unit_rows = legacy_units
                try:
                    auto.analyse_workspace(ws.app, 1)
                finally:
                    auto._build_unit_rows = base_units

            before, after, error = self._baseline_then(ws, run)
        self.assertIsInstance(error, auto.TakeoffRowContractError)
        self.assertEqual(after, before)

    def test_database_error_after_row_publication_rolls_everything_back(self):
        # Each write fails inside SQLite itself, after the take-off rows have
        # been written, as a lock or constraint failure would.
        failure_points = {
            "3D envelope write": ("model_masses", ""),
            "report write": ("workspace_settings", f"WHEN NEW.key = '{auto.SETTING_KEY}'"),
        }
        for name, (table, when) in failure_points.items():
            fail = f"SELECT RAISE(ABORT, 'simulated {name} failure')"
            with self.subTest(name), _PreparedWorkspace() as ws:
                def run():
                    for event in ("INSERT", "UPDATE"):
                        app_mod.lexecute(f"CREATE TRIGGER fail_{event} BEFORE {event} ON {table} {when} BEGIN {fail}; END")
                    try:
                        auto.analyse_workspace(ws.app, 1)
                    finally:
                        for event in ("INSERT", "UPDATE"):
                            app_mod.lexecute(f"DROP TRIGGER IF EXISTS fail_{event}")

                before, after, error = self._baseline_then(ws, run)
                self.assertIn(f"simulated {name} failure", str(error))
                self.assertEqual(after, before, "take-off rows, 3D mass, surfaces and report must stay mutually consistent")


if __name__ == "__main__":
    unittest.main()
