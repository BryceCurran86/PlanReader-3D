"""Tests for AG-13: Cross-Trade Geometry Reuse.

Proves that PlanReader's architecture can support multiple trade quantities
from a single authenticated physical building object without duplicate extraction
or fake trade quantities.
"""
from __future__ import annotations

import unittest
from typing import Any, Dict, List

from pb_cross_trade_geometry_reuse import (
    DerivedTradeQuantity,
    derive_wall_trade_quantities,
    derive_slab_trade_quantities,
    derive_roof_trade_quantities,
    derive_space_trade_quantities,
    to_takeoff_rows,
)
from pb_auto_geometry_v1219 import _validate_auto_rows


class TestCrossTradeGeometryReuse(unittest.TestCase):
    def test_wall_multi_trade_derivations(self) -> None:
        """Prove 1 physical wall produces 5 distinct trade quantities with identical host object identity."""
        wall = {
            "wall_ref": "wall_N01",
            "side": "North",
            "length_m": 10.0,
            "height_m": 2.7,
            "gross_m2": 27.0,
            "opening_deduction_m2": 3.6,
            "net_m2": 23.4,
            "is_external": True,
            "substrate": "Brick veneer",
        }
        specs = {
            "include_skirting": True,
            "door_width_deduction_m": 0.9,
        }

        quantities = derive_wall_trade_quantities(wall, specs)
        self.assertEqual(len(quantities), 5)

        trades = {q.trade_scope: q for q in quantities}
        self.assertIn("masonry", trades)
        self.assertIn("linings", trades)
        self.assertIn("painting", trades)
        self.assertIn("insulation", trades)
        self.assertIn("carpentry", trades)

        # Check values
        self.assertEqual(trades["masonry"].quantity, 23.40)
        self.assertEqual(trades["masonry"].unit, "m²")
        self.assertEqual(trades["linings"].quantity, 23.40)
        self.assertEqual(trades["painting"].quantity, 23.40)
        self.assertEqual(trades["insulation"].quantity, 23.40)
        self.assertEqual(trades["carpentry"].quantity, 9.10)
        self.assertEqual(trades["carpentry"].unit, "lm")

        # Every single trade quantity links back to the same host object
        for q in quantities:
            self.assertEqual(q.host_object_id, "wall_N01")
            self.assertEqual(q.host_object_type, "WALL")

    def test_slab_multi_trade_derivations(self) -> None:
        """Prove 1 physical slab produces concrete, formwork, membrane, and reinforcement quantities."""
        slab = {
            "floor_id": "slab_G01",
            "area_m2": 120.0,
            "thickness_m": 0.15,
            "perimeter_m": 44.0,
            "is_suspended": False,
        }
        specs = {
            "mesh_lap_factor": 1.10,
        }

        quantities = derive_slab_trade_quantities(slab, specs)
        self.assertEqual(len(quantities), 4)

        trades = {q.trade_scope: q for q in quantities}
        # 120.0 m2 * 0.15m = 18.0 m3 concrete -> normalized to canonical unit 'item'
        self.assertEqual(trades["concrete"].quantity, 18.00)
        self.assertEqual(trades["concrete"].unit, "item")

        # 44.0 lm * 0.15m = 6.6 m2 edge formwork
        self.assertEqual(trades["formwork"].quantity, 6.60)
        self.assertEqual(trades["formwork"].unit, "m²")

        # 120.0 m2 vapor barrier
        self.assertEqual(trades["waterproofing"].quantity, 120.00)
        self.assertEqual(trades["waterproofing"].unit, "m²")

        # 120.0 m2 * 1.10 lap = 132.0 m2 steel mesh
        self.assertEqual(trades["reinforcement"].quantity, 132.00)
        self.assertEqual(trades["reinforcement"].unit, "m²")

        for q in quantities:
            self.assertEqual(q.host_object_id, "slab_G01")
            self.assertEqual(q.host_object_type, "SLAB")

    def test_roof_multi_trade_derivations(self) -> None:
        """Prove 1 physical roof produces cladding, insulation, gutters, and capping quantities."""
        roof = {
            "roof_id": "roof_main",
            "plan_area_m2": 100.0,
            "pitch_deg": 22.5,
            "eave_length_lm": 42.0,
            "ridge_length_lm": 15.0,
        }

        quantities = derive_roof_trade_quantities(roof)
        self.assertEqual(len(quantities), 4)

        cladding = next(q for q in quantities if "cladding" in q.element.lower())
        insul = next(q for q in quantities if "insulation" in q.trade_scope.lower())
        gutters = next(q for q in quantities if "gutters" in q.element.lower())
        capping = next(q for q in quantities if "capping" in q.element.lower())

        # 100 m2 / cos(22.5 deg) ~= 108.24 m2
        self.assertAlmostEqual(cladding.quantity, 108.24, places=1)
        self.assertEqual(cladding.unit, "m²")
        self.assertAlmostEqual(insul.quantity, 108.24, places=1)
        self.assertEqual(gutters.quantity, 42.00)
        self.assertEqual(gutters.unit, "lm")
        self.assertEqual(capping.quantity, 15.00)
        self.assertEqual(capping.unit, "lm")

        for q in quantities:
            self.assertEqual(q.host_object_id, "roof_main")
            self.assertEqual(q.host_object_type, "ROOF")

    def test_space_multi_trade_derivations(self) -> None:
        """Prove 1 physical room produces floor finish, ceiling lining, skirting, and cornice."""
        space = {
            "room_number": "101",
            "name": "Master Bedroom",
            "specified_floor_area_m2": 24.0,
            "perimeter_m": 20.0,
        }
        doors = [{"width_m": 0.9}]

        quantities = derive_space_trade_quantities(space, doors=doors)
        self.assertEqual(len(quantities), 4)

        trades = {q.trade_scope: q for q in quantities}
        self.assertEqual(trades["finishes"].quantity, 24.00)
        self.assertEqual(trades["finishes"].unit, "m²")
        self.assertEqual(trades["linings"].quantity, 24.00)
        self.assertEqual(trades["linings"].unit, "m²")
        self.assertEqual(trades["carpentry"].quantity, 19.10)  # 20.0 - 0.9 = 19.1
        self.assertEqual(trades["carpentry"].unit, "lm")
        self.assertEqual(trades["plastering"].quantity, 20.00)
        self.assertEqual(trades["plastering"].unit, "lm")

        for q in quantities:
            self.assertEqual(q.host_object_id, "101")
            self.assertEqual(q.host_object_type, "SPACE")

    def test_takeoff_rows_contract_compliance(self) -> None:
        """Prove derived quantities translate into valid canonical 21-field takeoff rows."""
        wall = {
            "wall_ref": "wall_N01",
            "length_m": 10.0,
            "height_m": 2.7,
            "net_m2": 23.4,
            "is_external": True,
        }
        quantities = derive_wall_trade_quantities(wall)
        rows = to_takeoff_rows(workspace_id=77, quantities=quantities, source_page="p1")

        self.assertEqual(len(rows), 4)
        for r in rows:
            self.assertEqual(len(r), 21)
            self.assertEqual(r[0], 77)
            self.assertTrue(r[6] > 0.0)
            self.assertIn("wall_N01", r[10])

        # Validate against strict production auto-row validator
        _validate_auto_rows(rows, 77)


if __name__ == "__main__":
    unittest.main()
