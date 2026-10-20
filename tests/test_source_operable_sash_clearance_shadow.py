"""
tests/test_source_operable_sash_clearance_shadow.py

Unit tests for SourceOperableSashClearanceShadowAuthority.
"""

import unittest
from pb_source_operable_sash_clearance_shadow import (
    SourceOperableSashClearanceShadowAuthority,
    SashOperationType,
    OperableSashSpec,
    SNAP_TOLERANCE_PT
)


class TestSourceOperableSashClearanceShadow(unittest.TestCase):

    def test_parse_sash_annotation(self):
        op_type, w, h, screen = SourceOperableSashClearanceShadowAuthority.parse_sash_annotation(
            "AWNING SASH 900W x 1200H W/ CHAIN WINDER & FLYSCREEN"
        )
        self.assertEqual(op_type, SashOperationType.AWNING)
        self.assertEqual(w, 900.0)
        self.assertEqual(h, 1200.0)
        self.assertTrue(screen)

        op_type2, w2, h2, screen2 = SourceOperableSashClearanceShadowAuthority.parse_sash_annotation(
            "FIXED VISION PANEL 1800x1500"
        )
        self.assertEqual(op_type2, SashOperationType.FIXED)
        self.assertEqual(w2, 1800.0)
        self.assertEqual(h2, 1500.0)
        self.assertFalse(screen2)

        _op3, w3, h3, _screen3 = SourceOperableSashClearanceShadowAuthority.parse_sash_annotation(
            "SASH"
        )
        self.assertEqual(w3, 0.0)
        self.assertEqual(h3, 0.0)

    def test_omitted_insect_screen_does_not_assume_flyscreen(self):
        sash = OperableSashSpec(
            sash_id="S-UNKNOWN",
            parent_window_id="W-UNKNOWN",
            operation_type=SashOperationType.AWNING,
            width_mm=900.0,
            height_mm=1200.0,
        )
        self.assertFalse(sash.has_insect_screen)
        self.assertEqual(sash.opening_angle_deg, 0.0)
        self.assertEqual(sash.max_projection_mm, 0.0)
        self.assertEqual(
            SourceOperableSashClearanceShadowAuthority.compute_ventilation_area(sash),
            0.0,
        )
        res = SourceOperableSashClearanceShadowAuthority.evaluate_sashes([sash])
        self.assertEqual(res.quantities.total_screen_count, 0)

    def test_omitted_casement_angle_does_not_invent_fifteen_degrees(self):
        sash = OperableSashSpec(
            sash_id="S-CASE-UNKNOWN",
            parent_window_id="W-UNKNOWN",
            operation_type=SashOperationType.CASEMENT_RH,
            width_mm=800.0,
            height_mm=1500.0,
        )
        self.assertEqual(sash.opening_angle_deg, 0.0)
        self.assertEqual(
            SourceOperableSashClearanceShadowAuthority.compute_ventilation_area(sash),
            0.0,
        )

    def test_snap_point(self):
        ref_pts = [(0.0, 0.0), (100.0, 100.0)]
        snapped = SourceOperableSashClearanceShadowAuthority.snap_point((1.0, 1.0), ref_pts)
        self.assertEqual(snapped, (0.0, 0.0))

        unsnapped = SourceOperableSashClearanceShadowAuthority.snap_point((10.0, 10.0), ref_pts)
        self.assertEqual(unsnapped, (10.0, 10.0))

    def test_ventilation_area_calculations(self):
        # Sliding sash: 1000 x 1200mm -> 1.2 m2 * 0.5 = 0.6 m2
        s_sliding = OperableSashSpec(
            sash_id="S-1",
            parent_window_id="W-01",
            operation_type=SashOperationType.SLIDING,
            width_mm=1000.0,
            height_mm=1200.0
        )
        self.assertAlmostEqual(SourceOperableSashClearanceShadowAuthority.compute_ventilation_area(s_sliding), 0.6)

        # Fixed sash -> 0.0 m2
        s_fixed = OperableSashSpec(
            sash_id="S-2",
            parent_window_id="W-01",
            operation_type=SashOperationType.FIXED,
            width_mm=1000.0,
            height_mm=1200.0
        )
        self.assertEqual(SourceOperableSashClearanceShadowAuthority.compute_ventilation_area(s_fixed), 0.0)

        # Casement 90 deg -> gross area
        s_case = OperableSashSpec(
            sash_id="S-3",
            parent_window_id="W-02",
            operation_type=SashOperationType.CASEMENT_RH,
            width_mm=800.0,
            height_mm=1500.0,
            opening_angle_deg=90.0
        )
        self.assertAlmostEqual(SourceOperableSashClearanceShadowAuthority.compute_ventilation_area(s_case), 1.2)

    def test_multi_bay_window_takeoff(self):
        # 1 Fixed (1.2m x 1.5m = 1.8 m2) + 1 Awning (0.9m x 1.2m = 1.08 m2 w/ screen)
        s1 = OperableSashSpec(
            sash_id="S1",
            parent_window_id="W-01",
            operation_type=SashOperationType.FIXED,
            width_mm=1200.0,
            height_mm=1500.0,
            has_insect_screen=False
        )
        s2 = OperableSashSpec(
            sash_id="S2",
            parent_window_id="W-01",
            operation_type=SashOperationType.AWNING,
            width_mm=900.0,
            height_mm=1200.0,
            max_projection_mm=250.0,
            has_insect_screen=True
        )
        res = SourceOperableSashClearanceShadowAuthority.evaluate_sashes([s1, s2])
        self.assertEqual(res.quantities.total_sash_count, 2)
        self.assertEqual(res.quantities.total_fixed_panel_count, 1)
        self.assertEqual(res.quantities.total_operable_sash_count, 1)
        self.assertEqual(res.quantities.total_screen_count, 1)
        self.assertEqual(res.quantities.total_insect_screen_area_m2, 1.08)
        self.assertEqual(res.quantities.total_gross_sash_area_m2, 2.88)
        self.assertGreater(res.quantities.total_effective_ventilation_area_m2, 0.0)

    def test_invariants_and_safety(self):
        res = SourceOperableSashClearanceShadowAuthority.evaluate_sashes([])
        self.assertEqual(res.status, "CANDIDATE")
        self.assertFalse(res.commercial_projection_allowed)
        self.assertFalse(res.takeoff_eligible)


if __name__ == "__main__":
    unittest.main()
