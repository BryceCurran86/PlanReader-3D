"""Inside-face clockwise envelope: garage in, porch/alfresco out, party internal."""
from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from pb_source_inside_face_thermal_envelope_shadow import (
    build_inside_face_thermal_envelope_shadow,
)
from pb_source_shared_dwelling_envelope_shadow import CandidateSharedBuildingDivider


@dataclass(frozen=True)
class SourceBar:
    polygon: Polygon
    original_path_id: int

    def native_path_indices(self):
        return (self.original_path_id,)


def _building_bars(*, garage_front_gap: bool = False):
    # Outer frame + party wall. Optional south garage gap at left dwelling.
    rows = [
        (0, 0, 240, 3),       # south
        (0, 117, 240, 120),   # north
        (0, 0, 3, 120),       # west
        (237, 0, 240, 120),   # east
        (118, 0, 122, 120),   # party
    ]
    if garage_front_gap:
        rows[0] = (40, 0, 240, 3)  # open left south for garage panel
    return tuple(SourceBar(box(*r), i) for i, r in enumerate(rows))


def _party():
    return CandidateSharedBuildingDivider(
        source_page_index=2,
        annotation_word_ids=(733, 734),
        annotation_text="PARTY WALL",
        wall_native_path_ids=(4,),
        wall_layer="Enclosure_WallExternal",
        wall_bounds_pdf_pts=(118.0, 0.0, 122.0, 120.0),
        orientation="vertical",
        side_one_label="LIVING",
        side_two_label="MEDIA",
    )


def _words(*, garage=False, alfresco=False, porch=False):
    rows = [
        (47, 55, 67, 63, "LIVING", 0, 0, 0),
        (168, 55, 188, 63, "MEDIA", 1, 0, 0),
    ]
    if garage:
        rows.append((20, 20, 50, 28, "GARAGE", 2, 0, 0))
    if alfresco:
        rows.append((12, 25, 43, 33, "ALFRESCO", 3, 0, 0))
    if porch:
        rows.append((200, 20, 230, 28, "PORCH", 4, 0, 0))
    return tuple(rows)


def test_dual_dwelling_inside_face_dissolves_party_wall_as_internal():
    bars = _building_bars()
    union = unary_union([b.polygon for b in bars])
    result = build_inside_face_thermal_envelope_shadow(
        bars,
        _words(),
        shared_dividers=(_party(),),
        source_wall_union=union,
    )
    assert result.status == "CANDIDATE"
    assert result.enclosed_dwelling_zone_count == 2
    assert result.internal_party_wall_native_path_ids == (4,)
    assert 4 not in result.outer_wall_native_path_ids
    assert len(result.inside_face_clockwise_pdf_pts) >= 5
    assert result.inside_face_clockwise_pdf_pts[0] == result.inside_face_clockwise_pdf_pts[-1]
    assert result.physical_wall_authenticated is False
    assert result.commercial_publishable is False


def test_alfresco_inside_proposed_envelope_abstains():
    bars = _building_bars()
    union = unary_union([b.polygon for b in bars])
    result = build_inside_face_thermal_envelope_shadow(
        bars,
        _words(alfresco=True),
        shared_dividers=(_party(),),
        source_wall_union=union,
    )
    assert result.status == "ABSTAINED"
    assert result.reason in {
        "outdoor_porch_or_alfresco_inside_proposed_inside_face",
        "outdoor_space_inside_proposed_building",
    }
    assert result.inside_face_clockwise_pdf_pts == ()


def test_garage_label_without_panel_bridge_abstains_when_drawings_present():
    bars = _building_bars()
    union = unary_union([b.polygon for b in bars])
    # Empty drawings still allow detect to run and return (); garage labeled
    # with drawings provided requires a topology bridge.
    drawings = [
        {
            "layer": "WallExternal",
            "fill": None,
            "color": (0, 0, 0),
            "width": 0.5,
            "dashes": "",
            "type": "s",
            "items": [],
        }
    ]
    result = build_inside_face_thermal_envelope_shadow(
        bars,
        _words(garage=True),
        shared_dividers=(_party(),),
        source_wall_union=union,
        source_drawings=drawings,
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "garage_panel_topology_bridge_missing"
