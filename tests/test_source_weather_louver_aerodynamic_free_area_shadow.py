"""
tests/test_source_weather_louver_aerodynamic_free_area_shadow.py

Unit tests for SourceWeatherLouverAerodynamicFreeAreaShadowAuthority.
"""

import unittest
from pb_source_weather_louver_aerodynamic_free_area_shadow import (
    SourceWeatherLouverAerodynamicFreeAreaShadowAuthority,
    LouverBladeType,
    WeatherLouverSpec,
    SNAP_TOLERANCE_PT
)


class TestSourceWeatherLouverAerodynamicFreeAreaShadow(unittest.TestCase):

    def test_parse_louver_annotation(self):
        b_type, w, h, fa, pitch = SourceWeatherLouverAerodynamicFreeAreaShadowAuthority.parse_louver_annotation(
            "WEATHER LOUVER 1500W x 2000H TWO STAGE STORM 48% FREE AREA @ 75 PITCH"
        )
        self.assertEqual(b_type, LouverBladeType.TWO_STAGE_STORM)
        self.assertEqual(w, 1500.0)
        self.assertEqual(h, 2000.0)
        self.assertEqual(fa, 0.48)
        self.assertEqual(pitch, 75.0)

        b_type2, w2, h2, fa2, pitch2 = SourceWeatherLouverAerodynamicFreeAreaShadowAuthority.parse_louver_annotation(
            "ACOUSTIC CHEVRON LOUVER 1200x1800"
        )
        self.assertEqual(b_type2, LouverBladeType.ACOUSTIC_CHEVRON)
        self.assertEqual(w2, 1200.0)
        self.assertEqual(h2, 1800.0)
        self.assertEqual(fa2, 0.35)

    def test_snap_point(self):
        ref_pts = [(0.0, 0.0), (100.0, 100.0)]
        snapped = SourceWeatherLouverAerodynamicFreeAreaShadowAuthority.snap_point((1.0, 1.0), ref_pts)
        self.assertEqual(snapped, (0.0, 0.0))

        unsnapped = SourceWeatherLouverAerodynamicFreeAreaShadowAuthority.snap_point((10.0, 10.0), ref_pts)
        self.assertEqual(unsnapped, (10.0, 10.0))

    def test_weather_louver_takeoff(self):
        # 1500x2000mm louver, 48% free area, 75mm pitch:
        # Gross = 3.0 m2
        # Free area = 1.44 m2
        # Frame = 2 * (1.5 + 2.0) = 7.0 m
        # Blades = ceil(1900 / 75) = 26 blades
        # Mesh = 3.0 m2
        l = WeatherLouverSpec(
            louver_id="WL-01",
            blade_type=LouverBladeType.TWO_STAGE_STORM,
            location=(0.0, 0.0),
            width_mm=1500.0,
            height_mm=2000.0,
            blade_pitch_mm=75.0,
            free_area_ratio=0.48,
            has_bird_mesh=True
        )
        res = SourceWeatherLouverAerodynamicFreeAreaShadowAuthority.evaluate_louvers([l])
        self.assertEqual(res.quantities.total_louver_count, 1)
        self.assertEqual(res.quantities.total_gross_aperture_area_m2, 3.0)
        self.assertEqual(res.quantities.total_aerodynamic_free_area_m2, 1.44)
        self.assertEqual(res.quantities.total_perimeter_frame_length_m, 7.0)
        self.assertEqual(res.quantities.total_estimated_blade_count, 26)
        self.assertEqual(res.quantities.total_bird_mesh_area_m2, 3.0)

    def test_invariants_and_safety(self):
        res = SourceWeatherLouverAerodynamicFreeAreaShadowAuthority.evaluate_louvers([])
        self.assertEqual(res.status, "CANDIDATE")
        self.assertFalse(res.commercial_projection_allowed)
        self.assertFalse(res.takeoff_eligible)


if __name__ == "__main__":
    unittest.main()
