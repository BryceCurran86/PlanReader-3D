"""Tests for AG-11: Stable Object Identity Parity.

Target principle:
ONE PHYSICAL BUILDING OBJECT = ONE CANONICAL IDENTITY
Multiple pieces of evidence can attach to it.
Do not merge unrelated objects because they look geometrically similar.
"""
from __future__ import annotations

import unittest
from typing import Any, Dict, List

from pb_opening_detail_definition_bridge import (
    ConsolidatedPhysicalOpening,
    consolidate_opening_identities,
    enrich_openings_with_detail_definitions,
    apply_opening_deductions_to_walls,
)
from pb_opening_detail_definition_authority import (
    OpeningDetailDefinitionRecord,
)
from pb_auto_geometry_v1219 import _try_physical_net_wall_rows


class TestStableObjectIdentityParity(unittest.TestCase):
    def test_distinct_openings_same_wall_same_mark_keep_separate_identities(self) -> None:
        """Distinct physical openings on the same wall with identical marks MUST NOT collapse into one."""
        raw_openings = [
            {
                "opening_id": "win_north_01",
                "host_wall_id": "wall_north",
                "type_mark": "W01",
                "width_m": 1.2,
                "height_m": 1.5,
                "plan_page_id": "1",
            },
            {
                "opening_id": "win_north_02",
                "host_wall_id": "wall_north",
                "type_mark": "W01",
                "width_m": 1.2,
                "height_m": 1.5,
                "plan_page_id": "1",
            },
        ]
        consolidated = consolidate_opening_identities(raw_openings)
        self.assertEqual(len(consolidated), 2)
        ids = {op.opening_id for op in consolidated}
        self.assertEqual(ids, {"win_north_01", "win_north_02"})
        for op in consolidated:
            self.assertEqual(op.host_wall_id, "wall_north")
            self.assertEqual(op.type_mark, "W01")
            self.assertEqual(op.area_m2, 1.8)

        # Applying deductions to host wall must deduct BOTH openings (3.6 m2 total)
        walls = [
            {
                "wall_ref": "wall_north",
                "gross_m2": 20.0,
                "net_m2": 20.0,
                "opening_deduction_m2": 0.0,
            }
        ]
        deducted_walls = apply_opening_deductions_to_walls(walls, consolidated)
        self.assertEqual(len(deducted_walls), 1)
        w = deducted_walls[0]
        self.assertAlmostEqual(w["opening_deduction_m2"], 3.6, places=2)
        self.assertAlmostEqual(w["net_m2"], 16.4, places=2)

    def test_cross_sheet_same_opening_consolidates_identically(self) -> None:
        """Single physical opening observed across plan, elevation, schedule, and detail retains 1 identity."""
        raw_observations = [
            {"opening_id": "door_main", "host_wall_id": "wall_south", "type_mark": "D01", "width_m": 0.9, "plan_page_id": "1"},
            {"opening_id": "door_main", "host_wall_id": "wall_south", "type_mark": "D01", "height_m": 2.1, "elevation_page_id": "2"},
            {"opening_id": "door_main", "host_wall_id": "wall_south", "type_mark": "D01", "schedule_page_id": "3"},
            {"opening_id": "door_main", "host_wall_id": "wall_south", "type_mark": "D01", "detail_page_id": "4"},
        ]
        consolidated = consolidate_opening_identities(raw_observations)
        self.assertEqual(len(consolidated), 1)
        op = consolidated[0]
        self.assertEqual(op.opening_id, "door_main")
        self.assertEqual(op.host_wall_id, "wall_south")
        self.assertEqual(op.type_mark, "D01")
        self.assertEqual(op.width_m, 0.9)
        self.assertEqual(op.height_m, 2.1)
        self.assertEqual(op.area_m2, 1.89)
        self.assertEqual(op.plan_page_id, "1")
        self.assertEqual(op.elevation_page_id, "2")
        self.assertEqual(op.schedule_page_id, "3")
        self.assertEqual(op.detail_page_id, "4")

    def test_registered_walls_stable_identity_fallback(self) -> None:
        """Walls without wall_ref retain distinct identities via wall_id or candidate_id."""
        class MockApp:
            def build_registered_walls_v139(self, ws_id: int):
                return [
                    {
                        "wall_id": "wall_cand_alpha",
                        "side": "North",
                        "gross_m2": 25.0,
                        "net_m2": 22.0,
                        "opening_deduction_m2": 3.0,
                        "height_confidence": "Verified",
                    },
                    {
                        "candidate_id": "wall_cand_beta",
                        "side": "South",
                        "gross_m2": 30.0,
                        "net_m2": 28.0,
                        "opening_deduction_m2": 2.0,
                        "height_confidence": "Verified",
                    },
                ]

        rows = _try_physical_net_wall_rows(MockApp(), 42, [], {})
        self.assertEqual(len(rows), 2)
        locations = [r[3] for r in rows]
        source_refs = [r[10] for r in rows]

        self.assertIn("North · wall_cand_alpha", locations)
        self.assertIn("South · wall_cand_beta", locations)
        self.assertTrue(any("registered_wall:wall_cand_alpha" in s for s in source_refs))
        self.assertTrue(any("registered_wall:wall_cand_beta" in s for s in source_refs))


if __name__ == "__main__":
    unittest.main()
