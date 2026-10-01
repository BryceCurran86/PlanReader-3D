"""Test Suite for Electrical Trade Authority Engine (AG-29).

Tests:
1. Switchboards and distribution boards (No.).
2. Luminaires, emergency fittings, and light switches (No.).
3. General power outlets (GPOs) and dedicated circuits (No.).
4. Data/communications outlets (No.).
5. Cable tray and conduit runs (lm).
6. Strict compliance with 21-field core takeoff row contract in SQLite.
"""
from __future__ import annotations

import gc
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

import pb_electrical_trade_authority as electrical
import pb_takeoff_row_contract as takeoff_contract


class TestElectricalTradeAuthority(unittest.TestCase):
    def setUp(self) -> None:
        self.db_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_tmp.close()
        self.db_path = self.db_tmp.name
        self.ws_id = 1212
        self.now = "2026-10-01T20:00:00"

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

    def test_switchboard_and_lighting_calculations(self) -> None:
        """Verify switchboard and lighting item calculations."""
        # Switchboard: 1 No. DB-1
        db_spec = electrical.ElectricalDeviceSpec(
            device_type="switchboard",
            device_mark="DB-1",
            description="36-pole distribution board",
            location="Electrical Cupboard",
            count=1,
            source_page="Electrical E101",
        )
        sb_items = electrical.calculate_switchboard_items(db_spec)
        self.assertEqual(len(sb_items), 1)
        self.assertEqual(sb_items[0].quantity, 1.0)
        self.assertEqual(sb_items[0].unit, "No.")
        self.assertIn("DB-1", sb_items[0].location)

        # Lighting: 24 No. LED downlights
        light_spec = electrical.ElectricalDeviceSpec(
            device_type="light",
            device_mark="DL-01",
            description="13W LED recessed downlight",
            location="Offices",
            count=24,
            source_page="Electrical E101",
        )
        light_items = electrical.calculate_lighting_items(light_spec)
        self.assertEqual(len(light_items), 1)
        self.assertEqual(light_items[0].quantity, 24.0)
        self.assertEqual(light_items[0].unit, "No.")

    def test_power_and_data_calculations(self) -> None:
        """Verify GPOs, dedicated appliance circuits, and data outlets."""
        # Power: 16 No. double GPOs
        gpo_spec = electrical.ElectricalDeviceSpec(
            device_type="gpo",
            device_mark="GPO-D",
            description="10A double GPO",
            location="General areas",
            count=16,
            source_page="Electrical E102",
        )
        gpo_items = electrical.calculate_power_items(gpo_spec)
        self.assertEqual(len(gpo_items), 1)
        self.assertEqual(gpo_items[0].quantity, 16.0)
        self.assertEqual(gpo_items[0].unit, "No.")

        # Dedicated circuit: 1 No. 32A Cooktop isolator
        cooktop_spec = electrical.ElectricalDeviceSpec(
            device_type="gpo",
            device_mark="CKT-OVEN",
            description="32A Cooktop isolator and circuit",
            location="Kitchen",
            count=1,
            is_dedicated_circuit=True,
            source_page="Electrical E102",
        )
        cooktop_items = electrical.calculate_power_items(cooktop_spec)
        self.assertEqual(len(cooktop_items), 1)
        self.assertEqual(cooktop_items[0].quantity, 1.0)
        self.assertIn("Dedicated power circuit", cooktop_items[0].element)

        # Data: 12 No. Cat6 outlets
        data_spec = electrical.ElectricalDeviceSpec(
            device_type="data",
            device_mark="DATA-1",
            description="Dual Cat6 RJ45 outlet",
            location="Workstations",
            count=12,
            source_page="Comms E103",
        )
        data_items = electrical.calculate_data_items(data_spec)
        self.assertEqual(len(data_items), 1)
        self.assertEqual(data_items[0].quantity, 12.0)
        self.assertEqual(data_items[0].unit, "No.")

    def test_containment_calculations(self) -> None:
        """Verify cable tray and ladder runs."""
        tray_spec = electrical.ElectricalContainmentSpec(
            containment_type="ladder",
            size_desc="300mm NEMA 2 Cable Ladder",
            description="Main riser cable ladder",
            section="Structure",
            length_m=42.0,
            source_page="Electrical E104",
        )
        tray_items = electrical.calculate_containment_items(tray_spec)
        self.assertEqual(len(tray_items), 1)
        self.assertEqual(tray_items[0].quantity, 42.0)
        self.assertEqual(tray_items[0].unit, "lm")

    def test_sqlite_publication_and_contract_compliance(self) -> None:
        """Verify that electrical takeoff rows satisfy 21-field core contract in SQLite."""
        devices = [
            electrical.ElectricalDeviceSpec(
                device_type="switchboard",
                device_mark="MSB",
                description="Main switchboard",
                location="Switchroom",
                count=1,
            ),
            electrical.ElectricalDeviceSpec(
                device_type="light",
                device_mark="L1",
                description="LED Panel",
                location="Office",
                count=10,
            ),
        ]
        containments = [
            electrical.ElectricalContainmentSpec(
                containment_type="tray",
                size_desc="150mm Cable Tray",
                description="Corridor tray",
                length_m=25.0,
            ),
        ]

        rows = electrical.generate_workspace_electrical_takeoff(devices, containments, self.ws_id, self.now)
        self.assertEqual(len(rows), 3)

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
