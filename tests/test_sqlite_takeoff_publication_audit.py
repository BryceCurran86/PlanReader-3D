"""Tests for AG-18: SQLite Takeoff Publication Audit & Regression Coverage.

Verifies:
1. Canonical field contracts (core: 21, commercial: 26, commercial_provenance: 30).
2. Exact matching between column lists and placeholder binding counts across all production writers.
3. Transaction safety: atomic rollback on exception prevents dirty partial writes.
4. Deterministic replacement semantics: automatic rows are replaced idempotently without duplicate row proliferation or deleting manual estimator rows.
"""
from __future__ import annotations

import os
import re
import sqlite3
import tempfile
import unittest
from typing import Any, Dict, List

from pb_auto_geometry_v1219 import _replace_auto_rows, _takeoff_row, SOURCE_PREFIX
import pb_takeoff_row_contract as takeoff_contract


class TestSqliteTakeoffPublicationAudit(unittest.TestCase):
    def test_production_writer_sql_syntax_and_placeholder_parity(self) -> None:
        """Every production SQL INSERT INTO takeoff_rows must have matching column and placeholder counts."""
        prod_files = [
            "pb_auto_geometry_v1219.py",
            "pb_takeoff_row_contract.py",
            "pb_takeoff_review_v1226.py",
            "pb_premier_takeoff_v1225.py",
            "pb_planreader_3d_app.py",
            "pb_3d_surface_editor_v1212.py",
            "pb_floor_mapper_v127.py",
            "pb_full_reconstruction_v141.py",
            "pb_no_ai_takeoff_v1216.py",
            "pb_performance_v1215.py",
            "pb_takeoff_accuracy_v125.py",
            "pb_takeoff_studio_v1211.py",
            "pb_editable_3d_inspector_panel.py",
            "tradereader_app.py",
            "tradereader_plastering.py",
            "tradereader_universal_specialist.py",
        ]

        found_statements = 0
        for fn in prod_files:
            if not os.path.exists(fn):
                continue
            with open(fn, "r", encoding="utf-8", errors="ignore") as fp:
                lines = fp.readlines()
            for i, line in enumerate(lines):
                if "insert into takeoff_rows" in line.lower():
                    block = "".join(lines[i:min(len(lines), i + 25)])
                    m = re.search(r"insert\s+into\s+takeoff_rows\s*\((.*?)\)\s*values\s*\((.*?)\)", block, re.IGNORECASE | re.DOTALL)
                    if m:
                        cols = [c.strip() for c in m.group(1).split(",") if c.strip()]
                        qmarks = [q.strip() for q in m.group(2).split(",") if q.strip()]
                        # If formatted string like {','.join(fields)}
                        if any("join" in c for c in cols):
                            continue
                        self.assertEqual(
                            len(cols),
                            len(qmarks),
                            f"Mismatch in {fn}:{i+1}: {len(cols)} cols vs {len(qmarks)} placeholders",
                        )
                        self.assertIn(
                            len(cols),
                            (21, 26, 30),
                            f"Column count {len(cols)} in {fn}:{i+1} is not a canonical layout (21, 26, 30)",
                        )
                        found_statements += 1

        self.assertGreaterEqual(found_statements, 15)

    def test_transaction_rollback_prevents_dirty_writes(self) -> None:
        """On exception during auto publication, transaction rolls back completely."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            conn = sqlite3.connect(db_path)
            conn.execute(
                """CREATE TABLE takeoff_rows (
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
            conn.commit()
            conn.close()

            class FailApp:
                def local_connect(self):
                    c = sqlite3.connect(db_path)
                    c.row_factory = sqlite3.Row
                    return c
                def now_stamp(self):
                    return "2026-10-01T12:00:00"

            # Create an invalid row that violates contract (e.g. quantity is string or negative)
            valid_row = _takeoff_row(
                workspace_id=99,
                section="External",
                element="External walls",
                location="Perimeter",
                substrate="Brick",
                quantity=50.0,
                status="Measured",
                source_page="1",
                source_reference=f"{SOURCE_PREFIX} · valid_1",
                confidence="Documented",
                notes="Valid row",
            )
            # Row with bad unit that fails contract validation before commit
            bad_row = list(valid_row)
            bad_row[6] = -10.0  # Invalid negative quantity

            with self.assertRaises(Exception):
                _replace_auto_rows(FailApp(), 99, [valid_row, tuple(bad_row)])

            # Verify that database remained completely empty (atomic rollback)
            verify_conn = sqlite3.connect(db_path)
            rows = verify_conn.execute("SELECT COUNT(*) FROM takeoff_rows").fetchone()
            self.assertEqual(rows[0], 0)
            verify_conn.close()

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_deterministic_replacement_preserves_manual_rows(self) -> None:
        """Auto publication must replace automatic rows idempotently while preserving estimator manual rows."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            conn = sqlite3.connect(db_path)
            conn.execute(
                """CREATE TABLE takeoff_rows (
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
            # Insert a manual row created by the user / estimator
            conn.execute(
                """INSERT INTO takeoff_rows(
                    workspace_id,section,element,location,substrate,finish_system,quantity,unit,
                    quantity_status,source_page,source_reference,inclusion_status,coats,
                    coverage_m2_per_litre,productivity_m2_per_hour,rate_per_unit,confidence,notes,
                    row_role,created_at,updated_at)
                    VALUES(99, 'External', 'Manual allowance', 'Site', 'Sundries', '', 1.0, 'allowance',
                    'Estimated', '1', 'manual:user_entry', 'Included', 0, 0.0, 0.0, 500.0, 'Documented',
                    'Estimator allowance', '', '2026-10-01T10:00:00', '2026-10-01T10:00:00')"""
            )
            conn.commit()
            conn.close()

            class CleanApp:
                def local_connect(self):
                    c = sqlite3.connect(db_path)
                    c.row_factory = sqlite3.Row
                    return c
                def now_stamp(self):
                    return "2026-10-01T12:00:00"

            app = CleanApp()

            # First run: publish 2 auto rows
            auto1 = _takeoff_row(
                workspace_id=99,
                section="External",
                element="External walls",
                location="North",
                substrate="Brick",
                quantity=30.0,
                status="Measured",
                source_page="1",
                source_reference=f"{SOURCE_PREFIX} · wall_1",
                confidence="Documented",
                notes="Auto wall 1",
            )
            auto2 = _takeoff_row(
                workspace_id=99,
                section="External",
                element="External walls",
                location="South",
                substrate="Brick",
                quantity=35.0,
                status="Measured",
                source_page="1",
                source_reference=f"{SOURCE_PREFIX} · wall_2",
                confidence="Documented",
                notes="Auto wall 2",
            )
            _replace_auto_rows(app, 99, [auto1, auto2])

            verify_conn = sqlite3.connect(db_path)
            rows = verify_conn.execute("SELECT source_reference FROM takeoff_rows WHERE workspace_id=99").fetchall()
            refs = [r[0] for r in rows]
            self.assertEqual(len(refs), 3)
            self.assertIn("manual:user_entry", refs)
            verify_conn.close()

            # Second run: re-run auto geometry with updated quantities (idempotent replacement)
            auto1_updated = _takeoff_row(
                workspace_id=99,
                section="External",
                element="External walls",
                location="North",
                substrate="Brick",
                quantity=32.0,  # Updated
                status="Measured",
                source_page="1",
                source_reference=f"{SOURCE_PREFIX} · wall_1",
                confidence="Documented",
                notes="Auto wall 1 updated",
            )
            _replace_auto_rows(app, 99, [auto1_updated, auto2])

            verify_conn = sqlite3.connect(db_path)
            all_rows = verify_conn.execute(
                "SELECT source_reference, quantity FROM takeoff_rows WHERE workspace_id=99 ORDER BY id"
            ).fetchall()
            self.assertEqual(len(all_rows), 3)  # Still exactly 3 rows: 1 manual + 2 auto (no duplicate buildup!)
            self.assertEqual(all_rows[0][0], "manual:user_entry")
            self.assertEqual(all_rows[1][1], 32.0)  # Updated quantity reflected
            verify_conn.close()

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
