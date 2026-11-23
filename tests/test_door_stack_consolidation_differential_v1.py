"""Door stack consolidation: before/after differential and seam tests for the two-wall tag chain.

The chain is the owner contract ``pb_opening_two_wall_contact_tags`` (#4638, hardened by #4654 and #4655), the ring adapter
``tag_native_segmented_doorway_chords`` that the layered ring calls, the wall-end core ``pb_source_door_wall_end_sections``
and the internal-door front end ``pb_source_internal_door_two_wall_tags`` (#4649).

Every scene is synthetic: no source PDF, project name, benchmark value or file name is an input. The goldens in
``tests/fixtures/door_stack_consolidation_goldens_v1.json`` were produced by running these same scenes on the #4649 head
(before the consolidation) and on the consolidated head (after). A case differs between the two only where ``DELTA_CASES``
says so, and ``test_each_documented_delta_is_a_real_difference`` proves the difference in both directions. Receipt order
(the chord index for the adapter, ``(symbol_kind, mark path ids, entry id)`` for the front end) and every source path id
are part of what is pinned. Nothing here grants authority: every tag stays topology only.
"""
from __future__ import annotations

import ast
import collections
import copy
import dataclasses
import json
import math
import random
import types
from pathlib import Path

import fitz
import pytest

import pb_opening_two_wall_contact_tags as contract
import pb_source_door_wall_end_sections as core_mod
import pb_source_internal_door_two_wall_tags as front_mod
from pb_layered_wall_doorway_room_ring_shadow import _Gap, build_layered_wall_doorway_room_rings
from pb_opening_two_wall_contact_tags import (
    DetectedOpeningContacts,
    OpeningWallContact,
    TracedWallSection,
    tag_native_segmented_doorway_chords,
    tag_opening_to_two_wall_sections,
)
from pb_source_door_wall_end_sections import Blocked, WallEndReceipt, build_contract_inputs
from pb_source_internal_door_completeness_shadow import SourceInternalDoorMark
from pb_source_segmented_door_swing_shadow import propose_source_owned_doorway_chords

REPO = Path(__file__).resolve().parents[1]
GOLDEN_PATH = Path(__file__).resolve().parent / "fixtures" / "door_stack_consolidation_goldens_v1.json"
SCOPE = ("a" * 64, "revision-a", "page-3")
BLACK = (0.0, 0.0, 0.0)
WHITE = (1.0, 1.0, 1.0)
TAGGED = "TWO_WALL_SECTIONS_TAGGED"
UNRESOLVED = "UNRESOLVED"
WALL_LAYER = "Enclosure_WallInternal"

# Cases whose output changes on purpose. before = the #4649 head, after = the consolidated head.
DELTA_CASES = {
    "adapter_zero_width_chord",
    "adapter_collections_not_list_or_tuple",
    "contract_oversized_integer_contact",
    "core_malformed_native_points",
    "core_oversized_integer_anchors",
    "adapter_duck_typed_chord",
}

# ---------------------------------------------------------------------------------------------------------------------
# native rows
# ---------------------------------------------------------------------------------------------------------------------


def hair(a, b, *, layer=None):
    row = {"fill": None, "color": BLACK, "items": [("l", fitz.Point(*a), fitz.Point(*b))]}
    if layer is not None:
        row["layer"] = layer
    return row


def poly(x0, y0, x1, y1, *, fill=BLACK, layer=""):
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    items = tuple(("l", fitz.Point(*corners[i]), fitz.Point(*corners[(i + 1) % 4])) for i in range(4))
    return {"layer": layer, "rect": fitz.Rect(x0, y0, x1, y1), "type": "f", "fill": fill, "color": None, "items": items}


def rule(x0, y0, x1, y1):
    return {"layer": "", "rect": fitz.Rect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)), "type": "s",
            "fill": None, "color": BLACK, "width": 0.48, "items": (("l", fitz.Point(x0, y0), fitz.Point(x1, y1)),)}


def pocket(x_end, x_far, y0, y1, lip=0.57):
    pts = [(x_far, y0), (x_end, y0), (x_end, y0 + lip), (x_far + 1.4, y0 + lip), (x_far + 1.4, y1 - lip),
           (x_end, y1 - lip), (x_end, y1), (x_far, y1)]
    items = tuple(("l", fitz.Point(*pts[i]), fitz.Point(*pts[(i + 1) % len(pts)])) for i in range(len(pts)))
    return {"layer": "", "rect": fitz.Rect(min(x_far, x_end), y0, max(x_far, x_end), y1), "type": "f",
            "fill": BLACK, "color": None, "items": items}


def any_size_door(width, *, vertical=False, threshold=False, missing_right=False, dx=0.0, dy=0.0, scale=1.0):
    """CAD black strokes at a door's genuine sides, then the swing witness and the raw parent gap (no project coordinates)."""
    lo, hi, perp = 21.0, 21.0 + width, 78.0
    off_along, off_across = (dy, dx) if vertical else (dx, dy)

    def point(along, across):
        x, y = (across, along) if vertical else (along, across)
        return (x * scale + dx, y * scale + dy)

    def stroke(start, end):
        return {"fill": None, "color": BLACK, "items": [("l", fitz.Point(*point(*start)), fitz.Point(*point(*end)))]}

    native = [
        stroke((lo - 4, perp), (lo, perp)), stroke((hi, perp), (hi + 4, perp)),
        stroke((lo, perp - 3), (lo, perp)), stroke((hi, perp - 3), (hi, perp)),
    ]
    if missing_right:
        native.pop(1)
    if threshold:
        native.append(stroke((lo, perp), (hi, perp)))
    witness = {
        "native_source_path_indices": (100, 101, 102),
        "source_hinge_point_pdf_pts": point(hi, perp),
        "source_closed_leaf_tip_pdf_pts": point(lo, perp),
    }
    parent = _Gap(
        not vertical, ((perp - 4) * scale + off_across, (perp + 1) * scale + off_across),
        lo * scale + off_along, (hi + width * 4) * scale + off_along, (90,), (91,), False,
    )
    return native, witness, parent


def seam(width, **kwargs):
    drawings, witness, parent = any_size_door(width, **kwargs)
    return drawings, propose_source_owned_doorway_chords(drawings, [witness], [parent])


# ---------------------------------------------------------------------------------------------------------------------
# dumps: JSON-stable views of every receipt (order and source path ids included)
# ---------------------------------------------------------------------------------------------------------------------


def _num(value):
    if isinstance(value, float):
        return round(value, 6) if math.isfinite(value) else repr(value)
    if isinstance(value, (tuple, list)):
        return [_num(v) for v in value]
    return value


def tag_dump(tag):
    return {
        "opening_id": tag.opening_id, "status": tag.status, "reason": tag.reason,
        "wall_section_ids": list(tag.wall_section_ids), "contact_geometry": tag.contact_geometry,
        "candidate_sections_first": list(tag.candidate_sections_first),
        "candidate_sections_second": list(tag.candidate_sections_second),
        "source_topology_only": tag.source_topology_only,
        "physical_host_authorized": tag.physical_host_authorized, "measurement_authorized": tag.measurement_authorized,
    }


def tags_dump(tags):
    return [tag_dump(t) for t in tags]


def captured(fn):
    """The case's JSON view, or the name of the exception it raised (a before/after difference worth pinning)."""
    try:
        return json.loads(json.dumps(fn(), sort_keys=True))
    except Exception as exc:  # noqa: BLE001 - recorded, never swallowed silently
        return {"raised": type(exc).__name__}


def core_dump(rows, receipt):
    built = build_contract_inputs(rows, receipt)
    if isinstance(built, Blocked):
        return {"blocked": built.reason}
    contacts, sections = built
    tag = tag_opening_to_two_wall_sections(contacts, sections)
    return {
        "tag": tag_dump(tag),
        "sections": [{"id": s.section_id, "native_path_ids": list(s.native_path_ids), "start": _num(s.start_pdf_pts),
                      "end": _num(s.end_pdf_pts)} for s in sections],
        "contacts": [{"position": _num(c.position_pdf_pts), "wall_end_native_path_ids": list(c.wall_end_native_path_ids)}
                     for c in (contacts.first, contacts.second)],
        "opening_native_path_ids": list(contacts.opening_native_path_ids),
    }


# ---------------------------------------------------------------------------------------------------------------------
# the case registry
# ---------------------------------------------------------------------------------------------------------------------

CASES: dict = {}


def case(name):
    def register(fn):
        assert name not in CASES, name
        CASES[name] = fn
        return fn
    return register


# --- the producer-to-adapter seam: any width, either orientation, with and without a threshold line --------------------
for _width in (23.0, 52.08, 90.0, 138.0):
    for _vertical in (False, True):
        for _threshold in (False, True):
            def _seam_case(width=_width, vertical=_vertical, threshold=_threshold):
                drawings, chords = seam(width, vertical=vertical, threshold=threshold)
                return {"chords": len(chords), "tags": tags_dump(tag_native_segmented_doorway_chords(drawings, chords, scope=SCOPE))}
            CASES[f"adapter_seam_w{_width}_{'v' if _vertical else 'h'}_{'thr' if _threshold else 'plain'}"] = _seam_case


def _base_chord():
    drawings, chords = seam(52.08)
    assert len(chords) == 1
    return drawings, dict(chords[0])


def _tags(drawings, chords, scope=SCOPE):
    return tags_dump(tag_native_segmented_doorway_chords(drawings, chords, scope=scope))


@case("adapter_contacts_reversed")
def _():
    drawings, chord = _base_chord()
    chord["source_wall_end_left_path_indices"], chord["source_wall_end_right_path_indices"] = (
        chord["source_wall_end_right_path_indices"], chord["source_wall_end_left_path_indices"])
    return _tags(drawings, [chord])


@case("adapter_interval_and_band_reversed")
def _():
    drawings, chord = _base_chord()
    lo, hi = chord["door_interval_pdf_pts"]
    band_lo, band_hi = chord["wall_band_pdf_pts"]
    return _tags(drawings, [dict(chord, door_interval_pdf_pts=(hi, lo)), dict(chord, wall_band_pdf_pts=(band_hi, band_lo))])


@case("adapter_chord_repeated")
def _():
    drawings, chord = _base_chord()
    return _tags(drawings, [chord, chord, dict(chord)])


@case("adapter_infinite_and_nan_widths")
def _():
    drawings, chord = _base_chord()
    lo, hi = chord["door_interval_pdf_pts"]
    inf, nan = float("inf"), float("nan")
    variants = [dict(chord, door_interval_pdf_pts=(lo, inf)), dict(chord, door_interval_pdf_pts=(nan, hi)),
                dict(chord, door_interval_pdf_pts=(-inf, hi)), dict(chord, wall_band_pdf_pts=(-inf, inf))]
    return _tags(drawings, variants)


@case("adapter_oversized_integer_widths")
def _():
    drawings, chord = _base_chord()
    lo, hi = chord["door_interval_pdf_pts"]
    return _tags(drawings, [dict(chord, door_interval_pdf_pts=(lo, 10 ** 400)),
                            dict(chord, door_interval_pdf_pts=(-10 ** 400, hi)),
                            dict(chord, wall_band_pdf_pts=(0, 10 ** 400))])


@case("adapter_boolean_and_text_numbers")
def _():
    drawings, chord = _base_chord()
    lo, hi = chord["door_interval_pdf_pts"]
    return _tags(drawings, [dict(chord, door_interval_pdf_pts=(True, hi)), dict(chord, door_interval_pdf_pts=("21", hi)),
                            dict(chord, horizontal=1)])


@case("adapter_non_mapping_chord")
def _():
    drawings, chord = _base_chord()
    return _tags(drawings, [None, chord, "chord", 7])


class _DuckChord:
    """Not a Mapping, but answers chord[key]: a record type the adapter must not read as a source receipt."""

    def __init__(self, chord):
        self._chord = chord

    def __getitem__(self, key):
        return self._chord[key]


@case("adapter_duck_typed_chord")
def _():
    drawings, chord = _base_chord()
    return {"duck_alone": _tags(drawings, [_DuckChord(chord)]), "duck_between_two_mappings": _tags(drawings, [chord, _DuckChord(chord), chord])}


@case("adapter_missing_keys")
def _():
    drawings, chord = _base_chord()
    return _tags(drawings, [{k: v for k, v in chord.items() if k != key} for key in sorted(chord)[:6]])


@case("adapter_invalid_scope")
def _():
    drawings, chord = _base_chord()
    return {"empty_scope": _tags(drawings, [chord], scope=()), "one_part": _tags(drawings, [chord], scope=("x",)),
            "blank_part": _tags(drawings, [chord], scope=("x", " ")), "list_scope": _tags(drawings, [chord], scope=["a", "b"])}


@case("adapter_competing_wall_ends")
def _():
    drawings, chord = _base_chord()
    lo, hi = chord["door_interval_pdf_pts"]
    perp = 78.0
    extra = hair((lo - 5, perp + 0.5), (lo, perp + 0.5))   # a second stroke that also ends at the interval start
    drawings = [*drawings, extra]
    chord = dict(chord, source_wall_end_left_path_indices=(*chord["source_wall_end_left_path_indices"], len(drawings) - 1))
    return _tags(drawings, [chord])


@case("adapter_stroke_with_both_endpoints_at_the_contact")
def _():
    """A degenerate stroke whose two ends are both at the interval start is ambiguous: never elected as a wall end."""
    drawings, chord = _base_chord()
    lo, hi = chord["door_interval_pdf_pts"]
    tiny = hair((lo, 77.0), (lo, 77.1))
    drawings = [*drawings, tiny]
    return _tags(drawings, [dict(chord, source_wall_end_left_path_indices=(*chord["source_wall_end_left_path_indices"], len(drawings) - 1))])


@case("adapter_wall_end_in_and_beyond_the_band_slack")
def _():
    """The adapter reads a wall end up to 3 pt outside the stated wall band; one at 5 pt outside is not a contact."""
    def scene(offset):
        drawings = [hair((0.0, 79.0 + offset), (10.0, 79.0 + offset)), hair((20.0, 79.0 + offset), (30.0, 79.0 + offset))]
        chord = {"horizontal": True, "door_interval_pdf_pts": (10.0, 20.0), "wall_band_pdf_pts": (74.0, 79.0),
                 "source_wall_end_left_path_indices": (0,), "source_wall_end_right_path_indices": (1,),
                 "source_swing_native_path_indices": (80,)}
        return _tags(drawings, [chord])
    return {"inside_the_band": scene(0.0), "in_the_slack": scene(1.5), "beyond_the_slack": scene(5.0)}


@case("adapter_wall_end_around_the_endpoint_tolerance")
def _():
    """The contract's original-PDF endpoint tolerance is 0.18 pt: 0.17 is a contact, 0.19 is not."""
    def scene(offset):
        drawings = [hair((0.0, 78.0), (10.0 + offset, 78.0)), hair((20.0, 78.0), (30.0, 78.0))]
        chord = {"horizontal": True, "door_interval_pdf_pts": (10.0, 20.0), "wall_band_pdf_pts": (74.0, 79.0),
                 "source_wall_end_left_path_indices": (0,), "source_wall_end_right_path_indices": (1,),
                 "source_swing_native_path_indices": (80,)}
        return _tags(drawings, [chord])
    return {"exact": scene(0.0), "inside_0_17": scene(0.17), "outside_0_19": scene(0.19), "outside_0_4": scene(0.4)}


@case("adapter_wall_runs_through_the_opening")
def _():
    drawings, chord = _base_chord()
    lo, hi = chord["door_interval_pdf_pts"]
    perp = 78.0
    drawings = [*drawings, hair((lo - 4, perp), (hi + 4, perp))]   # one stroke through the whole interval, no end at it
    through = len(drawings) - 1
    return _tags(drawings, [dict(chord, source_wall_end_left_path_indices=(through,),
                                 source_wall_end_right_path_indices=(through,))])


@case("adapter_perpendicular_corner")
def _():
    drawings = [hair((0.0, 10.0), (10.0, 10.0)), hair((20.0, 10.0), (20.0, 25.0))]
    chord = {"horizontal": True, "door_interval_pdf_pts": (10.0, 20.0), "wall_band_pdf_pts": (7.0, 12.0),
             "source_wall_end_left_path_indices": (0,), "source_wall_end_right_path_indices": (1,),
             "source_swing_native_path_indices": (80,)}
    return _tags(drawings, [chord])


@case("adapter_zero_width_chord")
def _():
    drawings = [hair((0.0, 10.0), (10.0, 10.0)), hair((10.0, 10.0), (10.0, 0.0))]
    chord = {"horizontal": True, "door_interval_pdf_pts": (10.0, 10.0), "wall_band_pdf_pts": (7.0, 12.0),
             "source_wall_end_left_path_indices": (0,), "source_wall_end_right_path_indices": (1,),
             "source_swing_native_path_indices": (80,)}
    return _tags(drawings, [chord])


@case("adapter_solid_pier_between_two_openings")
def _():
    drawings = [hair((0.0, 10.0), (10.0, 10.0)), hair((20.0, 10.0), (30.0, 10.0)), hair((40.0, 10.0), (50.0, 10.0))]

    def chord(lo, hi, left, right):
        return {"horizontal": True, "door_interval_pdf_pts": (lo, hi), "wall_band_pdf_pts": (7.0, 12.0),
                "source_wall_end_left_path_indices": (left,), "source_wall_end_right_path_indices": (right,),
                "source_swing_native_path_indices": (80 + left,)}
    return _tags(drawings, [chord(10.0, 20.0, 0, 1), chord(30.0, 40.0, 1, 2)])


@case("adapter_wall_end_split_in_two_strokes")
def _():
    drawings = [hair((0.0, 10.0), (6.0, 10.0)), hair((6.0, 10.0), (10.0, 10.0)), hair((20.0, 10.0), (30.0, 10.0))]
    chord = {"horizontal": True, "door_interval_pdf_pts": (10.0, 20.0), "wall_band_pdf_pts": (7.0, 12.0),
             "source_wall_end_left_path_indices": (0, 1), "source_wall_end_right_path_indices": (2,),
             "source_swing_native_path_indices": (80,)}
    return _tags(drawings, [chord])


@case("adapter_unrelated_rows_added")
def _():
    drawings, chords = seam(52.08)
    far = [hair((5000.0 + i, 5000.0), (5010.0 + i, 5000.0)) for i in range(5)]
    return {"with_unrelated_rows": _tags([*drawings, *far], chords), "plain": _tags(drawings, chords)}


@case("adapter_rows_changed_between_calls")
def _():
    drawings, chords = seam(52.08)
    first = _tags(drawings, chords)
    moved = list(drawings)
    moved[chords[0]["source_wall_end_left_path_indices"][0]] = hair((0.0, 78.0), (3.0, 78.0))
    return {"first": first, "after_the_wall_end_moved": _tags(moved, chords), "third": _tags(drawings, chords)}


@case("adapter_collections_not_list_or_tuple")
def _():
    drawings, chords = seam(52.08)
    return {"drawings_user_list": _tags(collections.UserList(drawings), chords),
            "chords_user_list": _tags(drawings, collections.UserList(chords)),
            "chords_generator": _tags(drawings, (c for c in chords)),
            "plain_tuple": _tags(tuple(drawings), tuple(chords))}


@case("adapter_none_and_empty_rows")
def _():
    drawings, chords = seam(52.08)
    holes = [None if i % 2 else row for i, row in enumerate(drawings)]
    return {"none_rows": _tags(holes, chords), "no_rows": _tags([], chords), "no_chords": _tags(drawings, [])}


# --- the contract called directly ---------------------------------------------------------------------------------------


def _wall(ident, paths, a, b, scope=SCOPE):
    return TracedWallSection(ident, scope, paths, a, b)


def _opening(a=(10.0, 0.0), b=(12.0, 0.0), *, a_paths=(100,), b_paths=(200,), scope=SCOPE, oid="opening-a"):
    return DetectedOpeningContacts(oid, scope, (300, 301), OpeningWallContact(a, a_paths), OpeningWallContact(b, b_paths))


def _straight():
    return (_wall("segment-before", (100,), (0.0, 0.0), (10.0, 0.0)), _wall("segment-after", (200,), (12.0, 0.0), (20.0, 0.0)))


@case("contract_straight_gap")
def _():
    return tag_dump(tag_opening_to_two_wall_sections(_opening(), _straight()))


@case("contract_contacts_reversed_and_sections_shuffled")
def _():
    a, b = _straight()
    swapped = _opening((12.0, 0.0), (10.0, 0.0), a_paths=(200,), b_paths=(100,))
    return {"normal": tag_dump(tag_opening_to_two_wall_sections(_opening(), (a, b))),
            "sections_shuffled": tag_dump(tag_opening_to_two_wall_sections(_opening(), (b, a))),
            "contacts_swapped": tag_dump(tag_opening_to_two_wall_sections(swapped, (a, b)))}


@case("contract_perpendicular_corner")
def _():
    return tag_dump(tag_opening_to_two_wall_sections(
        _opening((10.0, 0.0), (14.0, 4.0), a_paths=(100,), b_paths=(200,)),
        (_wall("w-a", (100,), (0.0, 0.0), (10.0, 0.0)), _wall("w-b", (200,), (14.0, 4.0), (14.0, 20.0)))))


@case("contract_junction_coincident_contacts")
def _():
    return tag_dump(tag_opening_to_two_wall_sections(
        _opening((10.0, 0.0), (10.0, 0.0)),
        (_wall("w-a", (100,), (0.0, 0.0), (10.0, 0.0)), _wall("w-b", (200,), (10.0, 0.0), (10.0, 14.0)))))


@case("contract_competing_sections_at_one_contact")
def _():
    a, b = _straight()
    twin = _wall("segment-before-twin", (100,), (0.0, 0.0), (10.0, 0.0))
    return tag_dump(tag_opening_to_two_wall_sections(_opening(), (b, twin, a)))


@case("contract_competing_sections_on_both_sides")
def _():
    a, b = _straight()
    twin_before = _wall("segment-before-twin", (100,), (0.0, 0.0), (10.0, 0.0))
    twin_after = _wall("segment-after-twin", (200,), (12.0, 0.0), (20.0, 0.0))
    return {"unsorted_input": tag_dump(tag_opening_to_two_wall_sections(_opening(), (twin_after, twin_before, b, a))),
            "sorted_input": tag_dump(tag_opening_to_two_wall_sections(_opening(), (a, twin_before, b, twin_after)))}


@case("contract_duplicate_section_ids")
def _():
    a, b = _straight()
    clone = _wall("segment-before", (100,), (0.0, 0.0), (10.0, 0.0))   # the same id again
    return tag_dump(tag_opening_to_two_wall_sections(_opening(), (a, clone, b)))


@case("contract_one_wall_cannot_supply_both_sides")
def _():
    w = _wall("only", (100, 200), (0.0, 0.0), (10.0, 0.0))
    return tag_dump(tag_opening_to_two_wall_sections(_opening((10.0, 0.0), (10.0, 0.0), a_paths=(100,), b_paths=(200,)), (w,)))


@case("contract_straight_wall_runs_into_the_gap")
def _():
    into_the_gap = (_wall("a", (100,), (10.0, 0.0), (14.0, 0.0)), _wall("b", (200,), (12.0, 0.0), (20.0, 0.0)))
    return tag_dump(tag_opening_to_two_wall_sections(_opening((10.0, 0.0), (12.0, 0.0)), into_the_gap))


@case("contract_zero_span_collinear")
def _():
    return tag_dump(tag_opening_to_two_wall_sections(
        _opening((10.0, 0.0), (10.0, 0.0)),
        (_wall("w-a", (100,), (0.0, 0.0), (10.0, 0.0)), _wall("w-b", (200,), (10.0, 0.0), (20.0, 0.0)))))


@case("contract_infinite_and_boolean_contacts")
def _():
    a, b = _straight()
    return [tag_dump(tag_opening_to_two_wall_sections(_opening((float("inf"), 0.0)), (a, b))),
            tag_dump(tag_opening_to_two_wall_sections(_opening((float("nan"), 0.0)), (a, b))),
            tag_dump(tag_opening_to_two_wall_sections(_opening((True, 0.0)), (a, b)))]


@case("contract_oversized_integer_contact")
def _():
    a, b = _straight()
    return tag_dump(tag_opening_to_two_wall_sections(_opening((10 ** 400, 0.0)), (a, b)))


@case("contract_wrong_scope_or_revision")
def _():
    a, b = _straight()
    other = ("a" * 64, "revision-b", "page-3")
    return [tag_dump(tag_opening_to_two_wall_sections(_opening(scope=other), (a, b))),
            tag_dump(tag_opening_to_two_wall_sections(_opening(), (a, _wall("segment-after", (200,), (12.0, 0.0), (20.0, 0.0), other))))]


# --- the wall-end core on every convention ----------------------------------------------------------------------------

CAPS = ((10.0, 99.7, 11.1, 102.3), (34.9, 99.7, 36.0, 102.3))


def _leaf():
    return rule(11.1, 95.0, 34.9, 95.0)


def _receipt(first, second, anchors, *, opening=(0,), opening_id="opening-a", scope=SCOPE):
    return WallEndReceipt(opening_id, scope, opening, first, second, tuple(anchors))


def strip_scene():
    return [poly(0.0, 100.0, 10.0, 102.0), poly(36.0, 100.0, 60.0, 102.0), _leaf()], _receipt((0,), (1,), CAPS, opening=(2,))


def outlined_scene():
    rows = [rule(0.0, 100.0, 10.0, 100.0), rule(0.0, 102.0, 10.0, 102.0), rule(36.0, 100.0, 60.0, 100.0),
            rule(36.0, 102.0, 60.0, 102.0), _leaf()]
    return rows, _receipt((0, 1), (2, 3), CAPS, opening=(4,))


def outlined_end_cap_scene():
    rows = [rule(0.0, 100.0, 10.0, 100.0), rule(0.0, 102.0, 10.0, 102.0), rule(10.0, 100.0, 10.0, 102.0),
            rule(36.0, 100.0, 60.0, 100.0), rule(36.0, 102.0, 60.0, 102.0), rule(36.0, 100.0, 36.0, 102.0), _leaf()]
    return rows, _receipt((0, 1, 2), (3, 4, 5), CAPS, opening=(6,))


def hairline_scene():
    rows = [rule(0.0, 101.0, 10.0, 101.0), rule(36.0, 101.0, 60.0, 101.0), _leaf()]
    return rows, _receipt((0,), (1,), ((10.0, 100.0, 11.0, 102.0), (35.0, 100.0, 36.0, 102.0)), opening=(2,))


def pocket_scene():
    rows = [pocket(10.0, 0.0, 100.0, 102.55), pocket(36.0, 60.0, 100.0, 102.55), _leaf()]
    anchors = ((10.0, 99.7, 11.1, 102.9), (10.0, 99.9, 11.1, 102.6), (34.9, 101.8, 36.0, 102.9))
    return rows, _receipt((0,), (1,), anchors, opening=(2,))


def corner_scene():
    rows = [poly(0.0, 100.0, 10.0, 102.0), poly(10.0, 80.0, 12.0, 100.0), _leaf()]
    return rows, _receipt((0,), (1,), ((10.0, 99.7, 11.1, 102.3), (9.7, 100.0, 12.3, 101.1)), opening=(2,))


def junction_scene():
    rows = [poly(0.0, 100.0, 10.0, 102.0), poly(9.0, 80.0, 11.0, 101.0), _leaf()]
    return rows, _receipt((0,), (1,), ((10.0, 100.0, 11.0, 102.0), (9.0, 101.0, 11.0, 102.0)), opening=(2,))


def face_scene():
    rows = [poly(0.0, 100.0, 10.0, 102.0), poly(36.0, 60.0, 38.0, 140.0), _leaf()]
    return rows, _receipt((0,), (1,), CAPS, opening=(2,))


def pier_scene():
    """Two doorways, one solid pier between them: the pier is a wall end of BOTH, and no tag spans the pier."""
    rows = [poly(0.0, 100.0, 10.0, 102.0), poly(36.0, 100.0, 46.0, 102.0), poly(72.0, 100.0, 90.0, 102.0),
            rule(11.1, 95.0, 34.9, 95.0), rule(47.1, 95.0, 70.9, 95.0)]
    door_1 = _receipt((0,), (1,), CAPS, opening=(3,), opening_id="door-1")
    door_2 = _receipt((1,), (2,), ((46.0, 99.7, 47.1, 102.3), (70.9, 99.7, 72.0, 102.3)), opening=(4,), opening_id="door-2")
    return rows, door_1, door_2


CORE_SCENES = {
    "core_solid_strips": strip_scene, "core_outlined_faces": outlined_scene, "core_outlined_with_end_caps": outlined_end_cap_scene,
    "core_single_hairline": hairline_scene, "core_cavity_pocket": pocket_scene, "core_perpendicular_corner": corner_scene,
    "core_coincident_junction": junction_scene, "core_face_of_a_passing_wall": face_scene,
}
for _name, _scene in CORE_SCENES.items():
    CASES[_name] = (lambda scene=_scene: core_dump(*scene()))


@case("core_first_and_second_group_swapped")
def _():
    rows, rec = strip_scene()
    return core_dump(rows, _receipt(rec.second_wall_end_path_ids, rec.first_wall_end_path_ids, rec.anchors, opening=rec.opening_native_path_ids))


@case("core_group_ids_given_out_of_order")
def _():
    rows, rec = outlined_scene()
    ascending = core_dump(rows, rec)
    descending = core_dump(rows, _receipt((1, 0), (3, 2), rec.anchors, opening=rec.opening_native_path_ids))
    return {"ascending": ascending, "descending": descending}


@case("core_group_meets_the_opening_on_two_sides")
def _():
    rows = [poly(10.0, 100.0, 36.0, 102.0), _leaf(), poly(40.0, 100.0, 60.0, 102.0)]
    anchors = ((9.0, 99.7, 10.0, 102.3), (36.0, 99.7, 37.1, 102.3))
    return core_dump(rows, _receipt((0,), (2,), anchors, opening=(1,)))


@case("core_solid_pier_between_two_doorways")
def _():
    rows, door_1, door_2 = pier_scene()
    return {"door_1": core_dump(rows, door_1), "door_2": core_dump(rows, door_2)}


@case("core_malformed_receipts")
def _():
    rows, rec = strip_scene()
    anchors = rec.anchors
    variants = {
        "duplicate_ids": _receipt((0, 0), (1,), anchors, opening=(2,)),
        "shared_path": _receipt((0,), (0,), anchors, opening=(2,)),
        "id_out_of_range": _receipt((0,), (99,), anchors, opening=(2,)),
        "boolean_id": _receipt((True,), (1,), anchors, opening=(2,)),
        "opening_inside_a_group": _receipt((0,), (1,), anchors, opening=(0,)),
        "no_anchors": _receipt((0,), (1,), (), opening=(2,)),
        "nan_anchor": _receipt((0,), (1,), ((float("nan"), 0.0, 1.0, 1.0),), opening=(2,)),
        "reversed_anchor": _receipt((0,), (1,), ((5.0, 5.0, 1.0, 1.0),), opening=(2,)),
    }
    return {name: core_dump(rows, rec_) for name, rec_ in variants.items()}


MALFORMED_POINTS = {
    "dict": {}, "text": "ab", "bytes": b"ab", "list_of_text": ["a", "b"], "oversized_integer_attribute": types.SimpleNamespace(x=10 ** 400, y=1.0),
    "none_attribute": types.SimpleNamespace(x=None, y=1.0), "one_number": (1.0,), "nested_lists": [[1.0], [2.0]],
}
OVERSIZED_ANCHORS = {
    "high_x": (0.0, 0.0, 10 ** 400, 1.0), "low_x": (-10 ** 400, 0.0, 1.0, 1.0), "high_y": (0.0, 0.0, 1.0, 10 ** 400),
}


@case("core_malformed_native_points")
def _():
    rows, rec = strip_scene()
    return {name: captured(lambda p=point: core_dump([dict(rows[0], items=(("l", p, p),)), *rows[1:]], rec))
            for name, point in MALFORMED_POINTS.items()}


@case("core_oversized_integer_anchors")
def _():
    rows, rec = strip_scene()
    return {name: captured(lambda a=anchor: core_dump(rows, dataclasses.replace(rec, anchors=(a,))))
            for name, anchor in OVERSIZED_ANCHORS.items()}


# --- the internal-door front end ---------------------------------------------------------------------------------------


def _two_door_front_scene():
    rows = [poly(0.0, 100.0, 10.0, 102.0), poly(36.0, 100.0, 46.0, 102.0), poly(72.0, 100.0, 90.0, 102.0),
            poly(10.0, 99.7, 11.1, 102.3, fill=WHITE), poly(34.9, 99.7, 36.0, 102.3, fill=WHITE),
            poly(46.0, 99.7, 47.1, 102.3, fill=WHITE), poly(70.9, 99.7, 72.0, 102.3, fill=WHITE),
            rule(11.1, 95.0, 34.9, 95.0), rule(47.1, 95.0, 70.9, 95.0)]
    door_1 = SourceInternalDoorMark("native_swing_arc_leaf", "HOSTED_TOPOLOGY_ONLY", (11.1, 75.0, 34.9, 100.0),
                                    native_path_ids=(7, 0, 1, 3, 4), host_wall_native_path_ids=(0, 1), jamb_native_path_ids=(3, 4))
    door_2 = SourceInternalDoorMark("native_swing_arc_leaf", "HOSTED_TOPOLOGY_ONLY", (47.1, 75.0, 70.9, 100.0),
                                    native_path_ids=(8, 1, 2, 5, 6), host_wall_native_path_ids=(1, 2), jamb_native_path_ids=(5, 6))
    unhosted = SourceInternalDoorMark("native_swing_arc_leaf", "NEEDS_HOST", (100.0, 100.0, 120.0, 120.0), native_path_ids=(7,))
    return rows, [door_1, door_2, unhosted]


def review_dump(review):
    return {"status": review.status, "reason_codes": list(review.reason_codes), "entries": [e.to_dict() for e in review.entries],
            "public_summary": review.to_public_summary()}


@case("front_end_two_doors_one_pier_one_unhosted_mark")
def _():
    rows, marks = _two_door_front_scene()
    return {"in_order": review_dump(front_mod.tag_marks_to_two_wall_sections(rows, marks, page_index=2, scope=SCOPE)),
            "reversed": review_dump(front_mod.tag_marks_to_two_wall_sections(rows, marks[::-1], page_index=2, scope=SCOPE))}


def _cavity_and_hinged_front_scene():
    cavity_rows = [pocket(10.0, 0.0, 100.0, 102.55), pocket(36.0, 60.0, 100.0, 102.55),
                   poly(10.0, 99.7, 11.1, 102.9, fill=WHITE), poly(34.9, 101.8, 36.0, 102.9, fill=WHITE),
                   poly(10.0, 99.9, 11.1, 102.6, fill=WHITE), rule(11.1, 101.0, 34.9, 101.0)]
    hinged_rows = [poly(200.0, 100.0, 210.0, 102.0), poly(236.0, 100.0, 260.0, 102.0),
                   poly(210.0, 99.7, 211.1, 102.3, fill=WHITE), poly(234.9, 99.7, 236.0, 102.3, fill=WHITE), rule(211.1, 95.0, 234.9, 95.0)]
    slider = SourceInternalDoorMark("native_cavity_slider_callout", "HOSTED_TOPOLOGY_ONLY", (20.0, 90.0, 28.0, 98.0),
                                    native_path_ids=(0, 1, 2, 3, 4, 5), host_wall_native_path_ids=(0, 1), jamb_native_path_ids=(2, 3, 4),
                                    leaf_native_path_id=5, clear_interval_pdf_pts=(10.0, 36.0))
    hinged = SourceInternalDoorMark("native_swing_arc_leaf", "HOSTED_TOPOLOGY_ONLY", (211.1, 75.0, 234.9, 100.0),
                                    native_path_ids=(10, 6, 7, 8, 9), host_wall_native_path_ids=(6, 7), jamb_native_path_ids=(8, 9))
    return cavity_rows + hinged_rows, [slider, hinged]


@case("front_end_cavity_slider_and_hinged_mark")
def _():
    rows, marks = _cavity_and_hinged_front_scene()
    return {"slider_first": review_dump(front_mod.tag_marks_to_two_wall_sections(rows, marks, page_index=2, scope=SCOPE)),
            "hinged_first": review_dump(front_mod.tag_marks_to_two_wall_sections(rows, marks[::-1], page_index=2, scope=SCOPE))}


@case("front_end_invalid_scope")
def _():
    rows, marks = _two_door_front_scene()
    return review_dump(front_mod.tag_marks_to_two_wall_sections(rows, marks, page_index=2, scope=("x",)))


# ---------------------------------------------------------------------------------------------------------------------
# the golden differential
# ---------------------------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def goldens():
    assert GOLDEN_PATH.is_file(), "the before/after goldens are part of the change"
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))["cases"]


def test_every_case_has_a_golden_and_no_golden_is_stale(goldens):
    assert set(goldens) == set(CASES)


@pytest.mark.parametrize("name", sorted(CASES))
def test_case_matches_its_golden(name, goldens):
    entry = goldens[name]
    expected = entry["after"] if name in DELTA_CASES else entry["before"]
    assert captured(CASES[name]) == expected


def test_each_documented_delta_is_a_real_difference(goldens):
    for name in sorted(CASES):
        entry = goldens[name]
        if name in DELTA_CASES:
            assert "after" in entry and entry["before"] != entry["after"], name
        else:
            assert "after" not in entry, f"{name} changed between before and after but is not a documented delta"


def test_the_documented_deltas_are_the_intended_ones(goldens):
    zero = goldens["adapter_zero_width_chord"]
    assert zero["before"][0]["status"] == TAGGED and zero["before"][0]["contact_geometry"] == "WALL_JUNCTION"
    assert zero["after"][0]["status"] == UNRESOLVED and zero["after"][0]["reason"] == "source_chord_receipt_invalid"
    collections_ = goldens["adapter_collections_not_list_or_tuple"]
    assert collections_["before"]["drawings_user_list"][0]["status"] == TAGGED
    for key in ("drawings_user_list", "chords_user_list", "chords_generator"):
        assert collections_["after"][key] == [{
            "opening_id": "0", "status": UNRESOLVED, "reason": "source_chord_collection_invalid", "wall_section_ids": [],
            "contact_geometry": "UNRESOLVED", "candidate_sections_first": [], "candidate_sections_second": [],
            "source_topology_only": True, "physical_host_authorized": False, "measurement_authorized": False}]
    assert collections_["after"]["plain_tuple"] == collections_["before"]["plain_tuple"]
    duck = goldens["adapter_duck_typed_chord"]
    assert duck["before"]["duck_alone"][0]["status"] == TAGGED
    assert duck["after"]["duck_alone"][0]["status"] == UNRESOLVED and duck["after"]["duck_alone"][0]["reason"] == "source_chord_receipt_invalid"
    assert [t_["status"] for t_ in duck["after"]["duck_between_two_mappings"]] == [TAGGED, UNRESOLVED, TAGGED]
    for name in ("core_malformed_native_points", "core_oversized_integer_anchors"):
        before, after = goldens[name]["before"], goldens[name]["after"]
        assert any(v.get("raised") in ("KeyError", "OverflowError") for v in before.values()), name
        assert all("raised" not in v for v in after.values()), name
    overflow = goldens["contract_oversized_integer_contact"]
    assert overflow["before"] == {"raised": "OverflowError"}
    assert overflow["after"]["status"] == UNRESOLVED and overflow["after"]["reason"] == "opening_contact_geometry_invalid"


def test_every_recorded_tag_is_topology_only(goldens):
    def walk(value):
        if isinstance(value, dict):
            if "physical_host_authorized" in value:
                assert value["physical_host_authorized"] is False and value["measurement_authorized"] is False
                assert value.get("source_topology_only", True) is True
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
    for entry in goldens.values():
        walk(entry)


def test_recorded_receipts_keep_their_order_and_source_path_ids(goldens):
    repeated = goldens["adapter_chord_repeated"]["before"]
    assert [t["opening_id"] for t in repeated] == ["0", "1", "2"]
    assert repeated[0] == {**repeated[1], "opening_id": "0"} == {**repeated[2], "opening_id": "0"}
    seam_tags = goldens["adapter_seam_w52.08_h_plain"]["before"]["tags"]
    assert seam_tags[0]["wall_section_ids"] and all(s.startswith("native-wall-end:") for s in seam_tags[0]["wall_section_ids"])
    pier = goldens["adapter_solid_pier_between_two_openings"]["before"]
    assert pier[0]["wall_section_ids"][1] == pier[1]["wall_section_ids"][0] == "native-wall-end:1"
    core_pier = goldens["core_solid_pier_between_two_doorways"]["before"]
    assert core_pier["door_1"]["sections"][1]["id"] == core_pier["door_2"]["sections"][0]["id"]
    assert core_pier["door_1"]["sections"][1]["native_path_ids"] == [1]
    ordered = goldens["core_group_ids_given_out_of_order"]["before"]
    assert ordered["ascending"] == ordered["descending"]
    both = goldens["contract_competing_sections_on_both_sides"]["before"]
    assert both["unsorted_input"] == both["sorted_input"]
    assert both["unsorted_input"]["candidate_sections_second"] == sorted(both["unsorted_input"]["candidate_sections_second"])
    mixed = goldens["front_end_cavity_slider_and_hinged_mark"]["before"]
    assert mixed["slider_first"] == mixed["hinged_first"]
    assert [e["symbol_kind"] for e in mixed["slider_first"]["entries"]] == ["cavity_slider", "hinged_swing"]
    assert all(e["tag_status"] == TAGGED for e in mixed["slider_first"]["entries"])
    front = goldens["front_end_two_doors_one_pier_one_unhosted_mark"]["before"]
    assert front["in_order"] == front["reversed"]
    assert [e["reason"] for e in front["in_order"]["entries"]].count("mark_has_no_two_native_host_paths") == 1


# ---------------------------------------------------------------------------------------------------------------------
# properties that do not need a golden
# ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(MALFORMED_POINTS))
def test_core_blocks_a_malformed_native_point_without_raising(name):
    rows, rec = strip_scene()
    point = MALFORMED_POINTS[name]
    built = build_contract_inputs([dict(rows[0], items=(("l", point, point),)), *rows[1:]], rec)
    assert isinstance(built, Blocked)


@pytest.mark.parametrize("name", sorted(OVERSIZED_ANCHORS))
def test_core_treats_an_oversized_integer_anchor_as_no_anchor(name):
    rows, rec = strip_scene()
    assert build_contract_inputs(rows, dataclasses.replace(rec, anchors=(OVERSIZED_ANCHORS[name],))) == Blocked(core_mod.GATE_NO_ANCHORS)


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_case_replays_deterministically(name):
    assert captured(CASES[name]) == captured(CASES[name])


def test_inputs_are_never_mutated():
    drawings, chords = seam(52.08)
    snapshot = copy.deepcopy([(r["fill"], r["color"], [tuple(map(str, it)) for it in r["items"]]) for r in drawings])
    chords_snapshot = copy.deepcopy(list(chords))
    tag_native_segmented_doorway_chords(drawings, chords, scope=SCOPE)
    assert snapshot == [(r["fill"], r["color"], [tuple(map(str, it)) for it in r["items"]]) for r in drawings]
    assert chords_snapshot == list(chords)
    rows, rec = strip_scene()
    rows_snapshot = copy.deepcopy([(r["fill"], r["rect"], [tuple(map(str, it)) for it in r["items"]]) for r in rows])
    rec_snapshot = copy.deepcopy(rec)
    build_contract_inputs(rows, rec)
    assert rows_snapshot == [(r["fill"], r["rect"], [tuple(map(str, it)) for it in r["items"]]) for r in rows]
    assert rec == rec_snapshot


@pytest.mark.parametrize("kwargs", [
    {"dx": 137.25, "dy": -48.5}, {"scale": 2.0}, {"scale": 0.5, "dx": 12.0}, {"vertical": True, "dx": -300.0, "dy": 40.0},
])
@pytest.mark.parametrize("width", [23.0, 52.08, 138.0])
def test_rigid_and_uniform_scale_transforms_keep_the_decision(width, kwargs):
    """The scene is exactly aligned, so the absolute 0.18 pt contract tolerance is not what these transforms exercise."""
    base_vertical = kwargs.get("vertical", False)
    drawings, chords = seam(width, **kwargs)
    assert len(chords) == 1 and chords[0]["horizontal"] is not base_vertical
    moved = tag_native_segmented_doorway_chords(drawings, chords, scope=SCOPE)
    plain_drawings, plain_chords = seam(width)
    plain = tag_native_segmented_doorway_chords(plain_drawings, plain_chords, scope=SCOPE)
    assert moved == plain
    assert moved[0].status == TAGGED and moved[0].contact_geometry == "STRAIGHT_GAP"


def test_unrelated_far_content_does_not_change_the_tag():
    drawings, chords = seam(52.08)
    far = [hair((9000.0 + i, 9000.0), (9010.0 + i, 9000.0)) for i in range(40)]
    assert (tag_native_segmented_doorway_chords([*drawings, *far], chords, scope=SCOPE)
            == tag_native_segmented_doorway_chords(drawings, chords, scope=SCOPE))


def test_swapping_first_and_second_group_changes_nothing_in_the_core():
    rows, rec = strip_scene()
    forward = core_dump(rows, rec)
    swapped = core_dump(rows, _receipt(rec.second_wall_end_path_ids, rec.first_wall_end_path_ids, rec.anchors, opening=rec.opening_native_path_ids))
    assert forward == swapped


def test_a_wall_end_drawn_as_one_stroke_or_as_a_group_is_tagged_consistently():
    """One wall end as a single stroke (adapter) or as a group of paths (core): the tag decision is the same."""
    assert core_dump(*strip_scene())["tag"]["status"] == core_dump(*outlined_scene())["tag"]["status"] == TAGGED


# ---------------------------------------------------------------------------------------------------------------------
# the two front ends agree on the domain both accept
# ---------------------------------------------------------------------------------------------------------------------


def _with_rect(row):
    points = [p for _, a, b in row["items"] for p in (a, b)]
    row["rect"] = fitz.Rect(min(p.x for p in points), min(p.y for p in points), max(p.x for p in points), max(p.y for p in points))
    return row


def _agreement_scene(*, passing=False):
    """Hairline wall ends and jamb returns: the one scene the ring adapter and the wall-end core can both read."""
    rows = [hair((0.0, 10.0), (10.0, 10.0)), hair((20.0, 10.0), (30.0, 10.0)),
            hair((10.0, 7.0), (10.0, 12.0)), hair((20.0, 7.0), (20.0, 12.0))]
    if passing:
        rows[0] = hair((0.0, 10.0), (15.0, 10.0))
    rows = [_with_rect(r) for r in rows]
    chord = {"horizontal": True, "door_interval_pdf_pts": (10.0, 20.0), "wall_band_pdf_pts": (7.0, 12.0),
             "source_wall_end_left_path_indices": (0,), "source_wall_end_right_path_indices": (1,),
             "source_swing_native_path_indices": (80,)}
    receipt = _receipt((0,), (1,), tuple(core_mod.row_rect(rows[j]) for j in (2, 3)), opening=(2, 3), opening_id="agree")
    return rows, chord, receipt


def test_ring_adapter_and_core_agree_on_a_hairline_doorway():
    rows, chord, receipt = _agreement_scene()
    adapter = tag_native_segmented_doorway_chords(rows, [chord], scope=SCOPE)[0]
    built = build_contract_inputs(rows, receipt)
    assert not isinstance(built, Blocked)
    contacts, sections = built
    via_core = tag_opening_to_two_wall_sections(contacts, sections)
    assert adapter.status == via_core.status == TAGGED
    assert adapter.contact_geometry == via_core.contact_geometry == "STRAIGHT_GAP"
    adapter_paths = {int(s.split(":")[1]) for s in adapter.wall_section_ids}
    assert adapter_paths == {n for s in sections for n in s.native_path_ids} == {0, 1}
    assert adapter.measurement_authorized is via_core.measurement_authorized is False


def test_ring_adapter_and_core_both_refuse_a_wall_that_runs_through_the_opening():
    rows, chord, receipt = _agreement_scene(passing=True)
    adapter = tag_native_segmented_doorway_chords(rows, [chord], scope=SCOPE)[0]
    built = build_contract_inputs(rows, receipt)
    assert adapter.status == UNRESOLVED
    assert isinstance(built, Blocked) or tag_opening_to_two_wall_sections(*built).status == UNRESOLVED


# ---------------------------------------------------------------------------------------------------------------------
# fuzz: malformed source data never raises and never carries authority
# ---------------------------------------------------------------------------------------------------------------------

_JUNK = [None, True, False, 0, -1, 1, 2 ** 70, 10 ** 400, -10 ** 400, float("nan"), float("inf"), -float("inf"), 1e308, -0.0,
         "x", "", (), [], {}, (1,), (1, 2), [1, 2], (1.0, 2.0, 3.0), (None, None), fitz.Point(1, 2), object, b"a"]


def _junk(rng):
    return rng.choice(_JUNK)


def _fuzz_drawings(rng, drawings):
    rows = list(drawings)
    for _ in range(rng.randint(0, 3)):
        i = rng.randrange(len(rows))
        kind = rng.randint(0, 4)
        if kind == 0:
            rows[i] = _junk(rng)
        elif kind == 1 and isinstance(rows[i], dict):
            rows[i] = dict(rows[i], items=_junk(rng))
        elif kind == 2 and isinstance(rows[i], dict):
            rows[i] = dict(rows[i], fill=_junk(rng))
        elif kind == 3 and isinstance(rows[i], dict):
            rows[i] = dict(rows[i], items=[(rng.choice(["l", "re", "c", 5, None]), _junk(rng), _junk(rng))])
        else:
            rows[i] = {"fill": None, "items": [("l", types.SimpleNamespace(x=_junk(rng) if rng.random() < 0.5 else 1.0, y=2.0),
                                                 types.SimpleNamespace(x=3.0, y=_junk(rng) if rng.random() < 0.5 else 4.0))]}
    return rows


def _fuzz_chord(rng, chord):
    out = dict(chord)
    for _ in range(rng.randint(0, 3)):
        key = rng.choice(sorted(out) + ["extra"])
        action = rng.randint(0, 2)
        if action == 0:
            out.pop(key, None)
        elif action == 1:
            out[key] = _junk(rng)
        else:
            out[key] = (_junk(rng), _junk(rng))
    return out


def _assert_topology_only(tags):
    assert isinstance(tags, tuple)
    for tag in tags:
        assert tag.status in (TAGGED, UNRESOLVED)
        assert tag.physical_host_authorized is False and tag.measurement_authorized is False and tag.source_topology_only is True


def test_seeded_fuzz_of_the_ring_adapter_never_raises_and_never_grants_authority():
    rng = random.Random(20261124)
    drawings, chords = seam(52.08)
    base = chords[0]
    for _ in range(600):
        rows = _fuzz_drawings(rng, drawings)
        batch = [_fuzz_chord(rng, base) for _ in range(rng.randint(0, 3))]
        if rng.random() < 0.1:
            batch.append(_junk(rng))
        _assert_topology_only(tag_native_segmented_doorway_chords(rows, batch, scope=SCOPE))


def test_seeded_fuzz_of_the_contract_never_raises_and_never_grants_authority():
    rng = random.Random(20261125)
    a, b = _straight()
    for _ in range(600):
        opening = _opening()
        sections = [a, b]
        target = rng.randint(0, 5)
        if target == 0:
            opening = dataclasses.replace(opening, first=OpeningWallContact(_junk(rng), (100,)))
        elif target == 1:
            opening = dataclasses.replace(opening, second=OpeningWallContact((_junk(rng), _junk(rng)), _junk(rng)))
        elif target == 2:
            opening = dataclasses.replace(opening, scope=_junk(rng), opening_native_path_ids=_junk(rng))
        elif target == 3:
            sections[rng.randrange(2)] = dataclasses.replace(a, start_pdf_pts=(_junk(rng), _junk(rng)), end_pdf_pts=_junk(rng))
        elif target == 4:
            sections.append(_junk(rng))
        else:
            opening = dataclasses.replace(opening, opening_id=_junk(rng))
        tag = tag_opening_to_two_wall_sections(opening, rng.choice([sections, tuple(sections), _junk(rng)]))
        assert tag.status in (TAGGED, UNRESOLVED)
        assert tag.physical_host_authorized is False and tag.measurement_authorized is False


_NUMBERS = [0, 1, -1, 2 ** 70, 10 ** 400, -10 ** 400, float("nan"), float("inf"), -float("inf"), 1e308, -0.0, 0.5]


def _junk_anchor(rng):
    """A four-number rectangle most of the time, so the numeric checks (not only the type checks) are what is exercised."""
    if rng.random() < 0.15:
        return tuple(_junk(rng) for _ in range(rng.choice([3, 4, 5])))
    return tuple(rng.choice(_NUMBERS) if rng.random() < 0.6 else rng.choice([10.0, 11.1, 99.7, 102.3]) for _ in range(4))


def test_seeded_fuzz_of_the_wall_end_core_never_raises_and_never_grants_authority():
    rng = random.Random(20261126)
    rows, rec = strip_scene()
    reached = 0
    for _ in range(3000):
        fuzzed_rows = _fuzz_drawings(rng, rows) if rng.random() < 0.5 else list(rows)
        anchors = list(rec.anchors)
        if rng.random() < 0.7:
            anchors[rng.randrange(len(anchors))] = _junk_anchor(rng)
        receipt = WallEndReceipt(
            "fuzz", SCOPE, (2,) if rng.random() < 0.85 else _junk(rng), (0,) if rng.random() < 0.85 else _junk(rng),
            (1,) if rng.random() < 0.85 else _junk(rng), tuple(anchors))
        built = build_contract_inputs(fuzzed_rows, receipt)
        if isinstance(built, Blocked):
            continue
        reached += 1
        tag = tag_opening_to_two_wall_sections(*built)
        assert tag.status in (TAGGED, UNRESOLVED)
        assert tag.physical_host_authorized is False and tag.measurement_authorized is False
    assert reached > 100, "the fuzz must keep reaching the geometry stage, not only the receipt checks"


# ---------------------------------------------------------------------------------------------------------------------
# the one seam that reaches the layered ring: the field is topology only and nothing reads it
# ---------------------------------------------------------------------------------------------------------------------

EXPECTED_TAG_FIELDS = {
    "opening_id", "status", "reason", "wall_section_ids", "contact_geometry", "candidate_sections_first",
    "candidate_sections_second", "source_topology_only", "physical_host_authorized", "measurement_authorized",
}


def test_a_two_wall_tag_has_no_width_height_area_or_quantity_field():
    assert {f.name for f in dataclasses.fields(contract.TwoWallOpeningTag)} == EXPECTED_TAG_FIELDS
    for name in EXPECTED_TAG_FIELDS:
        assert not any(word in name for word in ("width", "height", "area", "length", "quantity", "metric"))


def _ring_function():
    tree = ast.parse((REPO / "pb_layered_wall_doorway_room_ring_shadow.py").read_text(encoding="utf-8"))
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "build_layered_wall_doorway_room_rings")


def test_the_ring_payload_of_a_tag_is_topology_only():
    payloads = [n for n in ast.walk(_ring_function()) if isinstance(n, ast.Dict)
                and any(isinstance(k, ast.Constant) and k.value == "opening_id" for k in n.keys)]
    assert len(payloads) == 1
    keys = {k.value for k in payloads[0].keys}
    assert keys == EXPECTED_TAG_FIELDS
    values = dict(zip((k.value for k in payloads[0].keys), payloads[0].values))
    for flag in ("physical_host_authorized", "measurement_authorized"):
        assert isinstance(values[flag], ast.Constant) and values[flag].value is False


def test_no_module_other_than_the_ring_reads_the_two_wall_tag_field():
    readers = []
    for path in sorted([*REPO.glob("*.py"), *REPO.glob("tools/*.py"), *REPO.glob("scripts/*.py")]):
        if "source_two_wall_opening_tags" in path.read_text(encoding="utf-8", errors="ignore"):
            readers.append(path.name)
    assert readers == ["pb_layered_wall_doorway_room_ring_shadow.py"]


def test_the_chord_interval_is_read_only_by_the_producer_the_adapter_and_the_ring_gap():
    readers = [p.name for p in sorted(REPO.glob("*.py")) if "door_interval_pdf_pts" in p.read_text(encoding="utf-8", errors="ignore")]
    assert readers == ["pb_layered_wall_doorway_room_ring_shadow.py", "pb_opening_two_wall_contact_tags.py",
                       "pb_source_segmented_door_swing_shadow.py"]


def _ring_rows(radius=24.0, *, transpose=False, dx=0.0, dy=0.0, drop=None, second_left_end=False):
    """A 100 x 100 room whose right wall has one doorway drawn the way segmented CAD swings are (a polyline arc, a radial leaf)."""
    def pt(x, y):
        x, y = (y, x) if transpose else (x, y)
        return fitz.Point(x + dx, y + dy)

    def strip(x0, y0, x1, y1):
        c = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        return {"layer": WALL_LAYER, "fill": BLACK, "color": None, "items": [("l", pt(*c[i]), pt(*c[(i + 1) % 4])) for i in range(4)]}

    def line(a, b):
        return {"layer": WALL_LAYER, "fill": None, "color": BLACK, "items": [("l", pt(*a), pt(*b))]}

    gap_lo = 40.0
    rows = [strip(0, 0, 100, 2), strip(0, 2, 2, 98), strip(0, 98, 100, 100), strip(98, 2, 100, gap_lo), strip(98, gap_lo + radius, 100, 98)]
    centre = (98.0, gap_lo)
    arc = [(centre[0] - radius * math.cos(math.pi / 2 * i / 9), centre[1] + radius * math.sin(math.pi / 2 * i / 9)) for i in range(10)]
    rows += [line(arc[i], arc[i + 1]) for i in range(9)]
    rows.append(line(centre, arc[0]))
    ends = [line((99.0, 2.0), (99.0, gap_lo)), line((99.0, gap_lo + radius), (99.0, 98.0)),
            line((98.0, gap_lo), (100.0, gap_lo)), line((98.0, gap_lo + radius), (100.0, gap_lo + radius))]
    if second_left_end:
        ends.append(line((99.4, 30.0), (99.4, gap_lo)))
    if drop is not None:
        ends.pop(drop)
    return rows + ends


def _ring(rows, **kwargs):
    return build_layered_wall_doorway_room_rings(rows, source_sha256="ab" * 32, page_index=0, dark_painted_wall_source=True, **kwargs)


@pytest.mark.parametrize("kwargs", [{}, {"transpose": True}, {"dx": 211.5, "dy": -73.25}, {"radius": 40.0}, {"radius": 19.5, "transpose": True}])
def test_ring_reports_the_two_wall_tag_of_a_segmented_swing_doorway(kwargs):
    result = _ring(_ring_rows(**kwargs))
    assert len(result.source_owned_doorway_chords) == 1
    (tag,) = result.source_two_wall_opening_tags
    assert tag["status"] == TAGGED and tag["contact_geometry"] == "STRAIGHT_GAP"
    assert tag["reason"] == "source_wall_ends_and_opening_contacts_match"
    assert len(tag["wall_section_ids"]) == 2 and all(s.startswith("native-wall-end:") for s in tag["wall_section_ids"])
    assert tag["physical_host_authorized"] is False and tag["measurement_authorized"] is False and tag["source_topology_only"] is True
    assert set(tag) == EXPECTED_TAG_FIELDS


def test_ring_tag_ids_name_the_chords_own_source_wall_end_paths():
    result = _ring(_ring_rows())
    chord = result.source_owned_doorway_chords[0]
    (tag,) = result.source_two_wall_opening_tags
    expected = ("native-wall-end:%d" % chord["source_wall_end_left_path_indices"][0],
                "native-wall-end:%d" % chord["source_wall_end_right_path_indices"][0])
    assert tuple(tag["wall_section_ids"]) == expected


def test_the_tag_call_changes_no_other_field_of_the_ring_result(monkeypatch):
    rows = _ring_rows()
    with_tags = _ring(rows)
    assert len(with_tags.source_two_wall_opening_tags) == 1
    monkeypatch.setattr(contract, "tag_native_segmented_doorway_chords", lambda *args, **kwargs: ())
    without_tags = _ring(rows)
    assert without_tags.source_two_wall_opening_tags == ()
    for field in dataclasses.fields(with_tags):
        if field.name != "source_two_wall_opening_tags":
            assert getattr(with_tags, field.name) == getattr(without_tags, field.name), field.name


def test_ring_replay_is_deterministic_and_leaves_its_rows_unchanged():
    rows = _ring_rows()
    before = copy.deepcopy([(r["layer"], r["fill"], r["color"], [tuple(map(str, it)) for it in r["items"]]) for r in rows])
    first, second = _ring(rows), _ring(rows)
    assert first == second and first.source_two_wall_opening_tags == second.source_two_wall_opening_tags
    assert before == [(r["layer"], r["fill"], r["color"], [tuple(map(str, it)) for it in r["items"]]) for r in rows]


@pytest.mark.parametrize("dropped", [0, 1, 2, 3])
def test_ring_gives_no_tag_when_one_wall_end_or_jamb_is_missing(dropped):
    result = _ring(_ring_rows(drop=dropped))
    assert result.source_owned_doorway_chords == () and result.source_two_wall_opening_tags == ()


def test_ring_retains_two_competing_wall_ends_without_choosing_one():
    result = _ring(_ring_rows(second_left_end=True))
    assert len(result.source_two_wall_opening_tags) == 1
    (tag,) = result.source_two_wall_opening_tags
    assert tag["status"] == UNRESOLVED and tag["reason"] == "source_wall_end_contact_ambiguous"
    assert len(tag["candidate_sections_first"]) == 2 and tag["wall_section_ids"] == ()


def test_ring_without_the_dark_painted_option_never_proposes_a_chord_or_a_tag():
    result = build_layered_wall_doorway_room_rings(_ring_rows(), source_sha256="ab" * 32, page_index=0)
    assert result.source_owned_doorway_chords == () and result.source_two_wall_opening_tags == ()
