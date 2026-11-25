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


# ---------------------------------------------------------------------------
# Item 10: Rotated schedule coordinates across 0/90/180/270 degrees + fail-closed
# ---------------------------------------------------------------------------

def _make_rotated_words_page(
    display_words,
    *,
    rotation: int,
    width: float = 500.0,
    height: float = 400.0,
    matrix_override=None,
):
    """Build a synthetic PDF page whose native words map via rotation_matrix to display_words."""
    norm = rotation % 360 if isinstance(rotation, int) and not isinstance(rotation, bool) and rotation % 90 == 0 else None
    if norm == 90:
        mat = _Matrix(a=0.0, b=1.0, c=-1.0, d=0.0, e=height, f=0.0)
        # Inverse of (x' = -y + H, y' = x) is (x = y', y = H - x')
        inv = lambda dx0, dy0, dx1, dy1: (dy0, height - dx1, dy1, height - dx0)
    elif norm == 180:
        mat = _Matrix(a=-1.0, b=0.0, c=0.0, d=-1.0, e=width, f=height)
        # Inverse of (x' = W - x, y' = H - y) is (x = W - x', y = H - y')
        inv = lambda dx0, dy0, dx1, dy1: (width - dx1, height - dy1, width - dx0, height - dy0)
    elif norm == 270:
        mat = _Matrix(a=0.0, b=-1.0, c=1.0, d=0.0, e=0.0, f=width)
        # Inverse of (x' = y, y' = W - x) is (x = W - y', y = x')
        inv = lambda dx0, dy0, dx1, dy1: (width - dy1, dx0, width - dy0, dx1)
    else:
        mat = _Matrix(a=1.0, b=0.0, c=0.0, d=1.0, e=0.0, f=0.0)
        inv = lambda dx0, dy0, dx1, dy1: (dx0, dy0, dx1, dy1)

    native_words = []
    for idx, (dx0, dy0, dx1, dy1, text) in enumerate(display_words):
        nx0, ny0, nx1, ny1 = inv(dx0, dy0, dx1, dy1)
        native_words.append((nx0, ny0, nx1, ny1, text, idx, 0, 0))

    class _DynamicRotatedPage:
        pass

    page = _DynamicRotatedPage()
    page.rotation = rotation
    page.rotation_matrix = mat if matrix_override is None else matrix_override
    page.get_text = lambda kind: list(native_words) if kind == "words" else ""
    return page


@pytest.mark.parametrize("rotation", [0, 90, 180, 270, -90, 360, 450])
def test_metamorphic_rotation_invariance_across_all_quadrants(rotation):
    """Identical display-space schedule yields identical entries across 0/90/180/270 deg."""
    display_words = [
        # Row 0: split mark top + centered spanning DOOR LEAF + NOTES
        (10.0, 10.0, 42.0, 20.0, "DOOR"),
        (125.0, 10.0, 160.0, 20.0, "DOOR"),
        (165.0, 10.0, 205.0, 20.0, "LEAF"),
        (280.0, 10.0, 325.0, 20.0, "NOTES"),
        # Row 1: split mark bottom + WIDTH + HEIGHT
        (10.0, 26.0, 35.0, 36.0, "NO."),
        (100.0, 26.0, 145.0, 36.0, "WIDTH"),
        (190.0, 26.0, 240.0, 36.0, "HEIGHT"),
        # Row 2: pure unit continuation row
        (105.0, 42.0, 138.0, 52.0, "(mm)"),
        (195.0, 42.0, 228.0, 52.0, "(mm)"),
        # Data rows + wrapped notes continuation line (must NOT shift left!)
        (10.0, 62.0, 36.0, 72.0, "D01"),
        (105.0, 62.0, 130.0, 72.0, "920"),
        (195.0, 62.0, 228.0, 72.0, "2040"),
        (280.0, 62.0, 320.0, 72.0, "Solid"),
        (324.0, 62.0, 355.0, 72.0, "core"),
        # Wrapped notes line containing a door mark token strictly in NOTES column
        (280.0, 78.0, 310.0, 88.0, "D99"),
        (10.0, 98.0, 58.0, 108.0, "D02-D03"),
        (105.0, 98.0, 130.0, 108.0, "820"),
        (195.0, 98.0, 228.0, 108.0, "2100"),
        (280.0, 98.0, 330.0, 108.0, "Hollow"),
    ]
    page = _make_rotated_words_page(display_words, rotation=rotation)
    out = parse_schedule_page(page, page_no=5, two_level_header=True)
    assert [(e.type_mark, e.width_mm, e.height_mm, e.dimension_basis) for e in out] == [
        ("D01", 920, 2040, "leaf"),
        ("D02", 820, 2100, "leaf"),
        ("D03", 820, 2100, "leaf"),
    ]


@pytest.mark.parametrize("bad_rotation", [45, 135, -45, True, "90", 90.5])
def test_invalid_page_rotation_values_fail_closed(bad_rotation):
    display_words = [
        (10.0, 10.0, 60.0, 20.0, "DOOR NO"),
        (100.0, 10.0, 150.0, 20.0, "LEAF WIDTH"),
        (190.0, 10.0, 240.0, 20.0, "LEAF HEIGHT"),
        (10.0, 40.0, 40.0, 50.0, "D01"),
        (100.0, 40.0, 130.0, 50.0, "920"),
        (190.0, 40.0, 220.0, 50.0, "2040"),
    ]
    page = _make_rotated_words_page(display_words, rotation=bad_rotation)
    assert parse_schedule_page(page, two_level_header=True) == []


@pytest.mark.parametrize(
    "rotation,bad_matrix",
    [
        # Identity matrix mismatched with rotation=90
        (90, _Matrix(a=1.0, b=0.0, c=0.0, d=1.0, e=0.0, f=0.0)),
        # 270 matrix mismatched with rotation=90
        (90, _Matrix(a=0.0, b=-1.0, c=1.0, d=0.0, e=0.0, f=500.0)),
        # Reflected matrix (negative determinant)
        (180, _Matrix(a=-1.0, b=0.0, c=0.0, d=1.0, e=500.0, f=0.0)),
        # Skewed non-orthogonal matrix
        (90, _Matrix(a=0.2, b=1.0, c=-1.0, d=0.0, e=400.0, f=0.0)),
        # Singular zero-determinant matrix
        (270, _Matrix(a=0.0, b=0.0, c=0.0, d=0.0, e=0.0, f=0.0)),
        # Non-finite translation
        (180, _Matrix(a=-1.0, b=0.0, c=0.0, d=-1.0, e=float("nan"), f=400.0)),
    ],
)
def test_corrupt_or_mismatched_rotation_matrix_fails_closed(rotation, bad_matrix):
    display_words = [
        (10.0, 10.0, 60.0, 20.0, "DOOR NO"),
        (100.0, 10.0, 150.0, 20.0, "LEAF WIDTH"),
        (190.0, 10.0, 240.0, 20.0, "LEAF HEIGHT"),
        (10.0, 40.0, 40.0, 50.0, "D01"),
        (100.0, 40.0, 130.0, 50.0, "920"),
        (190.0, 40.0, 220.0, 50.0, "2040"),
    ]
    page = _make_rotated_words_page(display_words, rotation=rotation, matrix_override=bad_matrix)
    assert parse_schedule_page(page, two_level_header=True) == []


def test_inverted_word_bbox_on_rotated_page_fails_closed():
    page = _make_rotated_words_page([], rotation=270)
    page.get_text = lambda kind: [
        (50.0, 10.0, 20.0, 20.0, "DOOR", 0, 0, 0),  # inverted x1 < x0
    ]
    assert parse_schedule_page(page, two_level_header=True) == []


# ---------------------------------------------------------------------------
# Item 11: Multi-line wrapped headers & cells WITHOUT crossing column ownership
# ---------------------------------------------------------------------------

def test_grid_parent_span_stops_at_unrelated_neighbor_column_without_crossing():
    """DOOR LEAF span MUST NOT cross VISION PANEL to steal its HEIGHT column."""
    rows = [
        ["DOOR NO.", "DOOR LEAF", None, "VISION PANEL", None],
        [None, "WIDTH", "THICKNESS", "HEIGHT", "GLAZING"],
        ["D01", "920", "40", "1200", "Toughened"],
    ]
    # Grid has no valid complete DOOR LEAF pair (HEIGHT belongs to VISION PANEL);
    # with an empty non-grid page it MUST abstain instead of pairing 920 x 1200.
    page = _PageWithGrid([rows])
    page.get_text = lambda kind: []
    assert parse_schedule_page(page, two_level_header=True) == []


def test_grid_multiline_split_mark_wrapped_units_3row_headers_and_wrapped_cells():
    # 1. 2-row vertically split mark header ("DOOR" / "NO."), wrapped "(mm)" child headers,
    #    and wrapped multi-line mark/dimension cells ("D01\nD02", "D03 -\nD04", "920\nmm").
    rows_2 = [
        ["DOOR", "ROUGH\nOPENING", None, "NOTES"],
        ["NO.", "WIDTH\n(mm)", "HEIGHT\n(MM)", None],
        ["D01\nD02", "920\nmm", "2040\nmm", "Line 1\nLine 2"],
        ["D03 -\nD04", "820", "2040", "Wrapped hyphen range"],
    ]
    out_2 = parse_schedule_page(_PageWithGrid([rows_2]), page_no=3, two_level_header=True)
    assert [(e.type_mark, e.width_mm, e.height_mm, e.dimension_basis) for e in out_2] == [
        ("D01", 920, 2040, "rough_opening"),
        ("D02", 920, 2040, "rough_opening"),
        ("D03", 820, 2040, "rough_opening"),
        ("D04", 820, 2040, "rough_opening"),
    ]

    # 2. 3-row stacked parent header ("DOOR" + "LEAF" over "WIDTH"/"HEIGHT").
    rows_3p = [
        ["DOOR", "DOOR", None],
        ["MARK", "LEAF", None],
        [None, "WIDTH (mm)", "HEIGHT (mm)"],
        ["D10", "900", "2100"],
    ]
    out_3p = parse_schedule_page(_PageWithGrid([rows_3p]), page_no=4, two_level_header=True)
    assert [(e.type_mark, e.width_mm, e.height_mm, e.dimension_basis) for e in out_3p] == [
        ("D10", 900, 2100, "leaf"),
    ]

    # 3. 3-row header with separate unit continuation row ("(mm)").
    rows_3u = [
        ["WINDOW\nMARK", "CLEAR\nOPENING", None],
        [None, "WIDTH", "HEIGHT"],
        [None, "(mm)", "(mm)"],
        ["W01,\nW02", "1200", "1500"],
    ]
    out_3u = parse_schedule_page(_PageWithGrid([rows_3u]), page_no=6, two_level_header=True)
    assert [(e.type_mark, e.width_mm, e.height_mm, e.dimension_basis) for e in out_3u] == [
        ("W01", 1200, 1500, "clear_opening"),
        ("W02", 1200, 1500, "clear_opening"),
    ]

    # 4. Single-row wrapped native grid header (both separate and combined).
    rows_1 = [
        ["DOOR\nMARK", "DOOR FRAME\nWIDTH\n(mm)", "DOOR FRAME\nHEIGHT\n(mm)"],
        ["D05", "960", "2080"],
    ]
    out_1 = parse_schedule_page(_PageWithGrid([rows_1]), page_no=7, two_level_header=True)
    assert [(e.type_mark, e.width_mm, e.height_mm, e.dimension_basis) for e in out_1] == [
        ("D05", 960, 2080, "frame"),
    ]


def test_grid_conflicting_child_basis_under_parent_span_fails_closed():
    rows = [
        ["DOOR NO.", "DOOR LEAF", None],
        [None, "FRAME WIDTH", "HEIGHT"],
        ["D01", "920", "2040"],
    ]
    assert parse_schedule_page(_PageWithGrid([rows]), two_level_header=True) == []


def test_rough_and_clear_opening_nested_text_headers_preserve_basis():
    rows = [
        row("DOOR NO", "ROUGH OPENING", "ROUGH OPENING"),
        row("NO", "WIDTH (mm)", "HEIGHT (mm)"),
        row("D01", "950", "2070"),
    ]
    out = parse_schedule_rows(rows, two_level_header=True)
    assert [(e.type_mark, e.width_mm, e.height_mm, e.dimension_basis) for e in out] == [
        ("D01", 950, 2070, "rough_opening"),
    ]


def test_borderless_data_phrase_crossing_two_columns_fails_closed():
    """A value physically bridging WIDTH and HEIGHT columns must fail closed."""
    display_words = [
        (10.0, 10.0, 60.0, 20.0, "DOOR NO"),
        (125.0, 10.0, 205.0, 20.0, "DOOR LEAF"),
        (100.0, 26.0, 145.0, 36.0, "WIDTH"),
        (190.0, 26.0, 240.0, 36.0, "HEIGHT"),
        (10.0, 50.0, 36.0, 60.0, "D01"),
        # Single wide phrase physically overlapping BOTH WIDTH [100,145] and HEIGHT [190,240]
        (115.0, 50.0, 215.0, 60.0, "920x2040"),
    ]
    page = _make_rotated_words_page(display_words, rotation=90)
    assert parse_schedule_page(page, two_level_header=True) == []


def test_borderless_spanning_parent_bleeding_into_unrelated_column_fails_closed():
    """Two parent phrases overlapping the same child column must fail closed."""
    display_words = [
        (10.0, 10.0, 60.0, 20.0, "DOOR NO"),
        (95.0, 10.0, 165.0, 20.0, "DOOR LEAF"),
        (140.0, 10.0, 245.0, 20.0, "DOOR FRAME"),
        (100.0, 26.0, 145.0, 36.0, "WIDTH"),
        (190.0, 26.0, 240.0, 36.0, "HEIGHT"),
        (10.0, 50.0, 36.0, 60.0, "D01"),
        (105.0, 50.0, 130.0, 60.0, "920"),
        (195.0, 50.0, 228.0, 60.0, "2040"),
    ]
    page = _make_rotated_words_page(display_words, rotation=0)
    assert parse_schedule_page(page, two_level_header=True) == []


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_real_pymupdf_rotated_page_extracts_identical_schedule(rotation):
    """End-to-end PyMuPDF page with real /Rotate 0/90/180/270 and display-upright text."""
    import fitz

    doc = fitz.open()
    # Mediabox dimensions chosen so display page is always 500 x 350.
    w_disp, h_disp = 500.0, 350.0
    if rotation in (90, 270):
        page = doc.new_page(width=h_disp, height=w_disp)
    else:
        page = doc.new_page(width=w_disp, height=h_disp)
    page.set_rotation(rotation)

    # Place words in display-space coordinates, transformed back into native
    # mediabox space via derotation_matrix. PDF /Rotate is clockwise while
    # PyMuPDF insert_text(rotate=) is counter-clockwise, so equal angles render
    # visually upright in display space (matching rotated CAD/Revit sheets).
    derot = page.derotation_matrix
    items = [
        (30.0, 40.0, "DOOR"),
        (140.0, 40.0, "DOOR LEAF SIZE"),
        (30.0, 62.0, "NO."),
        (140.0, 62.0, "WIDTH"),
        (210.0, 62.0, "HEIGHT"),
        (30.0, 95.0, "D01"),
        (145.0, 95.0, "920"),
        (215.0, 95.0, "2040"),
        (30.0, 125.0, "D02-D03"),
        (145.0, 125.0, "820"),
        (215.0, 125.0, "2100"),
    ]
    for dx, dy, text in items:
        pt = fitz.Point(dx, dy) * derot
        page.insert_text(pt, text, fontsize=9, rotate=rotation)

    raw = doc.tobytes()
    doc.close()

    reopened = fitz.open(stream=raw, filetype="pdf")
    try:
        out = parse_schedule_page(reopened[0], page_no=1, two_level_header=True)
    finally:
        reopened.close()
    assert [(e.type_mark, e.width_mm, e.height_mm, e.dimension_basis) for e in out] == [
        ("D01", 920, 2040, "leaf"),
        ("D02", 820, 2100, "leaf"),
        ("D03", 820, 2100, "leaf"),
    ]


class _CleanGridPage(_PageWithGrid):
    """Grid test page with empty fallback word stream so non-opening grids test true abstention."""

    def get_text(self, mode):
        if mode == "words":
            return []
        return super().get_text(mode)


def test_unfamiliar_plan_style_clear_opening_grouped_and_site_verify_exclusion():
    """Unfamiliar bordered commercial schedule with CLEAR OPENING + grouped marks + site-verify blank."""
    page = _CleanGridPage(
        [
            [
                ["WINDOW & DOOR SCHEDULE", None, None, None],
                ["DOOR / WINDOW MARK", "CLEAR OPENING", None, "REMARKS"],
                [None, "WIDTH (mm)", "HEIGHT (mm)", None],
                ["W01, W02", "1800", "1500", "DOUBLE GLAZED"],
                ["D04-D05", "920", "2040", "SOLID CORE"],
                ["D06", "BY MANUFACTURER", "VERIFY ON SITE", "CUSTOM ROLLER"],
            ]
        ]
    )
    out = parse_schedule_page(page, page_no=3, two_level_header=True)
    assert [(e.type_mark, e.width_mm, e.height_mm, e.dimension_basis) for e in out] == [
        ("W01", 1800, 1500, "clear_opening"),
        ("W02", 1800, 1500, "clear_opening"),
        ("D04", 920, 2040, "clear_opening"),
        ("D05", 920, 2040, "clear_opening"),
        ("D06", None, None, "clear_opening"),
    ]


def test_unfamiliar_non_opening_room_finish_and_structural_schedules_return_empty():
    """Unfamiliar non-opening schedules (room finishes, beams, narrative glazing notes) emit zero rows."""
    room_finish_grid = _CleanGridPage(
        [
            [
                ["ROOM NO", "FLOOR FINISH", "WALL FINISH", "CEILING HEIGHT"],
                ["R01", "FT2 VINYL", "PT1 PAINT", "2700"],
                ["R02", "FT3 TILE", "WT1 TILE", "2400"],
            ]
        ]
    )
    assert parse_schedule_page(room_finish_grid, page_no=1, two_level_header=True) == []

    structural_grid = _CleanGridPage(
        [
            [
                ["MEMBER", "SECTION SIZE", "SPAN (mm)", "GRADE"],
                ["B01", "250UB31", "4800", "300PLUS"],
                ["C01", "100x100x5 SHS", "3000", "C350"],
            ]
        ]
    )
    assert parse_schedule_page(structural_grid, page_no=2, two_level_header=True) == []

    narrative_glazing_grid = _CleanGridPage(
        [
            [
                ["WINDOW", "PERFORMANCE", "U-VALUE", "SHGC"],
                ["AND DOOR SCHEDULE", "THERMALLY BROKEN", "3.2", "0.45"],
                ["GENERAL NOTE", "ALL EXTERNAL GLAZING TO AS1288", None, None],
            ]
        ]
    )
    assert parse_schedule_page(narrative_glazing_grid, page_no=10, two_level_header=True) == []


@pytest.mark.parametrize("rotation", [180, 270])
def test_unfamiliar_rotated_rough_opening_pymupdf_schedule(rotation):
    """Unfamiliar /Rotate 180 & 270 schedule using ROUGH OPENING headers extracts rough_opening basis."""
    import fitz

    doc = fitz.open()
    w_disp, h_disp = 520.0, 340.0
    page = doc.new_page(width=h_disp, height=w_disp) if rotation == 270 else doc.new_page(width=w_disp, height=h_disp)
    page.set_rotation(rotation)
    derot = page.derotation_matrix
    items = [
        (30.0, 40.0, "REF"),
        (140.0, 40.0, "ROUGH OPENING"),
        (30.0, 62.0, "MARK"),
        (140.0, 62.0, "WIDTH"),
        (215.0, 62.0, "HEIGHT"),
        (30.0, 95.0, "W10"),
        (145.0, 95.0, "2400"),
        (220.0, 95.0, "1800"),
        (30.0, 125.0, "D12"),
        (145.0, 125.0, "1020"),
        (220.0, 125.0, "2140"),
    ]
    for dx, dy, text in items:
        page.insert_text(fitz.Point(dx, dy) * derot, text, fontsize=9, rotate=rotation)
    raw = doc.tobytes()
    doc.close()

    reopened = fitz.open(stream=raw, filetype="pdf")
    try:
        out = parse_schedule_page(reopened[0], page_no=1, two_level_header=True)
    finally:
        reopened.close()
    assert [(e.type_mark, e.width_mm, e.height_mm, e.dimension_basis) for e in out] == [
        ("W10", 2400, 1800, "rough_opening"),
        ("D12", 1020, 2140, "rough_opening"),
    ]



