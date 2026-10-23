"""
tests/test_source_steel_bracing_gusset_plate_shadow.py

Unit tests for SourceSteelBracingGussetPlateShadowAuthority.
"""

import unittest
from pb_source_steel_bracing_gusset_plate_shadow import (
    SourceSteelBracingGussetPlateShadowAuthority,
    BracingConfigType,
    GussetPlateSpec,
    BracingMemberSpec,
    SNAP_TOLERANCE_PT
)


class TestSourceSteelBracingGussetPlateShadow(unittest.TestCase):

    def test_parse_bracing_annotation(self):
        cfg, sec, mass, tb = SourceSteelBracingGussetPlateShadowAuthority.parse_bracing_annotation(
            "X-BRACING 75x75x6 EA W/ 12THK GUSSETS"
        )
        self.assertEqual(cfg, BracingConfigType.X_BRACE)
        self.assertEqual(sec, "75x75x6 EA")
        self.assertEqual(mass, 6.81)
        self.assertFalse(tb)

        cfg2, sec2, mass2, tb2 = SourceSteelBracingGussetPlateShadowAuthority.parse_bracing_annotation(
            "20 DIA TIE ROD W/ TURNBUCKLE"
        )
        self.assertEqual(cfg2, BracingConfigType.SINGLE_DIAGONAL)
        self.assertEqual(sec2, "20mm Round Bar")
        self.assertEqual(mass2, 2.47)
        self.assertTrue(tb2)

        cfg3, sec3, mass3, _tb3 = SourceSteelBracingGussetPlateShadowAuthority.parse_bracing_annotation(
            "BRACING"
        )
        self.assertEqual(cfg3, BracingConfigType.UNKNOWN)
        self.assertEqual(sec3, "")
        self.assertEqual(mass3, 0.0)

    def test_snap_point_3d(self):
        ref_pts = [(0.0, 0.0, 0.0), (100.0, 100.0, 50.0)]
        snapped = SourceSteelBracingGussetPlateShadowAuthority.snap_point_3d((1.0, 1.0, 0.5), ref_pts)
        self.assertEqual(snapped, (0.0, 0.0, 0.0))

        unsnapped = SourceSteelBracingGussetPlateShadowAuthority.snap_point_3d((10.0, 10.0, 0.0), ref_pts)
        self.assertEqual(unsnapped, (10.0, 10.0, 0.0))

    def test_x_bracing_bay_takeoff(self):
        # 6m bay width x 4m height: diag = 7.211 m
        # 2 members = 14.422 m
        # 4 gussets at 4 corners
        g1 = GussetPlateSpec(gusset_id="G1", location=(0.0, 0.0, 0.0), width_mm=250.0, height_mm=250.0, thickness_mm=12.0)
        g2 = GussetPlateSpec(gusset_id="G2", location=(6.0, 0.0, 4.0), width_mm=250.0, height_mm=250.0, thickness_mm=12.0)
        g3 = GussetPlateSpec(gusset_id="G3", location=(0.0, 0.0, 4.0), width_mm=250.0, height_mm=250.0, thickness_mm=12.0)
        g4 = GussetPlateSpec(gusset_id="G4", location=(6.0, 0.0, 0.0), width_mm=250.0, height_mm=250.0, thickness_mm=12.0)

        m1 = BracingMemberSpec(
            member_id="BR-1A",
            config_type=BracingConfigType.X_BRACE,
            start_point=(0.0, 0.0, 0.0),
            end_point=(6.0, 0.0, 4.0),
            linear_mass_kg_m=6.81,
            start_gusset=g1,
            end_gusset=g2
        )
        m2 = BracingMemberSpec(
            member_id="BR-1B",
            config_type=BracingConfigType.X_BRACE,
            start_point=(0.0, 0.0, 4.0),
            end_point=(6.0, 0.0, 0.0),
            linear_mass_kg_m=6.81,
            start_gusset=g3,
            end_gusset=g4
        )

        res = SourceSteelBracingGussetPlateShadowAuthority.evaluate_bracing_system([m1, m2])
        self.assertEqual(res.quantities.total_bracing_member_count, 2)
        self.assertEqual(res.quantities.total_gusset_plate_count, 4)
        self.assertAlmostEqual(res.quantities.total_bracing_linear_length_m, 14.422, places=2)
        self.assertAlmostEqual(res.quantities.total_member_steel_mass_kg, 98.21, places=1)
        self.assertAlmostEqual(res.quantities.total_gusset_plate_mass_kg, 23.55, places=1)
        self.assertAlmostEqual(res.quantities.total_system_steel_mass_kg, 121.76, places=1)

    def test_invariants_and_safety(self):
        res = SourceSteelBracingGussetPlateShadowAuthority.evaluate_bracing_system([])
        self.assertEqual(res.status, "CANDIDATE")
        self.assertFalse(res.commercial_projection_allowed)
        self.assertFalse(res.takeoff_eligible)

        omitted_g = GussetPlateSpec(gusset_id="G-OMIT", location=(0.0, 0.0, 0.0))
        self.assertEqual(omitted_g.width_mm, 0.0)
        self.assertEqual(omitted_g.height_mm, 0.0)
        self.assertEqual(omitted_g.thickness_mm, 0.0)
        omitted_m = BracingMemberSpec(
            member_id="BR-OMIT",
            config_type=BracingConfigType.X_BRACE,
            start_point=(0.0, 0.0, 0.0),
            end_point=(6.0, 0.0, 4.0),
            start_gusset=omitted_g,
        )
        self.assertEqual(omitted_m.section_name, "")
        self.assertEqual(omitted_m.linear_mass_kg_m, 0.0)
        omitted_res = SourceSteelBracingGussetPlateShadowAuthority.evaluate_bracing_system([omitted_m])
        self.assertEqual(omitted_res.quantities.total_gusset_plate_mass_kg, 0.0)
        self.assertEqual(omitted_res.quantities.total_member_steel_mass_kg, 0.0)


if __name__ == "__main__":
    unittest.main()
