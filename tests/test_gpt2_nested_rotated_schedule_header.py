"""Generic strict B2 nested door leaf/frame schedule and page-rotation tests.

Only source-text candidates: no installed opening or commercial quantities.
"""
from dataclasses import dataclass
import pytest

from pb_opening_schedule_v171 import parse_schedule_rows, parse_schedule_page


def row(*values):
    return {"text": "\t".join(values), "bbox": (0.0, 0.0, 300.0, 20.0)}


def test_nested_leaf_headers_bind_only_the_documented_leaf_columns():
    rows = [
        row("DOOR", "NOTES"),
        row("D99", "Read this schedule"),
        row("DOOR NO", "DOOR LEAF", "DOOR LEAF", "DOOR FRAME"),
        row("NO", "WIDTH", "HEIGHT", "TYPE"),
        row("D01", "920", "2040", "ALUMINIUM"),
        row("D02", "820", "2100", "STEEL"),
    ]
    entries = parse_schedule_rows(rows, two_level_header=True)
    assert [(e.type_mark, e.width_mm, e.height_mm) for e in entries] == [
        ("D01", 920, 2040), ("D02", 820, 2100)
    ]
    assert all(e.dimension_basis == "leaf" for e in entries)
    assert all(e.parse_source == "header_separate" for e in entries)
    assert parse_schedule_rows(rows[:2], two_level_header=True) == []


def test_other_unrelated_nested_schedule_is_read_by_same_rule():
    rows = [
        row("WINDOW MARK", "WINDOW FRAME", "WINDOW FRAME"),
        row("MARK", "WIDTH", "HEIGHT"),
        row("W03", "1200", "1500"),
    ]
    entries = parse_schedule_rows(rows, two_level_header=True)
    assert len(entries) == 1
    assert (entries[0].width_mm, entries[0].height_mm) == (1200, 1500)
    assert entries[0].dimension_basis == "frame"


def test_competing_leaf_and_frame_dimension_columns_abstain():
    rows = [
        row("DOOR NO", "DOOR LEAF", "DOOR LEAF", "DOOR FRAME", "DOOR FRAME"),
        row("NO", "WIDTH", "HEIGHT", "WIDTH", "HEIGHT"),
        row("D01", "920", "2040", "960", "2080"),
    ]
    assert parse_schedule_rows(rows, two_level_header=True) == []


def test_unaligned_nested_header_cannot_assume_spanning_group():
    rows = [
        row("DOOR NO", "DOOR LEAF"),
        row("NO", "WIDTH", "HEIGHT"),
        row("D01", "920", "2040"),
    ]
    assert parse_schedule_rows(rows, two_level_header=True) == []


def test_conflicting_repeated_nested_header_abstains():
    rows = [
        row("DOOR NO", "DOOR LEAF", "DOOR LEAF"),
        row("NO", "WIDTH", "HEIGHT"),
        row("D01", "920", "2040"),
        row("DOOR NO", "DOOR FRAME", "DOOR FRAME"),
        row("NO", "WIDTH", "HEIGHT"),
        row("D02", "980", "2080"),
    ]
    assert parse_schedule_rows(rows, two_level_header=True) == []


def test_unowned_note_mark_not_rescued_from_description_column():
    rows = [
        row("MARK", "LEAF WIDTH", "LEAF HEIGHT", "NOTES"),
        row("", "920", "2040", "Check D01"),
    ]
    assert parse_schedule_rows(rows, two_level_header=True) == []


@dataclass(frozen=True)
class _Matrix:
    a: float = 0
    b: float = 1
    c: float = -1
    d: float = 0
    e: float = 300
    f: float = 0


class _RotatedPage:
    rotation = 90
    rotation_matrix = _Matrix()
    def __init__(self, valid=True):
        self.valid = valid
    def get_text(self, kind):
        assert kind == "words"
        # Displayed coordinates transformed backward into NATIVE coordinates.
        labels = (
            ("DOOR NO", "DOOR LEAF", "DOOR LEAF"),
            ("NO", "WIDTH", "HEIGHT"),
            ("D01", "920", "2040"),
        )
        words = []
        for r, items in enumerate(labels):
            for i, text in enumerate(items):
                display_x0, display_x1 = 10.0 + i * 90, 60.0 + i * 90
                display_y0, display_y1 = 10.0 + r * 30, 20.0 + r * 30
                words.append((
                    display_y0, 300-display_x1, display_y1, 300-display_x0,
                    text, r, 0, i,
                ))
        if not self.valid:
            words[0] = (float("inf"), *words[0][1:])
        return words


def test_rotated_display_rows_produce_two_tier_leaf_measurements():
    page = _RotatedPage()
    entries = parse_schedule_page(page, two_level_header=True)
    assert [(e.type_mark, e.width_mm, e.height_mm, e.dimension_basis)
            for e in entries] == [("D01", 920, 2040, "leaf")]


def test_invalid_rotated_frame_abstains_without_partial_rows():
    page = _RotatedPage(valid=False)
    assert parse_schedule_page(page, two_level_header=True) == []


def test_ordinary_default_path_is_not_opted_into_rotated_reader(monkeypatch):
    import pb_opening_schedule_v171 as schedule
    called = []
    def ordinary(_):
        called.append(True)
        return [row("MARK", "WIDTH", "HEIGHT"), row("D01", "920", "2040")]
    monkeypatch.setattr(
        __import__("pb_plan_read_engine_v1228", fromlist=["_word_rows"]),
        "_word_rows", ordinary,
    )
    entries = schedule.parse_schedule_page(_RotatedPage())
    assert called
    assert len(entries) == 1
    assert entries[0].dimension_basis == ""
