"""
tests/test_source_timber_roof_truss_pitch_shadow.py

Unit tests for SourceTimberRoofTrussPitchShadowAuthority.
"""

import unittest
from pb_source_timber_roof_truss_pitch_shadow import (
    SourceTimberRoofTrussPitchShadowAuthority,
    TrussProfileType,
    TimberRoofTrussSpec,
    SNAP_TOLERANCE_PT
)


class TestSourceTimberRoofTrussPitchShadow(unittest.TestCase):

    def test_parse_truss_annotation(self):
        t_type, pitch, spacing, oh = SourceTimberRoofTrussPitchShadowAuthority.parse_truss_annotation(
            "FINK TRUSS 22.5 DEG PITCH @ 900 CTS 600 O/HANG"
        )
        self.assertEqual(t_type, TrussProfileType.FINK)
        self.assertEqual(pitch, 22.5)
        self.assertEqual(spacing, 900.0)
        self.assertEqual(oh, 600.0)

        t_type2, pitch2, spacing2, oh2 = SourceTimberRoofTrussPitchShadowAuthority.parse_truss_annotation(
            "SKILLION MONO TRUSS 15 DEG @ 600 CENTRES 450 OVERHANG"
        )
        self.assertEqual(t_type2, TrussProfileType.MONO_PITCH)
        self.assertEqual(pitch2, 15.0)
        self.assertEqual(spacing2, 600.0)
        self.assertEqual(oh2, 450.0)

        _t3, pitch3, _sp3, oh3 = SourceTimberRoofTrussPitchShadowAuthority.parse_truss_annotation(
            "TRUSS"
        )
        self.assertEqual(pitch3, 0.0)
        self.assertEqual(oh3, 0.0)
        omitted = TimberRoofTrussSpec(
            truss_id="T-UNKNOWN",
            truss_type=TrussProfileType.FINK,
            layout_line=[(0.0, 0.0), (1.0, 0.0)],
            span_mm=1000.0,
        )
        self.assertEqual(omitted.pitch_deg, 0.0)
        self.assertEqual(omitted.eaves_overhang_mm, 0.0)

    def test_snap_point(self):
        ref_pts = [(0.0, 0.0), (100.0, 100.0)]
        snapped = SourceTimberRoofTrussPitchShadowAuthority.snap_point((1.0, 1.0), ref_pts)
        self.assertEqual(snapped, (0.0, 0.0))

        unsnapped = SourceTimberRoofTrussPitchShadowAuthority.snap_point((10.0, 10.0), ref_pts)
        self.assertEqual(unsnapped, (10.0, 10.0))

    def test_dual_pitch_fink_truss_takeoff(self):
        # 10m span, 22.5 deg pitch, 600mm overhang, 900mm spacing, 10 trusses
        t = TimberRoofTrussSpec(
            truss_id="T-SET-01",
            truss_type=TrussProfileType.FINK,
            layout_line=[(0.0, 0.0), (10.0, 0.0)],
            span_mm=10000.0,
            pitch_deg=22.5,
            eaves_overhang_mm=600.0,
            spacing_centers_mm=900.0,
            count=10
        )
        res = SourceTimberRoofTrussPitchShadowAuthority.evaluate_roof_trusses([t])
        self.assertEqual(res.quantities.total_truss_count, 10)
        self.assertEqual(res.quantities.total_bottom_chord_length_m, 112.0)
        self.assertAlmostEqual(res.quantities.total_top_chord_sloped_length_m, 121.226, places=1)
        self.assertGreater(res.quantities.total_timber_linear_length_m, 200.0)
        self.assertGreater(res.quantities.total_roof_sloped_coverage_area_m2, 100.0)

    def test_invariants_and_safety(self):
        res = SourceTimberRoofTrussPitchShadowAuthority.evaluate_roof_trusses([])
        self.assertEqual(res.status, "CANDIDATE")
        self.assertFalse(res.commercial_projection_allowed)
        self.assertFalse(res.takeoff_eligible)


if __name__ == "__main__":
    unittest.main()
