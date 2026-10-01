"""Tests for AG-12: Provenance Chain Persistence.

Target:
quantity → building object → authority/evidence → page/sheet → source document

Verifies that customer takeoff rows retain full provenance from the numerical
quantity back to the physical building object, the deduction authority, the specific
sheet/page, and the source document file.
"""
from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from typing import Any, Dict, List

from pb_auto_geometry_v1219 import _try_physical_net_wall_rows, _replace_auto_rows
from pb_opening_detail_definition_bridge import ConsolidatedPhysicalOpening


class MockApp:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute(
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
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER,
                path TEXT
            )"""
        )
        self._conn.commit()

    def lquery(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(query, params)
        cols = [d[0] for d in cur.description] if cur.description else []
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def lexecute(self, query: str, params: tuple = ()) -> None:
        self._conn.execute(query, params)
        self._conn.commit()

    def local_connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def now_stamp(self) -> str:
        return "2026-10-01T12:00:00"

    def build_registered_walls_v139(self, ws_id: int):
        # Wall with detailed provenance
        op1 = ConsolidatedPhysicalOpening(
            opening_id="win_N01",
            type_mark="W01",
            host_wall_id="N01",
            width_m=1.5,
            height_m=1.2,
            area_m2=1.8,
            plan_page_id="1",
            elevation_page_id="3",
        )
        op2 = ConsolidatedPhysicalOpening(
            opening_id="door_N02",
            type_mark="D02",
            host_wall_id="N01",
            width_m=0.9,
            height_m=2.1,
            area_m2=1.89,
            plan_page_id="1",
            elevation_page_id="3",
        )
        return [
            {
                "wall_ref": "N01",
                "side": "North",
                "gross_m2": 30.0,
                "net_m2": 26.31,
                "opening_deduction_m2": 3.69,
                "height_status": "Measured 2.70m",
                "height_confidence": "Verified",
                "plan_page_id": "1",
                "elevation_page_id": "3",
                "source_document": "3LAUREL_ARCHITECTURAL_REV_B.pdf",
                "openings": [op1, op2],
            }
        ]


class TestProvenanceChainPersistence(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.app = MockApp(self.tmp.name)

    def tearDown(self) -> None:
        import os
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_full_provenance_chain_persists_in_takeoff_rows(self) -> None:
        """Prove: quantity → building object → authority/evidence → page/sheet → source document."""
        ws_id = 101

        # 1. Generate takeoff rows from verified evidence
        rows = _try_physical_net_wall_rows(self.app, ws_id, [], {})
        self.assertIsNotNone(rows)
        self.assertEqual(len(rows), 1)

        # 2. Persist rows to SQLite
        _replace_auto_rows(self.app, ws_id, rows)

        # 3. Query SQLite takeoff_rows and verify complete 5-link provenance chain
        db_rows = self.app.lquery(
            "SELECT quantity, location, source_reference, source_page, notes FROM takeoff_rows WHERE workspace_id=?",
            (ws_id,),
        )
        self.assertEqual(len(db_rows), 1)
        row = db_rows[0]

        # Link 1: Numerical Quantity
        self.assertEqual(row["quantity"], 26.31)

        # Link 2: Physical Building Object
        self.assertIn("North · N01", row["location"])

        # Link 3: Authority / Deduction Evidence
        self.assertIn("registered_wall:N01", row["source_reference"])
        self.assertIn("authenticated opening deductions 3.69 m²", row["notes"])
        self.assertIn("W01 (1.80 m²)", row["notes"])
        self.assertIn("D02 (1.89 m²)", row["notes"])

        # Link 4: Page / Sheet
        self.assertEqual(row["source_page"], "Plan p.1 / Elev p.3")

        # Link 5: Source Document
        self.assertIn("Doc: 3LAUREL_ARCHITECTURAL_REV_B.pdf", row["notes"])


if __name__ == "__main__":
    unittest.main()
