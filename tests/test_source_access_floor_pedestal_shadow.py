"""
tests/test_source_access_floor_pedestal_shadow.py

Unit tests for SourceAccessFloorPedestalShadowAuthority.
"""

import unittest
from pb_source_access_floor_pedestal_shadow import (
    SourceAccessFloorPedestalShadowAuthority,
    AccessFloorGrade,
    AccessFloorZoneSpec,
    SNAP_TOLERANCE_PT
)


class TestSourceAccessFloorPedestalShadow(unittest.TestCase):

    def test_parse_access_floor_tag(self):
        grade, ffh, p_size = SourceAccessFloorPedestalShadowAuthority.parse_access_floor_tag(
            "RAISED ACCESS FLOOR 600x600 HEAVY GRADE 300 FFH"
        )
        self.assertEqual(grade, AccessFloorGrade.HEAVY_GRADE)
        self.assertEqual(ffh, 300.0)
        self.assertEqual(p_size, 600.0)

        grade2, ffh2, p_size2 = SourceAccessFloorPedestalShadowAuthority.parse_access_floor_tag(
            "ACCESS FLOOR 150MM FFH MEDIUM GRADE"
        )
        self.assertEqual(grade2, AccessFloorGrade.MEDIUM_GRADE)
        self.assertEqual(ffh2, 150.0)
        self.assertEqual(p_size2, 600.0)

    def test_snap_point(self):
        ref_pts = [(0.0, 0.0), (100.0, 100.0)]
        snapped = SourceAccessFloorPedestalShadowAuthority.snap_point((1.0, 1.0), ref_pts)
        self.assertEqual(snapped, (0.0, 0.0))

        unsnapped = SourceAccessFloorPedestalShadowAuthority.snap_point((10.0, 10.0), ref_pts)
        self.assertEqual(unsnapped, (10.0, 10.0))

    def test_server_room_access_floor_takeoff(self):
        # 6.0m x 6.0m room = 36.0 m2, perimeter = 24.0m, FFH = 300mm
        # Panels = 36 / 0.36 = 100 panels
        # Plenum volume = 36 * 0.3 = 10.8 m3
        # Pedestals = ceil(36/0.36 + 24/1.2 + 1) = 100 + 20 + 1 = 121
        z = AccessFloorZoneSpec(
            zone_id="AF-SERVER-1",
            room_id="ROOM-SERVER",
            boundary_polygon=[(0.0, 0.0), (6.0, 0.0), (6.0, 6.0), (0.0, 6.0)],
            grade=AccessFloorGrade.HEAVY_GRADE,
            ffh_mm=300.0,
            panel_size_mm=600.0
        )
        res = SourceAccessFloorPedestalShadowAuthority.evaluate_access_flooring([z], drawing_scale=1.0)
        self.assertEqual(res.quantities.total_raised_floor_area_m2, 36.0)
        self.assertEqual(res.quantities.total_perimeter_trim_length_m, 24.0)
        self.assertEqual(res.quantities.total_panel_count, 100)
        self.assertEqual(res.quantities.total_pedestal_count, 121)
        self.assertEqual(res.quantities.total_plenum_volume_m3, 10.8)

    def test_invariants_and_safety(self):
        res = SourceAccessFloorPedestalShadowAuthority.evaluate_access_flooring([])
        self.assertEqual(res.status, "CANDIDATE")
        self.assertFalse(res.commercial_projection_allowed)
        self.assertFalse(res.takeoff_eligible)


if __name__ == "__main__":
    unittest.main()
