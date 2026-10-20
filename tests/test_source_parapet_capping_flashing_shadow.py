"""
tests/test_source_parapet_capping_flashing_shadow.py

Unit tests for SourceParapetCappingFlashingShadowAuthority.
"""

import unittest
from pb_source_parapet_capping_flashing_shadow import (
    SourceParapetCappingFlashingShadowAuthority,
    CappingMaterial,
    ParapetSegmentSpec,
    SNAP_TOLERANCE_PT
)


class TestSourceParapetCappingFlashingShadow(unittest.TestCase):

    def test_parse_parapet_annotation(self):
        mat, thk, h, girth, turnup = SourceParapetCappingFlashingShadowAuthority.parse_parapet_annotation(
            "PARAPET 200THK x 750H COLORBOND CAPPING 450 GIRTH W/ 250 MEMBRANE UPSTAND"
        )
        self.assertEqual(mat, CappingMaterial.COLORBOND_STEEL)
        self.assertEqual(thk, 200.0)
        self.assertEqual(h, 750.0)
        self.assertEqual(girth, 450.0)
        self.assertEqual(turnup, 250.0)

        # Aluminium capping
        mat2, thk2, h2, girth2, turnup2 = SourceParapetCappingFlashingShadowAuthority.parse_parapet_annotation(
            "ALUMINIUM COPING 300W x 900 HIGH 550 GIRTH"
        )
        self.assertEqual(mat2, CappingMaterial.ALUMINIUM)
        self.assertEqual(thk2, 300.0)
        self.assertEqual(h2, 900.0)
        self.assertEqual(girth2, 550.0)
        self.assertEqual(turnup2, 0.0)

        mat3, thk3, h3, girth3, turnup3 = SourceParapetCappingFlashingShadowAuthority.parse_parapet_annotation(
            "PARAPET"
        )
        self.assertEqual(mat3, CappingMaterial.UNKNOWN)
        self.assertEqual(thk3, 0.0)
        self.assertEqual(h3, 0.0)
        self.assertEqual(girth3, 0.0)
        self.assertEqual(turnup3, 0.0)

        omitted = ParapetSegmentSpec(
            segment_id="P-UNKNOWN",
            centerline_points=[(0.0, 0.0), (1.0, 0.0)],
        )
        self.assertEqual(omitted.wall_thickness_mm, 0.0)
        self.assertEqual(omitted.upstand_height_mm, 0.0)
        self.assertEqual(omitted.capping_girth_mm, 0.0)
        self.assertEqual(omitted.membrane_turnup_height_mm, 0.0)
        self.assertFalse(omitted.has_drip_groove)
        self.assertEqual(omitted.capping_material, CappingMaterial.UNKNOWN)

    def test_snap_point(self):
        ref_pts = [(0.0, 0.0), (100.0, 50.0)]
        snapped = SourceParapetCappingFlashingShadowAuthority.snap_point((0.5, 0.5), ref_pts)
        self.assertEqual(snapped, (0.0, 0.0))

        unsnapped = SourceParapetCappingFlashingShadowAuthority.snap_point((10.0, 10.0), ref_pts)
        self.assertEqual(unsnapped, (10.0, 10.0))

    def test_single_parapet_takeoff(self):
        # 20m straight parapet wall: 450mm girth capping, 250mm membrane upstand
        # Capping area = 20 * 0.45 = 9.0 m2
        # Membrane area = 20 * 0.25 = 5.0 m2
        # Counter-flashing = 20 m
        seg = ParapetSegmentSpec(
            segment_id="P-1",
            centerline_points=[(0.0, 0.0), (20.0, 0.0)],
            capping_girth_mm=450.0,
            membrane_turnup_height_mm=250.0
        )
        res = SourceParapetCappingFlashingShadowAuthority.evaluate_parapets([seg], drawing_scale=1.0)
        self.assertEqual(res.quantities.total_parapet_length_m, 20.0)
        self.assertEqual(res.quantities.total_capping_flashing_length_m, 20.0)
        self.assertEqual(res.quantities.total_capping_sheet_area_m2, 9.0)
        self.assertEqual(res.quantities.total_membrane_upstand_area_m2, 5.0)
        self.assertEqual(res.quantities.total_counterflashing_length_m, 20.0)

    def test_multi_segment_roof_perimeter(self):
        # 10m x 15m rectangular roof perimeter = 2 * (10 + 15) = 50m
        corners = [(0.0, 0.0), (10.0, 0.0), (10.0, 15.0), (0.0, 15.0), (0.0, 0.0)]
        seg = ParapetSegmentSpec(
            segment_id="P-ROOF-PERIMETER",
            centerline_points=corners,
            capping_girth_mm=500.0,
            membrane_turnup_height_mm=300.0
        )
        res = SourceParapetCappingFlashingShadowAuthority.evaluate_parapets([seg], drawing_scale=1.0)
        self.assertEqual(res.quantities.total_parapet_length_m, 50.0)
        self.assertEqual(res.quantities.total_capping_sheet_area_m2, 25.0)
        self.assertEqual(res.quantities.total_membrane_upstand_area_m2, 15.0)

    def test_invariants_and_safety(self):
        res = SourceParapetCappingFlashingShadowAuthority.evaluate_parapets([])
        self.assertEqual(res.status, "CANDIDATE")
        self.assertFalse(res.commercial_projection_allowed)
        self.assertFalse(res.takeoff_eligible)


if __name__ == "__main__":
    unittest.main()
