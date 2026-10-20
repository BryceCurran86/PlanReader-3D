"""
tests/test_source_acoustic_wall_lining_shadow.py

Unit tests for SourceAcousticWallLiningShadowAuthority.
"""

import unittest
from pb_source_acoustic_wall_lining_shadow import (
    SourceAcousticWallLiningShadowAuthority,
    AcousticDecouplingType,
    AcousticWallSpec,
    SNAP_TOLERANCE_PT
)


class TestSourceAcousticWallLiningShadow(unittest.TestCase):

    def test_parse_acoustic_wall_tag(self):
        decoupling, side_a, side_b, rw = SourceAcousticWallLiningShadowAuthority.parse_acoustic_wall_tag(
            "ACOUSTIC WALL RW55 DOUBLE STUD 2x13mm + 2x13mm"
        )
        self.assertEqual(decoupling, AcousticDecouplingType.DOUBLE_STUD_DISCONTINUOUS)
        self.assertEqual(side_a, 2)
        self.assertEqual(side_b, 2)
        self.assertEqual(rw, 55)

        decoupling2, side_a2, side_b2, rw2 = SourceAcousticWallLiningShadowAuthority.parse_acoustic_wall_tag(
            "WALL RW50 RC-1 RESILIENT MOUNT 2x16mm + 1x16mm"
        )
        self.assertEqual(decoupling2, AcousticDecouplingType.RESILIENT_CHANNEL_MOUNT)
        self.assertEqual(side_a2, 2)
        self.assertEqual(side_b2, 1)
        self.assertEqual(rw2, 50)

    def test_snap_point(self):
        ref_pts = [(0.0, 0.0), (100.0, 100.0)]
        snapped = SourceAcousticWallLiningShadowAuthority.snap_point((1.0, 1.0), ref_pts)
        self.assertEqual(snapped, (0.0, 0.0))

        unsnapped = SourceAcousticWallLiningShadowAuthority.snap_point((10.0, 10.0), ref_pts)
        self.assertEqual(unsnapped, (10.0, 10.0))

    def test_acoustic_wall_takeoff_double_stud(self):
        # 10m long wall, 3.0m high:
        # Elevation area = 30 m2
        # Side A = 2 layers -> 60 m2
        # Side B = 2 layers -> 60 m2
        # Total board = 120 m2
        # Sealant = 2 * (2 * 10 + 2 * 3) = 52.0 m
        wall = AcousticWallSpec(
            wall_id="AW-01",
            decoupling_type=AcousticDecouplingType.DOUBLE_STUD_DISCONTINUOUS,
            centerline_points=[(0.0, 0.0), (10.0, 0.0)],
            wall_height_m=3.0,
            side_a_layers=2,
            side_b_layers=2
        )
        res = SourceAcousticWallLiningShadowAuthority.evaluate_acoustic_walls([wall], drawing_scale=1.0)
        self.assertEqual(res.quantities.total_acoustic_wall_length_m, 10.0)
        self.assertEqual(res.quantities.total_wall_elevation_area_m2, 30.0)
        self.assertEqual(res.quantities.total_side_a_board_area_m2, 60.0)
        self.assertEqual(res.quantities.total_side_b_board_area_m2, 60.0)
        self.assertEqual(res.quantities.total_acoustic_board_area_m2, 120.0)
        self.assertEqual(res.quantities.total_resilient_channel_length_m, 0.0)
        self.assertEqual(res.quantities.total_perimeter_sealant_length_m, 52.0)

    def test_resilient_channel_takeoff(self):
        # 10m long wall, 3.0m high with RC-1 mount -> 5 rows of RC -> 50.0m
        wall = AcousticWallSpec(
            wall_id="AW-RC",
            decoupling_type=AcousticDecouplingType.RESILIENT_CHANNEL_MOUNT,
            centerline_points=[(0.0, 0.0), (10.0, 0.0)],
            wall_height_m=3.0,
            side_a_layers=2,
            side_b_layers=1
        )
        res = SourceAcousticWallLiningShadowAuthority.evaluate_acoustic_walls([wall], drawing_scale=1.0)
        self.assertEqual(res.quantities.total_resilient_channel_length_m, 50.0)
        self.assertEqual(res.quantities.total_side_a_board_area_m2, 60.0)
        self.assertEqual(res.quantities.total_side_b_board_area_m2, 30.0)
        self.assertEqual(res.quantities.total_acoustic_board_area_m2, 90.0)

    def test_invariants_and_safety(self):
        res = SourceAcousticWallLiningShadowAuthority.evaluate_acoustic_walls([])
        self.assertEqual(res.status, "CANDIDATE")
        self.assertFalse(res.commercial_projection_allowed)
        self.assertFalse(res.takeoff_eligible)


if __name__ == "__main__":
    unittest.main()
