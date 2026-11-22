"""Source-neutral finished-face authority regression tests.

No source-specific IDs, pages, coordinates or benchmark answers are used.
"""
import unittest
from types import SimpleNamespace

from pb_live_canonical_floor_surface import floor_finish_boundary_wall_failure


def room(*ids):
    return SimpleNamespace(canonical_bounding_wall_ids=ids, bounding_wall_ids=())


def wall(identity="w1", role="internal_finished_wall_face", resolved=True):
    return SimpleNamespace(
        canonical_wall_id=identity,
        role=role,
        physical_identity_resolved=resolved,
    )


class FloorFinishWallAuthorityTests(unittest.TestCase):
    def failure(self, room_object, walls):
        return floor_finish_boundary_wall_failure(
            room_object, walls, quantity_id="candidate-finish"
        )

    def test_missing_boundary_scope_abstains(self):
        result = self.failure(room(), {"w1": wall()})
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "floor_finish_bounding_wall_authority_incomplete")

    def test_missing_wall_abstains(self):
        result = self.failure(room("w1"), {})
        self.assertEqual(result[0], "floor_finish_bounding_wall_authority_incomplete")

    def test_mismatched_canonical_identity_abstains(self):
        result = self.failure(room("w1"), {"w1": wall(identity="other")})
        self.assertEqual(result[0], "floor_finish_bounding_wall_identity_unresolved")

    def test_unresolved_wall_abstains(self):
        result = self.failure(room("w1"), {"w1": wall(resolved=False)})
        self.assertEqual(result[0], "floor_finish_bounding_wall_identity_unresolved")

    def test_external_role_abstains(self):
        result = self.failure(room("w1"), {"w1": wall(role="external_wall")})
        self.assertEqual(result[0], "floor_finish_bounding_wall_not_finished_face")

    def test_authenticated_finished_face_passes(self):
        self.assertIsNone(self.failure(room("w1"), {"w1": wall()}))


if __name__ == "__main__":
    unittest.main()
