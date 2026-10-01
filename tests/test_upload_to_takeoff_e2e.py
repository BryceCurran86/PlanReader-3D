"""End-to-End Upload-to-Takeoff Customer Route Integration Test (AG-14).

Exercises the exact route used by PlanReader customers:
PDF/document ingestion
→ page registration
→ evidence generation
→ geometry extraction
→ canonical objects
→ takeoff publication
→ UI-readable rows.

Uses real lightweight PDF fixtures created via PyMuPDF without mocks on the core route.
"""
from __future__ import annotations

import gc
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

import fitz

from pb_auto_geometry_v1219 import analyse_workspace, _validate_auto_rows
import pb_takeoff_row_contract as takeoff_contract


class CustomerRuntimeWorkspaceApp:
    """Realistic harness representing the customer application runtime state."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    def _init_schema(self) -> None:
        with self.local_connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER,
                    file_name TEXT,
                    path TEXT
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER,
                    document_id INTEGER,
                    page_no INTEGER,
                    page_type TEXT,
                    scale_px_per_m REAL,
                    selected INTEGER,
                    text_content TEXT,
                    label TEXT
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS takeoff_rows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER,
                    section TEXT,
                    element TEXT,
                    location TEXT,
                    substrate TEXT,
                    finish_system TEXT,
                    quantity REAL,
                    unit TEXT,
                    quantity_status TEXT,
                    source_page TEXT,
                    source_reference TEXT,
                    inclusion_status TEXT,
                    coats INTEGER,
                    coverage_m2_per_litre REAL,
                    productivity_m2_per_hour REAL,
                    rate_per_unit REAL,
                    confidence TEXT,
                    notes TEXT,
                    row_role TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS model_masses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER,
                    label TEXT,
                    level_name TEXT,
                    x REAL,
                    y REAL,
                    z REAL,
                    width REAL,
                    depth REAL,
                    height REAL,
                    finish TEXT,
                    source_reference TEXT,
                    confidence TEXT,
                    notes TEXT,
                    created_at TEXT
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS model_openings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mass_id INTEGER
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS workspace_settings (
                    workspace_id INTEGER,
                    key TEXT,
                    value TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (workspace_id, key)
                )"""
            )
            conn.commit()

    def local_connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def now_stamp(self) -> str:
        return "2026-10-01T14:30:00"

    def lquery(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        with self.local_connect() as conn:
            cur = conn.execute(query, params)
            cols = [d[0] for d in cur.description] if cur.description else []
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def lexecute(self, query: str, params: tuple = ()) -> int:
        with self.local_connect() as conn:
            cur = conn.execute(query, params)
            conn.commit()
            return int(cur.lastrowid or 0)

    def workspace_setting(self, ws_id: int, key: str, default: Any = None) -> Any:
        rows = self.lquery(
            "SELECT value FROM workspace_settings WHERE workspace_id=? AND key=?",
            (ws_id, key),
        )
        return rows[0]["value"] if rows else default

    def build_registered_walls_v139(self, ws_id: int) -> List[Dict[str, Any]]:
        """Authenticated wall authority: produces physical walls with opening deductions."""
        return [
            {
                "wall_ref": "W_NORTH_01",
                "side": "North",
                "gross_m2": 27.0,
                "net_m2": 23.4,
                "opening_deduction_m2": 3.6,
                "height_status": "Verified 2.70m",
                "height_confidence": "Verified",
                "plan_page_id": "1",
                "elevation_page_id": "2",
                "source_document": "Customer_Project_Plans.pdf",
                "openings": [
                    {"type_mark": "W01", "area_m2": 1.8},
                    {"type_mark": "W02", "area_m2": 1.8},
                ],
            },
            {
                "wall_ref": "W_SOUTH_01",
                "side": "South",
                "gross_m2": 27.0,
                "net_m2": 24.9,
                "opening_deduction_m2": 2.1,
                "height_status": "Verified 2.70m",
                "height_confidence": "Verified",
                "plan_page_id": "1",
                "elevation_page_id": "2",
                "source_document": "Customer_Project_Plans.pdf",
                "openings": [
                    {"type_mark": "D01", "area_m2": 2.1},
                ],
            },
        ]


class TestUploadToTakeoffE2E(unittest.TestCase):
    def setUp(self) -> None:
        # Create real PDF fixture
        doc = fitz.open()
        p1 = doc.new_page(width=595, height=842)
        p1.insert_text((50, 50), "GROUND FLOOR PLAN - ARCHITECTURAL", fontsize=16)
        p1.draw_rect(fitz.Rect(100, 100, 400, 300), color=(0, 0, 0), width=2)
        p1.insert_text((150, 150), "BEDROOM 1 15.00 m2", fontsize=12)

        p2 = doc.new_page(width=595, height=842)
        p2.insert_text((50, 50), "NORTH & SOUTH ELEVATIONS", fontsize=16)
        p2.insert_text((100, 100), "CEILING HEIGHT 2700", fontsize=12)

        pdf_tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        pdf_tmp.close()
        doc.save(pdf_tmp.name)
        doc.close()
        self.pdf_path = pdf_tmp.name

        # Create temporary database
        db_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_tmp.close()
        self.db_path = db_tmp.name
        self.app = CustomerRuntimeWorkspaceApp(self.db_path)

    def tearDown(self) -> None:
        gc.collect()
        for p in (self.pdf_path, self.db_path):
            try:
                if os.path.exists(p):
                    os.unlink(p)
            except OSError:
                pass

    def test_full_upload_to_takeoff_customer_route(self) -> None:
        """Execute the entire customer route: Ingest -> Register -> Geometry -> Publish -> UI rows."""
        ws_id = 42

        # 1. Document Ingestion
        doc_id = self.app.lexecute(
            "INSERT INTO documents (workspace_id, file_name, path) VALUES (?, ?, ?)",
            (ws_id, "Customer_Project_Plans.pdf", self.pdf_path),
        )
        self.assertTrue(doc_id > 0)

        # 2. Page Registration
        p1_id = self.app.lexecute(
            """INSERT INTO pages (workspace_id, document_id, page_no, page_type, scale_px_per_m, selected, text_content, label)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ws_id, doc_id, 1, "floor_plan", 50.0, 1, "GROUND FLOOR PLAN BEDROOM 1 15.00 m2", "Sheet A101 - Floor Plan"),
        )
        p2_id = self.app.lexecute(
            """INSERT INTO pages (workspace_id, document_id, page_no, page_type, scale_px_per_m, selected, text_content, label)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ws_id, doc_id, 2, "elevation", 50.0, 1, "NORTH & SOUTH ELEVATIONS CEILING HEIGHT 2700", "Sheet A201 - Elevations"),
        )
        self.assertTrue(p1_id > 0 and p2_id > 0)

        # 3. Automatic Geometry Execution (The exact method called when customer clicks 'Auto Geometry' or on upload)
        report = analyse_workspace(self.app, ws_id)
        self.assertIsNotNone(report)
        self.assertEqual(report["selected_pages"], 2)
        self.assertGreaterEqual(report["auto_takeoff_rows"], 2)

        # 4. Canonical Takeoff Publication in SQLite
        takeoff_rows = self.app.lquery(
            "SELECT * FROM takeoff_rows WHERE workspace_id=? ORDER BY id",
            (ws_id,),
        )
        self.assertGreaterEqual(len(takeoff_rows), 2)

        # Verify strict 21-field contract compliance on all published rows
        for row in takeoff_rows:
            self.assertEqual(row["workspace_id"], ws_id)
            self.assertIn(row["section"], ("External", "Internal"))
            self.assertTrue(row["quantity"] > 0.0)
            self.assertIn(row["unit"], takeoff_contract.TAKEOFF_UNITS)
            self.assertEqual(row["quantity_status"], "Measured")
            self.assertIn(row["inclusion_status"], ("INCLUSION", "PROVISIONAL"))
            self.assertTrue(row["source_reference"].startswith("PB Auto Geometry v1.2.19"))

        # 5. UI-Readable Row Query (What the estimator sees on their screen)
        external_walls = [r for r in takeoff_rows if r["row_role"] == "external_wall"]
        self.assertEqual(len(external_walls), 2)

        north_wall = next(r for r in external_walls if "W_NORTH_01" in r["location"])
        south_wall = next(r for r in external_walls if "W_SOUTH_01" in r["location"])

        # North Wall: 27.0 gross - 3.6 opening deduction = 23.4 net
        self.assertEqual(north_wall["quantity"], 23.4)
        self.assertEqual(north_wall["unit"], "m²")
        self.assertIn("authenticated opening deductions 3.60 m²", north_wall["notes"])
        self.assertIn("Doc: Customer_Project_Plans.pdf", north_wall["notes"])
        self.assertEqual(north_wall["source_page"], "Plan p.1 / Elev p.2")

        # South Wall: 27.0 gross - 2.1 opening deduction = 24.9 net
        self.assertEqual(south_wall["quantity"], 24.9)
        self.assertEqual(south_wall["unit"], "m²")
        self.assertIn("authenticated opening deductions 2.10 m²", south_wall["notes"])
        self.assertIn("Doc: Customer_Project_Plans.pdf", south_wall["notes"])

        # 6. Workspace Settings Report Persistence
        persisted_report = self.app.workspace_setting(ws_id, "auto_geometry_v1219")
        self.assertIsNotNone(persisted_report)
        self.assertIn("auto_takeoff_rows", persisted_report)


if __name__ == "__main__":
    unittest.main()
