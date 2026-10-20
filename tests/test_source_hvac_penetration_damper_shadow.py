"""
tests/test_source_hvac_penetration_damper_shadow.py

Unit tests for SourceHVACPenetrationDamperShadowAuthority.
"""

import unittest
from pb_source_hvac_penetration_damper_shadow import (
    SourceHVACPenetrationDamperShadowAuthority,
    PenetratedElementKind,
    DuctProfileShape,
    FireDamperSpec,
    SNAP_TOLERANCE_PT
)


class TestSourceHVACPenetrationDamperShadow(unittest.TestCase):

    def test_parse_damper_annotation(self):
        shape, w, h, frl, mot = SourceHVACPenetrationDamperShadowAuthority.parse_damper_annotation(
            "FIRE DAMPER 600W x 400H FRL -/120/120 MOTORIZED"
        )
        self.assertEqual(shape, DuctProfileShape.RECTANGULAR)
        self.assertEqual(w, 600.0)
        self.assertEqual(h, 400.0)
        self.assertEqual(frl, "-/120/120")
        self.assertTrue(mot)

        shape2, w2, h2, frl2, mot2 = SourceHVACPenetrationDamperShadowAuthority.parse_damper_annotation(
            "CIRCULAR FD 300 DIA FRL -/60/60"
        )
        self.assertEqual(shape2, DuctProfileShape.CIRCULAR)
        self.assertEqual(w2, 300.0)
        self.assertEqual(frl2, "-/60/60")
        self.assertFalse(mot2)

        shape3, w3, h3, _frl3, _mot3 = SourceHVACPenetrationDamperShadowAuthority.parse_damper_annotation(
            "FIRE DAMPER"
        )
        self.assertEqual(w3, 0.0)
        self.assertEqual(h3, 0.0)

    def test_snap_point(self):
        ref_pts = [(0.0, 0.0), (100.0, 100.0)]
        snapped = SourceHVACPenetrationDamperShadowAuthority.snap_point((1.0, 1.0), ref_pts)
        self.assertEqual(snapped, (0.0, 0.0))

        unsnapped = SourceHVACPenetrationDamperShadowAuthority.snap_point((10.0, 10.0), ref_pts)
        self.assertEqual(unsnapped, (10.0, 10.0))

    def test_rectangular_damper_takeoff(self):
        # 600x400mm duct through 150mm wall, 25mm annular gap
        # Duct airflow = 0.24 m2
        # Opening = 0.65 * 0.45 = 0.2925 m2 -> round 0.293
        # Flange angles = 4 * (0.6 + 0.4) = 4.0 m
        # Firestop vol = (0.2925 - 0.24) * 0.15 = 0.007875 -> 0.0079 m3
        d = FireDamperSpec(
            damper_id="FD-01",
            penetrated_element=PenetratedElementKind.WALL_PARTITION,
            duct_shape=DuctProfileShape.RECTANGULAR,
            location=(5.0, 5.0),
            width_mm=600.0,
            height_mm=400.0,
            element_thickness_mm=150.0,
            annular_gap_mm=25.0
        )
        res = SourceHVACPenetrationDamperShadowAuthority.evaluate_dampers([d])
        self.assertEqual(res.quantities.total_damper_count, 1)
        self.assertEqual(res.quantities.total_duct_airflow_area_m2, 0.24)
        self.assertEqual(res.quantities.total_rough_opening_area_m2, 0.293)
        self.assertEqual(res.quantities.total_retaining_flange_length_m, 4.0)
        self.assertEqual(res.quantities.total_firestop_mortar_volume_m3, 0.0079)

    def test_invariants_and_safety(self):
        res = SourceHVACPenetrationDamperShadowAuthority.evaluate_dampers([])
        self.assertEqual(res.status, "CANDIDATE")
        self.assertFalse(res.commercial_projection_allowed)
        self.assertFalse(res.takeoff_eligible)

        omitted = FireDamperSpec(
            damper_id="FD-OMIT",
            penetrated_element=PenetratedElementKind.WALL_PARTITION,
            duct_shape=DuctProfileShape.RECTANGULAR,
            location=(5.0, 5.0),
        )
        self.assertEqual(omitted.width_mm, 0.0)
        self.assertEqual(omitted.height_mm, 0.0)
        omitted_res = SourceHVACPenetrationDamperShadowAuthority.evaluate_dampers([omitted])
        self.assertEqual(omitted_res.quantities.total_duct_airflow_area_m2, 0.0)
        self.assertEqual(omitted_res.quantities.total_retaining_flange_length_m, 0.0)


if __name__ == "__main__":
    unittest.main()
