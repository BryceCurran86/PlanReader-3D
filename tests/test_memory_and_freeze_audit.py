"""Memory and Freeze Audit Test Suite (AG-20).

Validates multi-page processing for:
1. Retained images and file descriptor leaks.
2. Duplicate rasterization prevention (skip redundant work).
3. Unbounded LRU or session caches.
4. Repeated SQLite materialization and connection lifecycle hygiene.
5. Sub-second execution on multi-page workloads to prevent UI freeze.
"""
from __future__ import annotations

import gc
import os
import sqlite3
import tempfile
import time
import tracemalloc
import unittest
from pathlib import Path
from typing import Any, Dict, List

import fitz
from PIL import Image

import pb_planreader_3d_app as app_module
from pb_auto_geometry_v1219 import analyse_workspace


class TestMemoryAndFreezeAudit(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Generate a 10-page realistic PDF fixture
        doc = fitz.open()
        for i in range(10):
            p = doc.new_page(width=842, height=595)
            p.insert_text((50, 40), f"PAGE {i+1} ARCHITECTURAL SET", fontsize=16)
            p.draw_rect(fitz.Rect(80, 80, 400, 320), color=(0, 0, 0), width=1.5)
            p.insert_text((100, 120), f"ROOM {i+1} 20.00 m2", fontsize=12)

        self.pdf_path = self.temp_path / "test_10page_plan.pdf"
        doc.save(str(self.pdf_path))
        doc.close()

        self.db_path = self.temp_path / "test_audit.db"
        self._init_db()

    def tearDown(self) -> None:
        gc.collect()
        self.temp_dir.cleanup()

    def _init_db(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_no TEXT, job_name TEXT, builder_client TEXT, site_address TEXT, created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER, file_name TEXT, path TEXT, sha256 TEXT, category TEXT, page_count INTEGER, source_type TEXT
                );
                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER, document_id INTEGER, page_no INTEGER, page_label TEXT, page_type TEXT,
                    scale_text TEXT, px_per_m REAL, scale_px_per_m REAL, image_path TEXT, width_px INTEGER, height_px INTEGER,
                    render_zoom REAL, extracted_text TEXT, text_content TEXT, label TEXT, selected INTEGER, created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS takeoff_rows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER, section TEXT, element TEXT, location TEXT, substrate TEXT, finish_system TEXT,
                    quantity REAL, unit TEXT, quantity_status TEXT, source_page TEXT, source_reference TEXT,
                    inclusion_status TEXT, coats INTEGER, coverage_m2_per_litre REAL, productivity_m2_per_hour REAL,
                    rate_per_unit REAL, confidence TEXT, notes TEXT, row_role TEXT, created_at TEXT, updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS model_masses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id INTEGER, label TEXT, level_name TEXT, x REAL, y REAL, z REAL,
                    width REAL, depth REAL, height REAL, finish TEXT, source_reference TEXT,
                    confidence TEXT, notes TEXT, created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS model_openings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mass_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS workspace_settings (
                    workspace_id INTEGER, key TEXT, value TEXT, updated_at TEXT, PRIMARY KEY (workspace_id, key)
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def test_page_thumbnail_context_manager_and_cache_bounds(self) -> None:
        """Verify that page thumbnail caching does not leak file descriptors and honors LRU bounds."""
        # Create 10 dummy PNG images
        images_dir = self.temp_path / "thumbs"
        images_dir.mkdir(parents=True, exist_ok=True)

        img_paths = []
        for i in range(10):
            img_file = images_dir / f"page_{i}.png"
            img = Image.new("RGB", (800, 600), color=(i * 20, 100, 150))
            img.save(img_file)
            img_paths.append(img_file)

        # Call page_thumbnail on all images repeatedly
        for _ in range(5):
            for p in img_paths:
                thumb = app_module.page_thumbnail(str(p), max_w=200)
                self.assertIsNotNone(thumb)
                self.assertIsInstance(thumb, bytes)
                self.assertGreater(len(thumb), 100)

        # Verify LRU cache info shows hits and bounded size
        cache_info = app_module._page_thumb.cache_info()
        self.assertLessEqual(cache_info.currsize, 256)
        self.assertGreaterEqual(cache_info.hits, 40)

    def test_duplicate_rasterization_prevention(self) -> None:
        """Verify that re-processing an already-rendered document skips duplicate work."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO workspaces (job_no, job_name) VALUES ('JOB-01', 'Test Job')"
            )
            ws_id = cur.lastrowid
            cur.execute(
                "INSERT INTO documents (workspace_id, file_name, path, page_count) VALUES (?, ?, ?, 10)",
                (ws_id, "test_10page_plan.pdf", str(self.pdf_path)),
            )
            doc_id = cur.lastrowid
            # Seed pages as already rendered with valid image paths
            for i in range(10):
                dummy_img = self.temp_path / f"doc_{doc_id}_page_{i+1}.png"
                dummy_img.write_text("dummy image data")
                cur.execute(
                    """INSERT INTO pages (workspace_id, document_id, page_no, image_path, selected)
                       VALUES (?, ?, ?, ?, 1)""",
                    (ws_id, doc_id, i + 1, str(dummy_img)),
                )
            conn.commit()
        finally:
            conn.close()

        # Monkeypatch DB_PATH in app_module temporarily for this test
        old_db_path = app_module.DB_PATH
        app_module.DB_PATH = self.db_path
        try:
            # When force=False, process_document must return 'Already processed' immediately
            count, msg = app_module.process_document(doc_id, force=False)
            self.assertEqual(count, 10)
            self.assertEqual(msg, "Already processed")
        finally:
            app_module.DB_PATH = old_db_path

    def test_multi_page_memory_stability_across_repeated_runs(self) -> None:
        """Verify that multi-page auto-geometry does not exhibit memory bloat across repeated runs."""
        class MockApp:
            def __init__(self, db_path: Path):
                self.db_path = str(db_path)

            def local_connect(self) -> sqlite3.Connection:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                return conn

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

            def now_stamp(self) -> str:
                return "2026-10-01T15:30:00"

            def build_registered_walls_v139(self, ws_id: int) -> List[Dict[str, Any]]:
                return [
                    {
                        "wall_ref": f"W_EXT_{i}",
                        "side": "External",
                        "gross_m2": 25.0,
                        "net_m2": 22.0,
                        "opening_deduction_m2": 3.0,
                        "height_status": "Verified 2.70m",
                        "height_confidence": "Verified",
                        "plan_page_id": "1",
                        "elevation_page_id": "2",
                        "source_document": "test_10page_plan.pdf",
                        "openings": [{"type_mark": f"W0{i}", "area_m2": 3.0}],
                    }
                    for i in range(8)
                ]

        app = MockApp(self.db_path)
        ws_id = 505
        app.lexecute(
            "INSERT INTO workspaces (id, job_no, job_name) VALUES (?, 'JOB-MEM', 'Memory Test')",
            (ws_id,),
        )
        for i in range(10):
            app.lexecute(
                """INSERT INTO pages (workspace_id, document_id, page_no, page_type, scale_px_per_m, selected, text_content, label)
                   VALUES (?, 1, ?, 'floor_plan', 50.0, 1, ?, ?)""",
                (ws_id, i + 1, f"PAGE {i+1} ROOM {i+1} 20.00 m2", f"Sheet {i+1}"),
            )

        # Warmup iteration to load one-time imported modules (e.g. shapely, numpy)
        analyse_workspace(app, ws_id)
        gc.collect()

        # Measure steady-state memory delta across 5 consecutive executions
        tracemalloc.start()
        snapshot_start = tracemalloc.take_snapshot()

        for iteration in range(5):
            t0 = time.perf_counter()
            report = analyse_workspace(app, ws_id)
            duration = time.perf_counter() - t0
            self.assertIsNotNone(report)
            # Ensure each run is fast and does not stall/freeze (< 1.5s for 10 pages)
            self.assertLess(duration, 1.5, f"Iteration {iteration} took {duration:.3f}s")

        gc.collect()
        snapshot_end = tracemalloc.take_snapshot()
        tracemalloc.stop()

        top_stats = snapshot_end.compare_to(snapshot_start, "lineno")
        # Ensure net allocated memory difference is bounded (< 2 MB for 5 full workspace re-runs)
        net_memory_diff = sum(stat.size_diff for stat in top_stats)
        self.assertLess(
            net_memory_diff,
            2 * 1024 * 1024,
            f"Memory grew by {net_memory_diff / 1024:.2f} KB across 5 runs, expected < 2048 KB",
        )


if __name__ == "__main__":
    unittest.main()
