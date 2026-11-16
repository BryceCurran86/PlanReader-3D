"""Alfresco and porch labels cannot turn roofed outdoor space into house footprint.

Native text and connected source wall owners, not page coordinate hacks.
"""
from types import SimpleNamespace

from shapely.geometry import box

from pb_source_spatial_subdivision_shadow import (
    SpatialRegionKind,
    _is_outdoor_name,
    build_source_spatial_subdivision,
)


def _wall(path_id: int, rect: tuple[float, float, float, float]):
    return SimpleNamespace(
        polygon=box(*rect),
        path_index=path_id,
        native_path_indices=lambda: (path_id,),
    )


def _attached_exterior_room(label: str):
    # Enclosed room (left) and adjacent roofed outdoor zone (right) share
    # a real thermal/exterior wall. Both are drawn as source-owned strips.
    bars = [
        _wall(1, (100, 100, 250, 110)),  # house top
        _wall(2, (100, 240, 250, 250)),  # house bottom
        _wall(3, (100, 100, 110, 250)),  # house outer face
        _wall(4, (240, 100, 250, 250)),  # physical shared house wall
        _wall(5, (250, 100, 350, 110)),  # outside-roofed-area top
        _wall(6, (250, 240, 350, 250)),  # outside-roofed-area bottom
        _wall(7, (340, 100, 350, 250)),  # outside-roofed-area outer edge
    ]
    drawings = [{"layer": "Enclosure_WallExternal", "fill": (0, 0, 0)} for _ in bars]
    # The original source page exposes independent text words with bboxes.
    text_words = [
        (150, 175, 195, 185, "LIVING"),
        (280, 175, 325, 185, label),
    ]
    return build_source_spatial_subdivision(
        drawings,
        bars=bars,
        page_rect=(0, 0, 500, 500),
        text_words=text_words,
    )


def test_user_confirmed_alfresco_and_porch_are_outdoor_not_conditioned_rooms():
    assert _is_outdoor_name("ALFRESCO") is True
    assert _is_outdoor_name("PORCH") is True
    assert _is_outdoor_name("LIVING") is False
    assert _is_outdoor_name("BED 5") is False
    for label in ("ALFRESCO", "PORCH"):
        report = _attached_exterior_room(label)
        regions = report.regions
        outdoor = [r for r in regions if r.kind == SpatialRegionKind.ATTACHED_OUTDOOR_REGION]
        interior = [r for r in regions if r.kind == SpatialRegionKind.INTERIOR_ENCLOSED_ROOM]
        assert report.attached_outdoor_count == 1, label
        assert len(outdoor) == 1 and outdoor[0].label == label
        assert outdoor[0].is_conditioned_living is False
        # Generic interior labels need a separately authenticated room key;
        # this outdoor-only change must not infer living-room ownership.
        assert len(interior) == 1
        assert interior[0].is_conditioned_living is True
        assert report.measurement_authorized is False
        assert report.commercial_publishable is False
        assert report.official_frozen120_score_change == 0
        # The source owner of the thermal wall must remain recoverable.
        shared = [f for f in report.boundary_faces if 4 in f.native_path_ids]
        assert shared and all(f.is_exterior_envelope for f in shared)
