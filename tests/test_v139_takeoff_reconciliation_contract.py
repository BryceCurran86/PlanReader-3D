"""Canonical 3D diagnostics recognise the take-off rows the v1.3.9 producer emits.

pb_3d_diagnostics_phase5m matches registered-wall take-off rows to canonical
walls by a literal source_reference prefix, while pb_unified_building_v139
builds that prefix from its VERSION. If either side drifts, every wall
silently reconciles as having no production row.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

import pb_3d_diagnostics_phase5m as diagnostics
import pb_unified_building_v139 as unified

WALL = {"side": "North", "wall_ref": "N01", "substrate": "Render", "net_m2": 12.5,
        "gross_m2": 14.0, "opening_deduction_m2": 1.5}


class V139ReconciliationContractTests(unittest.TestCase):
    def test_producer_rows_are_matched_to_their_registered_wall(self):
        row = unified.takeoff_rows([WALL])[0]
        self.assertEqual(diagnostics._row_wall_identity(row, {"N01", "S01"}), ("N01", "dedicated_v139"))

    def test_rows_for_unregistered_walls_stay_unmatched(self):
        row = unified.takeoff_rows([dict(WALL, wall_ref="N99")])[0]
        self.assertEqual(diagnostics._row_wall_identity(row, {"N01"}), (None, "v139_unknown_wall_ref"))

    def test_rows_of_another_producer_version_are_not_taken_as_v139(self):
        with patch.object(unified, "VERSION", "1.4.0"):
            row = unified.takeoff_rows([WALL])[0]
        self.assertEqual(diagnostics._row_wall_identity(row, {"N01"}), (None, "weak_or_missing_identity"))


if __name__ == "__main__":
    unittest.main()
