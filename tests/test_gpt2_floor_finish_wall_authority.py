"""Source-neutral finished-face authority regression tests.

No source-specific IDs, pages, coordinates or benchmark answers are used.
"""
import unittest
from types import SimpleNamespace

from pb_live_canonical_floor_surface import (
    floor_finish_boundary_wall_failure,
    quarantine_unverified_floor_finish_boundaries,
)
from pb_migration_contracts import QuantityEvidence


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

    def test_duplicate_boundary_wall_identity_abstains(self):
        result = self.failure(room("w1", "w1"), {"w1": wall()})
        self.assertEqual(result[0], "floor_finish_bounding_wall_identity_unresolved")

    def test_blank_boundary_wall_identity_abstains(self):
        result = self.failure(room(" "), {" ": wall(identity=" ")})
        self.assertEqual(result[0], "floor_finish_bounding_wall_identity_unresolved")

    def test_whitespace_colliding_boundary_ids_abstain(self):
        result = self.failure(room("w1", " w1 "), {"w1": wall(), " w1 ": wall(" w1 ")})
        self.assertEqual(result[0], "floor_finish_bounding_wall_identity_unresolved")

    def test_whitespace_colliding_wall_mapping_abstains(self):
        result = self.failure(room("w1"), {"w1": wall(), " w1 ": wall(" w1 ")})
        self.assertEqual(result[0], "floor_finish_bounding_wall_identity_unresolved")

    def test_blank_wall_mapping_key_abstains(self):
        result = self.failure(room("w1"), {"w1": wall(), " ": wall(" ")})
        self.assertEqual(result[0], "floor_finish_bounding_wall_identity_unresolved")

    def test_authenticated_finished_face_passes(self):
        self.assertIsNone(self.failure(room("w1"), {"w1": wall()}))


class FloorFinishQuantityAuthorityTests(unittest.TestCase):
    def candidate(self, family="floor_finish_area", reasons=()):
        return QuantityEvidence(
            quantity_id="quantity", family=family, semantic_key="surface",
            value=12.0, unit="m2", input_entity_ids=("floor",),
            authority="documented_dimension", status="firm", confidence=1.0,
            blocking_reasons=reasons,
        )

    def floor(self, room_id="room", resolved=True):
        return SimpleNamespace(canonical_floor_id="floor", room_entity_id=room_id, physical_floor_surface_id="surface-one", physical_floor_surface_identity_resolved=resolved)

    def owned_room(self):
        return SimpleNamespace(canonical_room_id="room", canonical_bounding_wall_ids=("w1",), bounding_wall_ids=())

    def quarantine(self, quantities, floors=None, rooms=None):
        return quarantine_unverified_floor_finish_boundaries(
            quantities, floors=[self.floor()] if floors is None else floors,
            rooms=[self.owned_room()] if rooms is None else rooms,
            walls_by_id={"w1": wall()},
        )

    def test_preblocked_firm_finish_abstains_without_losing_reason(self):
        q = self.candidate(reasons=("source_conflict",))
        out, = self.quarantine([q])
        self.assertTrue(out.abstained)
        self.assertIsNone(out.value)
        self.assertIn("source_conflict", out.blocking_reasons)
        self.assertIn("floor_finish_preexisting_authority_block", out.blocking_reasons)

    def test_duplicate_floor_owner_abstains(self):
        out, = self.quarantine([self.candidate()], floors=[self.floor(), self.floor()])
        self.assertTrue(out.abstained)
        self.assertIn("floor_finish_canonical_floor_owner_ambiguous", out.blocking_reasons)

    def test_competing_canonical_floors_for_one_physical_surface_abstain(self):
        original = self.floor()
        original.physical_floor_surface_id = "physical-surface"
        competing = self.floor()
        competing.canonical_floor_id = "other-canonical-floor"
        competing.physical_floor_surface_id = "physical-surface"
        out, = self.quarantine([self.candidate()], floors=[original, competing])
        self.assertTrue(out.abstained)
        self.assertIsNone(out.value)
        self.assertIn("floor_finish_physical_floor_owner_ambiguous", out.blocking_reasons)

    def test_distinct_physical_surfaces_preserve_valid_floor_finish(self):
        original = self.floor()
        original.physical_floor_surface_id = "physical-surface-one"
        other = self.floor()
        other.canonical_floor_id = "other-canonical-floor"
        other.physical_floor_surface_id = "physical-surface-two"
        q = self.candidate()
        out, = self.quarantine([q], floors=[original, other])
        self.assertIs(out, q)

    def test_duplicate_room_owner_abstains(self):
        out, = self.quarantine([self.candidate()], rooms=[self.owned_room(), self.owned_room()])
        self.assertTrue(out.abstained)
        self.assertIn("floor_finish_canonical_room_owner_ambiguous", out.blocking_reasons)

    def test_unresolved_physical_floor_owner_abstains(self):
        out, = self.quarantine([self.candidate()], floors=[self.floor(resolved=False)])
        self.assertTrue(out.abstained)
        self.assertIsNone(out.value)
        self.assertIn("floor_finish_physical_floor_identity_unresolved", out.blocking_reasons)

    def test_resolved_flag_without_physical_surface_id_abstains(self):
        floor = self.floor()
        del floor.physical_floor_surface_id
        out, = self.quarantine([self.candidate()], floors=[floor])
        self.assertTrue(out.abstained)
        self.assertIsNone(out.value)
        self.assertIn("floor_finish_physical_floor_identity_unresolved", out.blocking_reasons)

    def test_whitespace_physical_surface_id_abstains(self):
        floor = self.floor()
        floor.physical_floor_surface_id = " surface-one "
        out, = self.quarantine([self.candidate()], floors=[floor])
        self.assertTrue(out.abstained)
        self.assertIn("floor_finish_physical_floor_identity_unresolved", out.blocking_reasons)

    def test_missing_physical_floor_authority_abstains(self):
        floor = SimpleNamespace(canonical_floor_id="floor", room_entity_id="room")
        out, = self.quarantine([self.candidate()], floors=[floor])
        self.assertTrue(out.abstained)
        self.assertIn("floor_finish_physical_floor_identity_unresolved", out.blocking_reasons)

    def test_whitespace_colliding_floor_owners_abstain(self):
        other = SimpleNamespace(canonical_floor_id=" floor ", room_entity_id="room",
                                physical_floor_surface_identity_resolved=True)
        out, = self.quarantine([self.candidate()], floors=[self.floor(), other])
        self.assertTrue(out.abstained)
        self.assertIn("floor_finish_canonical_floor_owner_ambiguous", out.blocking_reasons)

    def test_whitespace_colliding_room_owners_abstain(self):
        other = SimpleNamespace(canonical_room_id=" room ",
                                canonical_bounding_wall_ids=("w1",), bounding_wall_ids=())
        out, = self.quarantine([self.candidate()], rooms=[self.owned_room(), other])
        self.assertTrue(out.abstained)
        self.assertIn("floor_finish_canonical_room_owner_ambiguous", out.blocking_reasons)

    def test_blank_floor_owner_scope_abstains(self):
        q = self.candidate()
        from dataclasses import replace
        q = replace(q, input_entity_ids=(" ",))
        out, = self.quarantine([q])
        self.assertTrue(out.abstained)
        self.assertIn("floor_finish_canonical_floor_scope_missing", out.blocking_reasons)

    def test_whitespace_room_reference_abstains(self):
        out, = self.quarantine([self.candidate()], floors=[self.floor(room_id=" room ")])
        self.assertTrue(out.abstained)
        self.assertIn("floor_finish_canonical_room_owner_missing", out.blocking_reasons)

    def test_missing_room_owner_abstains(self):
        out, = self.quarantine([self.candidate()], rooms=[])
        self.assertTrue(out.abstained)
        self.assertIn("floor_finish_canonical_room_owner_missing", out.blocking_reasons)

    def test_unrelated_firm_quantity_is_byte_for_byte_unchanged(self):
        q = self.candidate(family="room_area")
        out, = self.quarantine([q], floors=[], rooms=[])
        self.assertIs(out, q)
        self.assertEqual(out, q)

    def test_valid_finished_face_preserves_original_quantity(self):
        q = self.candidate()
        out, = self.quarantine([q])
        self.assertIs(out, q)


if __name__ == "__main__":
    unittest.main()
