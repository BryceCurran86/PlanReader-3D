"""Live source-owned room-area integration tests."""
from __future__ import annotations

from pb_live_room_area_integration import (
    LIVE_ROOM_AREA_RESOLVED,
    collect_live_room_area_claims,
)
from tests.test_live_ceiling_lining_integration_v1 import _write


def test_resolved_floor_plan_emits_firm_source_owned_room_areas(tmp_path) -> None:
    path = _write(tmp_path, framed=True)
    result = collect_live_room_area_claims(path, pages=(0,))

    assert result.status.value == "corroborated"
    assert result.reason_codes[0] == LIVE_ROOM_AREA_RESOLVED
    assert len(result.claims) == 2

    room_ids = {claim.room_entity_id for claim in result.claims}
    quantity_ids = {claim.room_quantity_id for claim in result.claims}
    assert len(room_ids) == 2
    assert len(quantity_ids) == 2
    for claim in result.claims:
        assert claim.quantity_m2 > 0.0
        assert claim.status == "firm"
        assert claim.authority == "pdf_scaled"
        assert claim.evidence_ids
        assert claim.physical_scale_record_id

def test_unframed_plan_publishes_no_live_room_area_claims(tmp_path) -> None:
    path = _write(tmp_path, framed=False)
    result = collect_live_room_area_claims(path, pages=(0,))

    assert result.claims == ()
    assert result.status.value == "abstained"


def test_room_area_claims_are_deterministic(tmp_path) -> None:
    path = _write(tmp_path, framed=True)
    first = collect_live_room_area_claims(path, pages=(0,))
    second = collect_live_room_area_claims(path, pages=(0,))

    assert first == second
