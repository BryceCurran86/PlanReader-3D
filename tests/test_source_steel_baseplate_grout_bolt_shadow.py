"""
tests/test_source_steel_baseplate_grout_bolt_shadow.py

Unit tests for SourceSteelBaseplateGroutBoltShadowAuthority.
"""

import unittest
from pb_source_steel_baseplate_grout_bolt_shadow import (
    SourceSteelBaseplateGroutBoltShadowAuthority,
    BoltGrade,
    SteelBaseplateSpec,
    SNAP_TOLERANCE_PT
)


class TestSourceSteelBaseplateGroutBoltShadow(unittest.TestCase):

    def test_parse_baseplate_annotation(self):
        pw, pl, pt, b_cnt, b_dia, b_emb, grt = SourceSteelBaseplateGroutBoltShadowAuthority.parse_baseplate_annotation(
            "BASEPLATE 400x400x25 THK W/ 4-M24 HD BOLTS (450 EMBED) & 50 GROUT BED"
        )
        self.assertEqual(pw, 400.0)
        self.assertEqual(pl, 400.0)
        self.assertEqual(pt, 25.0)
        self.assertEqual(b_cnt, 4)
        self.assertEqual(b_dia, 24.0)
        self.assertEqual(b_emb, 450.0)
        self.assertEqual(grt, 50.0)

        pw2, pl2, pt2, b_cnt2, b_dia2, b_emb2, grt2 = SourceSteelBaseplateGroutBoltShadowAuthority.parse_baseplate_annotation(
            "BP 300x300x16 4-M20 300 EMBED 25 GROUT"
        )
        self.assertEqual(pw2, 300.0)
        self.assertEqual(pl2, 300.0)
        self.assertEqual(pt2, 16.0)
        self.assertEqual(b_cnt2, 4)
        self.assertEqual(b_dia2, 20.0)
        self.assertEqual(b_emb2, 300.0)
        self.assertEqual(grt2, 25.0)

        pw3, pl3, pt3, c3, d3, e3, _g = SourceSteelBaseplateGroutBoltShadowAuthority.parse_baseplate_annotation(
            "BASEPLATE"
        )
        self.assertEqual(pw3, 0.0)
        self.assertEqual(pl3, 0.0)
        self.assertEqual(pt3, 0.0)
        self.assertEqual(c3, 0)
        self.assertEqual(d3, 0.0)
        self.assertEqual(e3, 0.0)

        omitted = SteelBaseplateSpec(
            connection_id="BP-UNKNOWN",
            column_id="COL-UNKNOWN",
            location=(0.0, 0.0),
        )
        self.assertEqual(omitted.plate_width_mm, 0.0)
        self.assertEqual(omitted.plate_length_mm, 0.0)
        self.assertEqual(omitted.plate_thickness_mm, 0.0)
        self.assertEqual(omitted.bolt_count, 0)
        self.assertEqual(omitted.bolt_diameter_mm, 0.0)
        self.assertEqual(omitted.bolt_embedment_depth_mm, 0.0)

    def test_snap_point(self):
        ref_pts = [(50.0, 50.0), (100.0, 100.0)]
        snapped = SourceSteelBaseplateGroutBoltShadowAuthority.snap_point((51.0, 50.5), ref_pts)
        self.assertEqual(snapped, (50.0, 50.0))

        unsnapped = SourceSteelBaseplateGroutBoltShadowAuthority.snap_point((60.0, 60.0), ref_pts)
        self.assertEqual(unsnapped, (60.0, 60.0))

    def test_baseplate_assembly_takeoff(self):
        # 400x400x25mm baseplate:
        # Vol = 0.4 * 0.4 * 0.025 = 0.004 m3 -> Mass = 0.004 * 7850 = 31.4 kg
        # 4 bolts: 450 embed + 25 plate + 50 grout + 75 extension = 600mm -> 0.6m * 4 = 2.4 m
        # Grout: 0.5 x 0.5 = 0.25 m2 -> Vol = 0.25 * 0.05 = 0.0125 m3
        conn = SteelBaseplateSpec(
            connection_id="BP-01",
            column_id="COL-1",
            location=(10.0, 10.0),
            plate_width_mm=400.0,
            plate_length_mm=400.0,
            plate_thickness_mm=25.0,
            bolt_count=4,
            bolt_diameter_mm=24.0,
            bolt_embedment_depth_mm=450.0,
            grout_thickness_mm=50.0
        )
        res = SourceSteelBaseplateGroutBoltShadowAuthority.evaluate_connections([conn])
        self.assertEqual(res.quantities.total_connection_count, 1)
        self.assertEqual(res.quantities.total_baseplate_mass_kg, 31.4)
        self.assertEqual(res.quantities.total_anchor_bolt_count, 4)
        self.assertEqual(res.quantities.total_anchor_bolt_rod_length_m, 2.4)
        self.assertEqual(res.quantities.total_grout_footprint_area_m2, 0.25)
        self.assertEqual(res.quantities.total_grout_volume_m3, 0.0125)

    def test_invariants_and_safety(self):
        res = SourceSteelBaseplateGroutBoltShadowAuthority.evaluate_connections([])
        self.assertEqual(res.status, "CANDIDATE")
        self.assertFalse(res.commercial_projection_allowed)
        self.assertFalse(res.takeoff_eligible)


if __name__ == "__main__":
    unittest.main()
