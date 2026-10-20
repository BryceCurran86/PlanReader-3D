"""
tests/test_source_roof_drainage_gutter_downpipe_shadow.py

Unit tests for SourceRoofDrainageGutterDownpipeShadowAuthority.
"""

import unittest
from pb_source_roof_drainage_gutter_downpipe_shadow import (
    SourceRoofDrainageGutterDownpipeShadowAuthority,
    GutterType,
    DrainageMaterial,
    GutterSpec,
    DownpipeSpec,
    OverflowScupperSpec,
    RainwaterHeadSpec,
    SNAP_TOLERANCE_PT
)


class TestSourceRoofDrainageGutterDownpipeShadow(unittest.TestCase):

    def test_parse_gutter_annotation(self):
        g_type, w, d, mat = SourceRoofDrainageGutterDownpipeShadowAuthority.parse_gutter_annotation(
            "COLORBOND BOX GUTTER 350W x 200D W/ 1:100 FALL"
        )
        self.assertEqual(g_type, GutterType.BOX_GUTTER)
        self.assertEqual(w, 350.0)
        self.assertEqual(d, 200.0)
        self.assertEqual(mat, DrainageMaterial.COLORBOND_STEEL)

        g_type2, w2, d2, mat2 = SourceRoofDrainageGutterDownpipeShadowAuthority.parse_gutter_annotation(
            "STAINLESS STEEL HALF ROUND GUTTER 200x120"
        )
        self.assertEqual(g_type2, GutterType.HALF_ROUND_GUTTER)
        self.assertEqual(w2, 200.0)
        self.assertEqual(d2, 120.0)
        self.assertEqual(mat2, DrainageMaterial.STAINLESS_STEEL)

        g_type3, w3, d3, _mat3 = SourceRoofDrainageGutterDownpipeShadowAuthority.parse_gutter_annotation(
            "GUTTER"
        )
        self.assertEqual(w3, 0.0)
        self.assertEqual(d3, 0.0)

        omitted = GutterSpec(
            gutter_id="G-UNKNOWN",
            gutter_type=GutterType.BOX_GUTTER,
            centerline_points=[(0.0, 0.0), (1.0, 0.0)],
        )
        self.assertEqual(omitted.width_mm, 0.0)
        self.assertEqual(omitted.depth_mm, 0.0)

    def test_snap_point(self):
        ref_pts = [(50.0, 50.0), (100.0, 100.0)]
        snapped = SourceRoofDrainageGutterDownpipeShadowAuthority.snap_point((50.5, 51.0), ref_pts)
        self.assertEqual(snapped, (50.0, 50.0))

        unsnapped = SourceRoofDrainageGutterDownpipeShadowAuthority.snap_point((60.0, 60.0), ref_pts)
        self.assertEqual(unsnapped, (60.0, 60.0))

    def test_roof_drainage_system_takeoff(self):
        # 15m box gutter: 350mm W x 200mm D. Girth = 0.85m -> Sheet area = 15 * 0.85 = 12.75 m2
        # 20m eaves gutter: 150mm W x 100mm D. Girth = 0.45m -> Sheet area = 20 * 0.45 = 9.0 m2
        # Total sheet area = 12.75 + 9.0 = 21.75 m2
        # 2 downpipes: 3.5m drop each -> 7.0m
        g1 = GutterSpec(
            gutter_id="BG-1",
            gutter_type=GutterType.BOX_GUTTER,
            centerline_points=[(0.0, 0.0), (15.0, 0.0)],
            width_mm=350.0,
            depth_mm=200.0
        )
        g2 = GutterSpec(
            gutter_id="EG-1",
            gutter_type=GutterType.EAVES_QUAD_GUTTER,
            centerline_points=[(0.0, 10.0), (20.0, 10.0)],
            width_mm=150.0,
            depth_mm=100.0
        )
        dp1 = DownpipeSpec(downpipe_id="DP-01", location=(15.0, 0.0), height_drop_m=3.5)
        dp2 = DownpipeSpec(downpipe_id="DP-02", location=(20.0, 10.0), height_drop_m=3.5)
        scupper = OverflowScupperSpec(scupper_id="SC-01", location=(15.0, 0.5))
        rhead = RainwaterHeadSpec(head_id="RH-01", location=(15.0, 0.0))

        res = SourceRoofDrainageGutterDownpipeShadowAuthority.evaluate_roof_drainage(
            gutters=[g1, g2],
            downpipes=[dp1, dp2],
            scuppers=[scupper],
            rainwater_heads=[rhead],
            drawing_scale=1.0
        )

        self.assertEqual(res.quantities.total_box_gutter_length_m, 15.0)
        self.assertEqual(res.quantities.total_eaves_gutter_length_m, 20.0)
        self.assertEqual(res.quantities.total_gutter_length_m, 35.0)
        self.assertEqual(res.quantities.total_gutter_sheet_area_m2, 21.75)
        self.assertEqual(res.quantities.total_downpipe_count, 2)
        self.assertEqual(res.quantities.total_downpipe_length_m, 7.0)
        self.assertEqual(res.quantities.total_scupper_count, 1)
        self.assertEqual(res.quantities.total_rainwater_head_count, 1)

    def test_omitted_height_drop_does_not_invent_three_metre_storey(self):
        dp = DownpipeSpec(downpipe_id="DP-UNKNOWN", location=(0.0, 0.0))
        self.assertEqual(dp.height_drop_m, 0.0)
        self.assertEqual(dp.diameter_mm, 0.0)
        res = SourceRoofDrainageGutterDownpipeShadowAuthority.evaluate_roof_drainage(
            [], [dp], [], []
        )
        self.assertEqual(res.quantities.total_downpipe_length_m, 0.0)

    def test_invariants_and_safety(self):
        res = SourceRoofDrainageGutterDownpipeShadowAuthority.evaluate_roof_drainage([], [], [], [])
        self.assertEqual(res.status, "CANDIDATE")
        self.assertFalse(res.commercial_projection_allowed)
        self.assertFalse(res.takeoff_eligible)


if __name__ == "__main__":
    unittest.main()
