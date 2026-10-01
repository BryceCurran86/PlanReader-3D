"""Test Suite for Masonry Trade Authority Engine (AG-25).

Tests:
1. Brickwork veneer walls, cavity ties, and base DPC flashings.
2. Concrete blockwork (200mm/150mm), core-fill grout volumes, and bond beams.
3. Galvanized steel opening lintels with end bearings.
4. Strict compliance with 21-field core takeoff row contract in SQLite.
"""
from __future__ import annotations

import gc
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

import pb_masonry_trade_authority as masonry
import pb_takeoff_row_contract as takeoff_contract


class TestMasonryTradeAuthority(unittest.TestCase):
    def setUp(self) -> None:
        self.db_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_tmp.close()
        self.db_path = self.db_tmp.name
        self.ws_id = 808
        self.now = "2026-10-01T18:00:00"

        conn = sqlite3.connect(self.db_path)
        try:
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
        finally:
            conn.close()

    def tearDown(self) -> None:
        gc.collect()
        try:
            if os.path.exists(self.db_path):
                os.unlink(self.db_path)
        except OSError:
            pass

    def test_brickwork_veneer_calculations(self) -> None:
        """Verify brickwork veneer: net face area, ties count, and DPC length."""
        # Wall: 15.0m long, 2.7m high = 40.5 m² gross
        # Openings: W01 (1.8 x 1.2 = 2.16 m²), D01 (0.9 x 2.1 = 1.89 m²) -> Total ded = 4.05 m²
        # Net face: 40.5 - 4.05 = 36.45 m²
        spec = masonry.MasonryWallSpec(
            element_id="WALL_BRICK_01",
            wall_type="brickwork_veneer",
            description="North external face brickwork",
            section="External",
            length_m=15.0,
            height_m=2.7,
            openings=[
                {"width": 1.8, "height": 1.2, "area": 2.16},
                {"width": 0.9, "height": 2.1, "area": 1.89},
            ],
            source_page="Architectural A101",
        )
        items = masonry.calculate_brickwork_items(spec)
        self.assertEqual(len(items), 3)  # Brick face m², cavity ties No., DPC lm

        # 1. Brick face m²
        face_item = items[0]
        self.assertEqual(face_item.quantity, 36.45)
        self.assertEqual(face_item.unit, "m²")
        self.assertEqual(face_item.row_role, "external_wall")
        self.assertIn("1,768 bricks", face_item.notes)

        # 2. Cavity wall ties No.
        tie_item = items[1]
        # 36.45 * 4.5 = 164 ties
        self.assertEqual(tie_item.quantity, 164.0)
        self.assertEqual(tie_item.unit, "No.")

        # 3. Base DPC lm
        dpc_item = items[2]
        self.assertEqual(dpc_item.quantity, 15.0)
        self.assertEqual(dpc_item.unit, "lm")

    def test_blockwork_and_core_fill_calculations(self) -> None:
        """Verify concrete blockwork wall, core fill concrete volume, and bond beams."""
        # 200mm block wall: 20.0m long, 3.0m high = 60.0 m² gross
        # Opening: 2.4 x 2.1 = 5.04 m² -> Net = 54.96 m²
        # Fully core filled: 54.96 * 0.10 = 5.50 m³ grout
        spec = masonry.MasonryWallSpec(
            element_id="BLOCK_WALL_01",
            wall_type="blockwork_200",
            description="Boundary retaining block wall",
            section="External",
            length_m=20.0,
            height_m=3.0,
            openings=[{"width": 2.4, "height": 2.1, "area": 5.04}],
            core_fill="full",
            has_bond_beam=True,
            source_page="Structural S105",
        )
        items = masonry.calculate_blockwork_items(spec)
        self.assertEqual(len(items), 3)  # Block area m², core fill grout item, bond beam lm

        # 1. Block area
        block_area = items[0]
        self.assertEqual(block_area.quantity, 54.96)
        self.assertEqual(block_area.unit, "m²")

        # 2. Core fill grout item: 5.50 m³
        grout_item = items[1]
        self.assertEqual(grout_item.quantity, 5.50)
        self.assertEqual(grout_item.unit, "item")
        self.assertIn("5.50 m³", grout_item.notes)

        # 3. Bond beam lm
        beam_item = items[2]
        self.assertEqual(beam_item.quantity, 20.0)
        self.assertEqual(beam_item.unit, "lm")

    def test_lintel_calculations(self) -> None:
        """Verify opening lintels with 150mm end bearings."""
        spec = masonry.MasonryWallSpec(
            element_id="WALL_LINTELS",
            wall_type="brickwork_veneer",
            description="Wall with windows",
            length_m=10.0,
            openings=[
                {"width": 1.2, "height": 1.0},  # 1.2 + 0.30 = 1.50 lm
                {"width": 2.4, "height": 2.1},  # 2.4 + 0.30 = 2.70 lm
            ],
            source_page="Architectural A101",
        )
        items = masonry.calculate_lintel_items(spec)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].quantity, 1.50)
        self.assertEqual(items[0].unit, "lm")
        self.assertEqual(items[1].quantity, 2.70)
        self.assertEqual(items[1].unit, "lm")

    def test_sqlite_publication_and_contract_compliance(self) -> None:
        """Verify that masonry takeoff rows satisfy 21-field core contract in SQLite."""
        specs = [
            masonry.MasonryWallSpec(
                element_id="W1",
                wall_type="brickwork_veneer",
                description="Brick veneer",
                length_m=12.0,
                height_m=2.7,
                openings=[{"width": 1.8, "height": 1.2, "area": 2.16}],
            ),
            masonry.MasonryWallSpec(
                element_id="W2",
                wall_type="blockwork_200",
                description="Block wall",
                length_m=10.0,
                height_m=2.5,
                core_fill="half",
                has_bond_beam=True,
            ),
        ]

        rows = masonry.generate_workspace_masonry_takeoff(specs, self.ws_id, self.now)
        # W1: face, ties, DPC, 1 lintel = 4
        # W2: block, core fill, bond beam = 3
        # Total = 7
        self.assertEqual(len(rows), 7)

        insert_sql = """
            INSERT INTO takeoff_rows (
                workspace_id, section, element, location, substrate, finish_system,
                quantity, unit, quantity_status, source_page, source_reference,
                inclusion_status, coats, coverage_m2_per_litre, productivity_m2_per_hour,
                rate_per_unit, confidence, notes, row_role, created_at, updated_at
            ) VALUES (
                :workspace_id, :section, :element, :location, :substrate, :finish_system,
                :quantity, :unit, :quantity_status, :source_page, :source_reference,
                :inclusion_status, :coats, :coverage_m2_per_litre, :productivity_m2_per_hour,
                :rate_per_unit, :confidence, :notes, :row_role, :created_at, :updated_at
            )
        """

        conn = sqlite3.connect(self.db_path)
        try:
            conn.executemany(insert_sql, rows)
            conn.commit()

            cur = conn.execute("SELECT * FROM takeoff_rows WHERE workspace_id=?", (self.ws_id,))
            db_rows = cur.fetchall()
            self.assertEqual(len(db_rows), len(rows))

            cols = [d[0] for d in cur.description]
            self.assertEqual(len(cols), 22)  # id + 21 core fields

            for r in db_rows:
                row_dict = dict(zip(cols, r))
                self.assertEqual(row_dict["workspace_id"], self.ws_id)
                self.assertIn(row_dict["unit"], takeoff_contract.TAKEOFF_UNITS)
                self.assertIn(row_dict["inclusion_status"], ("INCLUSION", "PROVISIONAL"))
                self.assertTrue(row_dict["quantity"] > 0.0)
                self.assertTrue(len(row_dict["notes"]) > 5)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
