"""Default-off floor-grid cell veto (MAX 29 Nov 00:09). Synthetic only."""
from __future__ import annotations

from types import SimpleNamespace

import fitz
import pytest
from test_live_physical_net_wall_integration import _two_room_cross_view_area_pdf

from pb_floor_grid_cell_veto_shadow import (
    REASON_FLOOR_GRID_CELL,
    REASON_ROOMS_WITHHELD,
    veto_floor_grid_cell_rooms,
)
from pb_live_canonical_room_composition import LiveCanonicalRoomComposition
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_migration_contracts import EvidenceResolutionStatus

GREY = (0.5, 0.5, 0.5)


def _grid(page, xs, ys):
    for x in xs:
        page.draw_line((x, ys[0] - 20.0), (x, ys[-1] + 20.0), color=GREY, width=0.24)
    for y in ys:
        page.draw_line((xs[0] - 20.0, y), (xs[-1] + 20.0, y), color=GREY, width=0.24)


def _plan(grid=True) -> bytes:
    document = fitz.open()
    page = document.new_page(width=300.0, height=200.0)
    for first, second in (((50.0, 50.0), (250.0, 50.0)), ((250.0, 50.0), (250.0, 150.0)), ((250.0, 150.0), (50.0, 150.0)),
                          ((50.0, 150.0), (50.0, 50.0)), ((150.0, 50.0), (150.0, 150.0))):
        page.draw_line(fitz.Point(*first), fitz.Point(*second), color=(0, 0, 0), width=1.0)
    if grid:
        _grid(page, (70.0, 90.0, 110.0, 130.0), (70.0, 90.0, 110.0, 130.0))
        _grid(page, (170.0, 190.0, 210.0, 230.0), (70.0, 90.0, 110.0, 130.0))
    page.insert_text((78.0, 100.0), "OFFICE", fontsize=9.0)
    page.insert_text((178.0, 100.0), "STUDY", fontsize=9.0)
    data = document.tobytes()
    document.close()
    return data


def _room(name, rect, page_id="1"):
    x0, y0, x1, y1 = rect
    return SimpleNamespace(canonical_room_id=name, page_id=page_id,
                           polygon_pdf_pts=((x0, y0), (x1, y0), (x1, y1), (x0, y1)))


def _composition(*rooms):
    return LiveCanonicalRoomComposition(status=EvidenceResolutionStatus.CORROBORATED, reason_codes=("x",),
                                        rooms=tuple(rooms), source_pages=(1,))


def test_only_interior_tile_cells_are_withheld():
    cell = _room("cell", (90.0, 90.0, 110.0, 110.0))
    edge_cell = _room("edge_cell", (50.0, 90.0, 70.0, 110.0))  # one side on a dark wall: 75%
    narrow = _room("narrow_between_walls", (150.0, 50.0, 170.0, 150.0))  # dark walls on three sides
    whole = _room("whole_room", (50.0, 50.0, 150.0, 150.0))
    off_page = _room("off_page", (90.0, 90.0, 110.0, 110.0), page_id="7")
    result, withheld = veto_floor_grid_cell_rooms(_composition(cell, edge_cell, narrow, whole, off_page), _plan())
    assert [r.canonical_room_id for r in result.rooms] == ["edge_cell", "narrow_between_walls", "whole_room", "off_page"]
    assert result.rooms[0] is edge_cell  # kept rooms are the same objects, ids unchanged
    [record] = withheld
    assert record["canonical_room_id"] == "cell" and record["reason"] == REASON_FLOOR_GRID_CELL
    assert record["floor_grid_outline_share"] >= 0.9 and record["floor_grid_lattice_ids"]
    assert result.reason_codes == ("x", REASON_ROOMS_WITHHELD) and result.status is EvidenceResolutionStatus.CORROBORATED


def test_nothing_to_withhold_returns_the_same_composition():
    composition = _composition(_room("whole_room", (50.0, 50.0, 150.0, 150.0)))
    for source in (_plan(), _plan(grid=False)):
        result, withheld = veto_floor_grid_cell_rooms(composition, source)
        assert result is composition and withheld == ()


def test_every_room_withheld_abstains():
    result, withheld = veto_floor_grid_cell_rooms(_composition(_room("cell", (90.0, 90.0, 110.0, 110.0))), _plan())
    assert result.rooms == () and result.status is EvidenceResolutionStatus.ABSTAINED and len(withheld) == 1


def test_live_claim_is_unchanged_unless_asked(tmp_path):
    path = tmp_path / "tiled.pdf"
    path.write_bytes(_plan())
    plain = collect_live_physical_net_wall_claim(path, pages=(0,))
    on = collect_live_physical_net_wall_claim(path, pages=(0,), floor_grid_cell_veto_shadow=True)
    assert "floor_grid_cell_veto" not in plain.surface_pipeline_diagnostics
    withheld = {r["canonical_room_id"] for r in on.surface_pipeline_diagnostics["floor_grid_cell_veto"]}
    before = {room.canonical_room_id: room for room in plain.canonical_rooms}
    after = {room.canonical_room_id: room for room in on.canonical_rooms}
    assert withheld and set(after) == set(before) - withheld
    assert all(after[i].polygon_pdf_pts == before[i].polygon_pdf_pts for i in after)
    assert (len(before), len(after)) == (50, 32)  # two 5 x 5 tiled rooms; the 9 interior cells of each withheld
    assert [w.canonical_wall_id for w in on.canonical_walls] == [w.canonical_wall_id for w in plain.canonical_walls]
    assert [o.physical_opening_id for o in on.canonical_openings] == [o.physical_opening_id for o in plain.canonical_openings]
    assert len(on.canonical_floors) == len(after) and not {f.room_entity_id for f in on.canonical_floors} & withheld
    with pytest.raises(ValueError):
        collect_live_physical_net_wall_claim(path, pages=(0,), floor_grid_cell_veto_shadow=1)


def test_withheld_cells_get_no_room_area_entry_and_other_rows_stay(tmp_path):
    document = fitz.open(stream=_two_room_cross_view_area_pdf(), filetype="pdf")
    page = document[0]
    for x in (170.0, 190.0, 210.0, 230.0):  # tiles in the second room only; the office with its printed size stays clean
        page.draw_line((x, 50.0), (x, 150.0), color=GREY, width=0.24)
    for y in (70.0, 90.0, 110.0, 130.0):
        page.draw_line((150.0, y), (250.0, y), color=GREY, width=0.24)
    path = tmp_path / "tiled_cross_view.pdf"
    path.write_bytes(document.tobytes())
    document.close()
    claims = [collect_live_physical_net_wall_claim(path, pages=(0,), room_area_support_pages=(1,),
                                                   **({"floor_grid_cell_veto_shadow": True} if on else {}))
              for on in (False, True)]
    off, on = claims
    withheld = on.surface_pipeline_diagnostics["floor_grid_cell_veto"]
    assert withheld and all(r["source_room_face_record_id"] for r in withheld)
    assert len(off.room_area_quantity_evidence) == len(off.canonical_rooms)
    assert len(on.room_area_quantity_evidence) == len(on.canonical_rooms)
    firm = [[round(float(q.value), 2) for q in c.room_area_quantity_evidence if not q.abstained] for c in claims]
    assert firm == [[8.64], [8.64]]
