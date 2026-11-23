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


if __name__ == "__main__":
    unittest.main()
