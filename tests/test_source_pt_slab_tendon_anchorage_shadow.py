"""
tests/test_source_pt_slab_tendon_anchorage_shadow.py

Unit tests for SourcePTSlabTendonAnchorageShadowAuthority.
"""

import unittest
from pb_source_pt_slab_tendon_anchorage_shadow import (
    SourcePTSlabTendonAnchorageShadowAuthority,
    TendonArrangementType,
    AnchorageType,
    AnchoragePocketSpec,
    TendonRunSpec,
    SNAP_TOLERANCE_PT
)


class TestSourcePTSlabTendonAnchorageShadow(unittest.TestCase):

    def test_parse_tendon_annotation(self):
        arr, cnt, dia = SourcePTSlabTendonAnchorageShadowAuthority.parse_tendon_annotation(
            "BANDED TENDON 5S12.7"
        )
        self.assertEqual(arr, TendonArrangementType.BANDED)
        self.assertEqual(cnt, 5)
        self.assertEqual(dia, 12.7)

        arr2, cnt2, dia2 = SourcePTSlabTendonAnchorageShadowAuthority.parse_tendon_annotation(
            "DISTRIBUTED TENDON 4S15.2 @ 1500 CTS"
        )
        self.assertEqual(arr2, TendonArrangementType.DISTRIBUTED)
        self.assertEqual(cnt2, 4)
        self.assertEqual(dia2, 15.2)

    def test_snap_point(self):
        ref_pts = [(0.0, 0.0), (100.0, 100.0)]
        snapped = SourcePTSlabTendonAnchorageShadowAuthority.snap_point((1.0, 1.0), ref_pts)
        self.assertEqual(snapped, (0.0, 0.0))

        unsnapped = SourcePTSlabTendonAnchorageShadowAuthority.snap_point((10.0, 10.0), ref_pts)
        self.assertEqual(unsnapped, (10.0, 10.0))

    def test_pt_slab_takeoff(self):
        # 20m long tendon, 5 strands of 12.7mm:
        # Path = 20.0 m
        # Strand length = 100.0 m
        # Steel mass = 100 * 0.785 = 78.5 kg
        # 1 Live end: 150x100x75mm = 0.001125 m3
        # 1 Dead end
        live_p = AnchoragePocketSpec(
            pocket_id="LP-01",
            anchorage_type=AnchorageType.LIVE_END_STRESSING,
            location=(0.0, 0.0),
            width_mm=150.0,
            height_mm=100.0,
            depth_mm=75.0
        )
        dead_p = AnchoragePocketSpec(
            pocket_id="DP-01",
            anchorage_type=AnchorageType.DEAD_END_BLIND,
            location=(20.0, 0.0)
        )
        t = TendonRunSpec(
            tendon_id="T-01",
            arrangement_type=TendonArrangementType.BANDED,
            centerline_points=[(0.0, 0.0), (20.0, 0.0)],
            strand_count=5,
            strand_diameter_mm=12.7,
            anchor_start=live_p,
            anchor_end=dead_p
        )
        res = SourcePTSlabTendonAnchorageShadowAuthority.evaluate_pt_system([t], drawing_scale=1.0)
        self.assertEqual(res.quantities.total_tendon_run_count, 1)
        self.assertEqual(res.quantities.total_tendon_path_length_m, 20.0)
        self.assertEqual(res.quantities.total_strand_length_m, 100.0)
        self.assertEqual(res.quantities.total_prestressing_steel_mass_kg, 78.5)
        self.assertEqual(res.quantities.total_live_anchorage_count, 1)
        self.assertEqual(res.quantities.total_dead_anchorage_count, 1)
        self.assertAlmostEqual(res.quantities.total_pocket_grout_volume_m3, 0.0011, places=4)

    def test_invariants_and_safety(self):
        res = SourcePTSlabTendonAnchorageShadowAuthority.evaluate_pt_system([])
        self.assertEqual(res.status, "CANDIDATE")
        self.assertFalse(res.commercial_projection_allowed)
        self.assertFalse(res.takeoff_eligible)


if __name__ == "__main__":
    unittest.main()
