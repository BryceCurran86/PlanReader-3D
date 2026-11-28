"""Default-off experiment (MAX 29 Nov 00:09): withhold canonical rooms whose outline is a floor-grid cell.

A room is a cell when at least 90% of its outline lies on lattice lines of ``pb_floor_grid_linework_shadow`` alone;
any stretch dark ink also draws never counts, so walls drawn over a grid keep their rooms. Withheld rooms are listed
with their share and the page's lattices (typed negative evidence); nothing is deleted from the source or from the
wall set, and every other room is returned unchanged.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

import fitz

from pb_floor_grid_linework_shadow import (
    floor_grid_boundary_shares,
    floor_grid_lattices,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

FLOOR_GRID_CELL_MIN_SHARE = 0.9
REASON_FLOOR_GRID_CELL = "floor_grid_cell"
REASON_ROOMS_WITHHELD = "floor_grid_cell_rooms_withheld"


def veto_floor_grid_cell_rooms(composition: Any, source_bytes: bytes) -> tuple[Any, tuple[dict[str, Any], ...]]:
    """(composition without floor-grid cells, one typed record per withheld room)."""
    by_page: dict[str, list] = {}
    for room in composition.rooms:
        by_page.setdefault(str(room.page_id), []).append(room)
    withheld: list[dict[str, Any]] = []
    removed: set[int] = set()
    with fitz.open(stream=source_bytes, filetype="pdf") as document:
        for page_id in sorted(by_page):
            if not page_id.isdigit() or not 1 <= int(page_id) <= len(document):
                continue
            drawings = document[int(page_id) - 1].get_drawings()
            lattices = floor_grid_lattices(drawings)
            if not lattices:
                continue
            rooms = by_page[page_id]
            shares = floor_grid_boundary_shares([room.polygon_pdf_pts for room in rooms], drawings, lattices)
            evidence = tuple(sorted(stable_contract_id(
                "floor_grid_lattice", {"page_id": page_id, "pen": list(r["pen"]), "items": [list(i) for i in r["items"]]})
                for r in lattices))
            for room, share in zip(rooms, shares):
                if share >= FLOOR_GRID_CELL_MIN_SHARE:
                    removed.add(id(room))
                    withheld.append({
                        "canonical_room_id": room.canonical_room_id, "page_id": page_id,
                        "status": EvidenceResolutionStatus.ABSTAINED.value, "reason": REASON_FLOOR_GRID_CELL,
                        "floor_grid_outline_share": round(share, 4), "floor_grid_lattice_ids": evidence,
                    })
    if not removed:
        return composition, ()
    kept = tuple(room for room in composition.rooms if id(room) not in removed)
    reasons = (*composition.reason_codes, REASON_ROOMS_WITHHELD)
    changes: dict[str, Any] = {"rooms": kept, "reason_codes": reasons}
    if not kept:
        changes.update(status=EvidenceResolutionStatus.ABSTAINED, source_pages=())
    return replace(composition, **changes), tuple(sorted(withheld, key=lambda r: (r["page_id"], r["canonical_room_id"])))
