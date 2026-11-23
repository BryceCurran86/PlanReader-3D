"""Source-neutral registration safety: invalid viewport orientation witnesses abstain."""
import math
import unittest

from pb_source_cross_view_floor_correspondence_shadow import rank_registrations


class InvalidOrientationWitnessTests(unittest.TestCase):
    def test_malformed_orientation_does_not_suppress_valid_hypothesis(self):
        src = {"H": {0.0: [(0.0, 100.0)]}, "V": {0.0: [(0.0, 100.0)]}}
        for invalid in ((math.nan, 0, 0, 1), (math.inf, 0, 0, 1),
                        (1e308, 0, 0, 1e308), (1, 0, 0), ("bad", 0, 0, 1)):
            with self.subTest(invalid=invalid):
                rows = rank_registrations(src, src,
                    orientations={"invalid": invalid, "identity": (1, 0, 0, 1)},
                    identity_scales=(1.0, 2.0), topn=2)
                self.assertTrue(any(row["orientation"] == "identity" for row in rows))
                self.assertFalse(any(row["orientation"] == "invalid" for row in rows))

    def test_boolean_orientation_coefficients_cannot_authenticate(self):
        # A truth value must not be coerced into a rotation/scale witness.
        src = {"H": {0.0: [(0.0, 100.0)]}, "V": {0.0: [(0.0, 100.0)]}}
        for bad in ((True, 0, 0, 1), (1, False, 0, 1),
                    (1, 0, True, 1), (1, 0, 0, False)):
            with self.subTest(matrix=bad):
                rows = rank_registrations(
                    src, src,
                    orientations={"bad": bad, "good": (1, 0, 0, 1)},
                    identity_scales=(1.0,), topn=2)
                self.assertFalse(any(row["orientation"] == "bad" for row in rows))
                self.assertTrue(any(row["orientation"] == "good" for row in rows))

    def test_boolean_scale_cannot_authenticate_viewport(self):
        # bool is a subclass of int, but is not a measured viewport scale.
        src = {"H": {0.0: [(0.0, 100.0)]}, "V": {0.0: [(0.0, 100.0)]}}
        invalid = rank_registrations(src, src,
            orientations={"identity": (1, 0, 0, 1)},
            identity_scales=(True, False), topn=2)
        self.assertEqual(invalid, [])
        valid = rank_registrations(src, src,
            orientations={"identity": (1, 0, 0, 1)},
            identity_scales=(1.0,), topn=2)
        self.assertTrue(any(row["orientation"] == "identity" for row in valid))

    def test_oversized_integer_scale_abstains_without_suppressing_valid_candidate(self):
        # An unhandled huge int must not raise OverflowError in float conversion
        # or math.isfinite(), and must not suppress the subsequent valid scale.
        src = {"H": {0.0: [(0.0, 100.0)]}, "V": {0.0: [(0.0, 100.0)]}}
        oversized = 10 ** 1000
        rows = rank_registrations(
            src, src,
            orientations={"identity": (1, 0, 0, 1)},
            identity_scales=(oversized, 1.0),
            topn=2,
        )
        self.assertTrue(any(row["orientation"] == "identity" and row["scale"] == 1.0 for row in rows))
        self.assertFalse(any(row["scale"] == oversized for row in rows))

    def test_finite_matrix_overflowing_source_coordinates_abstains(self):
        # All metadata numbers are finite, but applying scale to source
        # geometry overflows. Keep the independent valid candidate alive.
        src = {"H": {0.0: [(0.0, 1e308)]}, "V": {0.0: [(0.0, 1e308)]}}
        dst = {"H": {0.0: [(0.0, 100.0)]}, "V": {0.0: [(0.0, 100.0)]}}
        rows = rank_registrations(src, dst,
            orientations={"identity": (1, 0, 0, 1)},
            identity_scales=(2.0,), topn=2)
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
