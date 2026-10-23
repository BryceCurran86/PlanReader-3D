"""
tests/test_source_slab_drop_panel_capital_shadow.py

Unit tests for SourceSlabDropPanelCapitalShadowAuthority.
"""

import unittest
from pb_source_slab_drop_panel_capital_shadow import (
    SourceSlabDropPanelCapitalShadowAuthority,
    ShearThickeningType,
    CapitalShape,
    DropPanelSpec,
    ColumnCapitalSpec,
    SNAP_TOLERANCE_PT
)


class TestSourceSlabDropPanelCapitalShadow(unittest.TestCase):

    def test_parse_drop_panel_annotation(self):
        w, l, thk = SourceSlabDropPanelCapitalShadowAuthority.parse_drop_panel_annotation(
            "DROP PANEL 2400x2400x150 THK DP"
        )
        self.assertEqual(w, 2400.0)
        self.assertEqual(l, 2400.0)
        self.assertEqual(thk, 150.0)

        w2, l2, thk2 = SourceSlabDropPanelCapitalShadowAuthority.parse_drop_panel_annotation(
            "DP 2000x2500x200"
        )
        self.assertEqual(w2, 2000.0)
        self.assertEqual(l2, 2500.0)
        self.assertEqual(thk2, 200.0)

        w3, l3, thk3 = SourceSlabDropPanelCapitalShadowAuthority.parse_drop_panel_annotation(
            "DROP PANEL"
        )
        self.assertEqual(w3, 0.0)
        self.assertEqual(l3, 0.0)
        self.assertEqual(thk3, 0.0)

    def test_snap_point(self):
        ref_pts = [(50.0, 50.0), (100.0, 100.0)]
        snapped = SourceSlabDropPanelCapitalShadowAuthority.snap_point((51.0, 51.0), ref_pts)
        self.assertEqual(snapped, (50.0, 50.0))

        unsnapped = SourceSlabDropPanelCapitalShadowAuthority.snap_point((60.0, 60.0), ref_pts)
        self.assertEqual(unsnapped, (60.0, 60.0))

    def test_single_drop_panel_takeoff(self):
        # 2.4m x 2.4m square drop panel, 150mm drop thickness
        # Area = 5.76 m2
        # Vol = 5.76 * 0.15 = 0.864 m3
        # Perimeter = 9.6 m
        # Edge formwork = 9.6 * 0.15 = 1.44 m2
        dp = DropPanelSpec(
            panel_id="DP-C1",
            thickening_type=ShearThickeningType.DROP_PANEL,
            boundary_polygon=[(0.0, 0.0), (2.4, 0.0), (2.4, 2.4), (0.0, 2.4)],
            drop_thickness_mm=150.0,
            column_id="C1"
        )
        res = SourceSlabDropPanelCapitalShadowAuthority.evaluate_panels_and_capitals([dp], [], drawing_scale=1.0)
        self.assertEqual(res.quantities.total_drop_panel_count, 1)
        self.assertEqual(res.quantities.total_drop_soffit_area_m2, 5.76)
        self.assertEqual(res.quantities.total_drop_concrete_volume_m3, 0.864)
        self.assertEqual(res.quantities.total_drop_edge_formwork_area_m2, 1.44)

    def test_column_capital_frustum_volume(self):
        # 1200x1200mm top to 600x600mm bottom, height 600mm
        # Vol = (0.6 / 3) * (1.44 + 0.36 + 0.72) = 0.2 * 2.52 = 0.504 m3
        cap = ColumnCapitalSpec(
            capital_id="CAP-C2",
            top_width_mm=1200.0,
            top_length_mm=1200.0,
            bottom_width_mm=600.0,
            bottom_length_mm=600.0,
            height_mm=600.0,
            shape=CapitalShape.PYRAMIDAL,
            column_id="C2"
        )
        res = SourceSlabDropPanelCapitalShadowAuthority.evaluate_panels_and_capitals([], [cap], drawing_scale=1.0)
        self.assertEqual(res.quantities.total_capital_count, 1)
        self.assertEqual(res.quantities.total_capital_concrete_volume_m3, 0.504)

    def test_invariants_and_safety(self):
        res = SourceSlabDropPanelCapitalShadowAuthority.evaluate_panels_and_capitals([], [])
        self.assertEqual(res.status, "CANDIDATE")
        self.assertFalse(res.commercial_projection_allowed)
        self.assertFalse(res.takeoff_eligible)

        omitted_dp = DropPanelSpec(
            panel_id="DP-OMIT",
            thickening_type=ShearThickeningType.DROP_PANEL,
            boundary_polygon=[(0.0, 0.0), (2.4, 0.0), (2.4, 2.4), (0.0, 2.4)],
            drop_thickness_mm=150.0,
        )
        omitted_cap = ColumnCapitalSpec(
            capital_id="CAP-OMIT",
            top_width_mm=1200.0,
            top_length_mm=1200.0,
            bottom_width_mm=600.0,
            bottom_length_mm=600.0,
            height_mm=600.0,
        )
        self.assertEqual(omitted_dp.level_id, "")
        self.assertEqual(omitted_cap.level_id, "")
        self.assertEqual(omitted_cap.shape, CapitalShape.UNKNOWN)
        omitted = SourceSlabDropPanelCapitalShadowAuthority.evaluate_panels_and_capitals(
            [omitted_dp], [omitted_cap]
        )
        self.assertEqual(omitted.quantities.total_capital_concrete_volume_m3, 0.0)


if __name__ == "__main__":
    unittest.main()
