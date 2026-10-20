"""
tests/test_source_retaining_wall_drainage_shadow.py

Unit tests for SourceRetainingWallDrainageShadowAuthority.
"""

import unittest
from pb_source_retaining_wall_drainage_shadow import (
    SourceRetainingWallDrainageShadowAuthority,
    RetainingWallType,
    RetainingWallSpec,
    SNAP_TOLERANCE_PT
)


class TestSourceRetainingWallDrainageShadow(unittest.TestCase):

    def test_parse_retaining_wall_annotation(self):
        w_type, stem_t, h, fw, fd = SourceRetainingWallDrainageShadowAuthority.parse_retaining_wall_annotation(
            "RETAINING WALL 200THK STEM x 1800H W/ 1200W x 300D FOOTING"
        )
        self.assertEqual(w_type, RetainingWallType.RC_CANTILEVER)
        self.assertEqual(stem_t, 200.0)
        self.assertEqual(h, 1800.0)
        self.assertEqual(fw, 1200.0)
        self.assertEqual(fd, 300.0)

        w_type2, stem_t2, h2, fw2, fd2 = SourceRetainingWallDrainageShadowAuthority.parse_retaining_wall_annotation(
            "CORE FILLED CONCRETE BLOCK RETAINING WALL 190 THK x 1200 HIGH"
        )
        self.assertEqual(w_type2, RetainingWallType.CORE_FILLED_BLOCK)
        self.assertEqual(stem_t2, 190.0)
        self.assertEqual(h2, 1200.0)

    def test_snap_point(self):
        ref_pts = [(0.0, 0.0), (100.0, 100.0)]
        snapped = SourceRetainingWallDrainageShadowAuthority.snap_point((1.0, 1.0), ref_pts)
        self.assertEqual(snapped, (0.0, 0.0))

        unsnapped = SourceRetainingWallDrainageShadowAuthority.snap_point((10.0, 10.0), ref_pts)
        self.assertEqual(unsnapped, (10.0, 10.0))

    def test_retaining_wall_takeoff(self):
        # 10m long wall:
        # Stem: 200mm thk x 1800mm high -> 10 * 0.2 * 1.8 = 3.6 m3
        # Footing: 1200mm wide x 300mm deep -> 10 * 1.2 * 0.3 = 3.6 m3
        # Total conc = 7.2 m3
        # Agg backfill: 300mm wide x 1.8m high -> 10 * 0.3 * 1.8 = 5.4 m3
        # Tanking area: 10 * 1.8 = 18.0 m2
        # Ag-pipe: 10.0 m
        wall = RetainingWallSpec(
            wall_id="RW-01",
            wall_type=RetainingWallType.RC_CANTILEVER,
            centerline_points=[(0.0, 0.0), (10.0, 0.0)],
            stem_thickness_mm=200.0,
            retained_height_mm=1800.0,
            footing_width_mm=1200.0,
            footing_depth_mm=300.0,
            ag_pipe_diameter_mm=100.0,
            agg_backfill_width_mm=300.0,
            has_tanking_membrane=True
        )
        res = SourceRetainingWallDrainageShadowAuthority.evaluate_retaining_walls([wall], drawing_scale=1.0)
        self.assertEqual(res.quantities.total_wall_length_m, 10.0)
        self.assertEqual(res.quantities.total_stem_concrete_volume_m3, 3.6)
        self.assertEqual(res.quantities.total_footing_concrete_volume_m3, 3.6)
        self.assertEqual(res.quantities.total_concrete_volume_m3, 7.2)
        self.assertEqual(res.quantities.total_drainage_agg_volume_m3, 5.4)
        self.assertEqual(res.quantities.total_tanking_membrane_area_m2, 18.0)
        self.assertEqual(res.quantities.total_ag_pipe_length_m, 10.0)

    def test_omitted_tanking_does_not_assume_membrane(self):
        wall = RetainingWallSpec(
            wall_id="RW-UNKNOWN",
            wall_type=RetainingWallType.RC_CANTILEVER,
            centerline_points=[(0.0, 0.0), (10.0, 0.0)],
        )
        self.assertFalse(wall.has_tanking_membrane)
        res = SourceRetainingWallDrainageShadowAuthority.evaluate_retaining_walls([wall])
        self.assertEqual(res.quantities.total_tanking_membrane_area_m2, 0.0)

    def test_invariants_and_safety(self):
        res = SourceRetainingWallDrainageShadowAuthority.evaluate_retaining_walls([])
        self.assertEqual(res.status, "CANDIDATE")
        self.assertFalse(res.commercial_projection_allowed)
        self.assertFalse(res.takeoff_eligible)


if __name__ == "__main__":
    unittest.main()
