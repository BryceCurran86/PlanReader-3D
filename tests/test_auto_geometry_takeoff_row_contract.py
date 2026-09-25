"""Auto-geometry take-off row contract (Subscription Take-off crash regression).

The room-face wrapper around _build_unit_rows used to append hand-built
13-value tuples, so _replace_auto_rows() failed with
"Incorrect number of bindings supplied. The current statement uses 21, and
there are 13 supplied." These tests pin the 21-field row contract at every
producer and at the publication boundary, and run the real sequence:
selected pages -> automatic geometry -> unit/facade rows -> take-off
publication -> 3D envelope mass.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fitz

import pb_auto_geometry_guard_v1219 as guard
import pb_auto_geometry_v1219 as auto
import pb_context_floorarea_v1224 as context_floorarea
import pb_planreader_3d_app as app_mod
import pb_room_face_takeoff as room_face
import pb_selected_evidence_floor_v1226 as selected_evidence
import pb_unit_floor_area_gate_v1221 as unit_gate

RENDER_ZOOM = 2.0
PX_PER_M_1_100 = RENDER_ZOOM * 2834.646 / 100.0
_PATCHED = ("_build_unit_rows", "_build_facade_rows", "_auto_calibrate_page")


def _write_plan(pdf_path: Path, png_path: Path) -> None:
    """Native-vector 1:100 plan: 10 m x 6 m outline split into two labelled rooms."""
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    mm = 72 / 25.4
    ox, oy, w, h, split = 80, 80, 100 * mm, 60 * mm, 60 * mm
    for a, b in (((ox, oy), (ox + w, oy)), ((ox + w, oy), (ox + w, oy + h)),
                 ((ox + w, oy + h), (ox, oy + h)), ((ox, oy + h), (ox, oy)),
                 ((ox + split, oy), (ox + split, oy + h))):
        page.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1)
    page.insert_text(fitz.Point(ox + split / 2 - 20, oy + h / 2), "LOUNGE", fontsize=9)
    page.insert_text(fitz.Point(ox + split + (w - split) / 2 - 22, oy + h / 2), "BEDROOM", fontsize=9)
    page.get_pixmap(matrix=fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM)).save(png_path)
    doc.save(pdf_path)
    doc.close()


def _room_face_row(**changes):
    row = {
        "workspace_id": 1, "section": "Internal", "element": "Floor area", "location": "LOUNGE",
        "substrate": "Other", "unit": "m²", "quantity": 36.0, "quantity_status": "Measured",
        "source_page": 1, "source_reference": f"{room_face.SOURCE_PREFIX} · A101 · page:1",
        "confidence": "Derived", "notes": "Room area from calibrated vector face extraction.",
        "row_role": "floor_area",
    }
    row.update(changes)
    return row


class _Workspace:
    """Real app schema on a temporary database, with module patches restored."""

    def __init__(self, root: Path):
        self.root = root
        # The production app functions the wrapper chain calls, on the temp database.
        self.app = SimpleNamespace(
            lquery=app_mod.lquery, lexecute=app_mod.lexecute, local_connect=app_mod.local_connect,
            now_stamp=app_mod.now_stamp, workspace_setting=app_mod.workspace_setting,
            set_workspace_setting=app_mod.set_workspace_setting,
            auto_detect_scale=app_mod.auto_detect_scale, fitz=fitz,
        )

    def add_document(self, pdf_path: Path) -> None:
        app_mod.lexecute("INSERT INTO workspaces(id,job_name,created_at,updated_at) VALUES(1,'Contract','x','x')")
        app_mod.lexecute(
            "INSERT INTO documents(id,workspace_id,file_name,path,sha256,page_count) VALUES(1,1,?,?,'sha',3)",
            (pdf_path.name, str(pdf_path)),
        )

    def add_page(self, page_id: int, page_type: str, label: str, text: str, *, image: Path | None = None) -> None:
        app_mod.lexecute(
            """INSERT INTO pages(id,document_id,workspace_id,page_no,page_label,page_type,scale_text,px_per_m,
                   image_path,render_zoom,extracted_text,selected)
               VALUES(?,1,1,?,?,?,'1:100',?,?,?,?,1)""",
            (page_id, page_id, label, page_type, PX_PER_M_1_100, str(image) if image else None, RENDER_ZOOM, text),
        )

    def pages(self):
        return [dict(p) for p in app_mod.lquery("SELECT * FROM pages WHERE workspace_id=1 ORDER BY id")]


@contextmanager
def _workspace():
    saved = {name: getattr(auto, name) for name in _PATCHED}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, \
            patch.object(app_mod, "DB_PATH", Path(tmp) / "planreader.db"):
        app_mod.init_local_db()
        try:
            yield _Workspace(Path(tmp))
        finally:
            for name, fn in saved.items():
                setattr(auto, name, fn)


def _apply_production_chain(app) -> None:
    # Same order as pb_planreader_v126_app.py startup.
    for module in (guard, unit_gate, context_floorarea, selected_evidence, room_face):
        module.apply(app)


class TakeoffRowContractTests(unittest.TestCase):
    def test_takeoff_row_has_exactly_the_insert_fields(self):
        row = auto._takeoff_row(
            workspace_id=1, section="Internal", element="Floor area", location="Unit 1", substrate="Other",
            quantity=12.345, status="Measured", source_page="A101",
            source_reference=f"{auto.SOURCE_PREFIX} · unit", confidence="Documented", notes="n", row_role="floor_area",
        )
        self.assertEqual(len(row), 21)
        self.assertEqual(auto.TAKEOFF_ROW_FIELD_COUNT, 21)
        self.assertEqual(auto._TAKEOFF_INSERT.count("?"), 21)
        columns = auto._TAKEOFF_INSERT.split("(", 1)[1].split(")", 1)[0].split(",")
        self.assertEqual(tuple(columns), auto.TAKEOFF_ROW_FIELDS)
        self.assertEqual(row[auto.TAKEOFF_ROW_FIELDS.index("unit")], "m²")
        self.assertEqual(row[auto.TAKEOFF_ROW_FIELDS.index("quantity")], 12.35)
        self.assertEqual(row[auto.TAKEOFF_ROW_FIELDS.index("inclusion_status")], "INCLUSION")

    def test_build_unit_rows_emits_only_canonical_rows(self):
        with _workspace() as ws:
            ws.add_document(ws.root / "none.pdf")
            ws.add_page(1, "Floor Plan", "A101", "UNIT 1\nTOTAL AREA 85.4 m2")
            rows, summary = auto._build_unit_rows(ws.app, 1, ws.pages())
        self.assertEqual(len(rows), 1)
        self.assertTrue(all(len(r) == auto.TAKEOFF_ROW_FIELD_COUNT for r in rows))
        self.assertEqual(summary[0]["label"], "Unit 1")

    def test_build_facade_rows_emits_only_canonical_rows(self):
        with _workspace() as ws:
            ws.add_document(ws.root / "none.pdf")
            ws.add_page(1, "Elevation", "A301", "NORTH ELEVATION\nLINEABOARD CLADDING 42.5 m2")
            rows, _facades = auto._build_facade_rows(ws.app, 1, ws.pages())
        self.assertEqual(len(rows), 1)
        self.assertTrue(all(len(r) == auto.TAKEOFF_ROW_FIELD_COUNT for r in rows))
        self.assertEqual(rows[0][auto.TAKEOFF_ROW_FIELDS.index("quantity")], 42.5)

    def test_room_face_row_maps_every_field_by_name(self):
        row = room_face.room_row_to_auto_takeoff_row(auto, _room_face_row())
        fields = dict(zip(auto.TAKEOFF_ROW_FIELDS, row))
        self.assertEqual(len(row), 21)
        self.assertEqual(fields["unit"], "m²")
        self.assertEqual(fields["quantity"], 36.0)
        self.assertEqual(fields["quantity_status"], "Measured")
        self.assertEqual(fields["source_page"], "1")
        self.assertEqual(fields["confidence"], "Derived")
        self.assertEqual(fields["row_role"], "floor_area")
        self.assertEqual(fields["inclusion_status"], "INCLUSION")
        self.assertTrue(fields["source_reference"].startswith(auto.SOURCE_PREFIX))
        self.assertIn(room_face.SOURCE_PREFIX, fields["source_reference"])

    def test_uncalibrated_room_is_not_published_as_zero(self):
        self.assertIsNone(room_face.room_row_to_auto_takeoff_row(auto, _room_face_row(quantity=None)))

    def test_room_face_row_without_unit_fails_loudly(self):
        row = _room_face_row()
        del row["unit"]
        with self.assertRaises(KeyError):
            room_face.room_row_to_auto_takeoff_row(auto, row)

    def test_replace_auto_rows_accepts_generated_rows(self):
        with _workspace() as ws:
            ws.add_document(ws.root / "none.pdf")
            ws.add_page(1, "Floor Plan", "A101", "UNIT 1\nTOTAL AREA 85.4 m2")
            ws.add_page(2, "Elevation", "A301", "NORTH ELEVATION\nLINEABOARD CLADDING 42.5 m2")
            unit_rows, _ = auto._build_unit_rows(ws.app, 1, ws.pages())
            facade_rows, _ = auto._build_facade_rows(ws.app, 1, ws.pages())
            auto._replace_auto_rows(ws.app, 1, unit_rows + facade_rows)
            stored = app_mod.lquery("SELECT quantity,unit,created_at FROM takeoff_rows ORDER BY id")
        self.assertEqual([r["quantity"] for r in stored], [85.4, 42.5])
        self.assertTrue(all(r["unit"] == "m²" and r["created_at"] for r in stored))

    def test_legacy_13_value_row_fails_before_touching_sqlite(self):
        legacy = (1, "Internal", "Floor area", "LOUNGE", "Other", "m²", 36.0, "Measured", 1,
                  f"{room_face.SOURCE_PREFIX} · A101 · page:1", "Derived", "notes", "floor_area")
        with _workspace() as ws:
            ws.add_document(ws.root / "none.pdf")
            ws.add_page(1, "Floor Plan", "A101", "UNIT 1\nTOTAL AREA 85.4 m2")
            good, _ = auto._build_unit_rows(ws.app, 1, ws.pages())
            auto._replace_auto_rows(ws.app, 1, good)
            with self.assertRaises(auto.TakeoffRowContractError) as caught:
                auto._replace_auto_rows(ws.app, 1, good + [legacy])
            remaining = app_mod.lquery("SELECT COUNT(*) AS n FROM takeoff_rows")[0]["n"]
        message = str(caught.exception)
        self.assertIn("row 1", message)
        self.assertIn("13 values", message)
        self.assertIn("expected 21", message)
        self.assertIn(room_face.SOURCE_PREFIX, message)
        self.assertNotIsInstance(caught.exception, sqlite3.ProgrammingError)
        self.assertEqual(remaining, 1, "the existing batch must survive a rejected publication")

    def test_row_outside_the_auto_batch_prefix_is_rejected(self):
        row = list(auto._takeoff_row(
            workspace_id=1, section="Internal", element="Floor area", location="LOUNGE", substrate="Other",
            quantity=36.0, status="Measured", source_page="1",
            source_reference=f"{room_face.SOURCE_PREFIX} · A101 · page:1", confidence="Derived", notes="n",
        ))
        with self.assertRaises(auto.TakeoffRowContractError) as caught:
            auto._validate_auto_rows([tuple(row)])
        self.assertIn("would not be replaced on re-run", str(caught.exception))


class AutomaticGeometryEndToEndTests(unittest.TestCase):
    def test_plan_to_takeoff_rows_to_3d_mass_with_production_wrappers(self):
        with _workspace() as ws:
            pdf, png = ws.root / "plan.pdf", ws.root / "plan_p1.png"
            _write_plan(pdf, png)
            ws.add_document(pdf)
            ws.add_page(1, "Floor Plan", "A101", "UNIT 1\nTOTAL AREA 85.4 m2", image=png)
            ws.add_page(2, "Elevation", "A301", "NORTH ELEVATION\nLINEABOARD CLADDING 42.5 m2")
            _apply_production_chain(ws.app)
            self.assertIs(auto._build_unit_rows.__name__, "_build_unit_rows_with_room_faces")

            report = auto.analyse_workspace(ws.app, 1)
            first = app_mod.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=1 ORDER BY id")
            masses = app_mod.lquery("SELECT * FROM model_masses WHERE workspace_id=1")

            again = auto.analyse_workspace(ws.app, 1)
            second = app_mod.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=1 ORDER BY id")
            masses_again = app_mod.lquery("SELECT * FROM model_masses WHERE workspace_id=1")

        room_rows = [r for r in first if room_face.SOURCE_PREFIX in (r["source_reference"] or "")]
        self.assertGreaterEqual(len(room_rows), 1, "room-face rows must reach the take-off table")
        self.assertTrue(all(r["unit"] == "m²" and r["quantity"] > 0 for r in room_rows))
        self.assertTrue(all(r["source_reference"].startswith(auto.SOURCE_PREFIX) for r in first))
        self.assertEqual(report["auto_takeoff_rows"], len(first))
        self.assertTrue(any(r["element"] == "External walls / cladding" for r in first))
        self.assertIsNotNone(report["model_mass_id"], "the 3D envelope mass must be generated")
        self.assertEqual(len(masses), 1)
        self.assertAlmostEqual(masses[0]["width"], 10.0, delta=0.5)
        self.assertAlmostEqual(masses[0]["depth"], 6.0, delta=0.5)
        # Re-running replaces the batch instead of duplicating it.
        self.assertEqual(len(second), len(first))
        self.assertEqual(again["model_mass_id"], report["model_mass_id"])
        self.assertEqual(len(masses_again), 1)


if __name__ == "__main__":
    unittest.main()
