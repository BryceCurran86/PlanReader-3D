"""Review-only front end: source-native internal door marks -> two traced wall sections (owner contract).

Synthetic scenes only: no private drawing, project name, benchmark value or file name is an input. The geometry rules
(every wall convention, corners, junctions, boundaries) are proved in ``test_source_door_wall_end_sections_v1.py``; this
file proves what the front end adds: every inventory mark appears once, a mark is read only through the native rows it
names, the inventory's hosted, unhosted and unlayered cases are honest, and nothing carries authority.
"""
from __future__ import annotations

import ast
import copy
import json
import re
from pathlib import Path

import fitz
import pytest

import pb_source_internal_door_two_wall_tags as mod
from pb_source_door_wall_end_sections import (
    GATE_ANCHOR_MISSING,
    GATE_END_EDGE_MISSING,
    GATE_OPENING_PATHS_MISSING,
    GATE_ROW_UNREADABLE,
)
from pb_source_internal_door_completeness_shadow import SourceInternalDoorMark
from pb_source_internal_door_two_wall_tags import (
    GATE_MARK_NOT_HOSTED,
    InternalDoorTwoWallEntry,
    InternalDoorTwoWallReview,
    tag_internal_door_marks,
    tag_marks_to_two_wall_sections,
)

SCOPE = ("a" * 64, "revision-a", "page-3")
PAGE = 2
BLACK = (0.0, 0.0, 0.0)
WHITE = (1.0, 1.0, 1.0)
OK = "source_wall_ends_and_opening_contacts_match"


def poly(x0, y0, x1, y1, *, fill=BLACK, layer="Enclosure_WallInternal"):
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    items = tuple(("l", fitz.Point(*corners[i]), fitz.Point(*corners[(i + 1) % 4])) for i in range(4))
    return {"layer": layer, "rect": fitz.Rect(x0, y0, x1, y1), "type": "f", "fill": fill, "color": None,
            "items": items}


def stroke_line(x0, y0, x1, y1, *, layer="Enclosure_WallInternal"):
    return {"layer": layer, "rect": fitz.Rect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)), "type": "s",
            "fill": None, "color": BLACK, "width": 0.7,
            "items": (("l", fitz.Point(x0, y0), fitz.Point(x1, y1)),)}


def pocketed(x_end, x_far, y0, y1, lip=0.57):
    pts = [(x_far, y0), (x_end, y0), (x_end, y0 + lip), (x_far + 1.4, y0 + lip), (x_far + 1.4, y1 - lip),
           (x_end, y1 - lip), (x_end, y1), (x_far, y1)]
    items = tuple(("l", fitz.Point(*pts[i]), fitz.Point(*pts[(i + 1) % len(pts)])) for i in range(len(pts)))
    return {"layer": "Enclosure_WallInternal", "rect": fitz.Rect(min(x_far, x_end), y0, max(x_far, x_end), y1),
            "type": "f", "fill": BLACK, "color": None, "items": items}


def hinged_scene():
    rows = [
        poly(0.0, 100.0, 10.0, 102.0), poly(36.0, 100.0, 60.0, 102.0),
        poly(10.0, 99.7, 11.1, 102.3, fill=WHITE), poly(34.9, 99.7, 36.0, 102.3, fill=WHITE),
        stroke_line(11.1, 100.0, 11.1, 75.0), stroke_line(11.1, 75.0, 34.9, 75.0),
    ]
    mark = SourceInternalDoorMark(
        "native_swing_arc_leaf", "HOSTED_TOPOLOGY_ONLY", (11.1, 75.0, 34.9, 100.0),
        native_path_ids=(4, 5, 0, 1, 2, 3), host_wall_native_path_ids=(0, 1), jamb_native_path_ids=(2, 3),
    )
    return rows, mark


def cavity_scene():
    rows = [
        pocketed(10.0, 0.0, 100.0, 102.55), pocketed(36.0, 60.0, 100.0, 102.55),
        poly(10.0, 99.7, 11.1, 102.9, fill=WHITE), poly(34.9, 101.8, 36.0, 102.9, fill=WHITE),
        poly(10.0, 99.9, 11.1, 102.6, fill=WHITE), stroke_line(11.1, 101.0, 34.9, 101.0),
    ]
    mark = SourceInternalDoorMark(
        "native_cavity_slider_callout", "HOSTED_TOPOLOGY_ONLY", (20.0, 90.0, 28.0, 98.0),
        native_path_ids=(0, 1, 2, 3, 4, 5), host_wall_native_path_ids=(0, 1), jamb_native_path_ids=(2, 3, 4),
        leaf_native_path_id=5, clear_interval_pdf_pts=(10.0, 36.0),
    )
    return rows, mark


def line_cap_scene():
    rows = [
        poly(0.0, 100.0, 10.0, 102.0), poly(36.0, 100.0, 60.0, 102.0),
        stroke_line(10.0, 100.0, 10.0, 102.0), stroke_line(36.0, 100.0, 36.0, 102.0),
        stroke_line(10.0, 100.0, 36.0, 100.0),
    ]
    mark = SourceInternalDoorMark(
        "native_swing_arc_leaf", "HOSTED_TOPOLOGY_ONLY", (10.0, 100.0, 36.0, 102.0),
        native_path_ids=(4, 0, 1, 2, 3), host_wall_native_path_ids=(0, 1), jamb_native_path_ids=(2, 3),
    )
    return rows, mark


def review_of(rows, mark, *, scope=SCOPE):
    return tag_marks_to_two_wall_sections(rows, [mark], page_index=PAGE, scope=scope)


def only(review):
    assert len(review.entries) == 1
    return review.entries[0]


SCENES = [hinged_scene, cavity_scene, line_cap_scene]


@pytest.mark.parametrize("scene", SCENES)
def test_each_inventory_mark_is_tagged_with_its_two_wall_sections(scene):
    entry = only(review_of(*scene()))
    assert entry.tagged and entry.reason == OK and entry.contact_geometry == "STRAIGHT_GAP"
    assert len(entry.wall_section_ids) == 2 and entry.wall_section_ids[0] != entry.wall_section_ids[1]
    assert entry.host_native_path_ids == (0, 1) and entry.next_authority == mod.NEXT_AUTHORITY


def test_symbol_kind_follows_the_inventory_mark_kind():
    assert only(review_of(*hinged_scene())).symbol_kind == mod.SYMBOL_HINGED_SWING
    assert only(review_of(*cavity_scene())).symbol_kind == mod.SYMBOL_CAVITY_SLIDER


def test_mark_without_two_native_host_paths_is_reported_not_dropped():
    rows, mark = hinged_scene()
    for changed in (
        {"status": "NEEDS_HOST"},
        {"host_wall_native_path_ids": ()},
        {"host_wall_native_path_ids": (0,)},
        {"host_wall_native_path_ids": (0, 0)},
        {"host_wall_native_path_ids": (0, 99)},
        {"host_wall_native_path_ids": (-1, 1)},
        {"host_wall_native_path_ids": (True, 1)},
        {"host_wall_native_path_ids": (0, 1.0)},
    ):
        entry = only(review_of(rows, SourceInternalDoorMark(**{**mark.__dict__, **changed})))
        assert entry.reason == GATE_MARK_NOT_HOSTED and not entry.tagged and entry.contact_geometry == "UNRESOLVED"


def test_a_mark_is_read_only_through_the_native_rows_it_names():
    rows, mark = hinged_scene()
    dropped = SourceInternalDoorMark(**{**mark.__dict__, "jamb_native_path_ids": (2,)})
    assert only(review_of(rows, dropped)).reason == GATE_ANCHOR_MISSING
    none = SourceInternalDoorMark(**{**mark.__dict__, "jamb_native_path_ids": (2, 3, 99, -1, True)})
    assert only(review_of(rows, none)).tagged
    wall_only = SourceInternalDoorMark(**{**mark.__dict__, "native_path_ids": (0, 1)})
    assert only(review_of(rows, wall_only)).reason == GATE_OPENING_PATHS_MISSING
    rows[0] = {k: v for k, v in rows[0].items() if k != "rect"}
    assert only(review_of(rows, mark)).reason == GATE_ROW_UNREADABLE
    rows, mark = hinged_scene()
    rows[1] = {**rows[1], "items": ()}
    assert only(review_of(rows, mark)).reason == GATE_END_EDGE_MISSING


@pytest.mark.parametrize("scope", [(), ("a" * 64,), ("a" * 64, ""), ("a" * 64, 7), ["a" * 64, "r"], None, "ab"])
def test_invalid_scope_abstains_without_entries(scope):
    rows, mark = hinged_scene()
    review = tag_marks_to_two_wall_sections(rows, [mark], page_index=PAGE, scope=scope)
    assert review.status == mod.INTERNAL_DOOR_TWO_WALL_TAGS_ABSTAINED
    assert review.reason_codes == (mod.REASON_SCOPE_INVALID,) and review.entries == ()


AUTHORITY_FLAGS = (
    "physical_wall_authenticated", "physical_host_authorized", "physical_opening_authenticated",
    "kind_authorized", "measurement_authorized", "customer_quantity_authorized", "frozen_benchmark_scored",
)


def test_every_authority_flag_is_false_and_cannot_be_set():
    review = review_of(*hinged_scene())
    entry = only(review)
    for obj in (entry, review):
        for name in AUTHORITY_FLAGS:
            assert getattr(obj, name) is False
    for name in AUTHORITY_FLAGS:
        with pytest.raises(ValueError):
            InternalDoorTwoWallEntry(**{**entry.__dict__, name: True})
        with pytest.raises(ValueError):
            InternalDoorTwoWallReview(**{**review.__dict__, name: True})
    assert all(entry.to_dict()[name] is False for name in AUTHORITY_FLAGS)
    assert all(review.to_public_summary()[name] is False for name in AUTHORITY_FLAGS)


def test_public_summary_is_counts_only():
    rows, mark = hinged_scene()
    review = tag_marks_to_two_wall_sections(rows, [mark, SourceInternalDoorMark(
        "native_cavity_slider_callout", "NEEDS_JAMB_WITNESS", (0, 0, 1, 1))], page_index=PAGE, scope=SCOPE)
    summary = review.to_public_summary()
    assert summary["marks"] == 2 and summary["tagged"] == 1 and summary["unresolved"] == 1
    assert summary["by_symbol_kind"] == {"cavity_slider": 1, "hinged_swing": 1}
    text = json.dumps(summary)
    ids = [e.entry_id for e in review.entries] + [s for e in review.entries for s in e.wall_section_ids]
    assert not any(i in text for i in ids)
    assert not re.search(r"\d+\.\d", text.replace("1.0.0", ""))
    assert set(summary["by_reason"]) <= {OK, GATE_MARK_NOT_HOSTED}


def test_every_mark_appears_exactly_once_and_order_does_not_matter():
    rows, mark = hinged_scene()
    other = SourceInternalDoorMark("native_cavity_slider_callout", "NEEDS_HOST", (0, 0, 1, 1), native_path_ids=(7,))
    a = tag_marks_to_two_wall_sections(rows, [mark, other], page_index=PAGE, scope=SCOPE)
    b = tag_marks_to_two_wall_sections(rows, [other, mark], page_index=PAGE, scope=SCOPE)
    assert a == b and len(a.entries) == 2


def test_replay_is_deterministic_scope_changes_ids_and_inputs_are_not_mutated():
    rows, mark = cavity_scene()
    before = (copy.deepcopy(rows), copy.deepcopy(mark))
    first = review_of(rows, mark)
    assert first == review_of(copy.deepcopy(rows), mark)
    assert (rows, mark) == before
    other = review_of(rows, mark, scope=("b" * 64, "revision-a", "page-3"))
    assert only(other).entry_id != only(first).entry_id and only(other).wall_section_ids != only(first).wall_section_ids


def test_unrelated_rows_and_other_marks_do_not_change_a_tag():
    rows, mark = hinged_scene()
    base = only(review_of(rows, mark))
    noisy = list(rows) + [poly(500 + 30 * i, 500, 520 + 30 * i, 502) for i in range(40)] + [
        stroke_line(5.0, 99.9, 60.0, 99.9)]
    assert only(review_of(noisy, mark)) == base
    far = SourceInternalDoorMark("native_swing_arc_leaf", "HOSTED_TOPOLOGY_ONLY", (500, 500, 520, 502),
                                 native_path_ids=(6, 7, 8, 9, 10, 11), host_wall_native_path_ids=(6, 7),
                                 jamb_native_path_ids=(8, 9))
    both = tag_marks_to_two_wall_sections(noisy, [mark, far], page_index=PAGE, scope=SCOPE)
    assert [e for e in both.entries if e.entry_id == base.entry_id] == [base]


FLOOR_VIEWPORT = "source-authenticated-floor-plan-page-2"


def inventory_scene(layer="Enclosure_WallInternal"):
    def rect_row(bounds, shade):
        x0, y0, x1, y1 = bounds
        row = poly(x0, y0, x1, y1, fill=(shade,) * 3, layer=layer)
        row["viewport_id"] = FLOOR_VIEWPORT
        return row

    arc = {"layer": layer, "rect": fitz.Rect(100, 20, 125, 45), "type": "s", "fill": None, "color": (0, 0, 0),
           "viewport_id": FLOOR_VIEWPORT,
           "items": (("c", fitz.Point(125, 20), fitz.Point(125, 33.807), fitz.Point(113.807, 45),
                      fitz.Point(100, 45)),)}
    leaf = {"layer": layer, "rect": fitz.Rect(100, 20, 125, 20), "type": "s", "fill": None, "color": (0, 0, 0),
            "viewport_id": FLOOR_VIEWPORT, "items": (("l", fitz.Point(100, 20), fitz.Point(125, 20)),)}
    return [
        rect_row((97.8, 7, 99.8, 18.8), 0), rect_row((97.8, 46.2, 99.8, 59), 0),
        rect_row((97.5, 18.8, 100, 20), 1), rect_row((97.5, 45, 100, 46.2), 1), arc, leaf,
    ]


def test_end_to_end_through_the_strict_internal_door_inventory():
    review = tag_internal_door_marks(inventory_scene(), (), page_index=PAGE, scope=SCOPE)
    entry = only(review)
    assert entry.symbol_kind == mod.SYMBOL_HINGED_SWING and entry.tagged
    assert entry.contact_geometry == "STRAIGHT_GAP" and entry.host_native_path_ids == (0, 1)
    assert review.to_public_summary()["tagged"] == 1


def test_a_layer_the_inventory_does_not_accept_yields_no_mark_and_no_tag():
    # Honest limit: hosting still needs a recognised internal-wall layer name, so nothing is invented without it.
    assert tag_internal_door_marks(inventory_scene(layer="Layer-17"), (), page_index=PAGE, scope=SCOPE).entries == ()


def test_another_accepted_layer_convention_is_tagged_the_same_way():
    assert only(tag_internal_door_marks(inventory_scene(layer="A-WALL-INTR"), (), page_index=PAGE, scope=SCOPE)).tagged


MODULE_PATH = Path(mod.__file__)


def test_front_end_imports_only_the_contract_the_core_the_inventory_and_stable_ids():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert {n for n in imported if n.startswith("pb_")} == {
        "pb_migration_contracts", "pb_opening_two_wall_contact_tags", "pb_source_door_wall_end_sections",
        "pb_source_internal_door_completeness_shadow",
    }


def test_front_end_has_no_project_or_drawing_literal_and_never_claims_authority():
    source = MODULE_PATH.read_text(encoding="utf-8")
    forbidden = ("laurel", "maryborough", "lot16", "acacia", "Enclosure_", "2100", "720", "870", "Annotation_")
    assert [word for word in forbidden if word.lower() in source.lower()] == []
    assert "014e9f68" not in source
    for name in AUTHORITY_FLAGS:
        assert f"{name}=True" not in source.replace(" ", "")


def test_a_boolean_or_negative_value_is_not_a_jamb_path_id():
    # row 1 is the right jamb cap here, so a stray ``True`` (== 1) would silently select it
    rows = [
        poly(0.0, 100.0, 10.0, 102.0), poly(34.9, 99.7, 36.0, 102.3, fill=WHITE),
        poly(36.0, 100.0, 60.0, 102.0), poly(10.0, 99.7, 11.1, 102.3, fill=WHITE),
        stroke_line(11.1, 75.0, 34.9, 75.0),
    ]
    mark = SourceInternalDoorMark(
        "native_swing_arc_leaf", "HOSTED_TOPOLOGY_ONLY", (11.1, 75.0, 34.9, 100.0),
        native_path_ids=(4, 0, 2, 3, 1), host_wall_native_path_ids=(0, 2), jamb_native_path_ids=(3, 1),
    )
    assert only(review_of(rows, mark)).tagged
    as_bool = SourceInternalDoorMark(**{**mark.__dict__, "jamb_native_path_ids": (3, True)})
    assert only(review_of(rows, as_bool)).reason == GATE_ANCHOR_MISSING
