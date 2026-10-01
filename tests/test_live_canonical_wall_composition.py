from __future__ import annotations

from pb_live_canonical_wall_composition import (
    LIVE_CANONICAL_WALL_IDENTITY_CANDIDATE,
    LIVE_CANONICAL_WALL_PARTIAL,
    compose_live_canonical_walls,
)
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_live_canonical_room_composition import _source


def test_ambiguous_equivalence_preserves_candidate_wall_objects() -> None:
    source, wall_opening = _source(page_partitions=(True,))

    result = compose_live_canonical_walls(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.reason_codes[0] == LIVE_CANONICAL_WALL_PARTIAL
    assert LIVE_CANONICAL_WALL_IDENTITY_CANDIDATE in result.reason_codes
    assert result.source_pages == (1,)
    assert len(result.walls) == 5
    assert len(result.unresolved_wall_candidate_ids) == 5
    assert len(result.candidate_to_canonical_wall_id) == 5

    for wall in result.walls:
        assert wall.physical_wall_id is None
        assert wall.physical_identity_resolved is False
        assert wall.identity_status == "candidate_physical_equivalence_unresolved"
        assert wall.geometry_complete is True
        assert wall.metric_geometry_complete is False
        assert wall.quantity_complete is False
        assert len(wall.member_wall_candidate_ids) == 1
        assert len(wall.plan_members) == 1
        member_id = wall.member_wall_candidate_ids[0]
        assert result.candidate_to_canonical_wall_id[member_id] == wall.canonical_wall_id
        assert wall.plan_members[0].centerline_pts


def test_candidate_wall_payload_exposes_resolution_state() -> None:
    source, wall_opening = _source(page_partitions=(True,))
    result = compose_live_canonical_walls(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    payload = result.walls[0].to_dict()

    assert payload["identity_status"] == "candidate_physical_equivalence_unresolved"
    assert payload["physical_identity_resolved"] is False
    assert payload["geometry_complete"] is True
    assert payload["metric_geometry_complete"] is False
    assert payload["quantity_complete"] is False
    assert payload["plan_members"]
