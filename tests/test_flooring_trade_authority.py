"""Test Suite for Flooring & Tiling Trade Authority Engine (AG-26).

Tests:
1. Engineered timber flooring, acoustic underlay, and quad beading.
2. Broadloom carpet, carpet underlay, and smooth-edge grippers.
3. Floor tiles, sand & cement screed to falls, and waterproofing with upturns.
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

import pb_flooring_trade_authority as flooring
import pb_takeoff_row_contract as takeoff_contract


class TestFlooringTradeAuthority(unittest.TestCase):
    def setUp(self) -> None:
        self.db_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_tmp.close()
        self.db_path = self.db_tmp.name
        self.ws_id = 909
        self.now = "2026-10-01T18:30:00"

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

    def test_timber_flooring_calculations(self) -> None:
        """Verify timber flooring, underlay, and perimeter quad calculations."""
        spec = flooring.FlooringSpaceSpec(
            space_id="ROOM_LIVING_01",
            room_name="Living & Dining",
            floor_finish="timber",
            area_m2=45.0,
            perimeter_lm=28.0,
            door_deduction_lm=1.2,
            source_page="Finishes Schedule A501",
        )
        items = flooring.calculate_timber_flooring_items(spec)
        self.assertEqual(len(items), 3)  # Timber m², underlay m², quads lm

        # 1. Timber area
        timber_area = items[0]
        self.assertEqual(timber_area.quantity, 45.0)
        self.assertEqual(timber_area.unit, "m²")
        self.assertEqual(timber_area.row_role, "floor_area")

        # 2. Acoustic underlay
        underlay = items[1]
        self.assertEqual(underlay.quantity, 45.0)
        self.assertEqual(underlay.unit, "m²")

        # 3. Perimeter quad: 28.0 - 1.2 = 26.8 lm
        quad = items[2]
        self.assertEqual(quad.quantity, 26.8)
        self.assertEqual(quad.unit, "lm")

    def test_carpet_flooring_calculations(self) -> None:
        """Verify carpet, underlay, and smooth-edge grippers."""
        spec = flooring.FlooringSpaceSpec(
            space_id="ROOM_BED_01",
            room_name="Bedroom 1",
            floor_finish="carpet",
            area_m2=18.5,
            perimeter_lm=17.4,
            door_deduction_lm=0.9,
            source_page="Finishes Schedule A501",
        )
        items = flooring.calculate_carpet_flooring_items(spec)
        self.assertEqual(len(items), 3)

        carpet_area = items[0]
        self.assertEqual(carpet_area.quantity, 18.5)
        self.assertEqual(carpet_area.row_role, "floor_area")

        underlay = items[1]
        self.assertEqual(underlay.quantity, 18.5)

        # Grippers: 17.4 - 0.9 = 16.5 lm
        grippers = items[2]
        self.assertEqual(grippers.quantity, 16.5)
        self.assertEqual(grippers.unit, "lm")

    def test_wet_area_tiling_screed_and_waterproofing(self) -> None:
        """Verify floor tiling, sand/cement screed to falls, waterproofing upturns, and tile skirtings."""
        spec = flooring.FlooringSpaceSpec(
            space_id="ROOM_BATH_01",
            room_name="Master Bathroom",
            floor_finish="tiles",
            area_m2=8.40,
            perimeter_lm=11.6,
            door_deduction_lm=0.9,
            is_wet_area=True,
            requires_screed=True,
            screed_depth_mm=40,
            requires_waterproofing=True,
            tile_size_desc="600x600 Porcelain",
            source_page="Finishes Schedule A501",
        )
        items = flooring.calculate_tiling_items(spec)
        self.assertEqual(len(items), 4)  # Tiles, screed, waterproofing, skirtings

        # 1. Tiles area
        tiles = items[0]
        self.assertEqual(tiles.quantity, 8.40)
        self.assertEqual(tiles.row_role, "floor_area")

        # 2. Screed area
        screed = items[1]
        self.assertEqual(screed.quantity, 8.40)
        self.assertIn("40mm nominal", screed.notes)

        # 3. Waterproofing: 8.40 m² floor + (11.6 lm * 0.15m upturn = 1.74 m²) = 10.14 m²
        waterproofing = items[2]
        self.assertEqual(waterproofing.quantity, 10.14)
        self.assertEqual(waterproofing.unit, "m²")

        # 4. Tile skirtings: 11.6 - 0.9 = 10.7 lm
        skirtings = items[3]
        self.assertEqual(skirtings.quantity, 10.7)
        self.assertEqual(skirtings.unit, "lm")

    def test_sqlite_publication_and_contract_compliance(self) -> None:
        """Verify that flooring takeoff rows satisfy 21-field core contract in SQLite."""
        specs = [
            flooring.FlooringSpaceSpec(
                space_id="ROOM_LIVING",
                room_name="Living Room",
                floor_finish="timber",
                area_m2=35.0,
                perimeter_lm=24.0,
            ),
            flooring.FlooringSpaceSpec(
                space_id="ROOM_ENSUITE",
                room_name="Ensuite",
                floor_finish="tiles",
                area_m2=6.5,
                perimeter_lm=10.2,
                is_wet_area=True,
                requires_screed=True,
                requires_waterproofing=True,
            ),
        ]

        rows = flooring.generate_workspace_flooring_takeoff(specs, self.ws_id, self.now)
        # Living: timber, underlay, quads = 3
        # Ensuite: tiles, screed, waterproofing, skirtings = 4
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
