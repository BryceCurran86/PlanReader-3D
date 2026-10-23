"""
tests/test_source_precast_panel_joint_sealant_shadow.py

Unit tests for SourcePrecastPanelJointSealantShadowAuthority.
"""

import unittest
from pb_source_precast_panel_joint_sealant_shadow import (
    SourcePrecastPanelJointSealantShadowAuthority,
    PrecastJointType,
    JointSealantConfig,
    PrecastPanelSpec,
    PrecastJointSpec,
    SNAP_TOLERANCE_PT
)


class TestSourcePrecastPanelJointSealantShadow(unittest.TestCase):

    def test_parse_joint_annotation(self):
        j_type, w, d, rod, cfg = SourcePrecastPanelJointSealantShadowAuthority.parse_joint_annotation(
            "20mm VERTICAL CONTROL JOINT W/ 25 DIA PE ROD & DOUBLE POLYURETHANE SEALANT"
        )
        self.assertEqual(j_type, PrecastJointType.VERTICAL_BUTT_JOINT)
        self.assertEqual(w, 20.0)
        self.assertEqual(d, 0.0)
        self.assertEqual(rod, 25.0)
        self.assertEqual(cfg, JointSealantConfig.DOUBLE_BEAD)

        j_type2, w2, d2, rod2, cfg2 = SourcePrecastPanelJointSealantShadowAuthority.parse_joint_annotation(
            "HORIZONTAL SHIPLAP JOINT 25mm WIDE 12mm DEPTH SINGLE SEAL"
        )
        self.assertEqual(j_type2, PrecastJointType.HORIZONTAL_SHIPLAP_JOINT)
        self.assertEqual(w2, 25.0)
        self.assertEqual(d2, 12.0)
        self.assertEqual(cfg2, JointSealantConfig.SINGLE_BEAD)

        _jt3, w3, d3, rod3, cfg3 = SourcePrecastPanelJointSealantShadowAuthority.parse_joint_annotation(
            "JOINT"
        )
        self.assertEqual(w3, 0.0)
        self.assertEqual(d3, 0.0)
        self.assertEqual(rod3, 0.0)
        self.assertEqual(cfg3, JointSealantConfig.UNKNOWN)

    def test_snap_point(self):
        ref_pts = [(0.0, 0.0), (100.0, 100.0)]
        snapped = SourcePrecastPanelJointSealantShadowAuthority.snap_point((1.0, 1.0), ref_pts)
        self.assertEqual(snapped, (0.0, 0.0))

        unsnapped = SourcePrecastPanelJointSealantShadowAuthority.snap_point((10.0, 10.0), ref_pts)
        self.assertEqual(unsnapped, (10.0, 10.0))

    def test_precast_facade_takeoff(self):
        # 2 panels: 3.0m x 6.0m = 18 m2 each, 175mm thick
        # Total face area = 36.0 m2; conc vol = 36.0 * 0.175 = 6.3 m3
        p1 = PrecastPanelSpec(
            panel_id="PANEL-01",
            boundary_polygon=[(0.0, 0.0), (3.0, 0.0), (3.0, 6.0), (0.0, 6.0)],
            thickness_mm=175.0
        )
        p2 = PrecastPanelSpec(
            panel_id="PANEL-02",
            boundary_polygon=[(3.0, 0.0), (6.0, 0.0), (6.0, 6.0), (3.0, 6.0)],
            thickness_mm=175.0
        )

        # 1 joint at x=3.0, length 6.0m, 20mm wide x 10mm deep, double bead
        # Backing rod = 6.0 * 2 = 12.0m
        # Sealant vol = 6.0 * (0.02 * 0.01 * 2) * 1000 = 2.4 Liters
        j1 = PrecastJointSpec(
            joint_id="CJ-01",
            joint_type=PrecastJointType.VERTICAL_BUTT_JOINT,
            centerline_points=[(3.0, 0.0), (3.0, 6.0)],
            joint_width_mm=20.0,
            sealant_depth_mm=10.0,
            backing_rod_dia_mm=25.0,
            sealant_config=JointSealantConfig.DOUBLE_BEAD
        )

        res = SourcePrecastPanelJointSealantShadowAuthority.evaluate_precast_envelope([p1, p2], [j1])
        self.assertEqual(res.quantities.total_panel_count, 2)
        self.assertEqual(res.quantities.total_panel_face_area_m2, 36.0)
        self.assertEqual(res.quantities.total_panel_concrete_volume_m3, 6.3)
        self.assertEqual(res.quantities.total_joint_length_m, 6.0)
        self.assertEqual(res.quantities.total_backing_rod_length_m, 12.0)
        self.assertEqual(res.quantities.total_sealant_volume_liters, 2.4)

    def test_invariants_and_safety(self):
        res = SourcePrecastPanelJointSealantShadowAuthority.evaluate_precast_envelope([], [])
        self.assertEqual(res.status, "CANDIDATE")
        self.assertFalse(res.commercial_projection_allowed)
        self.assertFalse(res.takeoff_eligible)

        omitted_panel = PrecastPanelSpec(
            panel_id="PANEL-OMIT",
            boundary_polygon=[(0.0, 0.0), (3.0, 0.0), (3.0, 6.0), (0.0, 6.0)],
        )
        omitted_joint = PrecastJointSpec(
            joint_id="CJ-OMIT",
            joint_type=PrecastJointType.VERTICAL_BUTT_JOINT,
            centerline_points=[(3.0, 0.0), (3.0, 6.0)],
        )
        self.assertEqual(omitted_panel.thickness_mm, 0.0)
        self.assertEqual(omitted_joint.joint_width_mm, 0.0)
        self.assertEqual(omitted_joint.sealant_depth_mm, 0.0)
        self.assertEqual(omitted_joint.backing_rod_dia_mm, 0.0)
        self.assertEqual(omitted_joint.sealant_config, JointSealantConfig.UNKNOWN)
        omitted = SourcePrecastPanelJointSealantShadowAuthority.evaluate_precast_envelope(
            [omitted_panel], [omitted_joint]
        )
        self.assertEqual(omitted.quantities.total_panel_concrete_volume_m3, 0.0)
        self.assertEqual(omitted.quantities.total_backing_rod_length_m, 0.0)
        self.assertEqual(omitted.quantities.total_sealant_volume_liters, 0.0)


if __name__ == "__main__":
    unittest.main()
