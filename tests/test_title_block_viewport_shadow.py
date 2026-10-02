"""Shadow title-block floor-plan viewport proposal: synthetic adversarial matrix.

Synthetic sheets only. Production code may not branch on project names, page
numbers, coordinates or known dimensions; every sheet here differs only in
structure (where the title block is, what the title says, what linework exists).
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Iterable, Optional, Sequence

import fitz
import pytest

import pb_title_block_viewport_shadow as tbv
from pb_drawing_evidence_binding import DrawingViewType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_viewport_segmentation import (
    SegmentedViewport,
    ViewportSegmentationStatus,
    is_authoritative_derived_viewport,
    is_segment_page_viewports_product,
    segment_page_viewports,
)

CANDIDATE = EvidenceResolutionStatus.CANDIDATE
CONFLICT = EvidenceResolutionStatus.CONFLICT
ABSTAINED = EvidenceResolutionStatus.ABSTAINED
FLOOR = DrawingViewType.FLOOR_PLAN.value

W0, H0 = 1190.0, 842.0
DEFAULT_LABELS = ("DRAWING TITLE", "DRAWING NO", "SCALE", "DRAWN BY", "DATE")
PLAN = (120.0, 120.0, 760.0, 560.0)


def _reopen(doc: fitz.Document) -> fitz.Document:
    data = doc.tobytes()
    doc.close()
    return fitz.open(stream=data, filetype="pdf")


def _plan(page: fitz.Page, box: Sequence[float], *, split: bool = False, s: float = 1.0) -> None:
    x0, y0, x1, y1 = (v * s for v in box)
    xm, ym = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    lines = [
        ((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0)),
        ((x0, ym), (x1, ym)), ((xm, y0), (xm, y1)),
    ]
    for a, b in lines:
        if split:
            mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
            page.draw_line(a, mid, width=0.6 * s)
            page.draw_line(mid, b, width=0.6 * s)
        else:
            page.draw_line(a, b, width=0.6 * s)


def _title_block(
    page: fitz.Page,
    *,
    x: float,
    y: float,
    frame_to: Optional[tuple[float, float]],
    value: str = "FLOOR PLAN",
    labels: Sequence[str] = DEFAULT_LABELS,
    s: float = 1.0,
) -> None:
    if frame_to is not None:
        page.draw_rect(fitz.Rect((x - 20) * s, (y - 14) * s, frame_to[0] * s, frame_to[1] * s), width=0.5 * s)
    for index, label in enumerate(labels):
        page.insert_text(((x + index * 60) * s, y * s), label, fontsize=7 * s)
    page.insert_text((x * s, (y + 13) * s), value, fontsize=10 * s)


def _sheet(
    *,
    layout: str = "strip",
    value: str = "FLOOR PLAN",
    labels: Sequence[str] = DEFAULT_LABELS,
    plans: Iterable[Sequence[float]] = (PLAN,),
    texts: Iterable[tuple[str, tuple[float, float]]] = (),
    lines: Iterable[tuple[tuple[float, float], tuple[float, float]]] = (),
    rects: Iterable[Sequence[float]] = (),
    border: bool = True,
    split: bool = False,
    reverse: bool = False,
    s: float = 1.0,
    extra_w: float = 0.0,
    extra_h: float = 0.0,
    title_block: bool = True,
    frame: bool = True,
) -> fitz.Document:
    w, h = W0 + extra_w, H0 + extra_h
    doc = fitz.open()
    page = doc.new_page(width=w * s, height=h * s)
    ops = []
    if border:
        ops.append(lambda: page.draw_rect(fitz.Rect(20 * s, 20 * s, (w - 20) * s, (h - 20) * s), width=0.5 * s))
    if title_block:
        if layout == "strip":
            x, y, frame_to = w - 390.0, h - 122.0, (w - 30.0, h - 30.0)
        elif layout == "column":
            x, y, frame_to = w - 330.0, h * 0.60, (w - 30.0, h - 30.0)
        elif layout == "corner":
            x, y, frame_to = w - 300.0, h - 112.0, (w - 30.0, h - 30.0)
        elif layout == "centre":
            x, y, frame_to = w * 0.40, h * 0.45, (w * 0.40 + 240.0, h * 0.45 + 90.0)
        else:  # pragma: no cover
            raise AssertionError(layout)
        ops.append(lambda: _title_block(
            page, x=x, y=y, frame_to=frame_to if frame else None, value=value, labels=labels, s=s,
        ))
    for box in plans:
        ops.append(lambda box=box: _plan(page, box, split=split, s=s))
    for text, at in texts:
        ops.append(lambda text=text, at=at: page.insert_text((at[0] * s, at[1] * s), text, fontsize=10 * s))
    for a, b in lines:
        ops.append(lambda a=a, b=b: page.draw_line((a[0] * s, a[1] * s), (b[0] * s, b[1] * s), width=0.6 * s))
    for rect in rects:
        ops.append(lambda rect=rect: page.draw_rect(fitz.Rect(*(v * s for v in rect)), width=0.8 * s))
    for op in (reversed(ops) if reverse else ops):
        op()
    return _reopen(doc)


def _propose(doc: fitz.Document, **kwargs):
    return tbv.propose_title_block_floor_plan_viewport(doc[0], page_number=3, **kwargs)


def _contains(outer: Sequence[float], inner: Sequence[float], tol: float = 1.0) -> bool:
    return (
        outer[0] - tol <= inner[0] and outer[1] - tol <= inner[1]
        and outer[2] + tol >= inner[2] and outer[3] + tol >= inner[3]
    )


# ---------------------------------------------------------------------------
# Synthetic positives
# ---------------------------------------------------------------------------


def test_strip_title_block_yields_one_candidate_above_the_furniture() -> None:
    doc = _sheet()
    result = _propose(doc)
    assert result.status is CANDIDATE and result.is_candidate
    assert result.reason_codes == (tbv.TITLE_BLOCK_VIEWPORT_CANDIDATE,)
    assert result.view_type == FLOOR and result.title_text == "FLOOR PLAN"
    assert result.boundary_evidence == "title_block_layout_band"
    box = result.bounding_box
    assert box is not None
    assert _contains(box, PLAN)
    furniture_top = min(b[1] for b in result.furniture_boxes)
    assert box[3] < furniture_top  # the title block is excluded
    assert result.candidate_regions == (box,)
    assert result.authoritative is False
    doc.close()


def test_right_column_title_block_yields_the_band_beside_it() -> None:
    doc = _sheet(layout="column", plans=((100.0, 120.0, 700.0, 640.0),))
    result = _propose(doc)
    assert result.is_candidate
    box = result.bounding_box
    assert box is not None and _contains(box, (100.0, 120.0, 700.0, 640.0))
    assert box[2] < min(b[0] for b in result.furniture_boxes)
    assert [d["band"] for d in result.provenance["band_decisions"] if d["valid"]] == ["left_of_title_block"]
    doc.close()


def test_corner_block_returns_the_region_every_valid_reading_keeps() -> None:
    doc = _sheet(layout="corner", plans=((100.0, 100.0, 600.0, 500.0),))
    result = _propose(doc)
    assert result.is_candidate
    assert len(result.candidate_regions) == 2  # above and left of the block are both valid
    box = result.bounding_box
    assert box is not None
    assert all(_contains(region, box) for region in result.candidate_regions)
    assert _contains(box, (100.0, 100.0, 600.0, 500.0))
    doc.close()


def test_legend_heading_does_not_block_and_is_reported_as_a_competing_box() -> None:
    doc = _sheet(texts=(("LEGEND", (40.0, 300.0)),))
    result = _propose(doc)
    assert result.is_candidate
    assert len(result.competing_anchor_boxes) == 1
    doc.close()


def test_small_notes_panel_is_not_a_second_plan() -> None:
    panel = (((30.0, 100.0), (30.0, 400.0)), ((95.0, 100.0), (95.0, 400.0)))
    doc = _sheet(lines=panel, plans=((260.0, 120.0, 900.0, 560.0),))
    result = _propose(doc)
    assert result.is_candidate and not result.ambiguous
    doc.close()


def test_single_closed_drawing_frame_is_preferred_source_drawn_evidence() -> None:
    frame = (60.0, 60.0, 900.0, 640.0)
    doc = _sheet(rects=(frame,), plans=((120.0, 120.0, 760.0, 560.0),))
    result = _propose(doc)
    assert result.is_candidate
    assert result.boundary_evidence == "closed_native_drawing_frame"
    assert result.bounding_box is not None
    assert all(abs(a - b) < 1.0 for a, b in zip(result.bounding_box, frame))
    doc.close()


def test_nested_double_border_is_one_region_not_ambiguous() -> None:
    outer = (50.0, 50.0, 940.0, 660.0)
    inner = (70.0, 70.0, 920.0, 640.0)
    doc = _sheet(rects=(outer, inner))
    result = _propose(doc)
    assert result.is_candidate
    assert result.boundary_evidence == "closed_native_drawing_frame"
    assert result.bounding_box is not None
    assert all(abs(a - b) < 1.0 for a, b in zip(result.bounding_box, inner))
    doc.close()


# ---------------------------------------------------------------------------
# Fail-closed: classification, conflict, ambiguity, absent ownership
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    ["ROOF PLAN", "ELEVATIONS", "SITE PLAN", "SLAB PLAN", "COVER SHEET", "WINDOW SCHEDULE", "SECTION VIEW"],
)
def test_title_that_is_not_a_floor_plan_abstains(value: str) -> None:
    doc = _sheet(value=value)
    result = _propose(doc)
    assert result.status is ABSTAINED and not result.is_candidate
    assert result.bounding_box is None and result.viewport_id is None
    assert result.reason_codes[0] in (
        tbv.TITLE_BLOCK_VIEWPORT_TITLE_NOT_FLOOR_PLAN,
        tbv.TITLE_BLOCK_VIEWPORT_TITLE_UNAVAILABLE,
    )
    doc.close()


@pytest.mark.parametrize("value", ["FLOOR PLAN & ROOF PLAN", "FLOOR PLAN AND ELEVATIONS", "FLOOR PLAN / SECTION A"])
def test_title_naming_several_views_is_a_conflict(value: str) -> None:
    doc = _sheet(value=value)
    result = _propose(doc)
    assert result.status is CONFLICT and result.bounding_box is None
    assert result.reason_codes == (tbv.TITLE_BLOCK_VIEWPORT_TITLE_MULTI_VIEW,)
    doc.close()


def test_two_explicit_title_fields_with_different_views_conflict() -> None:
    doc = fitz.open()
    page = doc.new_page(width=W0, height=H0)
    x, y = W0 - 390.0, H0 - 122.0
    page.draw_rect(fitz.Rect(x - 20, y - 14, W0 - 30, H0 - 30), width=0.5)
    for index, label in enumerate(("DRAWING TITLE", "SCALE", "DRAWN BY", "DATE", "SHEET TITLE")):
        page.insert_text((x + index * 60, y), label, fontsize=7)
    page.insert_text((x, y + 13), "FLOOR PLAN", fontsize=10)
    page.insert_text((x + 240, y + 13), "ELEVATIONS", fontsize=10)
    _plan(page, PLAN)
    doc = _reopen(doc)
    result = _propose(doc)
    assert result.status is CONFLICT and result.bounding_box is None
    assert result.reason_codes == (tbv.TITLE_BLOCK_VIEWPORT_TITLE_CONFLICT,)
    doc.close()


def test_in_drawing_floor_plan_anchor_is_left_to_f07() -> None:
    doc = _sheet(texts=(("FLOOR PLAN", (150.0, 600.0)),))
    # F.07 owns an in-drawing titled plan; isolate the anchor rule itself.
    result = _propose(doc, f07_viewports=[])
    assert result.status is ABSTAINED and result.bounding_box is None
    assert result.reason_codes == (tbv.TITLE_BLOCK_VIEWPORT_IN_DRAWING_FLOOR_PLAN_ANCHOR,)
    doc.close()


@pytest.mark.parametrize("anchor", ["ELEVATION 1", "SECTION A", "WINDOW SCHEDULE", "ROOF PLAN"])
def test_other_in_drawing_views_conflict_with_a_single_view_claim(anchor: str) -> None:
    doc = _sheet(texts=((anchor, (150.0, 600.0)),))
    result = _propose(doc)
    assert result.status is CONFLICT and result.bounding_box is None
    assert result.reason_codes == (tbv.TITLE_BLOCK_VIEWPORT_VIEW_ANCHOR_CONFLICT,)
    doc.close()


def test_f07_floor_plan_already_present_means_no_proposal() -> None:
    doc = _sheet()
    existing = SegmentedViewport(
        view_id="view_p3_1", page_number=3, view_type=FLOOR, label="FLOOR PLAN",
        title_bbox=(0.0, 0.0, 10.0, 10.0), bounding_box=(0.0, 0.0, 800.0, 600.0),
        status=ViewportSegmentationStatus.DERIVED.value, boundary_source="title_partition", confidence=0.9,
    )
    result = _propose(doc, f07_viewports=[existing])
    assert result.status is ABSTAINED and result.bounding_box is None
    assert result.reason_codes == (tbv.TITLE_BLOCK_VIEWPORT_F07_FLOOR_PLAN_PRESENT,)
    doc.close()


def test_weak_title_block_without_an_explicit_title_field_abstains() -> None:
    doc = _sheet(labels=("SCALE", "DATE"), value="1:100")
    result = _propose(doc)
    assert result.status is ABSTAINED and result.bounding_box is None
    assert result.reason_codes == (tbv.TITLE_BLOCK_VIEWPORT_TITLE_UNAVAILABLE,)
    doc.close()


def test_bound_title_without_a_demonstrated_title_block_cannot_invent_geometry() -> None:
    doc = _sheet(labels=("DRAWING TITLE",), frame=False)
    result = _propose(doc)
    assert result.status is ABSTAINED and result.bounding_box is None
    assert result.reason_codes == (tbv.TITLE_BLOCK_VIEWPORT_BLOCK_UNPROVEN,)
    doc.close()


def test_title_block_in_the_middle_of_the_sheet_is_not_page_layout_evidence() -> None:
    doc = _sheet(layout="centre", plans=((60.0, 60.0, 360.0, 300.0),))
    result = _propose(doc)
    assert result.status is ABSTAINED and result.bounding_box is None
    assert result.reason_codes == (tbv.TITLE_BLOCK_VIEWPORT_BLOCK_NOT_IN_OUTER_BAND,)
    doc.close()


def test_title_text_alone_without_drawing_content_abstains() -> None:
    doc = _sheet(plans=())
    result = _propose(doc)
    assert result.status is ABSTAINED and result.bounding_box is None
    assert result.reason_codes == (tbv.TITLE_BLOCK_VIEWPORT_NO_DRAWING_CONTENT,)
    doc.close()


def test_linework_running_into_the_title_block_has_no_valid_region() -> None:
    doc = _sheet(lines=(((300.0, 100.0), (300.0, 790.0)), ((500.0, 100.0), (500.0, 790.0))))
    result = _propose(doc)
    assert result.status is ABSTAINED and result.bounding_box is None
    assert result.reason_codes == (tbv.TITLE_BLOCK_VIEWPORT_NO_VALID_REGION,)
    doc.close()


def test_two_separated_plans_are_ambiguous_and_both_retained() -> None:
    left = (80.0, 120.0, 380.0, 520.0)
    right = (640.0, 120.0, 940.0, 520.0)
    doc = _sheet(plans=(left, right))
    result = _propose(doc)
    assert result.status is ABSTAINED and result.ambiguous is True
    assert result.bounding_box is None and result.viewport_id is None
    assert result.reason_codes == (tbv.TITLE_BLOCK_VIEWPORT_AMBIGUOUS_REGIONS,)
    assert len(result.candidate_regions) == 2
    assert any(_contains(region, left, 2.0) for region in result.candidate_regions)
    assert any(_contains(region, right, 2.0) for region in result.candidate_regions)
    doc.close()


def test_two_framed_drawings_are_ambiguous() -> None:
    frames = ((60.0, 60.0, 560.0, 640.0), (600.0, 60.0, 1100.0, 640.0))
    plans = ((120.0, 120.0, 500.0, 560.0), (660.0, 120.0, 1040.0, 560.0))
    doc = _sheet(rects=frames, plans=plans)
    result = _propose(doc)
    assert result.status is ABSTAINED and result.ambiguous is True
    assert result.bounding_box is None
    assert len(result.candidate_regions) >= 2
    doc.close()


def test_rotated_page_fails_closed() -> None:
    doc = _sheet()
    doc[0].set_rotation(90)
    result = _propose(doc)
    assert result.status is ABSTAINED and result.bounding_box is None
    assert result.reason_codes == (tbv.TITLE_BLOCK_VIEWPORT_PAGE_ROTATION_UNSUPPORTED,)
    doc.close()


def test_unreadable_evidence_abstains_instead_of_raising(monkeypatch) -> None:
    doc = _sheet()

    def boom(*_args, **_kwargs):
        raise RuntimeError("unreadable")

    monkeypatch.setattr(tbv, "extract_native_page", boom)
    result = _propose(doc)
    assert result.status is ABSTAINED
    assert result.reason_codes == (tbv.TITLE_BLOCK_VIEWPORT_EVIDENCE_UNREADABLE,)
    doc.close()


# ---------------------------------------------------------------------------
# Never authoritative; F.07 untouched
# ---------------------------------------------------------------------------


def test_candidate_can_not_masquerade_as_an_f07_product() -> None:
    doc = _sheet()
    result = _propose(doc)
    viewport = result.to_segmented_viewport()
    assert viewport is not None
    assert viewport.view_type == FLOOR
    assert viewport.status == ViewportSegmentationStatus.DERIVED.value
    assert is_segment_page_viewports_product(viewport) is False
    assert is_authoritative_derived_viewport(viewport) is False
    assert viewport.provenance["shadow_only"] is True and viewport.provenance["authoritative"] is False
    assert viewport.provenance["partition_mode"] == tbv.TITLE_BLOCK_VIEWPORT_PARTITION_MODE
    doc.close()


def test_non_candidates_describe_no_viewport() -> None:
    doc = _sheet(value="ROOF PLAN")
    assert _propose(doc).to_segmented_viewport() is None
    doc.close()


def test_f07_output_is_unchanged_by_the_shadow_run() -> None:
    doc = _sheet(texts=(("LEGEND", (40.0, 300.0)),))
    page = doc[0]
    before = [(v.view_id, v.status, v.view_type, v.bounding_box) for v in segment_page_viewports(page, page_number=3)]
    _propose(doc)
    after = [(v.view_id, v.status, v.view_type, v.bounding_box) for v in segment_page_viewports(page, page_number=3)]
    assert before == after
    # F.07 keeps its own rule: a title-block-only sheet has no floor-plan viewport.
    assert not any(v.view_type == FLOOR and v.bounding_box is not None for v in segment_page_viewports(page, page_number=3))
    doc.close()


def test_no_production_module_imports_the_shadow_authority() -> None:
    root = Path(__file__).resolve().parent.parent
    offenders = []
    for path in sorted(root.glob("*.py")):
        if path.name == "pb_title_block_viewport_shadow.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            if "pb_title_block_viewport_shadow" in names:
                offenders.append(path.name)
    assert offenders == []


# ---------------------------------------------------------------------------
# Metamorphic, replay and mutation checks
# ---------------------------------------------------------------------------


def _box(doc: fitz.Document):
    result = _propose(doc)
    assert result.is_candidate, result.reason_codes
    return result.bounding_box


def test_uniform_scale_scales_the_region() -> None:
    base = _box(_sheet())
    for s in (0.5, 2.0):
        scaled = _box(_sheet(s=s))
        assert all(abs(a * s - b) <= 1.0 + 0.01 * s for a, b in zip(base, scaled)), (s, base, scaled)


def test_adding_blank_sheet_below_moves_only_the_title_block_side() -> None:
    base = _sheet()
    grown = _sheet(extra_h=80.0)
    first, second = _propose(base), _propose(grown)
    assert first.is_candidate and second.is_candidate
    # the plan is untouched and the title block moved down with the sheet edge
    assert _contains(second.bounding_box, PLAN)
    assert second.bounding_box[3] == pytest.approx(first.bounding_box[3] + 80.0, abs=0.01)


def test_drawing_order_does_not_change_the_result() -> None:
    forward = _propose(_sheet(texts=(("LEGEND", (40.0, 300.0)),)))
    reverse = _propose(_sheet(texts=(("LEGEND", (40.0, 300.0)),), reverse=True))
    assert forward.to_dict() == reverse.to_dict()
    assert forward.viewport_id == reverse.viewport_id


def test_splitting_linework_does_not_change_the_region() -> None:
    whole = _propose(_sheet())
    split = _propose(_sheet(split=True))
    assert whole.bounding_box == split.bounding_box
    assert whole.boundary_evidence == split.boundary_evidence


def test_unrelated_short_content_does_not_change_the_region() -> None:
    base = _propose(_sheet())
    noisy = _propose(_sheet(
        texts=(("3600", (60.0, 100.0)), ("NOTE", (900.0, 400.0))),
        lines=(((200.0, 600.0), (230.0, 600.0)),),
    ))
    assert base.bounding_box == noisy.bounding_box


def test_unrelated_long_line_inside_the_region_keeps_the_same_region() -> None:
    base = _propose(_sheet())
    more = _propose(_sheet(lines=(((100.0, 600.0), (700.0, 600.0)),)))
    assert base.bounding_box == more.bounding_box
    assert more.content_segment_count == base.content_segment_count + 1


def test_replay_and_resave_give_identical_ids() -> None:
    doc = _sheet()
    first = _propose(doc)
    second = _propose(doc)
    resaved = _reopen(doc)
    third = _propose(resaved)
    assert first.to_dict() == second.to_dict() == third.to_dict()
    assert first.viewport_id and first.viewport_id.startswith("title_block_viewport_")
    other = _propose(_sheet(plans=((120.0, 120.0, 760.0, 560.0), (200.0, 200.0, 300.0, 300.0))))
    assert other.viewport_id == first.viewport_id  # the id derives from the region, not the content count
    shifted = _propose(_sheet(extra_h=40.0))
    assert shifted.viewport_id != first.viewport_id
    json.dumps(first.to_dict())


def test_proposal_does_not_mutate_the_page() -> None:
    doc = _sheet(texts=(("LEGEND", (40.0, 300.0)),))
    page = doc[0]
    snapshot = (page.get_text("words"), len(page.get_drawings()), page.rect, page.rotation)
    _propose(doc)
    assert snapshot == (page.get_text("words"), len(page.get_drawings()), page.rect, page.rotation)
    doc.close()
