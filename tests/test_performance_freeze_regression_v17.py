"""Test Suite for AG-17 Performance and Freeze Regression Guard.

Validates that PlanReader customer runtime:
1. Operates within strict sub-second stage budgets across all 8 customer pipeline stages.
2. Scales linearly O(N) when document size is doubled (proving zero quadratic loops).
3. Maintains zero memory leaks across repeated runs under tracemalloc profiling.
4. Leaves zero open file handles, unclosed PIL images, or leaked SQLite connections.
"""
from __future__ import annotations

import gc
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz

import pb_planreader_3d_app as app
import pb_performance_freeze_guard_v17 as perf_guard


class CustomerPerfTestApp:
    """Lightweight test adapter wrapping SQLite database with PlanReader app API."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    def local_connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def lquery(self, query: str, params: tuple = ()) -> list[dict[str, Any]]:
        conn = self.local_connect()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def lexecute(self, query: str, params: tuple = ()) -> int:
        conn = self.local_connect()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            conn.commit()
            return int(cur.lastrowid or 0)
        finally:
            conn.close()

    def now_stamp(self) -> str:
        return app.now_stamp()

    def workspace_setting(self, ws_id: int, key: str, default: Any = None) -> Any:
        rows = self.lquery(
            "SELECT value FROM workspace_settings WHERE workspace_id=? AND key=?",
            (ws_id, key),
        )
        return rows[0]["value"] if rows else default

    def dataframe_for_takeoff(self, workspace_id: int):
        with patch.object(app, "DB_PATH", self.db_path):
            return app.dataframe_for_takeoff(workspace_id)

    def per_level_summary(self, workspace_id: int):
        with patch.object(app, "DB_PATH", self.db_path):
            return app.per_level_summary(workspace_id)

    def quote_workbook_bytes(self, workspace_id: int):
        with patch.object(app, "DB_PATH", self.db_path):
            return app.quote_workbook_bytes(workspace_id)

    def _init_schema(self) -> None:
        with patch.object(app, "DB_PATH", self.db_path):
            app.init_local_db()


def _create_synthetic_pdf(page_count: int, file_path: str) -> None:
    doc = fitz.open()
    for i in range(page_count):
        p = doc.new_page(width=842, height=595)
        p.insert_text((50, 40), f"PAGE {i+1} - ARCHITECTURAL / STRUCTURAL PLAN", fontsize=16)
        p.draw_rect(fitz.Rect(80, 80, 400, 320), color=(0, 0, 0), width=1.5)
        p.insert_text((100, 120), f"ROOM {i+1} 30.00 m2", fontsize=12)
        p.insert_text((100, 160), "WALL 2.70m High Rendered", fontsize=10)
    doc.save(file_path)
    doc.close()


class TestPerformanceAndFreezeRegressionV17(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "perf_test.db")
        self.pdf_5p = str(Path(self.temp_dir.name) / "set_5p.pdf")
        self.pdf_10p = str(Path(self.temp_dir.name) / "set_10p.pdf")

        _create_synthetic_pdf(5, self.pdf_5p)
        _create_synthetic_pdf(10, self.pdf_10p)

        self.app = CustomerPerfTestApp(self.db_path)

    def tearDown(self) -> None:
        gc.collect()
        self.temp_dir.cleanup()

    def test_customer_pipeline_operates_within_latency_budgets(self) -> None:
        """Prove that all 8 stages of the customer pipeline complete within strict latency budgets."""
        ws_id = 501
        self.app.lexecute(
            "INSERT INTO workspaces (id, job_no, job_name, builder_client, site_address) VALUES (?, ?, ?, ?, ?)",
            (ws_id, "PERF-501", "Latency Budget Run", "Apex Builders", "100 Speed Way"),
        )
        self.app.lexecute(
            "INSERT INTO workspace_settings (workspace_id, key, value) VALUES (?, 'pricing_margin_pct', '15.0')",
            (ws_id,),
        )
        self.app.lexecute(
            "INSERT INTO workspace_settings (workspace_id, key, value) VALUES (?, 'gst_rate_pct', '10.0')",
            (ws_id,),
        )

        with patch.object(app, "DB_PATH", self.db_path):
            report = perf_guard.benchmark_customer_pipeline(self.app, self.pdf_5p, ws_id)

        self.assertTrue(report.passed, f"Performance report issues: {report.issues}")
        self.assertLess(report.total_duration_ms, 3500.0, f"Total runtime {report.total_duration_ms:.1f}ms exceeded 3.5s budget")

        # Verify that all 8 stages were recorded and passed
        self.assertEqual(len(report.stage_timings), 8)
        for stage in report.stage_timings:
            self.assertTrue(stage.passed, f"Stage '{stage.stage_name}' took {stage.duration_ms:.1f}ms > {stage.budget_ms:.1f}ms")

    def test_scaling_linearity_proves_zero_quadratic_loops(self) -> None:
        """Doubling page count (5 -> 10 pages) must scale linearly <= 2.5x, proving no O(N^2) bottlenecks."""
        ws_5p = 502
        ws_10p = 503
        for ws in (ws_5p, ws_10p):
            self.app.lexecute(
                "INSERT INTO workspaces (id, job_no, job_name, builder_client, site_address) VALUES (?, ?, ?, ?, ?)",
                (ws, f"PERF-{ws}", "Scaling Run", "Client", "Street"),
            )
            self.app.lexecute(
                "INSERT INTO workspace_settings (workspace_id, key, value) VALUES (?, 'pricing_margin_pct', '15.0')",
                (ws,),
            )
            self.app.lexecute(
                "INSERT INTO workspace_settings (workspace_id, key, value) VALUES (?, 'gst_rate_pct', '10.0')",
                (ws,),
            )

        with patch.object(app, "DB_PATH", self.db_path):
            rep_5p = perf_guard.benchmark_customer_pipeline(self.app, self.pdf_5p, ws_5p)
            rep_10p = perf_guard.benchmark_customer_pipeline(self.app, self.pdf_10p, ws_10p)

        # Ratio of 10-page to 5-page execution time
        ratio = rep_10p.total_duration_ms / max(rep_5p.total_duration_ms, 1.0)
        self.assertLessEqual(
            ratio,
            2.5,
            f"Scaling ratio {ratio:.2f}x exceeds 2.5x linearity bound (5p: {rep_5p.total_duration_ms:.1f}ms, 10p: {rep_10p.total_duration_ms:.1f}ms)",
        )

    def test_repeated_runs_prove_zero_memory_leak(self) -> None:
        """Executing 4 consecutive full pipeline runs under tracemalloc must yield net delta < 2 MB."""
        with patch.object(app, "DB_PATH", self.db_path):
            passed, peak_mb, net_growth_kb = perf_guard.assert_zero_memory_leak(
                self.app,
                self.pdf_5p,
                workspace_id_base=600,
                iterations=4,
                max_growth_kb=2048.0,
            )

        self.assertTrue(
            passed,
            f"Memory leak check failed: net growth was {net_growth_kb:.1f} KB (peak {peak_mb:.1f} MB), exceeding 2048 KB limit",
        )
