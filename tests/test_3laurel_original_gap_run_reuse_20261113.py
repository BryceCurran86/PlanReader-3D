"""Original PlanReader wall-run reuse: keep source-attested door topology unchanged."""
from unittest.mock import patch

import pb_layered_wall_doorway_room_ring_shadow as rings
from test_layered_wall_doorway_room_ring_shadow_v1 import SHA, room, candidates


def test_wall_run_inventory_built_once_per_orientation_for_multiple_door_gaps():
    drawings = room(window=True, split_top=50)
    with patch.object(rings, "_runs", wraps=rings._runs) as inventory:
        result = rings.build_layered_wall_doorway_room_rings(
            drawings, source_sha256=SHA, page_index=0,
        )
    assert inventory.call_count == 2
    assert len(candidates(result)) == 1
    assert len(result.closures) == 2
    assert {closure.kind for closure in result.closures} == {
        rings.KIND_SWING, rings.KIND_STROKE,
    }
    assert result.rings[0].takeoff_eligible is False


def test_unproven_gap_still_refuses_room_and_customer_quantity():
    from test_layered_wall_doorway_room_ring_shadow_v1 import _open_gap_room
    with patch.object(rings, "_runs", wraps=rings._runs) as inventory:
        result = rings.build_layered_wall_doorway_room_rings(
            _open_gap_room(), source_sha256=SHA, page_index=0,
        )
    assert inventory.call_count == 2
    assert not candidates(result)
    assert not result.closures
