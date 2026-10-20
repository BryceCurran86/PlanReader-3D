"""
tests/test_source_suspended_ceiling_grid_shadow.py

Unit tests for SourceSuspendedCeilingGridShadowAuthority.
"""

import unittest
from pb_source_suspended_ceiling_grid_shadow import (
    SourceSuspendedCeilingGridShadowAuthority,
    CeilingGridModule,
    CeilingGridType,
    SuspendedCeilingSpec,
    SNAP_TOLERANCE_PT
)


class TestSourceSuspendedCeilingGridShadow(unittest.TestCase):

    def test_parse_ceiling_annotation(self):
        mod, g_type, clg_lvl, soffit_lvl = SourceSuspendedCeilingGridShadowAuthority.parse_ceiling_annotation(
            "SUSPENDED CEILING 1200x600 GRID EXPOSED TEE 2700 AFFL PLENUM 600"
        )
        self.assertEqual(mod, CeilingGridModule.GRID_1200X600)
        self.assertEqual(g_type, CeilingGridType.EXPOSED_TEE)
        self.assertEqual(clg_lvl, 2700.0)
        self.assertEqual(soffit_lvl, 3300.0)

        mod2, g_type2, clg_lvl2, soffit_lvl2 = SourceSuspendedCeilingGridShadowAuthority.parse_ceiling_annotation(
            "CONCEALED GRID 600X600 ACOUSTIC CEILING 3000 AFFL"
        )
        self.assertEqual(mod2, CeilingGridModule.GRID_600X600)
        self.assertEqual(g_type2, CeilingGridType.CONCEALED_TEE)
        self.assertEqual(clg_lvl2, 3000.0)
        self.assertEqual(soffit_lvl2, 3000.0)

        mod3, _type3, clg_lvl3, soffit_lvl3 = SourceSuspendedCeilingGridShadowAuthority.parse_ceiling_annotation(
            "CEILING"
        )
        self.assertEqual(clg_lvl3, 0.0)
        self.assertEqual(soffit_lvl3, 0.0)
        self.assertEqual(mod3, CeilingGridModule.UNKNOWN)

        omitted = SuspendedCeilingSpec(
            ceiling_id="CLG-UNKNOWN",
            room_id="ROOM-UNKNOWN",
            boundary_polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        )
        self.assertEqual(omitted.finished_ceiling_level_mm, 0.0)
        self.assertEqual(omitted.slab_soffit_level_mm, 0.0)
        self.assertEqual(omitted.grid_module, CeilingGridModule.UNKNOWN)
        res_omitted = SourceSuspendedCeilingGridShadowAuthority.evaluate_ceilings([omitted])
        self.assertEqual(res_omitted.quantities.total_main_runner_length_m, 0.0)
        self.assertEqual(res_omitted.quantities.total_cross_tee_length_m, 0.0)
        self.assertEqual(res_omitted.quantities.total_estimated_tile_count, 0)
        self.assertEqual(res_omitted.quantities.total_hanger_wire_points, 0)

    def test_snap_point(self):
        ref_pts = [(0.0, 0.0), (100.0, 100.0)]
        snapped = SourceSuspendedCeilingGridShadowAuthority.snap_point((1.0, 1.0), ref_pts)
        self.assertEqual(snapped, (0.0, 0.0))

        unsnapped = SourceSuspendedCeilingGridShadowAuthority.snap_point((10.0, 10.0), ref_pts)
        self.assertEqual(unsnapped, (10.0, 10.0))

    def test_suspended_ceiling_takeoff(self):
        # 6m x 12m rectangular office ceiling (72 m2):
        # Area = 72.0 m2
        # Perimeter trim = 2 * (6 + 12) = 36.0 m
        # Main runners = 72 / 1.2 = 60.0 m
        # Cross tees = 72 / 0.6 = 120.0 m
        # Hangers = ceil(72 / 1.44) = 50 hangers
        # Plenum depth = 3300 - 2700 = 600mm = 0.6m -> Wire length = 50 * 0.6 = 30.0 m
        # Tile count = ceil(72 / 0.72) = 100 tiles
        c = SuspendedCeilingSpec(
            ceiling_id="CLG-OFFICE-1",
            room_id="OFFICE-101",
            boundary_polygon=[(0.0, 0.0), (12.0, 0.0), (12.0, 6.0), (0.0, 6.0)],
            grid_module=CeilingGridModule.GRID_1200X600,
            grid_type=CeilingGridType.EXPOSED_TEE,
            finished_ceiling_level_mm=2700.0,
            slab_soffit_level_mm=3300.0
        )
        res = SourceSuspendedCeilingGridShadowAuthority.evaluate_ceilings([c], drawing_scale=1.0)
        self.assertEqual(res.quantities.total_ceiling_area_m2, 72.0)
        self.assertEqual(res.quantities.total_perimeter_wall_trim_length_m, 36.0)
        self.assertEqual(res.quantities.total_main_runner_length_m, 60.0)
        self.assertEqual(res.quantities.total_cross_tee_length_m, 120.0)
        self.assertEqual(res.quantities.total_hanger_wire_points, 50)
        self.assertEqual(res.quantities.total_hanger_wire_length_m, 30.0)
        self.assertEqual(res.quantities.total_estimated_tile_count, 100)

    def test_invariants_and_safety(self):
        res = SourceSuspendedCeilingGridShadowAuthority.evaluate_ceilings([])
        self.assertEqual(res.status, "CANDIDATE")
        self.assertFalse(res.commercial_projection_allowed)
        self.assertFalse(res.takeoff_eligible)


if __name__ == "__main__":
    unittest.main()
