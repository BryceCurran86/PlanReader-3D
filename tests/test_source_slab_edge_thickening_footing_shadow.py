"""
tests/test_source_slab_edge_thickening_footing_shadow.py

Unit tests for SourceSlabEdgeThickeningFootingShadowAuthority.
"""

import unittest
from pb_source_slab_edge_thickening_footing_shadow import (
    SourceSlabEdgeThickeningFootingShadowAuthority,
    FootingBeamType,
    FootingBeamSpec,
    BrickRebateSpec,
    SNAP_TOLERANCE_PT
)


class TestSourceSlabEdgeThickeningFootingShadow(unittest.TestCase):

    def test_parse_beam_annotation(self):
        # Edge beam with rebate
        b_type, w, d, reb = SourceSlabEdgeThickeningFootingShadowAuthority.parse_beam_annotation(
            "EDGE BEAM 300W x 450D W/ 110x50 REBATE"
        )
        self.assertEqual(b_type, FootingBeamType.EDGE_BEAM)
        self.assertEqual(w, 300.0)
        self.assertEqual(d, 450.0)
        self.assertIsNotNone(reb)
        self.assertEqual(reb.width_mm, 110.0)
        self.assertEqual(reb.depth_mm, 50.0)

        # Strip footing
        b_type, w, d, reb = SourceSlabEdgeThickeningFootingShadowAuthority.parse_beam_annotation(
            "STRIP FOOTING 450W x 600D"
        )
        self.assertEqual(b_type, FootingBeamType.STRIP_FOOTING)
        self.assertEqual(w, 450.0)
        self.assertEqual(d, 600.0)
        self.assertIsNone(reb)

        # Internal rib
        b_type, w, d, reb = SourceSlabEdgeThickeningFootingShadowAuthority.parse_beam_annotation(
            "INTERNAL RIB 300W x 300D"
        )
        self.assertEqual(b_type, FootingBeamType.INTERNAL_STIFFENER)
        self.assertEqual(w, 300.0)
        self.assertEqual(d, 300.0)

    def test_snap_point(self):
        ref_pts = [(100.0, 100.0), (200.0, 200.0)]
        # Within tolerance (2.0 pt dist)
        snapped = SourceSlabEdgeThickeningFootingShadowAuthority.snap_point((101.5, 100.0), ref_pts)
        self.assertEqual(snapped, (100.0, 100.0))

        # Outside tolerance (3.0 pt dist)
        unsnapped = SourceSlabEdgeThickeningFootingShadowAuthority.snap_point((103.0, 100.0), ref_pts)
        self.assertEqual(unsnapped, (103.0, 100.0))

    def test_edge_beam_rebate_deduction(self):
        # 10m long edge beam: 300mm wide x 450mm deep with 110x50mm rebate
        # Excavation = 10 * 0.3 * 0.45 = 1.35 m3
        # Rebate cutout = 10 * 0.11 * 0.05 = 0.055 m3
        # Concrete = 1.35 - 0.055 = 1.295 m3
        # Edge formwork = 10 * 0.45 = 4.5 m2
        beam = FootingBeamSpec(
            beam_id="EB-1",
            beam_type=FootingBeamType.EDGE_BEAM,
            centerline_points=[(0.0, 0.0), (10.0, 0.0)],
            width_mm=300.0,
            depth_mm=450.0,
            rebate=BrickRebateSpec(width_mm=110.0, depth_mm=50.0)
        )
        result = SourceSlabEdgeThickeningFootingShadowAuthority.evaluate_footings([beam], drawing_scale=1.0)
        self.assertEqual(result.quantities.total_centerline_length_m, 10.0)
        self.assertEqual(result.quantities.total_excavation_volume_m3, 1.35)
        self.assertEqual(result.quantities.total_concrete_volume_m3, 1.295)
        self.assertEqual(result.quantities.total_edge_formwork_area_m2, 4.5)
        self.assertEqual(result.quantities.rebate_length_m, 10.0)

    def test_combined_foundation_system(self):
        # Edge beam 20m + Internal rib 10m
        b1 = FootingBeamSpec(
            beam_id="EB-PERIMETER",
            beam_type=FootingBeamType.EDGE_BEAM,
            centerline_points=[(0.0, 0.0), (20.0, 0.0)],
            width_mm=300.0,
            depth_mm=400.0
        )
        b2 = FootingBeamSpec(
            beam_id="RIB-1",
            beam_type=FootingBeamType.INTERNAL_STIFFENER,
            centerline_points=[(10.0, 0.0), (10.0, 10.0)],
            width_mm=300.0,
            depth_mm=300.0
        )
        result = SourceSlabEdgeThickeningFootingShadowAuthority.evaluate_footings([b1, b2], drawing_scale=1.0)
        self.assertEqual(result.quantities.total_centerline_length_m, 30.0)
        # Excavation: b1 = 20 * 0.3 * 0.4 = 2.4 m3; b2 = 10 * 0.3 * 0.3 = 0.9 m3 -> 3.3 m3
        self.assertEqual(result.quantities.total_excavation_volume_m3, 3.3)
        # Edge formwork only from EB: 20 * 0.4 = 8.0 m2
        self.assertEqual(result.quantities.total_edge_formwork_area_m2, 8.0)

    def test_invariants_and_safety(self):
        result = SourceSlabEdgeThickeningFootingShadowAuthority.evaluate_footings([])
        self.assertEqual(result.status, "CANDIDATE")
        self.assertFalse(result.commercial_projection_allowed)
        self.assertFalse(result.takeoff_eligible)


if __name__ == "__main__":
    unittest.main()
