"""Unique source swing/leaf classifies a hosted opening; it does not mint one."""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path

import fitz
import pytest

from pb_opening_kind_authority import (
    SOURCE_DIAGONAL_DOOR_LEAF,
    SOURCE_QUARTER_SWING_AND_RADIAL_LEAF,
    resolve_opening_kind,
)
from pb_source_quarter_swing_opening_kind_shadow import (
    apply_source_quarter_swing_opening_kinds,
)
from tests.test_live_opening_area_quantity_publication import _composition, _opening

K = 0.5522847498
HINGE = (50.0, 50.0)
OPEN_TIP = (25.0, 50.0)
CLOSED_TIP = (50.0, 25.0)
RADIUS = 25.0


def _point(xy: tuple[float, float]) -> fitz.Point:
    return fitz.Point(xy[0], xy[1])


def _stroke(kind: str, *points: tuple[float, float], layer: str = "Enclosure_WallExternal",
            stroke_opacity: float | None = None):
    row = {
        "layer": layer,
        "fill": None,
        "color": (0.0, 0.0, 0.0),
        "items": [(kind, *(_point(p) for p in points))],
    }
    if stroke_opacity is not None:
        row["stroke_opacity"] = stroke_opacity
    return row


def _quarter_swing_drawings() -> list[dict]:
    p2 = (OPEN_TIP[0], HINGE[1] - K * RADIUS)
    p3 = (HINGE[0] - K * RADIUS, CLOSED_TIP[1])
    return [
        _stroke("l", HINGE, OPEN_TIP),
        _stroke("c", OPEN_TIP, p2, p3, CLOSED_TIP),
    ]


def _hosted(*, geom, kind=None, opening_id="opening-1"):
    return replace(
        _opening(canonical_id=opening_id, kind=kind, area_m2=None, area_basis=None),
        source_geometries=(geom,),
        structural_pattern="jamb_bounded_two_face_interruption",
        host_frame_record_id=None,
    )


def test_quarter_swing_structural_pattern_is_a_door() -> None:
    result = resolve_opening_kind(structural_pattern=SOURCE_QUARTER_SWING_AND_RADIAL_LEAF)
    assert result.opening_kind == "door"
    result = resolve_opening_kind(structural_pattern=SOURCE_DIAGONAL_DOOR_LEAF)
    assert result.opening_kind == "door"


def test_unique_cubic_swing_classifies_the_hosted_opening_at_the_hinge() -> None:
    opening = _hosted(geom=(49.2, 50.0, 52.5, 50.0))
    composition = apply_source_quarter_swing_opening_kinds(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
    )
    updated = composition.canonical_openings[0]
    assert updated.opening_kind == "door"
    assert updated.canonical_opening_id == opening.canonical_opening_id
    assert any(item.startswith("source_drawn_door_leaf_") for item in updated.evidence_ids)


def test_two_hosted_openings_at_the_same_swing_abstain() -> None:
    first = _hosted(geom=(49.2, 50.0, 52.5, 50.0), opening_id="opening-a")
    second = _hosted(geom=(50.0, 49.2, 50.0, 52.5), opening_id="opening-b")
    composition = apply_source_quarter_swing_opening_kinds(
        _composition(first, second),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
    )
    assert composition.canonical_openings[0].opening_kind is None
    assert composition.canonical_openings[1].opening_kind is None


def test_a_typed_neighbour_at_the_same_swing_keeps_the_unkinded_opening_unkinded() -> None:
    unkinded = _hosted(geom=(49.2, 50.0, 52.5, 50.0), opening_id="opening-unkinded")
    typed_door = _hosted(geom=(50.0, 49.2, 50.0, 52.5), kind="door", opening_id="opening-door")
    composition = apply_source_quarter_swing_opening_kinds(
        _composition(unkinded, typed_door),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
    )
    by_id = {item.canonical_opening_id: item for item in composition.canonical_openings}
    assert by_id["opening-unkinded"].opening_kind is None
    assert by_id["opening-door"].opening_kind == "door"


def test_a_typed_window_neighbour_at_the_same_swing_is_not_invisible_to_uniqueness() -> None:
    unkinded = _hosted(geom=(49.2, 50.0, 52.5, 50.0), opening_id="opening-unkinded")
    typed_window = _hosted(geom=(50.0, 49.2, 50.0, 52.5), kind="window", opening_id="opening-window")
    composition = apply_source_quarter_swing_opening_kinds(
        _composition(unkinded, typed_window),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
    )
    by_id = {item.canonical_opening_id: item for item in composition.canonical_openings}
    assert by_id["opening-unkinded"].opening_kind is None
    assert by_id["opening-window"].opening_kind == "window"


def test_zero_opacity_wall_stroke_does_not_classify_a_door() -> None:
    opening = _hosted(geom=(20.0, 20.0, 20.0, 17.5))
    drawings = [
        _stroke("l", (20.0, 20.0), (44.66, 44.66), layer="Enclosure_WallInternal", stroke_opacity=0.0)
    ]
    composition = apply_source_quarter_swing_opening_kinds(
        _composition(opening),
        drawings_by_page_id={"3": drawings},
    )
    assert composition.canonical_openings[0].opening_kind is None


def test_zero_opacity_cubic_swing_does_not_classify_a_door() -> None:
    opening = _hosted(geom=(49.2, 50.0, 52.5, 50.0))
    drawings = [
        replace_opacity(row, 0.0) for row in _quarter_swing_drawings()
    ]
    composition = apply_source_quarter_swing_opening_kinds(
        _composition(opening),
        drawings_by_page_id={"3": drawings},
    )
    assert composition.canonical_openings[0].opening_kind is None


def replace_opacity(row: dict, opacity: float) -> dict:
    updated = dict(row)
    updated["stroke_opacity"] = opacity
    return updated


def test_unhosted_opening_at_the_swing_stays_unkinded() -> None:
    opening = replace(_hosted(geom=(49.2, 50.0, 52.5, 50.0)), host_wall_id=None, host_binding_record_id=None)
    composition = apply_source_quarter_swing_opening_kinds(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
    )
    assert composition.canonical_openings[0].opening_kind is None


def test_existing_window_kind_is_not_reclassified() -> None:
    opening = _hosted(geom=(49.2, 50.0, 52.5, 50.0), kind="window")
    composition = apply_source_quarter_swing_opening_kinds(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
    )
    assert composition.canonical_openings[0].opening_kind == "window"


def test_unique_diagonal_leaf_classifies_a_hosted_opening() -> None:
    hinge = (20.0, 20.0)
    tip = (20.0 + 24.66, 20.0 + 24.66)
    opening = _hosted(geom=(20.0, 20.0, 20.0, 17.5))
    drawings = [_stroke("l", hinge, tip, layer="Enclosure_WallInternal")]
    composition = apply_source_quarter_swing_opening_kinds(
        _composition(opening),
        drawings_by_page_id={"3": drawings},
    )
    assert composition.canonical_openings[0].opening_kind == "door"


def test_two_diagonal_leaves_on_one_opening_abstain() -> None:
    opening = _hosted(geom=(20.0, 20.0, 20.0, 17.5))
    drawings = [
        _stroke("l", (20.0, 20.0), (44.66, 44.66), layer="Enclosure_WallInternal"),
        _stroke("l", (20.0, 20.0), (44.66, -4.66), layer="Enclosure_WallInternal"),
    ]
    composition = apply_source_quarter_swing_opening_kinds(
        _composition(opening),
        drawings_by_page_id={"3": drawings},
    )
    assert composition.canonical_openings[0].opening_kind is None


def test_original_hosted_opening_at_a_detected_swing_becomes_a_door() -> None:
    from pb_layered_wall_doorway_room_ring_shadow import _swing_arcs

    original = os.environ.get("PLANREADER_3LAUREL_ORIGINAL_PDF")
    if not original or not Path(original).is_file():
        pytest.skip("private 3Laurel original not provisioned")
    with fitz.open(original) as doc:
        drawings = tuple(doc[2].get_drawings())
    arcs, _rejected = _swing_arcs(drawings)
    assert arcs
    hinge = tuple(arcs[0]["centre"])
    opening = _hosted(geom=(hinge[0] - 0.8, hinge[1], hinge[0] + 2.5, hinge[1]))
    composition = apply_source_quarter_swing_opening_kinds(
        _composition(opening),
        drawings_by_page_id={"3": drawings},
    )
    assert composition.canonical_openings[0].opening_kind == "door"


def test_window_interruption_without_a_leaf_stays_unkinded() -> None:
    opening = _hosted(geom=(100.0, 100.0, 102.5, 100.0))
    drawings = [_stroke("l", (90.0, 100.0), (110.0, 100.0))]
    composition = apply_source_quarter_swing_opening_kinds(
        _composition(opening),
        drawings_by_page_id={"3": drawings},
    )
    assert composition.canonical_openings[0].opening_kind is None
