"""
tests/test_source_balustrade_handrail_guardrail_shadow.py

Unit tests for SourceBalustradeHandrailGuardrailShadowAuthority.
"""

import unittest
from pb_source_balustrade_handrail_guardrail_shadow import (
    SourceBalustradeHandrailGuardrailShadowAuthority,
    BarrierLocationKind,
    BarrierInfillType,
    BalustradeRunSpec,
    SNAP_TOLERANCE_PT
)


class TestSourceBalustradeHandrailGuardrailShadow(unittest.TestCase):

    def test_parse_balustrade_annotation(self):
        loc, infill, h, hr = SourceBalustradeHandrailGuardrailShadowAuthority.parse_balustrade_annotation(
            "FRAMELESS GLASS BALUSTRADE 1100 HIGH W/ CONTINUOUS HANDRAIL"
        )
        self.assertEqual(loc, BarrierLocationKind.BALCONY_TERRACE)
        self.assertEqual(infill, BarrierInfillType.FRAMELESS_GLASS)
        self.assertEqual(h, 1100.0)
        self.assertTrue(hr)

        loc2, infill2, h2, hr2 = SourceBalustradeHandrailGuardrailShadowAuthority.parse_balustrade_annotation(
            "STAIR BALUSTRADE 1000H VERTICAL PICKETS"
        )
        self.assertEqual(loc2, BarrierLocationKind.STAIR_FLIGHT)
        self.assertEqual(infill2, BarrierInfillType.VERTICAL_BALUSTERS)
        self.assertEqual(h2, 1000.0)
        self.assertFalse(hr2)

        loc3, _infill3, h3, _hr3 = SourceBalustradeHandrailGuardrailShadowAuthority.parse_balustrade_annotation(
            "BALUSTRADE"
        )
        self.assertEqual(h3, 0.0)

    def test_snap_point(self):
        ref_pts = [(0.0, 0.0), (100.0, 100.0)]
        snapped = SourceBalustradeHandrailGuardrailShadowAuthority.snap_point((1.0, 1.0), ref_pts)
        self.assertEqual(snapped, (0.0, 0.0))

        unsnapped = SourceBalustradeHandrailGuardrailShadowAuthority.snap_point((10.0, 10.0), ref_pts)
        self.assertEqual(unsnapped, (10.0, 10.0))

    def test_balcony_glass_balustrade_takeoff(self):
        # 10m long, 1100mm high, 1000mm post spacing
        # Area = 11.0 m2, Handrail = 10.0 m, Posts = 11
        r = BalustradeRunSpec(
            run_id="BAL-01",
            location_kind=BarrierLocationKind.BALCONY_TERRACE,
            infill_type=BarrierInfillType.FRAMELESS_GLASS,
            centerline_points=[(0.0, 0.0), (10.0, 0.0)],
            height_mm=1100.0,
            post_spacing_mm=1000.0,
            has_continuous_handrail=True
        )
        res = SourceBalustradeHandrailGuardrailShadowAuthority.evaluate_balustrades([r])
        self.assertEqual(res.quantities.total_balustrade_count, 1)
        self.assertEqual(res.quantities.total_linear_run_m, 10.0)
        self.assertEqual(res.quantities.total_barrier_face_area_m2, 11.0)
        self.assertEqual(res.quantities.total_handrail_length_m, 10.0)
        self.assertEqual(res.quantities.total_post_count, 11)
        self.assertEqual(res.quantities.non_compliant_height_count, 0)

    def test_stair_balustrade_with_extensions(self):
        # 4m long stair balustrade, 1000mm high, 0.3m extensions each end -> handrail = 4.6m
        r = BalustradeRunSpec(
            run_id="STAIR-BAL",
            location_kind=BarrierLocationKind.STAIR_FLIGHT,
            infill_type=BarrierInfillType.VERTICAL_BALUSTERS,
            centerline_points=[(0.0, 0.0), (4.0, 0.0)],
            height_mm=1000.0,
            has_continuous_handrail=True,
            handrail_extension_m=0.30
        )
        res = SourceBalustradeHandrailGuardrailShadowAuthority.evaluate_balustrades([r])
        self.assertEqual(res.quantities.total_handrail_length_m, 4.6)
        self.assertEqual(res.quantities.non_compliant_height_count, 0)

    def test_non_compliant_height_flag(self):
        # 900mm on balcony is non-compliant (requires min 1100mm)
        r = BalustradeRunSpec(
            run_id="BAL-LOW",
            location_kind=BarrierLocationKind.BALCONY_TERRACE,
            infill_type=BarrierInfillType.HORIZONTAL_WIRE_CABLE,
            centerline_points=[(0.0, 0.0), (5.0, 0.0)],
            height_mm=900.0
        )
        res = SourceBalustradeHandrailGuardrailShadowAuthority.evaluate_balustrades([r])
        self.assertEqual(res.quantities.non_compliant_height_count, 1)

    def test_invariants_and_safety(self):
        res = SourceBalustradeHandrailGuardrailShadowAuthority.evaluate_balustrades([])
        self.assertEqual(res.status, "CANDIDATE")
        self.assertFalse(res.commercial_projection_allowed)
        self.assertFalse(res.takeoff_eligible)

        omitted = BalustradeRunSpec(
            run_id="BAL-OMIT",
            location_kind=BarrierLocationKind.BALCONY_TERRACE,
            infill_type=BarrierInfillType.FRAMELESS_GLASS,
            centerline_points=[(0.0, 0.0), (10.0, 0.0)],
        )
        self.assertEqual(omitted.height_mm, 0.0)
        self.assertEqual(omitted.post_spacing_mm, 0.0)
        self.assertFalse(omitted.has_continuous_handrail)
        self.assertEqual(omitted.handrail_extension_m, 0.0)
        omitted_res = SourceBalustradeHandrailGuardrailShadowAuthority.evaluate_balustrades([omitted])
        self.assertEqual(omitted_res.quantities.total_barrier_face_area_m2, 0.0)
        self.assertEqual(omitted_res.quantities.non_compliant_height_count, 0)
        self.assertEqual(omitted_res.quantities.total_post_count, 0)
        self.assertEqual(omitted_res.quantities.total_handrail_length_m, 0.0)


if __name__ == "__main__":
    unittest.main()
