"""Audit tests for the ported door-kind and opening-identity shadows.

The donor tests (kept as ported) cover the swing, hosting, typed-neighbour and viewport cases. These add what the
repository requires of every geometric hypothesis and what the audit of the port found: metamorphic and ordering
invariance, unrelated-content invariance, replay, no mutation, authority and wiring isolation, no project literal,
fail-closed behaviour on a look-alike, and the identity rules the port tightened.
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

from pb_layered_wall_doorway_room_ring_shadow import _swing_arcs
from pb_source_opening_identity_partition_shadow import (
    AMBIGUOUS,
    DISTINCT,
    SAME,
    cluster_live_canonical_opening_identities,
    compare_live_canonical_opening_identity,
)
import pb_source_opening_identity_partition_shadow as identity_module
import pb_source_quarter_swing_opening_kind_shadow as kind_module
from pb_source_quarter_swing_opening_kind_shadow import apply_source_quarter_swing_opening_kinds
from tests.test_live_opening_area_quantity_publication import _composition
from tests.test_source_quarter_swing_opening_kind_shadow import (
    CLOSED_TIP,
    HINGE,
    OPEN_TIP,
    RADIUS,
    _hosted,
    _quarter_swing_drawings,
    _stroke,
)

AT_HINGE = (50.0, 50.0, 52.5, 50.0)  # an interruption segment that starts exactly on the hinge


def _kind(drawings, *openings, page="3"):
    composition = apply_source_quarter_swing_opening_kinds(
        _composition(*openings), drawings_by_page_id={page: drawings},
    )
    return {item.canonical_opening_id: item.opening_kind for item in composition.canonical_openings}


# ---------------------------------------------------------------- the one edit to the shared swing detector

def test_the_shared_swing_detector_exposes_the_open_tip_and_keeps_its_old_keys():
    arcs, rejected = _swing_arcs(_quarter_swing_drawings())
    assert rejected == 0 and len(arcs) == 1
    arc = arcs[0]
    assert set(arc) == {"arc", "leaf", "centre", "open_tip", "closed_tip", "radius"}
    assert tuple(arc["centre"]) == HINGE
    assert tuple(arc["open_tip"]) == OPEN_TIP  # the arc end the leaf reaches
    assert tuple(arc["closed_tip"]) == CLOSED_TIP  # the other arc end
    assert arc["radius"] == RADIUS
    assert (arc["arc"], arc["leaf"]) == (1, 0)


# ---------------------------------------------------------------- visible paint

@pytest.mark.parametrize("opacity", [0.0, -0.5, float("nan"), float("inf") * 0.0, True, "1"])
@pytest.mark.parametrize("which", ["arc", "leaf"])
def test_a_swing_or_leaf_that_is_not_visibly_painted_never_kinds_a_door(opacity, which):
    drawings = _quarter_swing_drawings()
    drawings[1 if which == "arc" else 0]["stroke_opacity"] = opacity
    assert _kind(drawings, _hosted(geom=AT_HINGE)) == {"opening-1": None}


@pytest.mark.parametrize("opacity", [None, 1.0, 0.5])
def test_missing_or_visible_paint_still_kinds_the_door(opacity):
    drawings = _quarter_swing_drawings()
    if opacity is not None:
        for row in drawings:
            row["stroke_opacity"] = opacity
    assert _kind(drawings, _hosted(geom=AT_HINGE)) == {"opening-1": "door"}


# ---------------------------------------------------------------- metamorphic and ordering invariance

_TRANSFORMS = {
    "identity": lambda p: p,
    "translate": lambda p: (p[0] + 123.5, p[1] - 40.25),
    "rotate90": lambda p: (-p[1], p[0]),
    "rotate180": lambda p: (-p[0], -p[1]),
    "mirror": lambda p: (-p[0], p[1]),
    "scale3": lambda p: (p[0] * 3.0, p[1] * 3.0),
}


def _move_drawings(drawings, transform):
    moved = []
    for row in drawings:
        row = dict(row)
        row["items"] = [
            (item[0], *(fitz.Point(*transform((point.x, point.y))) for point in item[1:]))
            for item in row["items"]
        ]
        moved.append(row)
    return moved


def _move_geometry(geometry, transform):
    a, b = transform((geometry[0], geometry[1])), transform((geometry[2], geometry[3]))
    return (a[0], a[1], b[0], b[1])


@pytest.mark.parametrize("name", sorted(_TRANSFORMS))
def test_the_decision_survives_translation_rotation_mirror_and_scale(name):
    transform = _TRANSFORMS[name]
    drawings = _move_drawings(_quarter_swing_drawings(), transform)
    on_hinge = _hosted(geom=_move_geometry(AT_HINGE, transform), opening_id="on-hinge")
    far = _hosted(geom=_move_geometry((300.0, 300.0, 302.5, 300.0), transform), opening_id="far-away")
    assert _kind(drawings, on_hinge, far) == {"on-hinge": "door", "far-away": None}


def test_a_swing_that_is_not_an_axis_aligned_quarter_is_not_a_door_it_abstains():
    # The shared detector reads axis-aligned quarter swings. A rotated look-alike must abstain, never mis-kind.
    angle = math.radians(30.0)
    rotate = lambda p: (p[0] * math.cos(angle) - p[1] * math.sin(angle), p[0] * math.sin(angle) + p[1] * math.cos(angle))
    drawings = _move_drawings(_quarter_swing_drawings(), rotate)
    assert _kind(drawings, _hosted(geom=_move_geometry(AT_HINGE, rotate))) == {"opening-1": None}


def test_input_order_unrelated_content_and_viewport_expansion_do_not_change_the_result():
    hinged = _hosted(geom=AT_HINGE, opening_id="hinged")
    window_like = _hosted(geom=(400.0, 400.0, 402.5, 400.0), opening_id="window-like")
    base = _kind(_quarter_swing_drawings(), hinged, window_like)
    assert base == {"hinged": "door", "window-like": None}
    assert _kind(_quarter_swing_drawings(), window_like, hinged) == base  # openings reversed
    noise = [_stroke("l", (600.0 + i, 600.0), (610.0 + i, 600.0)) for i in range(30)]
    padded = noise[:10] + _quarter_swing_drawings() + noise[10:]  # every path index shifts
    assert _kind(padded, hinged, window_like) == base
    rng = random.Random(3)
    far = [
        _hosted(geom=(1000 + rng.random() * 500, 900.0, 1003 + rng.random() * 500, 900.0), opening_id=f"far-{i}")
        for i in range(25)
    ]
    expanded = _kind(_quarter_swing_drawings(), hinged, window_like, *far)
    assert {key: expanded[key] for key in base} == base and not any(expanded[f"far-{i}"] for i in range(25))


def test_an_opening_on_a_page_with_no_drawings_is_untouched():
    other_page = replace(_hosted(geom=AT_HINGE, opening_id="other"), page_id="9")
    assert _kind(_quarter_swing_drawings(), other_page, page="3") == {"other": None}


# ---------------------------------------------------------------- replay, mutation, authority

def test_replay_is_deterministic_and_the_evidence_id_is_stable_and_path_bound():
    opening = _hosted(geom=AT_HINGE)
    composition = _composition(opening)
    first = apply_source_quarter_swing_opening_kinds(composition, drawings_by_page_id={"3": _quarter_swing_drawings()})
    second = apply_source_quarter_swing_opening_kinds(composition, drawings_by_page_id={"3": _quarter_swing_drawings()})
    assert first == second
    leaf_ids = [e for e in first.canonical_openings[0].evidence_ids if e.startswith("source_drawn_door_leaf_")]
    assert len(leaf_ids) == 1 and re.fullmatch(r"source_drawn_door_leaf_[0-9a-f]{32}", leaf_ids[0])
    shifted = [_stroke("l", (700.0, 700.0), (710.0, 700.0))] + _quarter_swing_drawings()
    third = apply_source_quarter_swing_opening_kinds(composition, drawings_by_page_id={"3": shifted})
    other_ids = [e for e in third.canonical_openings[0].evidence_ids if e.startswith("source_drawn_door_leaf_")]
    assert other_ids != leaf_ids  # the id names the drawn path indices it was read from


def test_inputs_are_never_mutated_and_only_kind_and_evidence_change():
    drawings = _quarter_swing_drawings()
    opening = _hosted(geom=AT_HINGE)
    composition = _composition(opening)
    drawings_before = copy.deepcopy(drawings)
    result = apply_source_quarter_swing_opening_kinds(composition, drawings_by_page_id={"3": drawings})
    assert drawings == drawings_before
    assert composition == _composition(opening)  # a fresh, equal composition: the input was not touched
    updated = result.canonical_openings[0]
    assert updated.opening_kind == "door" and len(updated.evidence_ids) == len(opening.evidence_ids) + 1
    assert replace(updated, opening_kind=opening.opening_kind, evidence_ids=opening.evidence_ids) == opening
    assert replace(result, canonical_openings=composition.canonical_openings) == composition


def test_no_kind_is_written_without_a_hosted_unkinded_opening():
    unhosted = replace(_hosted(geom=AT_HINGE), host_wall_id=None, host_binding_record_id=None, host_frame_record_id=None)
    assert _kind(_quarter_swing_drawings(), unhosted) == {"opening-1": None}
    receipt_less = replace(_hosted(geom=AT_HINGE), host_binding_record_id=None, host_frame_record_id=None)
    assert _kind(_quarter_swing_drawings(), receipt_less) == {"opening-1": None}


# ---------------------------------------------------------------- isolation and hygiene

_ROOT = Path(__file__).resolve().parents[1]
_SHADOWS = ("pb_source_quarter_swing_opening_kind_shadow", "pb_source_opening_identity_partition_shadow")


def test_no_live_or_application_module_imports_the_shadows_yet():
    wired = [
        path for pattern in ("pb_live_*.py", "pb_new_*.py", "pb_planreader_pdf_extractor.py", "tools/*.py")
        for path in _ROOT.glob(pattern)
        if any(name in path.read_text(encoding="utf-8", errors="ignore") for name in _SHADOWS)
    ]
    assert wired == []


@pytest.mark.parametrize("module", [kind_module, identity_module])
def test_the_shadows_carry_no_project_sha_page_layer_or_width_literal(module):
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    numbers = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and type(n.value) in (int, float)}
    blob = " ".join(strings).lower()
    for banned in ("laurel", "lot16", "maryborough", "q5446", "acacia", "enclosure", "annotation_", "wallinternal"):
        assert banned not in blob
    assert not [s for s in strings if re.fullmatch(r"[0-9a-f]{40,64}", s)]
    assert not {720, 870, 900, 1200, 2100, 2400} & {n for n in numbers if type(n) is int}


# ---------------------------------------------------------------- identity partition: the rules the port tightened

def _scoped(geom, opening_id, **fields):
    return replace(_hosted(geom=geom, opening_id=opening_id), **fields)


def test_a_bare_matching_frame_string_is_not_shared_ownership_but_an_issued_receipt_is():
    geom = (10.0, 10.0, 14.0, 10.0)
    # the shared fixture gives every record the same binding receipt, so isolate the frame branch
    bare_a = _scoped(geom, "a", host_binding_record_id=None, host_frame_record_id="frame-9")
    bare_b = _scoped(geom, "b", host_binding_record_id=None, host_frame_record_id="frame-9")
    assert compare_live_canonical_opening_identity(bare_a, bare_b) == AMBIGUOUS
    issued_a = replace(bare_a, evidence_ids=(*bare_a.evidence_ids, "frame-9"))
    issued_b = replace(bare_b, evidence_ids=(*bare_b.evidence_ids, "frame-9"))
    assert compare_live_canonical_opening_identity(issued_a, issued_b) == SAME
    assert compare_live_canonical_opening_identity(issued_a, bare_b) == AMBIGUOUS  # only one side carries the receipt


def test_a_binding_receipt_must_also_be_on_both_records_evidence():
    geom = (10.0, 10.0, 14.0, 10.0)
    a = _scoped(geom, "a", host_binding_record_id="bind-7", evidence_ids=("a", "bind-7"))
    b = _scoped(geom, "b", host_binding_record_id="bind-7", evidence_ids=("b",))
    assert compare_live_canonical_opening_identity(a, b) == AMBIGUOUS
    assert compare_live_canonical_opening_identity(a, replace(b, evidence_ids=("b", "bind-7"))) == SAME


def test_scope_viewport_and_identity_rules():
    base = _scoped((10.0, 10.0, 14.0, 10.0), "a")
    twin = _scoped((60.0, 60.0, 64.0, 60.0), "b")
    assert compare_live_canonical_opening_identity(base, base) == SAME
    assert compare_live_canonical_opening_identity(base, twin) == AMBIGUOUS  # far apart is still not DISTINCT
    for field in ("document_id", "revision_id", "source_sha256", "snapshot_id", "page_id", "viewport_id"):
        assert compare_live_canonical_opening_identity(base, replace(twin, **{field: "other-" + field})) == DISTINCT, field
    same_physical = replace(twin, physical_opening_id=base.physical_opening_id)
    assert compare_live_canonical_opening_identity(base, same_physical) == SAME


def test_identity_is_symmetric_and_clusters_are_order_stable():
    rng = random.Random(21)
    pool = [
        replace(
            _scoped((rng.choice((10.0, 10.5, 40.0)), 10.0, rng.choice((14.0, 14.5, 44.0)), 10.0), f"o{i}"),
            viewport_id=rng.choice(("vp-floor-1", "vp-floor-1", "vp-other", "")),
        )
        for i in range(14)
    ]
    for left in pool:
        for right in pool:
            assert compare_live_canonical_opening_identity(left, right) == compare_live_canonical_opening_identity(right, left)
    clusters = cluster_live_canonical_opening_identities(pool)
    shuffled = pool[:]
    random.Random(4).shuffle(shuffled)
    assert {frozenset(c) for c in cluster_live_canonical_opening_identities(shuffled)} == {frozenset(c) for c in clusters}


def test_identity_refuses_foreign_objects():
    with pytest.raises(TypeError):
        compare_live_canonical_opening_identity(object(), _scoped((1.0, 1.0, 2.0, 1.0), "a"))
    with pytest.raises(TypeError):
        compare_live_canonical_opening_identity(_scoped((1.0, 1.0, 2.0, 1.0), "a"), "b")
