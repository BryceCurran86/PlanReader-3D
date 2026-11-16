"""Source-owned internal-door closure can reveal rooms, never approve areas."""
from types import SimpleNamespace

import fitz
from shapely.geometry import box

from pb_source_internal_swing_room_barrier import (
    SourceInternalSwingRoomBarrier,
    detect_source_internal_swing_room_barriers,
)
from pb_source_spatial_subdivision_shadow import (
    build_source_spatial_subdivision,
)


def _bar(idx, bounds):
    return SimpleNamespace(
        path_index=idx, polygon=box(*bounds),
        native_path_indices=lambda: (idx,),
    )


def _drawing(bounds, fill=0.0):
    return {
        "layer": "Enclosure_WallInternal",
        "rect": fitz.Rect(*bounds),
        "fill": (fill, fill, fill),
        "items": (("re", fitz.Rect(*bounds), 1),),
    }


def _fixture():
    # One original closed-shaped physical room except the 25pt top doorway.
    bounds = (
        (100, 100, 105, 102.5),
        (130, 100, 200, 102.5),
        (100, 190, 200, 200),
        (100, 100, 110, 200),
        (190, 100, 200, 200),
    )
    drawings = [_drawing(b) for b in bounds]
    bars = [_bar(i, b) for i, b in enumerate(bounds)]
    swing_points = (
        (105.85, 76.4), (118.7, 76.4),
        (129.15, 86.85), (129.15, 99.7),
    )
    drawings.append({
        "layer": "Enclosure_WallInternal",
        "rect": fitz.Rect(105.85, 76.4, 129.15, 99.7),
        "fill": None,
        "items": (("c", *(fitz.Point(*p) for p in swing_points)),),
    })
    drawings.append(_drawing((105, 99.7, 105.85, 102.2), fill=1))
    drawings.append(_drawing((129.15, 99.7, 130, 102.2), fill=1))
    return drawings, bars


def test_internal_source_door_closes_review_room_not_a_customer_quantity():
    drawings, bars = _fixture()
    source = detect_source_internal_swing_room_barriers(drawings, page_index=2)
    assert len(source) == 1, source
    before = build_source_spatial_subdivision(
        drawings, bars=bars, page_rect=(0, 0, 300, 300)
    )
    after = build_source_spatial_subdivision(
        drawings, bars=bars, page_rect=(0, 0, 300, 300),
        topology_barriers=source,
    )
    assert after.source_topology_barrier_count == 1
    assert after.interior_room_count > before.interior_room_count
    assert after.measurement_authorized is False
    assert after.physical_space_authenticated is False
    assert after.commercial_publishable is False
    assert after.official_frozen120_score_change == 0
    assert after.to_dict()["source_topology_barrier_count"] == 1


def test_dictionary_and_missing_source_owner_cannot_close_a_room():
    drawings, bars = _fixture()
    source = detect_source_internal_swing_room_barriers(drawings)[0]
    bad = source.to_dict()
    bad["measurement_authorized"] = True
    result = build_source_spatial_subdivision(
        drawings, bars=bars, page_rect=(0, 0, 300, 300),
        topology_barriers=(bad,),
    )
    assert result.source_topology_barrier_count == 0
    phantom = SourceInternalSwingRoomBarrier(
        first_host_path_id=999, second_host_path_id=source.second_host_path_id,
        swing_arc_path_id=source.swing_arc_path_id,
        jamb_cap_path_ids=source.jamb_cap_path_ids,
        bounds_pdf_pts=source.bounds_pdf_pts, axis=source.axis,
        page_index=source.page_index,
    )
    result = build_source_spatial_subdivision(
        drawings, bars=bars, page_rect=(0, 0, 300, 300),
        topology_barriers=(phantom,),
    )
    assert result.source_topology_barrier_count == 0


def test_cross_viewport_source_witness_cannot_close_review_space():
    drawings, bars = _fixture()
    source = detect_source_internal_swing_room_barriers(drawings)[0]
    drawings[0]["viewport_id"] = "floor-plan"
    drawings[1]["viewport_id"] = "elevation"
    result = build_source_spatial_subdivision(
        drawings, bars=bars, page_rect=(0, 0, 300, 300),
        topology_barriers=(source,),
    )
    assert result.source_topology_barrier_count == 0
    assert result.measurement_authorized is False
