"""Title-block ownership of view-title anchors, and same-identity duplicates.

Synthetic drawings only.  Production code may not branch on project names,
page numbers, coordinates or expected quantities; these tests build sheets
whose only distinguishing evidence is structure:

* Part A: a title-like fragment that ``pb_page_title_authority`` positively
  demonstrates as a title-block field value is not a drawing-view title anchor.
* Part B: unframed anchors with the same normalised text and view type are not
  turned into several derived halves unless a validated title grid separates
  them.
"""
from __future__ import annotations

import fitz
import pytest

import pb_viewport_segmentation as vs
from pb_drawing_evidence_binding import DrawingViewType
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    extract_view_title_anchors,
    segment_page_viewports,
)
from pb_wall_topology_diagnostics import _eligible_floor_plan_viewports

FLOOR = DrawingViewType.FLOOR_PLAN.value
DERIVED = ViewportSegmentationStatus.DERIVED.value
AMBIGUOUS = ViewportSegmentationStatus.AMBIGUOUS.value
UNSUPPORTED = ViewportSegmentationStatus.UNSUPPORTED.value
RESOLVED = ViewportSegmentationStatus.RESOLVED.value


def _reopen(doc: fitz.Document) -> fitz.Document:
    data = doc.tobytes()
    doc.close()
    return fitz.open(stream=data, filetype="pdf")


def _title_block(
    page: fitz.Page,
    *,
    x: float,
    y: float,
    scale: float = 1.0,
    value: str = "FLOOR PLAN",
    labels: tuple[str, ...] = ("DRAWING TITLE", "DRAWING NO", "SCALE", "DRAWN BY", "DATE"),
) -> None:
    """A label cluster with a bound title value under the first label."""
    size = 7.0 * scale
    for index, label in enumerate(labels):
        page.insert_text((x + index * 60 * scale, y), label, fontsize=size)
    page.insert_text((x, y + 13 * scale), value, fontsize=10 * scale)


def _sheet(
    *,
    plan_title_at: tuple[float, float] | None = (150.0, 300.0),
    block_at: tuple[float, float] | None = (560.0, 540.0),
    block_labels: tuple[str, ...] = ("DRAWING TITLE", "DRAWING NO", "SCALE", "DRAWN BY", "DATE"),
    scale: float = 1.0,
    dx: float = 0.0,
    dy: float = 0.0,
    reverse: bool = False,
    unrelated: bool = False,
) -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page(width=(842 + dx) * scale, height=(595 + dy) * scale)
    ops = []
    if plan_title_at is not None:
        ops.append(lambda: page.insert_text(
            ((plan_title_at[0] + dx) * scale, (plan_title_at[1] + dy) * scale),
            "FLOOR PLAN", fontsize=14 * scale,
        ))
    if block_at is not None:
        ops.append(lambda: _title_block(
            page, x=(block_at[0] + dx) * scale, y=(block_at[1] + dy) * scale,
            scale=scale, labels=block_labels,
        ))
    if unrelated:
        ops.append(lambda: page.insert_text(((60 + dx) * scale, (120 + dy) * scale), "3600", fontsize=9 * scale))
        ops.append(lambda: page.draw_line(((60 + dx) * scale, (200 + dy) * scale), ((300 + dx) * scale, (200 + dy) * scale)))
    for op in (reversed(ops) if reverse else ops):
        op()
    return _reopen(doc)


def _plans(viewports):
    return [v for v in viewports if v.view_type == FLOOR]


def _signature(viewports):
    return sorted((v.view_id, v.status, v.label, v.bounding_box) for v in viewports)


# ---------------------------------------------------------------------------
# Part A
# ---------------------------------------------------------------------------


def test_title_block_owned_title_is_not_a_drawing_title_anchor() -> None:
    doc = _sheet()
    page = doc[0]
    assert vs._title_field_owned_regions(page), "the synthetic title block must be demonstrated"
    anchors = extract_view_title_anchors(page)
    assert len(anchors) == 1
    # the surviving anchor is the drawing title, not the title-block value
    assert anchors[0].bbox[1] < 400 and anchors[0].bbox[0] < 300
    doc.close()


def test_title_block_duplicate_cannot_create_a_derived_partition() -> None:
    doc = _sheet()
    viewports = segment_page_viewports(doc[0], page_number=3)
    plans = _plans(viewports)
    assert len(plans) == 1
    assert plans[0].status == UNSUPPORTED  # option (i): fail closed, no invented extent
    assert plans[0].bounding_box is None
    assert not any(v.status == DERIVED for v in viewports)
    assert _eligible_floor_plan_viewports(viewports, allow_derived=True) == []
    doc.close()


def test_without_ownership_evidence_the_same_sheet_is_ambiguous_not_two_halves(monkeypatch) -> None:
    """Part B is the backstop when Part A is unavailable: still no two halves."""
    monkeypatch.setattr(vs, "_title_field_owned_regions", lambda page: [])
    doc = _sheet()
    viewports = segment_page_viewports(doc[0], page_number=3)
    plans = _plans(viewports)
    assert len(plans) == 2
    assert all(v.status == AMBIGUOUS and v.bounding_box is None for v in plans)
    assert not any(v.status == DERIVED for v in viewports)
    doc.close()


def test_weak_title_block_without_an_explicit_title_field_cannot_suppress_a_title() -> None:
    # two non-title field labels only: neither a demonstrated title block nor
    # an explicit drawing-title field binding
    doc = _sheet(block_labels=("SCALE", "DATE"))
    page = doc[0]
    assert vs._title_field_owned_regions(page) == []
    assert len(extract_view_title_anchors(page)) == 2
    plans = _plans(segment_page_viewports(page, page_number=1))
    assert len(plans) == 2
    assert all(v.status == AMBIGUOUS for v in plans)
    doc.close()


def test_explicit_title_field_binding_owns_its_value_without_a_demonstrated_block() -> None:
    # only two labels (a weak cluster), but one is an explicit drawing-title
    # field whose bound value is "FLOOR PLAN"
    doc = _sheet(block_labels=("DRAWING TITLE", "DRAWING NO"))
    page = doc[0]
    analysis = vs._title_authority.analyse_cells(
        vs._title_authority.page_cells(page), page.rect.width, page.rect.height, 0, "native"
    )
    assert analysis.title_block is None  # not a demonstrated block
    assert vs._title_field_owned_regions(page)
    anchors = extract_view_title_anchors(page)
    assert len(anchors) == 1 and anchors[0].bbox[1] < 400
    doc.close()


@pytest.mark.parametrize("label", ["Drawing name:", "Sheet title", "Drawing Title:"])
def test_each_explicit_title_label_form_owns_its_value(label: str) -> None:
    doc = _sheet(block_labels=(label, "DATE"))
    assert len(extract_view_title_anchors(doc[0])) == 1
    doc.close()


def test_bare_title_label_is_not_explicit_ownership() -> None:
    doc = _sheet(block_labels=("TITLE", "DATE"))
    assert vs._title_field_owned_regions(doc[0]) == []
    assert len(extract_view_title_anchors(doc[0])) == 2
    doc.close()


def test_real_drawing_title_next_to_but_outside_the_title_block_is_kept() -> None:
    doc = _sheet(plan_title_at=(470.0, 545.0), block_at=(620.0, 540.0))
    page = doc[0]
    regions = vs._title_field_owned_regions(page)
    assert regions
    anchors = extract_view_title_anchors(page)
    assert len(anchors) == 1
    centre_x = (anchors[0].bbox[0] + anchors[0].bbox[2]) / 2.0
    assert centre_x < min(r[0] for r in regions)
    doc.close()


def test_no_title_block_means_no_suppression() -> None:
    doc = _sheet(block_at=None)
    assert vs._title_field_owned_regions(doc[0]) == []
    assert len(extract_view_title_anchors(doc[0])) == 1
    doc.close()


def test_framed_plan_beside_a_title_block_duplicate_stays_resolved() -> None:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.draw_rect(fitz.Rect(40, 30, 520, 470))
    page.insert_text((60, 450), "FLOOR PLAN", fontsize=14)
    _title_block(page, x=560, y=540)
    doc = _reopen(doc)
    plans = _plans(segment_page_viewports(doc[0], page_number=1))
    assert len(plans) == 1
    assert plans[0].status == RESOLVED
    assert plans[0].bounding_box == pytest.approx((40, 30, 520, 470), abs=1.5)
    doc.close()


# ---------------------------------------------------------------------------
# Part B
# ---------------------------------------------------------------------------


def test_same_text_same_type_unframed_titles_fail_closed() -> None:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((80, 300), "FLOOR PLAN", fontsize=14)
    page.insert_text((560, 300), "FLOOR PLAN", fontsize=14)
    doc = _reopen(doc)
    viewports = segment_page_viewports(doc[0], page_number=1)
    assert len(viewports) == 2
    assert all(v.status == AMBIGUOUS and v.bounding_box is None for v in viewports)
    doc.close()


def test_duplicate_group_is_quarantined_without_collateral_to_unrelated_anchors() -> None:
    doc = fitz.open()
    page = doc.new_page(width=1190, height=842)
    page.insert_text((60, 500), "FLOOR PLAN", fontsize=14)
    page.insert_text((700, 780), "FLOOR PLAN", fontsize=14)
    page.insert_text((900, 150), "NORTH ELEVATION", fontsize=14)
    doc = _reopen(doc)
    by_label = {}
    for v in segment_page_viewports(doc[0], page_number=1):
        by_label.setdefault(v.label, []).append(v)
    assert [v.status for v in by_label["FLOOR PLAN"]] == [AMBIGUOUS, AMBIGUOUS]
    assert all(v.bounding_box is None for v in by_label["FLOOR PLAN"])
    (elevation,) = by_label["NORTH ELEVATION"]
    assert elevation.status == UNSUPPORTED  # a lone unframed title: its own evidence path
    assert elevation.bounding_box is None
    doc.close()


def test_unrelated_distinct_anchors_still_partition_beside_a_duplicate_group() -> None:
    doc = fitz.open()
    page = doc.new_page(width=1190, height=842)
    page.insert_text((60, 500), "FLOOR PLAN", fontsize=14)
    page.insert_text((700, 780), "FLOOR PLAN", fontsize=14)
    page.insert_text((300, 150), "NORTH ELEVATION", fontsize=14)
    page.insert_text((900, 150), "SOUTH ELEVATION", fontsize=14)
    doc = _reopen(doc)
    viewports = segment_page_viewports(doc[0], page_number=1)
    plans = _plans(viewports)
    elevations = [v for v in viewports if v.view_type != FLOOR]
    assert [v.status for v in plans] == [AMBIGUOUS, AMBIGUOUS]
    assert [v.status for v in elevations] == [DERIVED, DERIVED]
    assert vs.validate_non_overlapping_viewports(viewports)
    doc.close()


def test_distinct_unframed_titles_still_partition() -> None:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((80, 300), "GROUND FLOOR PLAN", fontsize=14)
    page.insert_text((560, 300), "FIRST FLOOR PLAN", fontsize=14)
    doc = _reopen(doc)
    viewports = segment_page_viewports(doc[0], page_number=1)
    assert len(viewports) == 2
    assert all(v.status == DERIVED and v.bounding_box is not None for v in viewports)
    assert vs.validate_non_overlapping_viewports(viewports)
    doc.close()


def test_distinct_view_types_still_partition() -> None:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((80, 300), "GROUND FLOOR PLAN", fontsize=14)
    page.insert_text((560, 300), "NORTH ELEVATION", fontsize=14)
    doc = _reopen(doc)
    viewports = segment_page_viewports(doc[0], page_number=1)
    assert sorted(v.status for v in viewports) == [DERIVED, DERIVED]
    doc.close()


def test_framed_same_text_views_stay_resolved() -> None:
    """Positive frame evidence separates same-text views; Part B never touches them."""
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.draw_rect(fitz.Rect(30, 30, 400, 300))
    page.draw_rect(fitz.Rect(440, 30, 810, 300))
    page.insert_text((60, 280), "FLOOR PLAN", fontsize=14)
    page.insert_text((470, 280), "FLOOR PLAN", fontsize=14)
    doc = _reopen(doc)
    plans = _plans(segment_page_viewports(doc[0], page_number=1))
    assert [v.status for v in plans] == [RESOLVED, RESOLVED]
    assert vs.validate_non_overlapping_viewports(plans)
    doc.close()


# ---------------------------------------------------------------------------
# Invariance, determinism, no mutation
# ---------------------------------------------------------------------------


def _outcome(doc: fitz.Document):
    viewports = segment_page_viewports(doc[0], page_number=3)
    return sorted((v.label, v.status, v.bounding_box is None) for v in viewports)


def test_outcome_is_invariant_to_translation_scale_order_and_unrelated_content() -> None:
    base = _outcome(_sheet())
    assert base == [("FLOOR PLAN", UNSUPPORTED, True)]
    for kwargs in (
        {"dx": 137.0, "dy": 61.0},
        {"scale": 1.7},
        {"reverse": True},
        {"unrelated": True},
        {"dx": 40.0, "dy": 20.0, "scale": 0.9, "reverse": True, "unrelated": True},
    ):
        assert _outcome(_sheet(**kwargs)) == base, kwargs


def test_rotated_page_gives_the_same_outcome() -> None:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((150, 300), "FLOOR PLAN", fontsize=14)
    _title_block(page, x=560, y=540)
    page.set_rotation(180)
    doc = _reopen(doc)
    assert _outcome(doc) == [("FLOOR PLAN", UNSUPPORTED, True)]
    doc.close()


def test_replay_is_deterministic_and_input_is_not_mutated() -> None:
    doc = _sheet()
    page = doc[0]
    before_text = page.get_text("dict")
    before_draw = page.get_drawings()
    first = _signature(segment_page_viewports(page, page_number=3))
    second = _signature(segment_page_viewports(page, page_number=3))
    assert first == second
    assert page.get_text("dict") == before_text
    assert page.get_drawings() == before_draw
    doc.close()


def test_page_without_title_shaped_text_is_untouched() -> None:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((100, 100), "3600", fontsize=9)
    doc = _reopen(doc)
    assert segment_page_viewports(doc[0], page_number=1) == []
    doc.close()
