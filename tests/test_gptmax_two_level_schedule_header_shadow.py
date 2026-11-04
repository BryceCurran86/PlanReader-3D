"""Default-off B2 two-level opening schedule header regression.

Source-neutral, without private PDFs. Original SHA-backed replay and typed
producer/consumer binding remain separate release gates.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from pb_opening_schedule_v171 import parse_schedule_rows


def _row(text: str) -> dict:
    return {"text": text, "bbox": (0, 0, 200, 20)}


def test_two_level_door_schedule_skips_preceding_notes_and_parses_all_rows():
    rows = [
        _row("DOOR\tNOTES"),
        _row("NO\tDESCRIPTION"),
        _row("D99\tRefer to specification"),  # note, not a table instance
        _row("DOOR SCHEDULE"),
        _row("DOOR NO\tWIDTH\tHEIGHT\tREMARKS"),
    ] + [
        _row(f"D{i:02d}\t{820 + 10 * (i % 3)}\t2040\tDoor type")
        for i in range(1, 29)
    ]
    before = deepcopy(rows)
    entries = parse_schedule_rows(rows, page_no=28, two_level_header=True)
    assert [entry.type_mark for entry in entries] == [
        f"D{i:02d}" for i in range(1, 29)
    ]
    assert all(entry.height_mm == 2040 for entry in entries)
    assert all(entry.width_mm is not None for entry in entries)
    assert all(entry.dimension_basis == "" for entry in entries)
    assert all(entry.parse_source == "header_separate" for entry in entries)
    assert all(entry.count_explicit is False for entry in entries)
    assert all(entry.page_no == 28 for entry in entries)
    assert rows == before  # no source record mutation


def test_original_default_parser_remains_separate():
    # B2 original defaults still accept a width-only/mark-only heading; the
    # strict two-level mode must not change historic source-neutral callers.
    rows = [_row("Door\tNotes"), _row("D01\t820x2040")]
    original = parse_schedule_rows(rows)
    assert [e.type_mark for e in original] == ["D01"]
    assert parse_schedule_rows(rows, two_level_header=True) == []


def test_composite_mark_heading_is_explicit_but_generic_basis_remains_unknown():
    rows = [_row("WINDOW MARK\tWIDTH\tHEIGHT"), _row("W01\t1200\t1500")]
    entries = parse_schedule_rows(rows, two_level_header=True)
    assert len(entries) == 1
    assert (entries[0].width_mm, entries[0].height_mm) == (1200, 1500)
    assert entries[0].dimension_basis == ""
    assert entries[0].basis_source == ""


def test_explicit_basis_survives_only_when_both_dimension_columns_agree():
    rows = [
        _row("Door No\tRough Opening Width\tRough Opening Height"),
        _row("D01\t920\t2100"),
    ]
    entries = parse_schedule_rows(rows, two_level_header=True)
    assert len(entries) == 1
    assert entries[0].dimension_basis == "rough_opening"


def test_competing_incompatible_complete_headers_abstain():
    rows = [
        _row("Mark\tSize"),  # combined dimension layout
        _row("DOOR NO\tWIDTH\tHEIGHT"),
        _row("D01\t920\t2040"),
    ]
    assert parse_schedule_rows(rows, two_level_header=True) == []
    assert parse_schedule_rows(list(reversed(rows)), two_level_header=True) == []


def test_competing_width_height_basis_headers_abstain():
    rows = [
        _row("Mark\tFrame Width\tFrame Height"),
        _row("Door No\tRough Opening Width\tRough Opening Height"),
        _row("D01\t920\t2100"),
    ]
    assert parse_schedule_rows(rows, two_level_header=True) == []


def test_repeated_identical_header_safe_and_no_ghost_rows():
    rows = [
        _row("DOOR NO\tWIDTH\tHEIGHT"),
        _row("D01\t820\t2040"),
        _row("DOOR NO\tWIDTH\tHEIGHT"),
        _row("D02\t920\t2040"),
    ]
    entries = parse_schedule_rows(rows, two_level_header=True)
    assert [e.type_mark for e in entries] == ["D01", "D02"]


def test_missing_or_incomplete_header_abstains_without_heuristic_fallback():
    rows = [
        _row("Door Schedule"),
        _row("DOOR\tNOTES"),
        _row("D01\t820x2040"),
    ]
    assert parse_schedule_rows(rows, two_level_header=True) == []
    assert len(parse_schedule_rows(rows)) == 1


@pytest.mark.parametrize("invalid", [None, 0, 1, "true", [], {}])
def test_only_boolean_opt_in_is_accepted(invalid):
    with pytest.raises(TypeError, match="two_level_header must be a bool"):
        parse_schedule_rows([_row("Mark\tSize")], two_level_header=invalid)


# Actual producer-owned physical-opening instance schedule seam.
# These are source-neutral row contracts, not fake original-source receipts.
from pb_schedule_opening_instance_binding_authority import (
    _header_table_specs,
    _schedule_entries_for_page,
)


def _native_header(cells: tuple[str, ...], y: float):
    return (
        {
            "text": "\t".join(cells),
            "bounds": [(float(i * 80), float(i * 80 + 50)) for i in range(len(cells))],
            "center_y": y,
        },
        tuple(f"source-word-{int(y)}-{i}" for i in range(len(cells))),
    )


@pytest.mark.parametrize("cells", [
    ("DOOR", "NOTES"),
    ("MARK", "DESCRIPTION"),
    ("MARK", "WIDTH", "NOTES"),
    ("MARK", "HEIGHT", "COUNT"),
])
def test_real_instance_schedule_producer_ignores_dimensionless_headers(cells):
    row, ids = _native_header(cells, 10)
    assert _header_table_specs(row, ids) == []


def test_real_instance_schedule_producer_rejects_note_before_real_table():
    note = _native_header(("DOOR", "NOTES"), 10)
    faux = _native_header(("D01", "920x2040"), 19)
    header = _native_header(("MARK", "WIDTH", "HEIGHT"), 30)
    real = _native_header(("D01", "920", "2040"), 39)
    found = _schedule_entries_for_page((note, faux, header, real), 28)
    assert len(found) == 1
    entry, ids = found[0]
    assert entry.type_mark == "D01"
    assert (entry.width_mm, entry.height_mm) == (920, 2040)
    assert entry.dimension_basis == ""
    assert entry.count_explicit is False
    assert ids == real[1]


def test_real_instance_schedule_producer_still_accepts_complete_headers():
    for cells in (
        ("MARK", "SIZE"),
        ("MARK", "WIDTH", "HEIGHT"),
        ("DOOR", "TYPE", "WIDTH", "HEIGHT"),
    ):
        row, ids = _native_header(cells, 10)
        assert len(_header_table_specs(row, ids)) == 1


def test_real_instance_schedule_producer_preserves_two_side_by_side_headers():
    cells = ("MARK", "WIDTH", "HEIGHT", "MARK", "WIDTH", "HEIGHT")
    row, ids = _native_header(cells, 10)
    assert len(_header_table_specs(row, ids)) == 2


def test_dimensional_admission_cannot_run_past_partial_header_boundary():
    """A notes/partial table is a stop signal, not a dimensioned new table."""
    first = _native_header(("MARK", "WIDTH", "HEIGHT"), 10)
    first_row = _native_header(("D01", "820", "2040"), 19)
    partial = _native_header(("MARK", "DESCRIPTION"), 29)
    ghost = _native_header(("D02", "920", "2040"), 39)
    new_header = _native_header(("MARK", "WIDTH", "HEIGHT"), 49)
    new_row = _native_header(("D03", "900", "2100"), 59)
    assert _header_table_specs(partial[0], partial[1]) == []
    assert _header_table_specs(partial[0], partial[1], stop_boundary=True)
    matches = _schedule_entries_for_page(
        (first, first_row, partial, ghost, new_header, new_row), 28,
    )
    assert [entry.type_mark for entry, _ in matches] == ["D01", "D03"]
    assert [ids for _, ids in matches] == [first_row[1], new_row[1]]


def test_partial_stop_header_does_not_suppress_adjacent_independent_table():
    """Stop boundaries use observed ink bounds, not an infinite x window."""
    header = _native_header(
        ("MARK", "WIDTH", "HEIGHT", "MARK", "WIDTH", "HEIGHT"), 10,
    )
    row1 = _native_header(
        ("D01", "820", "2040", "W01", "900", "2100"), 19,
    )
    left_partial = _native_header(("MARK", "DESCRIPTION"), 29)
    row2 = _native_header(
        ("D02", "820", "2040", "W02", "900", "2100"), 39,
    )
    matches = _schedule_entries_for_page(
        (header, row1, left_partial, row2), 28,
    )
    assert [entry.type_mark for entry, _ in matches] == [
        "D01", "W01", "W02",
    ]
    assert matches[-1][1] == row2[1][3:]
