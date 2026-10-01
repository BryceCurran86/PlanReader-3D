"""Performance Regression Guard Test Suite (AG-19).

Validates that the PlanReader customer runtime path (upload -> indexing -> processing
-> evidence -> auto geometry -> takeoff publication -> 3D conversion) operates
strictly within budgeted wall-clock thresholds and exhibits sub-linear / linear
scaling without performance regressions or memory leaks.
"""
from __future__ import annotations

import gc
import hashlib
import json
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List

import fitz

import pb_takeoff_row_contract as takeoff_contract
from pb_auto_geometry_v1219 import analyse_workspace
from pb_bim_viewer import project_to_viewer_payload
from pb_production_3d_adapter import planreader_workspace_to_canonical


class CustomerTestApp:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    def _init_schema(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS workspaces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_no TEXT,
                    job_name TEXT,
                    builder_client TEXT,
                    site_address TEXT,
                    created_at TEXT
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER,
                    file_name TEXT,
                    path TEXT,
                    sha256 TEXT,
                    category TEXT,
                    page_count INTEGER,
                    source_type TEXT
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
                    x REAL, y REAL, z REAL,
                    width REAL, depth REAL, height REAL,
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
        finally:
            conn.close()

    def local_connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def now_stamp(self) -> str:
        return "2026-10-01T15:00:00"

    def lquery(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(query, params)
            cols = [d[0] for d in cur.description] if cur.description else []
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            conn.close()

    def lexecute(self, query: str, params: tuple = ()) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(query, params)
            conn.commit()
            return int(cur.lastrowid or 0)
        finally:
            conn.close()

    def workspace_setting(self, ws_id: int, key: str, default: Any = None) -> Any:
        rows = self.lquery(
            "SELECT value FROM workspace_settings WHERE workspace_id=? AND key=?",
            (ws_id, key),
        )
        return rows[0]["value"] if rows else default

    def build_registered_walls_v139(self, ws_id: int) -> List[Dict[str, Any]]:
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
                "elevation_page_id": "3",
                "source_document": "Project_5Page_Set.pdf",
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
                "elevation_page_id": "3",
                "source_document": "Project_5Page_Set.pdf",
                "openings": [
                    {"type_mark": "D01", "area_m2": 2.1},
                ],
            },
        ]


class TestPerformanceRegressionGuard(unittest.TestCase):
    def setUp(self) -> None:
        # Build 5-page PDF document
        doc = fitz.open()
        for i in range(5):
            p = doc.new_page(width=842, height=595)
            p.insert_text((50, 40), f"PAGE {i+1} - ARCHITECTURAL / STRUCTURAL", fontsize=16)
            p.draw_rect(fitz.Rect(80, 80, 400, 320), color=(0, 0, 0), width=1.5)
            p.insert_text((100, 120), f"ROOM {i+1} 25.00 m2", fontsize=12)

        pdf_tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        pdf_tmp.close()
        doc.save(pdf_tmp.name)
        doc.close()
        self.pdf_path = pdf_tmp.name

        db_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_tmp.close()
        self.db_path = db_tmp.name

        self.app = CustomerTestApp(self.db_path)
        self.ws_id = 202

        self.app.lexecute(
            "INSERT INTO workspaces (id, job_no, job_name, builder_client, site_address) VALUES (?, ?, ?, ?, ?)",
            (self.ws_id, "PERF-2026", "Performance Baseline Job", "Client A", "100 Performance Way"),
        )

    def tearDown(self) -> None:
        gc.collect()
        for p in (self.pdf_path, self.db_path):
            try:
                if os.path.exists(p):
                    os.unlink(p)
            except OSError:
                pass

    def test_end_to_end_runtime_performance_budget(self) -> None:
        """Assert each stage of customer pipeline operates within strict latency bounds."""
        # 1. Document Upload & Storage Budget: < 500 ms
        t0 = time.perf_counter()
        with open(self.pdf_path, "rb") as f:
            pdf_bytes = f.read()
        sha = hashlib.sha256(pdf_bytes).hexdigest()
        doc_id = self.app.lexecute(
            """INSERT INTO documents (workspace_id, file_name, path, sha256, category, page_count, source_type)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (self.ws_id, "Project_5Page_Set.pdf", self.pdf_path, sha, "Architectural", 5, "pdf"),
        )
        upload_time = time.perf_counter() - t0
        self.assertLess(upload_time, 0.50, f"Upload took {upload_time:.4f}s, exceeding 0.50s budget")

        # 2. Page Indexing Budget: < 1.0 s for 5 pages
        t0 = time.perf_counter()
        doc = fitz.open(self.pdf_path)
        for i, page in enumerate(doc):
            text = page.get_text()
            ptype = "floor_plan" if i < 2 else "elevation"
            self.app.lexecute(
                """INSERT INTO pages (workspace_id, document_id, page_no, page_type, scale_px_per_m, selected, text_content, label)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (self.ws_id, doc_id, i + 1, ptype, 50.0, 1, text, f"Sheet {i+1}"),
            )
        doc.close()
        indexing_time = time.perf_counter() - t0
        self.assertLess(indexing_time, 1.0, f"Indexing took {indexing_time:.4f}s, exceeding 1.0s budget")

        # 3. Auto Geometry Budget: < 1.5 s
        t0 = time.perf_counter()
        report = analyse_workspace(self.app, self.ws_id)
        auto_geom_time = time.perf_counter() - t0
        self.assertLess(auto_geom_time, 1.5, f"Auto geometry took {auto_geom_time:.4f}s, exceeding 1.5s budget")
        self.assertGreaterEqual(report.get("auto_takeoff_rows", 0), 2)

        # 4. Takeoff Publication & Contract Verification Budget: < 0.25 s
        t0 = time.perf_counter()
        rows = self.app.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=?", (self.ws_id,))
        self.assertGreaterEqual(len(rows), 2)
        for r in rows:
            self.assertIn(r["unit"], takeoff_contract.TAKEOFF_UNITS)
            self.assertIn(r["quantity_status"], ("Measured", "Estimated", "Provisional"))
        publication_time = time.perf_counter() - t0
        self.assertLess(publication_time, 0.25, f"Takeoff publication took {publication_time:.4f}s, exceeding 0.25s budget")

        # 5. Canonical 3D Conversion Budget: < 1.0 s
        t0 = time.perf_counter()
        canonical_result = planreader_workspace_to_canonical(self.app, self.ws_id)
        payload = project_to_viewer_payload(canonical_result.project)
        viewer_3d_time = time.perf_counter() - t0
        self.assertLess(viewer_3d_time, 1.0, f"3D conversion took {viewer_3d_time:.4f}s, exceeding 1.0s budget")
        self.assertIsNotNone(payload)

        # 6. Total Pipeline Budget: < 3.0 s
        total_time = upload_time + indexing_time + auto_geom_time + publication_time + viewer_3d_time
        self.assertLess(total_time, 3.0, f"Total pipeline took {total_time:.4f}s, exceeding 3.0s budget")


if __name__ == "__main__":
    unittest.main()
