"""Original-source internal swing threshold closure for candidate room topology.

Only an original PDF swing arc, TWO distinct native black internal-wall ends
and TWO uniquely hosted original jamb caps may supply a temporary barrier.
The geometry closes a room for *review*, never for physical wall material or
billable customer floor, wall, ceiling or opening quantities.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence
import re
from typing import Any

from pb_source_swing_door_footprint_continuity import (
    detect_exterior_swing_door_footprint_bridges,
)

_INTERNAL_WALL_LAYER = re.compile(r"WallInternal|Wall_Internal|InternalWall", re.I)


@dataclass(frozen=True)
class SourceInternalSwingRoomBarrier:
    first_host_path_id: int
    second_host_path_id: int
    swing_arc_path_id: int
    jamb_cap_path_ids: tuple[int, int]
    bounds_pdf_pts: tuple[float, float, float, float]
    axis: str
    page_index: int
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "source_owned_internal_swing_room_closure_only",
            "first_host_path_id": self.first_host_path_id,
            "second_host_path_id": self.second_host_path_id,
            "swing_arc_path_id": self.swing_arc_path_id,
            "jamb_cap_path_ids": list(self.jamb_cap_path_ids),
            "bounds_pdf_pts": list(self.bounds_pdf_pts),
            "axis": self.axis,
            "page_index": self.page_index,
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
        }


def detect_source_internal_swing_room_barriers(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Any] = (),
    *,
    page_index: int = -1,
) -> tuple[SourceInternalSwingRoomBarrier, ...]:
    """Source native unique-host+arc+caps; internal cap widths vary slightly.

    The external door classifier is unchanged at its original 0.5pt tolerance.
    Internal 0.75pt tolerance is used only when a full original jamb cap,
    quarter-arc and both black internal faces prove the *same* opening.
    """
    receipts = detect_exterior_swing_door_footprint_bridges(
        drawings,
        source_words,
        page_index=page_index,
        wall_layer_pattern=_INTERNAL_WALL_LAYER,
        cap_across_tolerance_pt=0.75,
    )
    return tuple(
        SourceInternalSwingRoomBarrier(
            first_host_path_id=r.first_host_path_id,
            second_host_path_id=r.second_host_path_id,
            swing_arc_path_id=r.swing_arc_path_id,
            jamb_cap_path_ids=r.jamb_cap_path_ids,
            bounds_pdf_pts=r.bounds_pdf_pts,
            axis=r.axis,
            page_index=page_index,
        )
        for r in receipts
    )
