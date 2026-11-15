"""Unique figured width written in a painted swing binds that hosted door."""
from __future__ import annotations

from dataclasses import replace

from pb_source_swing_figured_width_shadow import (
    SwingFiguredWidthCallout,
    apply_source_swing_figured_widths,
)
from tests.test_live_opening_area_quantity_publication import _composition
from tests.test_source_quarter_swing_opening_kind_shadow import (
    _hosted,
    _quarter_swing_drawings,
)


def _callout(callout_id: str, value_mm: float, bbox) -> SwingFiguredWidthCallout:
    return SwingFiguredWidthCallout(
        callout_id=callout_id,
        value_mm=value_mm,
        text_bbox=bbox,
    )


def test_already_kinded_hosted_door_still_takes_unique_in_swing_width() -> None:
    opening = _hosted(geom=(49.2, 50.0, 52.5, 50.0), kind="door")
    composition = apply_source_swing_figured_widths(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
        dimensions_by_page_id={
            "3": (_callout("native-870", 870.0, (35.0, 35.0, 40.0, 40.0)),)
        },
    )
    updated = composition.canonical_openings[0]
    assert updated.figured_single_axis_mm == 870.0
    assert updated.figured_area_record_id == "native-870"
    assert "native-870" in updated.evidence_ids


def test_window_does_not_take_in_swing_figured_width() -> None:
    opening = _hosted(geom=(49.2, 50.0, 52.5, 50.0), kind="window")
    composition = apply_source_swing_figured_widths(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
        dimensions_by_page_id={
            "3": (_callout("native-870", 870.0, (35.0, 35.0, 40.0, 40.0)),)
        },
    )
    assert composition.canonical_openings[0].figured_single_axis_mm is None


def test_unique_figure_in_the_swing_is_the_door_width() -> None:
    opening = _hosted(geom=(49.2, 50.0, 52.5, 50.0))
    composition = apply_source_swing_figured_widths(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
        dimensions_by_page_id={
            "3": (_callout("native-870", 870.0, (35.0, 35.0, 40.0, 40.0)),)
        },
    )
    updated = composition.canonical_openings[0]
    assert updated.figured_single_axis_mm == 870.0
    assert updated.figured_area_record_id == "native-870"
    assert "native-870" in updated.evidence_ids


def test_two_figures_in_the_same_swing_stay_unbound() -> None:
    opening = _hosted(geom=(49.2, 50.0, 52.5, 50.0))
    composition = apply_source_swing_figured_widths(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
        dimensions_by_page_id={
            "3": (
                _callout("native-870", 870.0, (35.0, 35.0, 40.0, 40.0)),
                _callout("native-720", 720.0, (36.0, 36.0, 41.0, 41.0)),
            )
        },
    )
    assert composition.canonical_openings[0].figured_single_axis_mm is None


def test_figure_outside_the_swing_is_not_the_door_width() -> None:
    opening = _hosted(geom=(49.2, 50.0, 52.5, 50.0))
    composition = apply_source_swing_figured_widths(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
        dimensions_by_page_id={
            "3": (_callout("native-900", 900.0, (80.0, 80.0, 88.0, 88.0)),)
        },
    )
    assert composition.canonical_openings[0].figured_single_axis_mm is None


def test_existing_figured_width_is_not_replaced() -> None:
    opening = replace(
        _hosted(geom=(49.2, 50.0, 52.5, 50.0)),
        figured_single_axis_mm=920.0,
        figured_area_record_id="already-bound",
    )
    composition = apply_source_swing_figured_widths(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
        dimensions_by_page_id={
            "3": (_callout("native-870", 870.0, (35.0, 35.0, 40.0, 40.0)),)
        },
    )
    updated = composition.canonical_openings[0]
    assert updated.figured_single_axis_mm == 920.0
    assert updated.figured_area_record_id == "already-bound"


def test_sliding_cavity_opening_does_not_take_a_stacked_2100_by_900() -> None:
    opening = replace(
        _hosted(geom=(80.0, 80.0, 82.0, 80.0), kind=None),
        host_wall_id="opening_host_binding_group_slider",
        evidence_ids=(
            "opening-1",
            "source_sliding_leaf_opening_host_abc",
        ),
    )
    composition = apply_source_swing_figured_widths(
        _composition(opening),
        drawings_by_page_id={"3": _quarter_swing_drawings()},
        dimensions_by_page_id={
            "3": (
                _callout("native-2100", 2100.0, (80.0, 78.0, 88.0, 82.0)),
                _callout("native-900", 900.0, (80.0, 84.0, 88.0, 88.0)),
            )
        },
    )
    updated = composition.canonical_openings[0]
    assert updated.figured_single_axis_mm is None
    assert updated.area_m2 is None
    assert updated.opening_kind is None
