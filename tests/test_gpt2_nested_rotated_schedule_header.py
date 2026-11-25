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


class _Table:
    def __init__(self, rows):
        self.rows = rows
    def extract(self):
        return self.rows


class _PageWithGrid(_RotatedPage):
    def __init__(self, tables, valid=True):
        super().__init__(valid=valid)
        self.tables = tuple(_Table(rows) for rows in tables)
    def find_tables(self, *, strategy):
        assert strategy == "lines_strict"
        from types import SimpleNamespace
        return SimpleNamespace(tables=self.tables)


def _nested_grid_rows():
    return [
        [None, "DOOR SCHEDULE", None, None, None, None, None, None, None],
        [None, "DOOR No.", "ROOM NAME", "TYPE", "DOOR LEAF", None, None,
         None, "DOOR FRAME"],
        [None, None, None, None, "WIDTH", "HEIGHT", None, "THICKNESS",
         "TYPE"],
        [None, "D01", "Sales", "AUTOMATED DOUBLE", None, None, None, None,
         "Aluminium"],
        [None, "D07", "WC & SHOWER", "SINGLE SWING", "920", "2040", None,
         "40", "Aluminium"],
        [None, "D08", "WC & SHOWER", "SINGLE SWING", "920", "2040", None,
         "40", "Aluminium"],
        [None, "D18", "Freezer", "AS PER MANUFACTURER", None, None, None,
         None, "Lessee contractor"],
    ]


def test_original_style_spanning_parent_and_native_grid_cell_ownership():
    page = _PageWithGrid([_nested_grid_rows()])
    entries = parse_schedule_page(page, page_no=28, two_level_header=True)
    assert [e.type_mark for e in entries] == ["D01", "D07", "D08", "D18"]
    assert [(e.width_mm, e.height_mm) for e in entries] == [
        (None, None), (920, 2040), (920, 2040), (None, None)
    ]
    assert all(e.dimension_basis == "leaf" for e in entries)
    assert all(e.parse_source == "source_grid_nested_header" for e in entries)
    assert all(e.count_explicit is False for e in entries)


def test_unrelated_spanning_window_frame_grid_uses_same_rule():
    rows = [
        ["WINDOW MARK", "WINDOW FRAME", None, None],
        [None, "WIDTH", "HEIGHT", "DESCRIPTION"],
        ["W01", "1200", "1500", "aluminium"],
    ]
    out = parse_schedule_page(_PageWithGrid([rows]), two_level_header=True)
    assert [(e.type_mark, e.width_mm, e.height_mm, e.dimension_basis)
            for e in out] == [("W01", 1200, 1500, "frame")]


def test_conflicting_competing_scheduled_grid_tables_abstain():
    rows = _nested_grid_rows()
    assert parse_schedule_page(
        _PageWithGrid([rows, rows]), two_level_header=True
    ) == []


def test_duplicate_grid_mark_is_not_silently_overwritten():
    rows = _nested_grid_rows()
    rows.append([None, "D07", "other", "SWING", "820", "2040",
                 None, "40", "steel"])
    assert parse_schedule_page(
        _PageWithGrid([rows]), two_level_header=True
    ) == []


def test_invalid_grid_without_unique_child_dimension_basis_falls_back_without_promotion():
    rows = _nested_grid_rows()
    rows[2][5] = "WIDTH"
    # Invalid grid goes to ordinary rotated-word candidate. Fake visible
    # words still independently describe one explicit nested leaf row.
    out = parse_schedule_page(_PageWithGrid([rows]), two_level_header=True)
    assert [e.type_mark for e in out] == ["D01"]
    assert out[0].dimension_basis == "leaf"


def _second_format_grouped_grid_rows():
    """Second schedule format: grouped door marks + manufacturer exclusions."""
    return [
        ["DOOR SCHEDULE - COMMERCIAL FITOUT", None, None, None, None, None],
        ["DOOR MARK", "LOCATION", "DOOR LEAF", None, "DOOR FRAME", "NOTES"],
        [None, None, "WIDTH", "HEIGHT", "MATERIAL", None],
        ["D01", "Entry", "AS PER MANUFACTURER", "AS PER MANUFACTURER (2400mm)",
         "Aluminium", "Auto slider by specialist"],
        ["D02", "Lounge", "900 mm", "2050 mm", "Alum", ""],
        ["D04-D06", "Cubicles", "600", "1700", "Partition", "Compact laminate"],
        ["D07, D08, D09", "Amenities", "920", "2040", "Alum", "25mm undercut"],
        ["D11 & D12", "Ambulant", "820", "2040", "Alum", "AS1428.1"],
        ["D16 / D17", "Coolroom", "800", "2000", "Insulated", "BY COOLROOM CONTRACTOR"],
        ["D18 to D20", "Display", "BY OTHERS (900mm)", "TBC 2100",
         "By lessee", "AS PER MANUFACTURER"],
        ["D21", "Service", "N/A", "REFER DETAIL 1200mm", "By others", "NIC"],
    ]


def test_second_schedule_format_grouped_doors_and_manufacturer_exclusions_grid():
    out = parse_schedule_page(
        _PageWithGrid([_second_format_grouped_grid_rows()]),
        page_no=14,
        two_level_header=True,
    )
    by_mark = {e.type_mark: (e.width_mm, e.height_mm, e.dimension_basis, e.count_explicit) for e in out}
    assert [e.type_mark for e in out] == [
        "D01", "D02",
        "D04", "D05", "D06",
        "D07", "D08", "D09",
        "D11", "D12",
        "D16", "D17",
        "D18", "D19", "D20",
        "D21",
    ]
    # Manufacturer/contractor exclusions in dimension cells abstain even when a
    # stray reference number appears inside the exclusion text.
    assert by_mark["D01"] == (None, None, "leaf", False)
    for mark in ("D18", "D19", "D20", "D21"):
        assert by_mark[mark] == (None, None, "leaf", False)
    # Explicit numeric leaf sizes stay exact (no 35/50 mm frame adjustment), even
    # when the separate NOTES column mentions a trade contractor.
    assert by_mark["D02"] == (900, 2050, "leaf", False)
    for mark in ("D04", "D05", "D06"):
        assert by_mark[mark] == (600, 1700, "leaf", False)
    for mark in ("D07", "D08", "D09"):
        assert by_mark[mark] == (920, 2040, "leaf", False)
    for mark in ("D11", "D12"):
        assert by_mark[mark] == (820, 2040, "leaf", False)
    for mark in ("D16", "D17"):
        assert by_mark[mark] == (800, 2000, "leaf", False)
    assert all(e.parse_source == "source_grid_nested_header" for e in out)


def test_second_schedule_format_grouped_rows_text_table_and_frame_basis():
    rows = [
        row("WINDOW MARK", "WINDOW FRAME", "WINDOW FRAME", "NOTES"),
        row("MARK", "WIDTH", "HEIGHT", "NOTES"),
        row("W01-W03", "1200", "1500", "Fixed aluminium"),
        row("W04, W05", "BY MANUFACTURER 1800mm", "AS PER MFR", "Shopfront"),
        row("W06 & W07", "900", "TBC 1200", "Verify on site"),
    ]
    out = parse_schedule_rows(rows, page_no=9, two_level_header=True)
    assert [(e.type_mark, e.width_mm, e.height_mm, e.dimension_basis, e.count_explicit) for e in out] == [
        ("W01", 1200, 1500, "frame", False),
        ("W02", 1200, 1500, "frame", False),
        ("W03", 1200, 1500, "frame", False),
        ("W04", None, None, "frame", False),
        ("W05", None, None, "frame", False),
        ("W06", 900, None, "frame", False),
        ("W07", 900, None, "frame", False),
    ]


@pytest.mark.parametrize("bad_mark", [
    "D06-D04",       # reversed range
    "D01-W03",       # mixed prefix range
    "D01-D99",       # oversized range (>50)
    "D04-D006",      # forward mixed zero-padding width
    "D1-D03",        # reverse mixed zero-padding width
    "D01-D3",        # padded-to-unpadded mixed width
    "D01-X03",       # malformed range endpoint (non-opening mark)
    "X01-D03",       # malformed range start (non-opening mark)
    "D01-99",        # numeric-only range endpoint
    "D01 to X03",    # malformed 'to' range endpoint
    "D01, X03",      # malformed list member
    "D04, D04",      # duplicate in same cell
    "D1, D01",       # canonically duplicate mark in same cell
    "D04-D06, D05",  # overlapping range and explicit duplicate
    "D04-D06, D5",   # overlapping range and canonically duplicate mark
    "D01-D02-D03",   # chained malformed range
    "D01,",          # trailing delimiter
])
def test_malformed_grouped_mark_expressions_fail_closed(bad_mark):
    rows = [
        ["DOOR MARK", "DOOR LEAF", None],
        [None, "WIDTH", "HEIGHT"],
        [bad_mark, "920", "2040"],
    ]
    # Grid fail-closed MUST return [] and NEVER fall back to _RotatedPage's word-row D01.
    assert parse_schedule_page(_PageWithGrid([rows]), two_level_header=True) == []
    text_rows = [
        row("DOOR NO", "DOOR LEAF", "DOOR LEAF"),
        row("NO", "WIDTH", "HEIGHT"),
        row(bad_mark, "920", "2040"),
    ]
    assert parse_schedule_rows(text_rows, two_level_header=True) == []


@pytest.mark.parametrize("second_mark", ["D05", "D5", "d05"])
def test_grouped_mark_overlapping_later_individual_or_canonical_row_fails_closed(second_mark):
    rows = [
        ["DOOR MARK", "DOOR LEAF", None],
        [None, "WIDTH", "HEIGHT"],
        ["D04-D06", "600", "1700"],
        [second_mark, "920", "2040"],
    ]
    # Must fail closed without falling back to _RotatedPage word rows.
    assert parse_schedule_page(_PageWithGrid([rows]), two_level_header=True) == []
    text_rows = [
        row("DOOR NO", "DOOR LEAF", "DOOR LEAF"),
        row("NO", "WIDTH", "HEIGHT"),
        row("D04-D06", "600", "1700"),
        row(second_mark, "920", "2040"),
    ]
    assert parse_schedule_rows(text_rows, two_level_header=True) == []


def test_duplicate_canonical_marks_d1_and_d01_across_rows_fail_closed():
    rows = [
        ["DOOR MARK", "DOOR LEAF", None],
        [None, "WIDTH", "HEIGHT"],
        ["D1", "820", "2040"],
        ["D01", "920", "2040"],
    ]
    assert parse_schedule_page(_PageWithGrid([rows]), two_level_header=True) == []
    text_rows = [
        row("DOOR NO", "DOOR LEAF", "DOOR LEAF"),
        row("NO", "WIDTH", "HEIGHT"),
        row("D1", "820", "2040"),
        row("D01", "920", "2040"),
    ]
    assert parse_schedule_rows(text_rows, two_level_header=True) == []


def test_strict_combined_dims_and_separate_cells_reject_arbitrary_prose_with_numbers():
    rows = [
        row("DOOR MARK", "LEAF SIZE", "NOTES"),
        row("D01-D02", "920 x 2040", "Solid core"),
        row("D03", "AS PER MANUFACTURER (920 x 2040)", "Coolroom"),
        row("D04", "BY OTHERS 820x2040", "Tenant"),
        row("D05", "Check detail 920 x 2040 before order", "Arbitrary prose"),
        row("D06", "Door leaf 820 x 2040 pending review", "Arbitrary prose"),
        row("D07", "920mm x 2040mm", "Valid with units"),
        row("D08", "0.92 m x 2.04 m", "Valid metres"),
    ]
    out = parse_schedule_rows(rows, two_level_header=True)
    assert [(e.type_mark, e.width_mm, e.height_mm, e.dimension_basis) for e in out] == [
        ("D01", 920, 2040, "leaf"),
        ("D02", 920, 2040, "leaf"),
        ("D03", None, None, "leaf"),
        ("D04", None, None, "leaf"),
        ("D05", None, None, "leaf"),
        ("D06", None, None, "leaf"),
        ("D07", 920, 2040, "leaf"),
        ("D08", 920, 2040, "leaf"),
    ]
    sep_rows = [
        row("DOOR NO", "DOOR LEAF", "DOOR LEAF"),
        row("NO", "WIDTH", "HEIGHT"),
        row("D01", "Check 920", "Confirm 2040"),
        row("D02", "920mm", "2040mm"),
    ]
    sep_out = parse_schedule_rows(sep_rows, two_level_header=True)
    assert [(e.type_mark, e.width_mm, e.height_mm) for e in sep_out] == [
        ("D01", None, None),
        ("D02", 920, 2040),
    ]
