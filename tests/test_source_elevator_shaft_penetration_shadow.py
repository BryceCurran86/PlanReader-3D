"""
tests/test_source_elevator_shaft_penetration_shadow.py

Unit tests for SourceElevatorShaftPenetrationShadowAuthority.
"""

import unittest
from pb_source_elevator_shaft_penetration_shadow import (
    SourceElevatorShaftPenetrationShadowAuthority,
    ElevatorType,
    ElevatorLandingDoorSpec,
    ElevatorShaftSpec,
    SNAP_TOLERANCE_PT
)


class TestSourceElevatorShaftPenetrationShadow(unittest.TestCase):

    def test_parse_shaft_annotation(self):
        el_type, w, d, pit, ovr = SourceElevatorShaftPenetrationShadowAuthority.parse_shaft_annotation(
            "MRL LIFT SHAFT 2100W x 2400D CLEAR, PIT 1500, OVERRUN 4200"
        )
        self.assertEqual(el_type, ElevatorType.MRL_TRACTION)
        self.assertEqual(w, 2100.0)
        self.assertEqual(d, 2400.0)
        self.assertEqual(pit, 1500.0)
        self.assertEqual(ovr, 4200.0)

        el_type2, w2, d2, pit2, ovr2 = SourceElevatorShaftPenetrationShadowAuthority.parse_shaft_annotation(
            "HYDRAULIC GOODS LIFT 2500x3000 PIT 1200 OVERRUN 3600"
        )
        self.assertEqual(el_type2, ElevatorType.HYDRAULIC)
        self.assertEqual(w2, 2500.0)
        self.assertEqual(d2, 3000.0)
        self.assertEqual(pit2, 1200.0)
        self.assertEqual(ovr2, 3600.0)

    def test_snap_point(self):
        ref_pts = [(100.0, 100.0), (300.0, 300.0)]
        snapped = SourceElevatorShaftPenetrationShadowAuthority.snap_point((101.0, 100.5), ref_pts)
        self.assertEqual(snapped, (100.0, 100.0))

        unsnapped = SourceElevatorShaftPenetrationShadowAuthority.snap_point((110.0, 110.0), ref_pts)
        self.assertEqual(unsnapped, (110.0, 110.0))

    def test_three_story_elevator_shaft_takeoff(self):
        # 3 storeys: 2 inter-story spans of 3.5m each = 7.0m
        # Pit = 1.5m, Overrun = 4.5m -> Total height = 13.0m
        # Clear hoistway: 2.0m x 2.4m -> Volume = 2.0 * 2.4 * 13.0 = 62.4 m3
        # Wall thk = 0.2m -> Centerline perim = 2 * (2.2 + 2.6) = 9.6m
        # Gross wall area = 9.6 * 13.0 = 124.8 m2
        # 3 landing doors: 1.0m x 2.1m = 2.1 m2 each -> Total 6.3 m2
        # Net wall area = 124.8 - 6.3 = 118.5 m2
        # Rails = 4 * 13.0 = 52.0 m
        doors = [
            ElevatorLandingDoorSpec(level_id="L0", width_mm=1000.0, height_mm=2100.0, sill_datum_m=0.0),
            ElevatorLandingDoorSpec(level_id="L1", width_mm=1000.0, height_mm=2100.0, sill_datum_m=3.5),
            ElevatorLandingDoorSpec(level_id="L2", width_mm=1000.0, height_mm=2100.0, sill_datum_m=7.0),
        ]
        shaft = ElevatorShaftSpec(
            shaft_id="LIFT-01",
            elevator_type=ElevatorType.PASSENGER_TRACTION,
            clear_width_mm=2000.0,
            clear_depth_mm=2400.0,
            wall_thickness_mm=200.0,
            lowest_level_id="L0",
            highest_level_id="L2",
            pit_depth_mm=1500.0,
            overrun_height_mm=4500.0,
            floor_to_floor_heights_m=[3.5, 3.5],
            landing_doors=doors
        )
        res = SourceElevatorShaftPenetrationShadowAuthority.evaluate_shafts([shaft])
        self.assertEqual(res.quantities.total_shaft_count, 1)
        self.assertEqual(res.quantities.total_shaft_vertical_height_m, 13.0)
        self.assertEqual(res.quantities.total_shaft_internal_volume_m3, 62.4)
        self.assertEqual(res.quantities.total_gross_enclosure_wall_area_m2, 124.8)
        self.assertEqual(res.quantities.total_landing_door_opening_area_m2, 6.3)
        self.assertEqual(res.quantities.total_net_enclosure_wall_area_m2, 118.5)
        self.assertEqual(res.quantities.total_guide_rail_length_m, 52.0)

    def test_omitted_landing_door_size_does_not_invent_typical_leaf(self):
        door = ElevatorLandingDoorSpec(level_id="L0")
        self.assertEqual(door.width_mm, 0.0)
        self.assertEqual(door.height_mm, 0.0)

    def test_invariants_and_safety(self):
        res = SourceElevatorShaftPenetrationShadowAuthority.evaluate_shafts([])
        self.assertEqual(res.status, "CANDIDATE")
        self.assertFalse(res.commercial_projection_allowed)
        self.assertFalse(res.takeoff_eligible)


if __name__ == "__main__":
    unittest.main()
