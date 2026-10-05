from __future__ import annotations

import inspect

import fitz
import pytest

from pb_live_physical_net_wall_integration import (
    collect_live_physical_net_wall_claim,
)
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_live_physical_opening_void_composition import _complete_void_pdf


def test_live_physical_net_wall_runs_real_source_chain_and_fails_closed_without_height(
    tmp_path,
) -> None:
    path = tmp_path / "physical-net-wall.pdf"
    path.write_bytes(_complete_void_pdf())

    result = collect_live_physical_net_wall_claim(path, pages=(0,))

    # This fixture deliberately has no independent wall-height authority.
    # The live seam must execute the source-owned chain without manufacturing
    # a default-height gross/net wall quantity.
    assert result.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert result.quantity_m2 is None
    assert result.quantity_id is None

    # Semantic wall identity/geometry must survive independently from later
    # height/gross/net-wall quantity authority.
    assert result.canonical_wall_status is EvidenceResolutionStatus.CORROBORATED
    assert result.canonical_walls
    assert all(wall.geometry_complete for wall in result.canonical_walls)
    assert any(
        wall.physical_identity_resolved
        and wall.identity_status == "physical_resolved_by_opening_host_frame"
        for wall in result.canonical_walls
    )
    assert all(
        wall.metric_geometry_complete is False
        for wall in result.canonical_walls
    )

    assert result.canonical_openings
    assert all(
        opening.canonical_opening_id == opening.physical_opening_id
        for opening in result.canonical_openings
    )
    assert result.external_wall_ids == ()


def test_live_physical_net_wall_rejects_empty_or_out_of_range_page_scope(
    tmp_path,
) -> None:
    path = tmp_path / "physical-net-wall.pdf"
    path.write_bytes(_complete_void_pdf())

    with pytest.raises(ValueError):
        collect_live_physical_net_wall_claim(path, pages=())

    with pytest.raises(ValueError):
        collect_live_physical_net_wall_claim(path, pages=(999,))


def test_live_physical_net_wall_accepts_no_quantity_truth_inputs() -> None:
    parameters = set(
        inspect.signature(collect_live_physical_net_wall_claim).parameters
    )
    forbidden = {
        "wall_id",
        "wall_ids",
        "external_wall_ids",
        "gross_area_m2",
        "net_area_m2",
        "opening_area_m2",
        "opening_count",
        "quantity",
        "trade_scope_id",
        "deduction_rule",
        "expected",
        "benchmark",
    }
    assert not (parameters & forbidden)


def _two_room_cross_view_area_pdf() -> bytes:
    doc = fitz.open()
    try:
        plan = doc.new_page(width=300.0, height=200.0)
        for first, second in (
            ((50.0, 50.0), (250.0, 50.0)),
            ((250.0, 50.0), (250.0, 150.0)),
            ((250.0, 150.0), (50.0, 150.0)),
            ((50.0, 150.0), (50.0, 50.0)),
            ((150.0, 50.0), (150.0, 150.0)),
        ):
            plan.draw_line(
                fitz.Point(*first),
                fitz.Point(*second),
                color=(0, 0, 0),
                width=1.0,
            )
        plan.insert_text((78.0, 100.0), "OFFICE", fontsize=9.0)
        plan.insert_text((178.0, 100.0), "STUDY", fontsize=9.0)

        detail = doc.new_page(width=400.0, height=300.0)
        detail.insert_text((150.0, 150.0), "OFFICE", fontsize=10.0)
        detail.draw_line((100.0, 80.0), (250.0, 80.0), color=(0, 0, 0), width=1.0)
        detail.draw_line((100.0, 68.0), (100.0, 92.0), color=(0, 0, 0), width=1.0)
        detail.draw_line((250.0, 68.0), (250.0, 92.0), color=(0, 0, 0), width=1.0)
        detail.insert_text((164.0, 77.0), "3600", fontsize=9.0)

        detail.draw_line((280.0, 100.0), (280.0, 200.0), color=(0, 0, 0), width=1.0)
        detail.draw_line((268.0, 100.0), (292.0, 100.0), color=(0, 0, 0), width=1.0)
        detail.draw_line((268.0, 200.0), (292.0, 200.0), color=(0, 0, 0), width=1.0)
        detail.insert_text((277.0, 167.0), "2400", fontsize=9.0, rotate=90)
        return doc.tobytes()
    finally:
        doc.close()


def test_cross_view_room_area_reaches_same_canonical_floor_without_scale(
    tmp_path,
) -> None:
    path = tmp_path / "cross-view-room-area.pdf"
    path.write_bytes(_two_room_cross_view_area_pdf())
    result = collect_live_physical_net_wall_claim(
        path,
        pages=(0,),
        room_area_support_pages=(1,),
    )

    assert len(result.canonical_rooms) == 2
    assert {room.room_label for room in result.canonical_rooms} == {
        "OFFICE",
        "STUDY",
    }
    assert len(result.canonical_floors) == 2

    resolved_floors = [
        floor for floor in result.canonical_floors
        if floor.metric_area_m2 is not None
    ]
    assert len(resolved_floors) == 1
    resolved_floor = resolved_floors[0]
    office_room = next(
        room for room in result.canonical_rooms
        if room.room_label == "OFFICE"
    )
    assert resolved_floor.room_entity_id == office_room.physical_room_id
    assert resolved_floor.metric_area_m2 == 8.64
    assert resolved_floor.metric_area_quantity_id
    assert resolved_floor.metric_area_authority
    assert resolved_floor.commercial_quantity_authority is False
    assert resolved_floor.finish_descriptor is None

    firm_room_areas = [
        quantity for quantity in result.room_area_quantity_evidence
        if not quantity.abstained
    ]
    assert len(firm_room_areas) == 1
    assert firm_room_areas[0].value == 8.64
    assert firm_room_areas[0].formula == "authoritative_explicit_area"


def test_room_area_support_pages_do_not_expand_topology_scope(
    tmp_path,
) -> None:
    path = tmp_path / "cross-view-room-area-scope.pdf"
    path.write_bytes(_two_room_cross_view_area_pdf())
    result = collect_live_physical_net_wall_claim(
        path,
        pages=(0,),
        topology_pages=(0,),
        room_area_support_pages=(1,),
    )

    assert result.canonical_room_source_pages == (1,)
    assert all(room.page_id == "1" for room in result.canonical_rooms)
    assert all(floor.page_id == "1" for floor in result.canonical_floors)
