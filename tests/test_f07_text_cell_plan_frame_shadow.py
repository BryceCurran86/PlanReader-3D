"""Synthetic proofs for the default-off F.07 ``source_connected_text_cell_plan_frame_shadow``.

Every page here is built with PyMuPDF in memory; nothing reads a customer PDF,
a project name, a file name or an expected quantity. The shadow only ever
REMOVES table evidence for a plan title / a schedule binding and relaxes the
strict nested-band rule; with the flag absent or False the output is the legacy
output.
"""
from __future__ import annotations

import copy
import hashlib
import json

import fitz
import pytest

import pb_viewport_segmentation as v

FLAG = "source_connected_text_cell_plan_frame_shadow"
RESOLVED = v.ViewportSegmentationStatus.RESOLVED.value
AMBIGUOUS = v.ViewportSegmentationStatus.AMBIGUOUS.value

FRAME = (40.0, 30.0, 760.0, 520.0)
# A plan-sized frame can hold a lattice, a tile grid or a table. Cells are 40x20.
PLAN_TITLE = "GROUND FLOOR PLAN"


def _reopen(doc: fitz.Document) -> fitz.Document:
    data = doc.tobytes()
    doc.close()
    return fitz.open(stream=data, filetype="pdf")


def _new_page(width: float = 800.0, height: float = 600.0):
    doc = fitz.open()
    return doc, doc.new_page(width=width, height=height)


def _label(page, rect: fitz.Rect, text: str = "T-1", fontsize: float = 6.0) -> None:
    page.insert_text((rect.x0 + 3.0, rect.y0 + rect.height * 0.75), text, fontsize=fontsize)


def _frame(page, box) -> None:
    page.draw_rect(fitz.Rect(*box), color=(0, 0, 0), width=1.0)


def _lattice(page, x0, y0, cols, rows, w, h, pitch_x, pitch_y, *, text="T-1", dx=0.0, dy=0.0) -> None:
    """Separate fixtures on a regular lattice (open gaps), each labelled inside."""
    for row in range(rows):
        for col in range(cols):
            rect = fitz.Rect(
                x0 + col * pitch_x + dx, y0 + row * pitch_y + dy,
                x0 + col * pitch_x + w + dx, y0 + row * pitch_y + h + dy,
            )
            page.draw_rect(rect, color=(0, 0, 0), width=0.5)
            if text:
                _label(page, rect, text)


def _contiguous_grid(page, x0, y0, cols, rows, w, h, *, labelled: bool, dx=0.0, dy=0.0) -> None:
    """Adjacent cells that share every edge (a table, or a blank tile grid)."""
    for row in range(rows):
        for col in range(cols):
            rect = fitz.Rect(
                x0 + col * w + dx, y0 + row * h + dy,
                x0 + (col + 1) * w + dx, y0 + (row + 1) * h + dy,
            )
            page.draw_rect(rect, color=(0, 0, 0), width=0.5)
            if labelled:
                _label(page, rect, f"R{row}C{col}")


def _title(page, text=PLAN_TITLE, at=(60.0, 505.0), fontsize=11.0) -> None:
    page.insert_text(at, text, fontsize=fontsize)


def _lattice_plan(*, dx=0.0, dy=0.0, title=PLAN_TITLE, reverse=False):
    """One plan frame holding a labelled fixture lattice (the false-table pattern)."""
    doc, page = _new_page()
    ops = [
        lambda: _frame(page, tuple(c + o for c, o in zip(FRAME, (dx, dy, dx, dy)))),
        lambda: _lattice(page, 80.0, 60.0, 8, 6, 40.0, 20.0, 80.0, 40.0, dx=dx, dy=dy),
        lambda: _title(page, title, at=(60.0 + dx, 505.0 + dy)),
    ]
    for op in (reversed(ops) if reverse else ops):
        op()
    return _reopen(doc)


def _tile_plan():
    """One plan frame holding a contiguous BLANK tile grid and two room labels."""
    doc, page = _new_page()
    _frame(page, FRAME)
    _contiguous_grid(page, 80.0, 80.0, 10, 8, 40.0, 25.0, labelled=False)
    page.insert_text((90.0, 95.0), "RM1", fontsize=6.0)
    page.insert_text((300.0, 200.0), "RM2", fontsize=6.0)
    _title(page)
    return _reopen(doc)


def _segment(doc, **kw):
    return v.segment_page_viewports(doc[0], page_number=1, **kw)


def _vector_resolved(views):
    return [
        row for row in views
        if row.status == RESOLVED and row.boundary_source == v.ViewportBoundarySource.VECTOR_FRAME.value
    ]


def _fingerprints(views):
    return [v.segmented_viewport_producer_fingerprint(row) for row in views]


def _calibration(page):
    return v.calibrate_viewport_layout(page)


# ---------------------------------------------------------------------------
# the table predicate: connected AND text-bearing, never wider than legacy
# ---------------------------------------------------------------------------


def test_lattice_of_labelled_fixtures_is_legacy_table_but_not_shadow_table():
    doc = _lattice_plan()
    page = doc[0]
    cal = _calibration(page)
    fragments = v._text_fragments(page)
    assert v._frame_looks_like_table(FRAME, page, cal, allow_line_grid_only=False)
    assert not v._frame_looks_like_source_connected_text_cell_table(
        FRAME, page, cal, fragments, allow_line_grid_only=False
    )
    # The labels are real: the family is text-bearing, so text alone could not tell.
    mesh = v._frame_source_edge_mesh(FRAME, page)
    assert not mesh
    doc.close()


def test_contiguous_blank_tile_grid_is_legacy_table_but_not_shadow_table():
    doc = _tile_plan()
    page = doc[0]
    cal = _calibration(page)
    fragments = v._text_fragments(page)
    assert v._frame_looks_like_table(FRAME, page, cal, allow_line_grid_only=False)
    assert len(v._frame_source_edge_mesh(FRAME, page)) == 80  # connected: edges alone cannot tell
    assert not v._frame_looks_like_source_connected_text_cell_table(
        FRAME, page, cal, fragments, allow_line_grid_only=False
    )
    doc.close()


def _table_page(*, schedule_title=None, plan_title=None):
    doc, page = _new_page()
    box = (60.0, 40.0, 500.0, 300.0)
    _frame(page, box)
    _contiguous_grid(page, 80.0, 60.0, 10, 8, 40.0, 25.0, labelled=True)
    if schedule_title:
        page.insert_text((80.0, 330.0), schedule_title, fontsize=11.0)
    if plan_title:
        page.insert_text((80.0, 330.0), plan_title, fontsize=11.0)
    return _reopen(doc), box


def test_real_connected_text_filled_table_stays_a_table():
    doc, box = _table_page()
    page = doc[0]
    cal = _calibration(page)
    fragments = v._text_fragments(page)
    assert v._frame_looks_like_table(box, page, cal, allow_line_grid_only=False)
    assert v._frame_looks_like_source_connected_text_cell_table(
        box, page, cal, fragments, allow_line_grid_only=False
    )
    doc.close()


def test_table_with_unequal_column_widths_stays_a_table_through_its_neighbours():
    """Connectivity is measured over every rectangle, so equal-size columns that are not adjacent still count."""
    doc, page = _new_page()
    box = (60.0, 40.0, 500.0, 300.0)
    _frame(page, box)
    widths = [60.0, 40.0, 100.0, 40.0, 60.0, 40.0, 60.0]  # columns 2, 4, 6 share one width: never adjacent
    heights = [25.0] * 8
    y = 60.0
    for row, h in enumerate(heights):
        x = 70.0
        for col, w in enumerate(widths):
            rect = fitz.Rect(x, y, x + w, y + h)
            page.draw_rect(rect, color=(0, 0, 0), width=0.5)
            _label(page, rect, f"R{row}C{col}")
            x += w
        y += h
    doc = _reopen(doc)
    page = doc[0]
    cal = _calibration(page)
    assert v._frame_looks_like_table(box, page, cal, allow_line_grid_only=False)
    assert v._frame_looks_like_source_connected_text_cell_table(
        box, page, cal, v._text_fragments(page), allow_line_grid_only=False
    )
    doc.close()


def test_shadow_table_is_never_true_where_legacy_is_false_and_leaves_line_grid_tables_alone():
    # No rectangle cells at all: a bare frame is not a table either way.
    doc, page = _new_page()
    _frame(page, FRAME)
    _title(page)
    doc = _reopen(doc)
    page = doc[0]
    cal = _calibration(page)
    fragments = v._text_fragments(page)
    assert not v._frame_looks_like_table(FRAME, page, cal)
    assert not v._frame_looks_like_source_connected_text_cell_table(FRAME, page, cal, fragments)
    doc.close()

    # A table drawn only with line strokes is the legacy line-grid branch: unchanged by the shadow.
    doc, page = _new_page()
    box = (60.0, 40.0, 500.0, 300.0)
    _frame(page, box)
    for r in range(9):
        page.draw_line((80.0, 60.0 + r * 25.0), (480.0, 60.0 + r * 25.0), color=(0, 0, 0), width=0.5)
    for c in range(11):
        page.draw_line((80.0 + c * 40.0, 60.0), (80.0 + c * 40.0, 260.0), color=(0, 0, 0), width=0.5)
    doc = _reopen(doc)
    page = doc[0]
    cal = _calibration(page)
    fragments = v._text_fragments(page)
    assert v._frame_looks_like_table(box, page, cal) is True
    assert v._frame_looks_like_table(box, page, cal, allow_line_grid_only=False) is False
    assert v._frame_looks_like_source_connected_text_cell_table(box, page, cal, fragments) is True
    assert v._frame_looks_like_source_connected_text_cell_table(
        box, page, cal, fragments, allow_line_grid_only=False
    ) is False
    doc.close()


def test_unknown_text_evidence_cannot_demote_a_connected_grid():
    """No live text in the frame at all (e.g. outlined glyphs): keep the legacy table answer."""
    doc, page = _new_page()
    box = (60.0, 40.0, 500.0, 300.0)
    _frame(page, box)
    _contiguous_grid(page, 80.0, 60.0, 10, 8, 40.0, 25.0, labelled=False)
    doc = _reopen(doc)
    page = doc[0]
    cal = _calibration(page)
    assert v._frame_looks_like_table(box, page, cal, allow_line_grid_only=False)
    assert v._frame_looks_like_source_connected_text_cell_table(
        box, page, cal, v._text_fragments(page), allow_line_grid_only=False
    )
    doc.close()


def test_connectivity_that_cannot_be_measured_never_demotes_a_table(monkeypatch):
    """Over the rectangle bound the mesh is unknown: the legacy table answer stands and the veto stays."""
    doc = _lattice_plan()
    page = doc[0]
    assert v._frame_source_edge_mesh(FRAME, page) == frozenset()
    monkeypatch.setattr(v, "_TABLE_EDGE_MESH_MAX_RECTANGLES", 10)
    assert len(v._frame_source_edge_mesh(FRAME, page)) == 48
    assert _vector_resolved(_segment(doc, **{FLAG: True})) == []
    doc.close()


def test_family_filter_default_none_is_the_legacy_predicate_and_can_only_reject():
    doc = _lattice_plan()
    page = doc[0]
    cal = _calibration(page)
    legacy = v._frame_looks_like_table(FRAME, page, cal, allow_line_grid_only=False)
    assert legacy is True
    assert v._frame_looks_like_table(
        FRAME, page, cal, allow_line_grid_only=False, family_filter=None
    ) is legacy
    assert v._frame_looks_like_table(
        FRAME, page, cal, allow_line_grid_only=False, family_filter=lambda family: True
    ) is legacy
    assert v._frame_looks_like_table(
        FRAME, page, cal, allow_line_grid_only=False, family_filter=lambda family: False
    ) is False
    seen = []
    v._frame_looks_like_table(
        FRAME, page, cal, allow_line_grid_only=False,
        family_filter=lambda family: seen.append(len(family)) or False,
    )
    assert seen == [48]  # only structurally qualified families are ever offered to the filter
    doc.close()


def test_edge_mesh_unit_cases():
    def grid(cols, rows, w=30.0, h=20.0, gap_x=0.0, gap_y=0.0, x0=10.0, y0=10.0):
        return [
            (x0 + c * (w + gap_x), y0 + r * (h + gap_y), x0 + c * (w + gap_x) + w, y0 + r * (h + gap_y) + h)
            for r in range(rows) for c in range(cols)
        ]

    assert v._source_edge_connected_rects(grid(3, 3)) == frozenset(grid(3, 3))
    assert v._source_edge_connected_rects(grid(4, 2)) == frozenset(grid(4, 2))  # exactly 8 cells
    assert v._source_edge_connected_rects(grid(7, 1)) == frozenset()  # one row: x edges only, and < 8
    assert v._source_edge_connected_rects(grid(10, 1)) == frozenset()  # one axis only
    assert v._source_edge_connected_rects(grid(1, 10)) == frozenset()
    assert v._source_edge_connected_rects(grid(3, 3, gap_x=1.0, gap_y=1.0)) == frozenset()  # open gaps
    assert v._source_edge_connected_rects(grid(6, 6, gap_x=60.0, gap_y=60.0)) == frozenset()  # lattice
    # native numerical exactness only: 0.005 pt still shares an edge, 0.02 pt does not
    near = grid(3, 3, gap_x=0.005)
    assert v._source_edge_connected_rects(near) == frozenset(near)
    assert v._source_edge_connected_rects(grid(3, 3, gap_x=0.02)) == frozenset()
    # two separate 2x2 blocks never merge into one 8-cell block
    two_blocks = grid(2, 2) + grid(2, 2, x0=200.0)
    assert v._source_edge_connected_rects(two_blocks) == frozenset()
    # input order and translation do not matter
    cells = grid(3, 4)
    forward = v._source_edge_connected_rects(cells)
    assert forward == v._source_edge_connected_rects(list(reversed(cells)))
    moved = [(a + 321.5, b - 17.25, c + 321.5, d - 17.25) for a, b, c, d in cells]
    assert len(v._source_edge_connected_rects(moved)) == len(forward) == 12


def test_text_bearing_fraction_counts_cells_with_a_centre_and_includes_edges():
    cells = [(0.0, 0.0, 10.0, 10.0), (10.0, 0.0, 20.0, 10.0), (20.0, 0.0, 30.0, 10.0), (30.0, 0.0, 40.0, 10.0)]
    centres = sorted([(5.0, 5.0), (10.0, 5.0), (5.0, 5.0)])  # one inside cell 0, one ON the edge of cells 0/1
    xs = [c[0] for c in centres]
    assert v._cells_text_bearing_fraction(cells, centres, xs) == 0.5
    assert v._cells_text_bearing_fraction(cells, [], []) == 0.0
    assert v._cells_text_bearing_fraction([], centres, xs) == 0.0


# ---------------------------------------------------------------------------
# near-nested band collapse
# ---------------------------------------------------------------------------

OUTER = (40.0, 30.0, 760.0, 520.0)
BAND = (30.0, 380.0, 230.0, 525.0)  # overhangs the outer frame by 10pt; 92% of its area is inside


def test_near_nested_band_collapse_unit_cases():
    kept, dropped = v._collapse_near_nested_band_frames([OUTER, BAND])
    assert kept == [OUTER] and dropped == [(BAND, OUTER)]
    # the strict legacy rule does NOT see this as nested (the band sticks out of the outer frame)
    assert v._collapse_nested_band_frames([OUTER, BAND]) == [OUTER, BAND]
    # input order does not matter
    kept2, dropped2 = v._collapse_near_nested_band_frames([BAND, OUTER])
    assert sorted(kept2) == sorted(kept) and dropped2 == dropped
    # a near-equal frame (not a band) is never ordered by size; neither is a disjoint or half-overlapping one
    shifted = (48.0, 36.0, 768.0, 526.0)
    assert v._collapse_near_nested_band_frames([OUTER, shifted]) == ([OUTER, shifted], [])
    half = (300.0, 30.0, 760.0, 520.0)
    assert v._collapse_near_nested_band_frames([(40.0, 30.0, 500.0, 520.0), half])[1] == []
    disjoint_pair = [(40.0, 30.0, 760.0, 250.0), (40.0, 270.0, 760.0, 520.0)]
    assert v._collapse_near_nested_band_frames(disjoint_pair) == (disjoint_pair, [])
    # a nested frame that is not a band stays a rival
    big_inner = (60.0, 60.0, 700.0, 480.0)
    assert v._collapse_near_nested_band_frames([OUTER, big_inner]) == ([OUTER, big_inner], [])
    # a band that only 80% overlaps its container is a partial overlap: kept
    mostly_out = (-60.0, 380.0, 140.0, 525.0)
    assert v._collapse_near_nested_band_frames([OUTER, mostly_out])[1] == []
    # idempotent
    assert v._collapse_near_nested_band_frames(kept) == (kept, [])


def test_near_nested_receipt_names_the_smallest_container_regardless_of_order():
    """Three frames hold the band; only the band is dropped, and the receipt names the tightest one."""
    mid = (35.0, 25.0, 765.0, 525.0)  # holds the band too, but OUTER is not a band inside it
    huge = (0.0, 0.0, 799.0, 599.0)
    for order in ([OUTER, BAND, mid, huge], [huge, mid, BAND, OUTER], [mid, OUTER, huge, BAND]):
        kept, dropped = v._collapse_near_nested_band_frames(order)
        assert dropped == [(BAND, OUTER)]  # the smallest frame that still holds it
        assert sorted(kept) == sorted([OUTER, mid, huge])  # near-equal rivals keep competing


def _two_rival_frames_page(boxes, *, title_at=(60.0, 505.0)):
    doc, page = _new_page()
    for box in boxes:
        _frame(page, box)
    page.insert_text(title_at, PLAN_TITLE, fontsize=11.0)
    return _reopen(doc)


def test_near_nested_band_competes_by_default_and_collapses_with_the_flag():
    doc = _two_rival_frames_page([OUTER, BAND])
    default = _segment(doc)
    assert [row.status for row in default] == [AMBIGUOUS]
    assert default[0].provenance["candidate_frames"] == [BAND, OUTER]
    assert FLAG not in default[0].provenance

    shadow = _segment(doc, **{FLAG: True})
    resolved = _vector_resolved(shadow)
    assert len(resolved) == 1 and resolved[0].bounding_box == pytest.approx(OUTER)
    receipt = resolved[0].provenance[FLAG]
    assert receipt["table_veto_lifted_frames"] == []
    assert receipt["near_nested_rival_frames"] == [{"frame": BAND, "contained_in": OUTER}]
    # nothing about the rival was deleted: it is in the receipt, the default output is untouched
    assert _fingerprints(default) == _fingerprints(_segment(doc, **{FLAG: False}))
    doc.close()


def test_rivals_that_are_not_bands_inside_one_another_keep_competing_with_the_flag():
    cases = {
        "near-equal shifted frames": [OUTER, (48.0, 36.0, 768.0, 526.0)],
        "half-overlapping frames": [(40.0, 30.0, 500.0, 520.0), (300.0, 30.0, 760.0, 520.0)],
    }
    for name, boxes in cases.items():
        doc = _two_rival_frames_page(boxes, title_at=(330.0, 505.0))
        default = _segment(doc)
        shadow = _segment(doc, **{FLAG: True})
        assert [row.status for row in default] == [AMBIGUOUS], name
        assert [row.status for row in shadow] == [AMBIGUOUS], name
        assert len(shadow[0].provenance["candidate_frames"]) == 2, name
        assert _vector_resolved(shadow) == [], name
        doc.close()


def test_two_disjoint_plan_frames_still_compete_with_the_flag():
    """The title sits inside the lower frame and directly below the upper one: two disjoint rivals."""
    upper, lower = (40.0, 30.0, 760.0, 250.0), (40.0, 270.0, 760.0, 520.0)
    doc = _two_rival_frames_page([upper, lower], title_at=(60.0, 290.0))
    default = _segment(doc)
    shadow = _segment(doc, **{FLAG: True})
    assert [row.status for row in default] == [AMBIGUOUS]
    assert [row.status for row in shadow] == [AMBIGUOUS]
    assert sorted(shadow[0].provenance["candidate_frames"]) == sorted([upper, lower])
    assert FLAG not in shadow[0].provenance  # the flag changed nothing, so there is no receipt
    assert _fingerprints(default) == _fingerprints(shadow)
    doc.close()


# ---------------------------------------------------------------------------
# end to end: plan title vs the false-table pattern
# ---------------------------------------------------------------------------


def test_labelled_fixture_lattice_vetoes_the_plan_frame_by_default_and_not_with_the_flag():
    doc = _lattice_plan()
    default = _segment(doc)
    assert _vector_resolved(default) == []  # the legacy veto fires

    shadow = _segment(doc, **{FLAG: True})
    resolved = _vector_resolved(shadow)
    assert len(resolved) == 1
    assert resolved[0].view_type == v.DrawingViewType.FLOOR_PLAN.value
    assert resolved[0].bounding_box == pytest.approx(FRAME)
    assert resolved[0].provenance[FLAG] == {
        "table_veto_lifted_frames": [FRAME],
        "near_nested_rival_frames": [],
    }
    doc.close()


def test_contiguous_blank_tile_grid_vetoes_the_plan_frame_by_default_and_not_with_the_flag():
    doc = _tile_plan()
    assert _vector_resolved(_segment(doc)) == []
    resolved = _vector_resolved(_segment(doc, **{FLAG: True}))
    assert len(resolved) == 1 and resolved[0].bounding_box == pytest.approx(FRAME)
    doc.close()


def test_real_text_filled_table_frame_still_vetoes_a_plan_title_with_the_flag():
    doc, box = _table_page(plan_title=PLAN_TITLE)
    assert _vector_resolved(_segment(doc)) == []
    shadow = _segment(doc, **{FLAG: True})
    assert _vector_resolved(shadow) == []
    assert _fingerprints(shadow) == _fingerprints(_segment(doc))
    doc.close()


def test_schedule_title_still_binds_to_a_real_table_with_and_without_the_flag():
    doc, box = _table_page(schedule_title="DOOR SCHEDULE")
    default = _vector_resolved(_segment(doc))
    shadow = _vector_resolved(_segment(doc, **{FLAG: True}))
    assert len(default) == 1 and default[0].view_type == v.DrawingViewType.SCHEDULE.value
    assert default[0].bounding_box == pytest.approx(box)
    assert len(shadow) == 1 and shadow[0].bounding_box == pytest.approx(box)
    assert _fingerprints(_segment(doc)) == _fingerprints(_segment(doc, **{FLAG: True}))
    doc.close()


def test_schedule_title_stops_binding_to_a_plan_whose_fixture_lattice_mimics_a_table():
    """The external-caption false binding: a schedule title just below a fixture lattice."""
    doc, page = _new_page()
    box = (60.0, 40.0, 500.0, 300.0)
    _frame(page, box)
    _lattice(page, 80.0, 60.0, 8, 5, 20.0, 10.0, 50.0, 40.0)
    page.insert_text((80.0, 330.0), "DOOR SCHEDULE", fontsize=11.0)
    doc = _reopen(doc)
    default = _vector_resolved(_segment(doc))
    assert len(default) == 1 and default[0].bounding_box == pytest.approx(box)  # the legacy false binding
    shadow = _segment(doc, **{FLAG: True})
    assert _vector_resolved(shadow) == []
    doc.close()


def test_composite_overhanging_ring_and_outline_both_held_by_lattices():
    """The shape of the target pattern: an outline and a room ring both mislabelled as tables."""
    doc, page = _new_page()
    _frame(page, OUTER)
    _frame(page, BAND)
    _lattice(page, 80.0, 60.0, 8, 6, 40.0, 20.0, 80.0, 40.0)  # lattice inside the outline
    _lattice(page, 50.0, 395.0, 4, 3, 20.0, 10.0, 40.0, 30.0)  # small lattice inside the ring
    _title(page)
    doc = _reopen(doc)
    page = doc[0]
    cal = _calibration(page)
    fragments = v._text_fragments(page)
    assert v._frame_looks_like_table(OUTER, page, cal) and v._frame_looks_like_table(BAND, page, cal)
    assert not v._frame_looks_like_source_connected_text_cell_table(OUTER, page, cal, fragments)
    assert not v._frame_looks_like_source_connected_text_cell_table(BAND, page, cal, fragments)

    default = _segment(doc)
    assert _vector_resolved(default) == []
    shadow = _segment(doc, **{FLAG: True})
    resolved = _vector_resolved(shadow)
    assert len(resolved) == 1 and resolved[0].bounding_box == pytest.approx(OUTER)
    receipt = resolved[0].provenance[FLAG]
    assert sorted(receipt["table_veto_lifted_frames"]) == sorted([OUTER, BAND])
    assert receipt["near_nested_rival_frames"] == [{"frame": BAND, "contained_in": OUTER}]
    doc.close()


# ---------------------------------------------------------------------------
# default-off contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("builder", [_lattice_plan, _tile_plan, lambda: _two_rival_frames_page([OUTER, BAND])])
def test_default_output_is_byte_identical_with_the_flag_absent_or_false(builder):
    doc = builder()
    absent = _segment(doc)
    explicit = _segment(doc, **{FLAG: False})
    assert absent == explicit
    assert _fingerprints(absent) == _fingerprints(explicit)
    assert all(FLAG not in (row.provenance or {}) for row in [*absent, *explicit])
    assert json.dumps([v._producer_fingerprint_payload(row) for row in absent], sort_keys=True, default=str) == json.dumps(
        [v._producer_fingerprint_payload(row) for row in explicit], sort_keys=True, default=str
    )
    # the shadow genuinely differs on these pages, so the identity above is not vacuous
    assert _fingerprints(_segment(doc, **{FLAG: True})) != _fingerprints(absent)
    doc.close()


def test_flag_is_forwarded_only_when_on(monkeypatch):
    doc = _lattice_plan()
    seen = []
    real = v._frame_resolved_viewports

    def spy(*args, **kwargs):
        seen.append(dict(kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(v, "_frame_resolved_viewports", spy)
    _segment(doc)
    _segment(doc, **{FLAG: False})
    _segment(doc, **{FLAG: True})
    assert FLAG not in seen[0] and FLAG not in seen[1]
    assert seen[2][FLAG] is True
    doc.close()


@pytest.mark.parametrize("bad", [1, 0, "true", None, 1.0, [], (), object()])
def test_flag_requires_an_explicit_bool_everywhere(bad):
    doc = _lattice_plan()
    with pytest.raises(ValueError, match="explicit_bool"):
        _segment(doc, **{FLAG: bad})
    page = doc[0]
    cal = _calibration(page)
    anchors = v.extract_view_title_anchors(page)
    frames = v.extract_vector_frames(page, cal)
    with pytest.raises(ValueError, match="explicit_bool"):
        v._frame_resolved_viewports(page, anchors, frames, cal, page_number=1, **{FLAG: bad})
    doc.close()


def test_existing_guards_and_their_messages_are_unchanged():
    doc = _lattice_plan()
    with pytest.raises(ValueError, match="source_multipath_requires_connected_source_cell_guard"):
        _segment(doc, source_native_multipath_semantic_frame_shadow=True)
    with pytest.raises(ValueError, match="source_table_shadow_requires_explicit_bool"):
        _segment(doc, source_connected_table_cell_shadow=1)
    # the new flag composes with the existing guarded shadows without relaxing them
    _segment(doc, source_connected_table_cell_shadow=True, **{FLAG: True})
    doc.close()


def test_the_flag_lifts_a_veto_only_for_plan_titles():
    """An elevation title keeps the legacy table veto, flag or not."""
    doc, page = _new_page()
    _frame(page, FRAME)
    _lattice(page, 80.0, 60.0, 8, 6, 40.0, 20.0, 80.0, 40.0)
    page.insert_text((60.0, 505.0), "NORTH ELEVATION", fontsize=11.0)
    doc = _reopen(doc)
    assert _vector_resolved(_segment(doc)) == []
    shadow = _segment(doc, **{FLAG: True})
    assert _vector_resolved(shadow) == []
    assert _fingerprints(shadow) == _fingerprints(_segment(doc))
    doc.close()


# ---------------------------------------------------------------------------
# metamorphic / determinism / no mutation
# ---------------------------------------------------------------------------


def test_translation_moves_the_shadow_result_rigidly():
    base = _vector_resolved(_segment(_lattice_plan(), **{FLAG: True}))[0]
    moved = _vector_resolved(_segment(_lattice_plan(dx=13.0, dy=7.0), **{FLAG: True}))[0]
    assert tuple(m - b for m, b in zip(moved.bounding_box, base.bounding_box)) == pytest.approx((13.0, 7.0, 13.0, 7.0))
    assert moved.status == base.status and moved.view_type == base.view_type


def test_input_order_does_not_change_the_shadow_result():
    forward = _segment(_lattice_plan(), **{FLAG: True})
    backward = _segment(_lattice_plan(reverse=True), **{FLAG: True})
    assert [(r.view_type, r.status, r.bounding_box) for r in forward] == [
        (r.view_type, r.status, r.bounding_box) for r in backward
    ]


def _rotated_lattice_plan(rotation: int):
    doc = fitz.open()
    page = doc.new_page(width=600.0, height=800.0)
    frame = fitz.Rect(60.0, 80.0, 500.0, 650.0)
    page.draw_rect(frame, color=(0, 0, 0), width=1.0)
    _lattice(page, 80.0, 100.0, 7, 8, 30.0, 16.0, 60.0, 50.0)
    if rotation == 0:
        page.insert_text((80.0, 680.0), PLAN_TITLE, fontsize=12.0)  # directly below the frame
    else:
        # visually below the frame after /Rotate 90: authored vertically to the right of the native frame
        page.insert_text((530.0, 300.0), PLAN_TITLE, fontsize=12.0, rotate=90)
    page.set_rotation(rotation)
    return doc, page, frame


@pytest.mark.parametrize("rotation", [0, 90])
def test_page_rotation_0_and_90_resolve_the_same_native_frame(rotation):
    doc, page, frame = _rotated_lattice_plan(rotation)
    try:
        default = v.segment_page_viewports(page, page_number=1)
        assert _vector_resolved(default) == []
        shadow = v.segment_page_viewports(page, page_number=1, **{FLAG: True})
        resolved = _vector_resolved(shadow)
        assert len(resolved) == 1
        assert resolved[0].bounding_box == pytest.approx((frame.x0, frame.y0, frame.x1, frame.y1))
        assert _fingerprints(default) == _fingerprints(v.segment_page_viewports(page, page_number=1, **{FLAG: False}))
    finally:
        doc.close()


def test_shadow_run_is_deterministic_and_leaves_the_page_and_inputs_unchanged():
    doc = _lattice_plan()
    page = doc[0]
    drawings_before = hashlib.sha256(repr(page.get_drawings()).encode()).hexdigest()
    text_before = hashlib.sha256(repr(page.get_text("dict")).encode()).hexdigest()
    first = _segment(doc, **{FLAG: True})
    second = _segment(doc, **{FLAG: True})
    assert _fingerprints(first) == _fingerprints(second)

    cal = _calibration(page)
    anchors = v.extract_view_title_anchors(page)
    frames = v.extract_vector_frames(page, cal)
    anchors_before, frames_before = copy.deepcopy(anchors), copy.deepcopy(frames)
    v._frame_resolved_viewports(page, anchors, frames, cal, page_number=1, **{FLAG: True})
    assert anchors == anchors_before and frames == frames_before

    assert hashlib.sha256(repr(page.get_drawings()).encode()).hexdigest() == drawings_before
    assert hashlib.sha256(repr(page.get_text("dict")).encode()).hexdigest() == text_before
    doc.close()


def test_unrelated_content_elsewhere_does_not_change_the_verdict():
    """Extra furniture and notes outside the frame do not turn the plan frame into, or out of, a table."""
    doc, page = _new_page()
    _frame(page, FRAME)
    _lattice(page, 80.0, 60.0, 8, 6, 40.0, 20.0, 80.0, 40.0)
    _title(page)
    # unrelated labelled boxes and a note on the same sheet, outside the plan frame
    page.draw_rect(fitz.Rect(770.0, 100.0, 795.0, 120.0), color=(0, 0, 0), width=0.5)
    page.insert_text((10.0, 560.0), "NOTES: DO NOT SCALE", fontsize=8.0)
    doc = _reopen(doc)
    resolved = _vector_resolved(_segment(doc, **{FLAG: True}))
    assert len(resolved) == 1 and resolved[0].bounding_box == pytest.approx(FRAME)
    assert _vector_resolved(_segment(doc)) == []
    doc.close()
