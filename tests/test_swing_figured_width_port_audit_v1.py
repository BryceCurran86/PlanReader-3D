"""Audit tests for the ported in-swing figured width shadow.

The donor tests cover the single binding, a window, two figures, an outside figure, an existing width and a
sliding door. These add the repository's invariance and isolation requirements and the two rules the audit found
missing: a figure that sits in two doors' swings belongs to neither (it used to belong to whichever door was processed
first), and a callout id seen twice with different values is dropped rather than resolved by order.
"""
from __future__ import annotations

import ast
import copy
from dataclasses import replace
import math
from pathlib import Path
import random
import re

import fitz
import pytest

import pb_source_swing_figured_width_shadow as width_module
from pb_source_swing_figured_width_shadow import (
    SwingFiguredWidthCallout,
    apply_source_swing_figured_widths,
    callouts_from_trusted_native_dimensions,
    point_in_painted_swing_sector,
)
from tests.test_door_kind_identity_port_audit_v1 import _TRANSFORMS, _move_drawings, _move_geometry
from tests.test_live_opening_area_quantity_publication import _composition
from tests.test_source_quarter_swing_opening_kind_shadow import (
    HINGE,
    K,
    RADIUS,
    _hosted,
    _quarter_swing_drawings,
    _stroke,
)


def _callout(callout_id, value_mm, bbox):
    return SwingFiguredWidthCallout(callout_id=callout_id, value_mm=value_mm, text_bbox=bbox)


def _widths(drawings, openings, callouts, page="3"):
    composition = apply_source_swing_figured_widths(
        _composition(*openings),
        drawings_by_page_id={page: drawings},
        dimensions_by_page_id={page: tuple(callouts)},
    )
    return {item.canonical_opening_id: item.figured_single_axis_mm for item in composition.canonical_openings}


def _second_swing():
    """A second quarter swing whose disk overlaps the fixture's: hinge (30, 50), leaf to the right, arc down-left."""
    hinge, open_tip, closed_tip = (30.0, 50.0), (55.0, 50.0), (30.0, 25.0)
    return [
        _stroke("l", hinge, open_tip),
        _stroke("c", open_tip, (open_tip[0], hinge[1] - K * RADIUS), (hinge[0] + K * RADIUS, closed_tip[1]), closed_tip),
    ]


def _two_doors():
    drawings = _quarter_swing_drawings() + _second_swing()
    first = _hosted(geom=(49.2, 50.0, 52.5, 50.0), opening_id="door-1")
    second = _hosted(geom=(29.2, 50.0, 32.5, 50.0), opening_id="door-2")
    return drawings, first, second


# the first door's swing covers x 22.5-52.5, the second's x 27.5-57.5
IN_BOTH = (38.0, 38.0, 42.0, 42.0)  # centre (40, 40): inside both disks
IN_FIRST_ONLY = (24.0, 44.0, 27.0, 47.0)  # centre (25.5, 45.5)
IN_SECOND_ONLY = (54.0, 44.0, 57.0, 47.0)  # centre (55.5, 45.5)


# ---------------------------------------------------------------- the two rules the audit added

def test_a_figure_in_two_swings_belongs_to_neither_in_any_order():
    drawings, first, second = _two_doors()
    shared = _callout("fig-shared", 870.0, IN_BOTH)
    expected = {"door-1": None, "door-2": None}
    assert _widths(drawings, (first, second), (shared,)) == expected
    assert _widths(drawings, (second, first), (shared,)) == expected  # openings reversed
    assert _widths(list(reversed(drawings)), (first, second), (shared,)) == expected  # path indices reversed


def test_a_shared_figure_does_not_stop_each_door_taking_its_own_figure():
    drawings, first, second = _two_doors()
    callouts = (
        _callout("fig-shared", 900.0, IN_BOTH),
        _callout("fig-first", 870.0, IN_FIRST_ONLY),
        _callout("fig-second", 720.0, IN_SECOND_ONLY),
    )
    # each door now has two figures in its swing (the shared one and its own), so both stay unbound: no tie-break
    assert _widths(drawings, (first, second), callouts) == {"door-1": None, "door-2": None}
    only_own = (_callout("fig-first", 870.0, IN_FIRST_ONLY), _callout("fig-second", 720.0, IN_SECOND_ONLY))
    assert _widths(drawings, (first, second), only_own) == {"door-1": 870.0, "door-2": 720.0}
    assert _widths(drawings, (second, first), only_own[::-1]) == {"door-2": 720.0, "door-1": 870.0}


def test_a_callout_id_seen_twice_with_different_content_is_dropped_not_resolved_by_order():
    one = _callout("fig", 870.0, (35.0, 35.0, 40.0, 40.0))
    other = _callout("fig", 900.0, (35.0, 35.0, 40.0, 40.0))
    moved = _callout("fig", 870.0, (36.0, 35.0, 41.0, 40.0))
    assert callouts_from_trusted_native_dimensions([one, one]) == (one,)  # identical copies collapse
    assert callouts_from_trusted_native_dimensions([one, other]) == ()
    assert callouts_from_trusted_native_dimensions([other, one]) == ()
    assert callouts_from_trusted_native_dimensions([one, moved]) == ()
    kept = _callout("keep", 720.0, (1.0, 1.0, 2.0, 2.0))
    assert callouts_from_trusted_native_dimensions([one, kept, other]) == (kept,)
    drawings = _quarter_swing_drawings()
    opening = _hosted(geom=(49.2, 50.0, 52.5, 50.0))
    assert _widths(drawings, (opening,), (one, other)) == {"opening-1": None}
    assert _widths(drawings, (opening,), (other, one)) == {"opening-1": None}


# ---------------------------------------------------------------- input validation

class _Dim:
    def __init__(self, dimension_id, value_mm, text_bbox):
        self.dimension_id, self.value_mm, self.text_bbox = dimension_id, value_mm, text_bbox


@pytest.mark.parametrize("bad", [
    _Dim("", 870.0, (1, 1, 2, 2)),
    _Dim("   ", 870.0, (1, 1, 2, 2)),
    _Dim(7, 870.0, (1, 1, 2, 2)),
    _Dim("x", 0.0, (1, 1, 2, 2)),
    _Dim("x", -5.0, (1, 1, 2, 2)),
    _Dim("x", True, (1, 1, 2, 2)),
    _Dim("x", "870", (1, 1, 2, 2)),
    _Dim("x", float("nan"), (1, 1, 2, 2)),
    _Dim("x", float("inf"), (1, 1, 2, 2)),
    _Dim("x", 870.0, (1, 1, 2)),
    _Dim("x", 870.0, (1, 1, float("nan"), 2)),
    _Dim("x", 870.0, ("a", "b", "c", "d")),
    _Dim("x", 870.0, None),
    object(),
])
def test_malformed_dimensions_never_become_callouts(bad):
    assert callouts_from_trusted_native_dimensions([bad]) == ()


def test_a_duck_typed_dimension_with_the_three_fields_is_a_callout():
    got = callouts_from_trusted_native_dimensions([_Dim("dim-1", 870, [1, 2, 3, 4])])
    assert got == (SwingFiguredWidthCallout("dim-1", 870.0, (1.0, 2.0, 3.0, 4.0)),)


# ---------------------------------------------------------------- the swing sector

@pytest.mark.parametrize("dx,dy,inside", [
    (0.0, 0.0, True), (-12.0, -12.0, True), (-24.9, 0.0, True), (-27.4, 0.0, True), (-27.5, 0.0, True),
    (-27.6, 0.0, False), (0.0, -27.5, True), (0.0, -27.6, False), (+2.4, 0.0, True), (+2.6, 0.0, False),
    (-12.0, +2.4, True), (-12.0, +2.6, False), (-30.0, -30.0, False),
])
def test_a_point_is_in_the_swing_only_inside_the_quarter_disk_plus_the_snap(dx, dy, inside):
    assert point_in_painted_swing_sector(
        centre=HINGE, open_tip=(25.0, 50.0), closed_tip=(50.0, 25.0), radius=RADIUS,
        point=(HINGE[0] + dx, HINGE[1] + dy),
    ) is inside


# ---------------------------------------------------------------- invariance, replay, mutation

def _bbox_after(bbox, transform):
    a, b = transform((bbox[0], bbox[1])), transform((bbox[2], bbox[3]))
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))


@pytest.mark.parametrize("name", sorted(_TRANSFORMS))
def test_the_binding_survives_translation_rotation_mirror_and_scale(name):
    transform = _TRANSFORMS[name]
    opening = _hosted(geom=(50.0, 50.0, 52.5, 50.0), opening_id="the-door")
    inside = _callout("inside", 870.0, (35.0, 35.0, 40.0, 40.0))
    outside = _callout("outside", 720.0, (300.0, 300.0, 305.0, 305.0))
    drawings = _move_drawings(_quarter_swing_drawings(), transform)
    moved_opening = replace(opening, source_geometries=(_move_geometry(opening.source_geometries[0], transform),))
    moved = tuple(replace(c, text_bbox=_bbox_after(c.text_bbox, transform)) for c in (inside, outside))
    assert _widths(drawings, (moved_opening,), moved) == {"the-door": 870.0}


def test_callout_and_opening_order_unrelated_content_and_viewport_expansion_do_not_change_the_result():
    drawings = _quarter_swing_drawings()
    door = _hosted(geom=(49.2, 50.0, 52.5, 50.0), opening_id="door")
    far_window = _hosted(geom=(500.0, 500.0, 503.0, 500.0), opening_id="far", kind="window")
    figure = _callout("fig", 870.0, (35.0, 35.0, 40.0, 40.0))
    base = _widths(drawings, (door, far_window), (figure,))
    assert base == {"door": 870.0, "far": None}
    assert _widths(drawings, (far_window, door), (figure,)) == base
    rng = random.Random(8)
    noise = [_callout(f"n{i}", 900.0 + i, (1000 + rng.random() * 800, 900.0, 1004 + rng.random() * 800, 905.0)) for i in range(25)]
    assert _widths(drawings, (door, far_window), (*noise[:12], figure, *noise[12:])) == base
    padded = [_stroke("l", (700.0 + i, 700.0), (710.0 + i, 700.0)) for i in range(20)] + drawings
    assert _widths(padded, (door, far_window), (figure,)) == base


def test_replay_is_deterministic_inputs_are_untouched_and_only_the_width_fields_change():
    drawings = _quarter_swing_drawings()
    door = _hosted(geom=(49.2, 50.0, 52.5, 50.0), opening_id="door")
    composition = _composition(door)
    figure = _callout("fig", 870.0, (35.0, 35.0, 40.0, 40.0))
    drawings_before = copy.deepcopy(drawings)
    first = apply_source_swing_figured_widths(composition, drawings_by_page_id={"3": drawings}, dimensions_by_page_id={"3": (figure,)})
    second = apply_source_swing_figured_widths(composition, drawings_by_page_id={"3": drawings}, dimensions_by_page_id={"3": (figure,)})
    assert first == second and drawings == drawings_before and composition == _composition(door)
    updated = first.canonical_openings[0]
    assert updated.figured_single_axis_mm == 870.0 and updated.figured_area_record_id == "fig"
    assert updated.evidence_ids[-1] == "fig" and updated.evidence_ids[:-1] == door.evidence_ids
    assert replace(
        updated, figured_single_axis_mm=None, figured_area_record_id=door.figured_area_record_id, evidence_ids=door.evidence_ids,
    ) == door
    assert replace(first, canonical_openings=composition.canonical_openings) == composition


def test_nothing_is_written_when_there_is_no_hosted_door_drawing_or_callout():
    drawings = _quarter_swing_drawings()
    door = _hosted(geom=(49.2, 50.0, 52.5, 50.0), opening_id="door")
    figure = _callout("fig", 870.0, (35.0, 35.0, 40.0, 40.0))
    assert _widths(drawings, (door,), ()) == {"door": None}
    assert _widths([], (door,), (figure,)) == {"door": None}
    unhosted = replace(door, host_wall_id=None, host_binding_record_id=None, host_frame_record_id=None)
    assert _widths(drawings, (unhosted,), (figure,)) == {"door": None}
    other_page = replace(door, page_id="9")
    assert _widths(drawings, (other_page,), (figure,), page="3") == {"door": None}
    with pytest.raises(TypeError):
        apply_source_swing_figured_widths(object(), drawings_by_page_id={}, dimensions_by_page_id={})


# ---------------------------------------------------------------- isolation and hygiene

_ROOT = Path(__file__).resolve().parents[1]


def test_no_live_or_application_module_imports_the_width_shadow_yet():
    wired = [
        path for pattern in ("pb_live_*.py", "pb_new_*.py", "pb_planreader_pdf_extractor.py", "tools/*.py")
        for path in _ROOT.glob(pattern)
        if "pb_source_swing_figured_width_shadow" in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert wired == []


def test_the_width_shadow_carries_no_project_sha_page_layer_or_width_literal():
    tree = ast.parse(Path(width_module.__file__).read_text(encoding="utf-8"))
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    numbers = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and type(n.value) in (int, float)}
    blob = " ".join(strings).lower()
    for banned in ("laurel", "lot16", "maryborough", "q5446", "acacia", "enclosure", "annotation_"):
        assert banned not in blob
    assert not [s for s in strings if re.fullmatch(r"[0-9a-f]{40,64}", s)]
    assert not {720, 870, 900, 1200, 2100, 2400} & {n for n in numbers if type(n) is int}
    assert math.isfinite(width_module._SWING_OPENING_BIND_PT)  # the snap is the kind shadow's, not a second constant
