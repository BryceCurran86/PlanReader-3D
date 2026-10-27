"""The sub-floor ink census through the real producer on synthetic PDFs (no caller-built records, no private file)."""
from __future__ import annotations

import inspect
import random
from dataclasses import fields, replace

import fitz
import pytest

import pb_subfloor_ink_census_shadow as C
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED, VISIBLE_SOURCE_AUTHORITY_REQUIRED
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from plan_callout_strip_fixture import Sheet

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
Q = 0.24
P = fitz.Point
BLACK = (0, 0, 0)
W = 0.5
# coordinates below are multiples of 1/64 so that MuPDF's float32 geometry is exact
HIDDEN_GLASS = 0.484375          # a glass pair this thick has end ticks shorter than the producer's floor
VISIBLE_GLASS = 0.75
VIEWPORT = (10.0, 10.0, 890.0, 690.0)


# --- synthetic documents --------------------------------------------------------------------------------------------


class Doc:
    """A synthetic PDF built from scratch with PyMuPDF; pages are fetched by index on use."""

    def __init__(self, pages=1, size=(900.0, 700.0)):
        self.size = size
        self.doc = fitz.open()
        for _ in range(pages):
            self.doc.new_page(width=size[0], height=size[1])

    def line(self, a, b, *, width=W, color=BLACK, page=0, opacity=None, dashes=None):
        kw = {} if opacity is None else {"stroke_opacity": opacity}
        self.doc[page].draw_line(P(*a), P(*b), color=color, width=width, dashes=dashes, **kw)

    def rect(self, x0, y0, x1, y1, *, width=W, color=BLACK, fill=None, fill_opacity=None, page=0):
        kw = {} if fill_opacity is None else {"fill_opacity": fill_opacity}
        self.doc[page].draw_rect(fitz.Rect(x0, y0, x1, y1), color=color, fill=fill, width=width, **kw)

    def text(self, xy, text, *, size=10, page=0):
        self.doc[page].insert_text(P(*xy), text, fontsize=size, fontname="helv")

    def clipped_line(self, a, b, clip, *, width=W, page=0):
        """Append one black line drawn under a rectangular clip (both in page coordinates), after everything else."""
        pg = self.doc[page]
        pg.clean_contents()
        xref = pg.get_contents()[0]
        height = self.size[1]                                          # PDF space runs upward, page space downward
        x0, y0, x1, y1 = clip
        ops = (f"\nq {x0} {height - y1} {x1 - x0} {y1 - y0} re W n 0 0 0 RG {width} w "
               f"{a[0]} {height - a[1]} m {b[0]} {height - b[1]} l S Q\n").encode()
        self.doc.update_stream(xref, self.doc.xref_stream(xref) + ops)

    def pdf(self):
        return self.doc.tobytes()


def draw_window(doc, *, x=100.0, y=300.0, length=60.0, depth=5.5, post=2.5, glass=HIDDEN_GLASS, width=W, panels=1,
                shift=(0.0, 0.0), ticks=True, order=None, page=0, styles=None):
    """A glazing strip as a CAD export draws it: frame lines, a full-depth tick at both ends of every cell, a glass
    pair in each cell and two pane end ticks that span the pair. Returns where everything is."""
    dx, dy = shift
    panel = (length - (panels + 1) * post) / panels
    cells = [(x + post + k * (panel + post), x + post + k * (panel + post) + panel) for k in range(panels)]
    p0 = y + (depth - glass) / 2.0
    p1 = p0 + glass
    strokes = [("top", (x, y), (x + length, y)), ("bot", (x, y + depth), (x + length, y + depth))]
    for k, (a, b) in enumerate(cells):
        strokes += [(f"fa{k}", (a, y), (a, y + depth)), (f"fb{k}", (b, y), (b, y + depth)),
                    (f"pl{k}", (a, p0), (b, p0)), (f"pu{k}", (a, p1), (b, p1))]
    tick_names = []
    if ticks:
        for k, (a, b) in enumerate(cells):
            strokes += [(f"tl{k}", (a, p0), (a, p1)), (f"th{k}", (b, p0), (b, p1))]
            tick_names += [f"tl{k}", f"th{k}"]
    if order is not None:
        strokes = [strokes[i] for i in order(len(strokes))]
    placed = {}
    for name, a, b in strokes:
        doc.line((a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy), width=width, page=page, **(styles or {}).get(name, {}))
        placed[name] = (a[0] + dx, a[1] + dy, b[0] + dx, b[1] + dy)
    return {"cells": [(a + dx, b + dx) for a, b in cells], "p": (p0 + dy, p1 + dy), "box": (x + dx, y + dy, x + length + dx, y + depth + dy),
            "ticks": {n: placed[n] for n in tick_names}, "order": [n for n, _, _ in strokes]}


def publish(doc, document_id="subfloor-census"):
    source = SourceVisibilityProducer(producer_method="subfloor-census-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id=document_id, source_bytes=doc.pdf(), source_locator="memory://subfloor-census.pdf")
    return source, published


def selector(published, oid):
    return ObservationSelector(published.revision.document_id, published.revision.revision_id,
                               published.revision.source_sha256, published.snapshot.snapshot_id, oid)


def ids_in(source, published, box, page="1", tol=0.01):
    """Visible observation ids of one page that lie wholly inside a box (a test-side way to nominate ink)."""
    vis = source.authority()
    out = []
    for oid in published.visible_observation_ids:
        o = vis.resolve_visible(selector(published, oid)).observation
        if o is None or str(o.page_id) != page:
            continue
        g = o.geometry
        if (box[0] - tol <= min(g[0], g[2]) and max(g[0], g[2]) <= box[2] + tol
                and box[1] - tol <= min(g[1], g[3]) and max(g[1], g[3]) <= box[3] + tol):
            out.append(oid)
    return tuple(sorted(out))


def floor_plan_viewport(monkeypatch, *, view_type="floor_plan", boxes=(VIEWPORT,)):
    """The repository's own test convention: stamp the viewports at the segmentation boundary."""
    import pb_viewport_segmentation as seg

    def segment(_page, *, page_number):
        return tuple(seg._stamp_segment_page_viewports_product([
            seg.SegmentedViewport(
                view_id=f"vp-{k}", page_number=page_number, view_type=view_type, label=view_type.upper(),
                title_bbox=(20.0, 10.0, 160.0, 25.0), bounding_box=box,
                status=seg.ViewportSegmentationStatus.RESOLVED.value,
                boundary_source=seg.ViewportBoundarySource.VECTOR_FRAME.value, confidence=1.0)
            for k, box in enumerate(boxes)]))

    monkeypatch.setattr(seg, "segment_page_viewports", segment)


def window_ids(source, published, first=0):
    """The six strokes of a window drawn from drawing `first` on, whatever else was painted in its box later."""
    vis = source.authority()
    wanted = {f"visible:segment:d{k}i0" for k in range(first, first + 6)}
    return tuple(sorted(o for o in published.visible_observation_ids
                        if vis.resolve_visible(selector(published, o)).observation.source_primitive_ref in wanted))


def hidden_window(**kw):
    doc = Doc()
    meta = draw_window(doc, **kw)
    source, published = publish(doc)
    return doc, meta, source, published, ids_in(source, published, meta["box"])


def census(source, published, ids=None, *, region=None, enabled=True, page_id=1, quantum=Q):
    shadow = C.SubFloorInkCensusShadow(source, enabled=enabled)
    if region is not None:
        return shadow.census(revision_id=published.revision.revision_id, page_id=page_id, coordinate_quantum_pt=quantum,
                             region_bbox=region)
    return shadow.census(revision_id=published.revision.revision_id, page_id=page_id, coordinate_quantum_pt=quantum,
                         nominated_observation_ids=ids)


def raw_sub_floor_geometry(census_result):
    return sorted(tuple(round(v, 4) for v in i.geometry) for i in census_result.sub_floor_items)


# --- gate -------------------------------------------------------------------------------------------------------------


def test_the_census_is_off_by_default_and_a_disabled_call_touches_nothing():
    _, _, source, published, ids = hidden_window()
    shadow = C.SubFloorInkCensusShadow(source)
    before = _shape(source)
    got = shadow.census(revision_id=published.revision.revision_id, page_id=1, coordinate_quantum_pt=Q,
                        nominated_observation_ids=ids)
    assert got.status is ABST and got.reason_codes == (C.CENSUS_DISABLED,) and got.ownership is None
    assert got.evidence_atoms == () and got.sub_floor_items == () and got.cells == ()
    assert _shape(source) == before and source._physical_opening_authority_cache is None


@pytest.mark.parametrize("bad", [1, 0, None, "true", [], {}])
def test_the_gate_must_be_a_strict_boolean_and_the_source_the_concrete_producer(bad):
    _, _, source, _, _ = hidden_window()
    with pytest.raises(ValueError):
        C.SubFloorInkCensusShadow(source, enabled=bad)
    with pytest.raises(TypeError):
        C.SubFloorInkCensusShadow(object(), enabled=True)


def test_there_is_no_caller_channel_for_widths_colours_roles_paint_order_or_provenance():
    signature = inspect.signature(C.SubFloorInkCensusShadow.census)
    assert [p for p in signature.parameters if p != "self"] == [
        "revision_id", "page_id", "coordinate_quantum_pt", "region_bbox", "nominated_observation_ids"]
    _, _, source, published, ids = hidden_window()
    for extra in ("stroke_width", "items", "visible", "paint", "viewport", "floor"):
        with pytest.raises(TypeError):
            C.SubFloorInkCensusShadow(source, enabled=True).census(
                revision_id=published.revision.revision_id, page_id=1, coordinate_quantum_pt=Q,
                nominated_observation_ids=ids, **{extra: 1})


# --- the producer's floor, probed ---------------------------------------------------------------------------------------


def test_the_producers_own_extraction_drops_exactly_the_line_items_the_census_calls_sub_floor(monkeypatch):
    """Fails if the producer's floor moves: the census mirrors the constant, this probes the behaviour."""
    from pb_vector_geometry_v130 import extract_native_page

    floor_plan_viewport(monkeypatch)
    lengths = [0.484375, 0.498046875, 0.5, 0.515625, 5.0]
    doc = Doc()
    for k, length in enumerate(lengths):
        doc.line((100.0 + 10 * k, 100.0), (100.0 + 10 * k, 100.0 + length))
    source, published = publish(doc)
    with fitz.open(stream=doc.pdf(), filetype="pdf") as opened:
        emitted = {s["id"] for s in extract_native_page(opened[0])["segments"]}
    assert emitted == {"d2i0", "d3i0", "d4i0"}                        # the first two (below 0.5) are dropped
    visible = {source.authority().resolve_visible(selector(published, o)).observation.source_primitive_ref
               for o in published.visible_observation_ids}
    assert visible == {"visible:segment:d2i0", "visible:segment:d3i0", "visible:segment:d4i0"}
    got = census(source, published, region=(90.0, 90.0, 160.0, 110.0))
    assert [i.item_id for i in got.sub_floor_items] == ["d0i0", "d1i0"]
    assert [round(i.length, 6) for i in got.sub_floor_items] == [0.484375, 0.498047]
    assert all(i.hidden_by == C.HIDDEN_BY_EXTRACTOR_LINE_FLOOR and i.kind == C.ITEM_KIND_LINE for i in got.sub_floor_items)


def test_rectangle_edges_below_the_floor_survive_the_extraction_and_die_at_the_visibility_authority(monkeypatch):
    from pb_vector_geometry_v130 import extract_native_page

    floor_plan_viewport(monkeypatch)
    doc = Doc()
    doc.rect(100.0, 100.0, 100.375, 110.0)             # two 0.375 edges (hidden) and two 10 pt edges
    doc.rect(120.0, 100.0, 120.5, 110.0)               # exactly the floor: not hidden
    source, published = publish(doc)
    with fitz.open(stream=doc.pdf(), filetype="pdf") as opened:
        emitted = {s["id"] for s in extract_native_page(opened[0])["segments"]}
    assert {"d0i0e0", "d0i0e2"} <= emitted                         # the extraction keeps every rectangle edge
    refs = {source.authority().resolve_visible(selector(published, o)).observation.source_primitive_ref
            for o in published.visible_observation_ids}
    assert "visible:segment:d0i0e0" not in refs and "visible:segment:d0i0e2" not in refs      # the second floor
    assert {"visible:segment:d0i0e1", "visible:segment:d0i0e3", "visible:segment:d1i0e0", "visible:segment:d1i0e1"} <= refs
    got = census(source, published, region=(90.0, 90.0, 130.0, 120.0))
    assert [(i.item_id, i.hidden_by) for i in got.sub_floor_items] == [
        ("d0i0e0", C.HIDDEN_BY_VISIBILITY_SEGMENT_FLOOR), ("d0i0e2", C.HIDDEN_BY_VISIBILITY_SEGMENT_FLOOR)]
    assert all(i.kind == C.ITEM_KIND_RECT_EDGE and i.edge_index in (0, 2) for i in got.sub_floor_items)
    assert all(i.length == pytest.approx(0.375) and i.orientation == "H" for i in got.sub_floor_items)


# --- hidden ticks, visible ticks, no double counting -------------------------------------------------------------------------


def test_sub_floor_ticks_are_reported_with_the_producers_own_addresses_and_make_a_candidate_never_a_window(monkeypatch):
    floor_plan_viewport(monkeypatch)
    doc, meta, source, published, ids = hidden_window()
    got = census(source, published, ids)
    assert got.status is CAND and got.reason_codes == (C.SUB_FLOOR_TICKS_WOULD_CLOSE_CELL,)
    assert got.ownership.document_id == published.revision.document_id
    assert (got.ownership.revision_id, got.ownership.source_sha256, got.ownership.snapshot_id, got.ownership.page_id) == (
        published.revision.revision_id, published.revision.source_sha256, published.snapshot.snapshot_id, "1")
    assert got.mode == "nominated" and got.axis == "H" and got.viewport_id == "vp-0"
    assert [i.item_id for i in got.sub_floor_items] == ["d6i0", "d7i0"]          # six strokes precede the two ticks
    with fitz.open(stream=doc.pdf(), filetype="pdf") as opened:
        drawings = opened[0].get_drawings()
    for item, name in zip(got.sub_floor_items, ("tl0", "th0")):
        d = drawings[item.drawing_index]
        assert item.geometry == pytest.approx(meta["ticks"][name]) and (d["items"][item.item_index][0], item.kind) == ("l", "line")
        assert item.length == pytest.approx(HIDDEN_GLASS) and item.stroke_width == pytest.approx(W)
        assert item.stroke_rgb == (0.0, 0.0, 0.0) and item.orientation == "V" and item.strip_relation == "perpendicular"
        assert item.sequence_number == d["seqno"] and item.solid is True and item.stroke_opacity == 1.0
        assert item.paint_order == C.PAINT_CLEAR and item.paint_basis == C.PAINT_BASIS_CLEAR
        assert item.touches_band_edge is None                                  # the glass pair sits inside the band
    assert got.would_close_cell is True and len(got.cells) == 1
    cell = got.cells[0]
    assert cell.completion_paint == "clear" and cell.pane_lines == pytest.approx(meta["p"]) and cell.frame_lines == pytest.approx((300.0, 305.5))
    assert cell.along == pytest.approx(meta["cells"][0])
    assert got.standing_limits == C.STANDING_LIMITS
    for flag in C._GRANT_FLAGS:
        assert getattr(got, flag) is False and got.evidence_atoms[0].metadata[flag] is False
    assert got.evidence_atoms[0].status is CAND and got.evidence_atoms[0].document_id == got.ownership.document_id


def test_visible_length_ticks_are_never_reported_so_nothing_is_double_counted(monkeypatch):
    floor_plan_viewport(monkeypatch)
    _, meta, source, published, ids = hidden_window(glass=VISIBLE_GLASS)
    got = census(source, published, ids)
    assert got.sub_floor_items == () and got.groups == () and got.unstroked_sub_floor_count == 0
    assert got.status is ABST and got.reason_codes == (C.CENSUS_ONLY_NO_CELL_COMPLETION,) and got.would_close_cell is False
    assert len(got.cells) == 1 and got.cells[0].visible_closed and got.cells[0].lo_tick.support == C.TICK_VISIBLE
    both = Doc()
    draw_window(both, x=100.0, y=300.0)
    draw_window(both, x=300.0, y=300.0, glass=VISIBLE_GLASS)
    two_source, two_published = publish(both)
    region = census(two_source, two_published, region=(90.0, 290.0, 380.0, 315.0))
    assert len(region.sub_floor_items) == 2 and all(i.geometry[0] < 200.0 for i in region.sub_floor_items)
    assert len(two_published.visible_observation_ids) == 6 + 6 + 2         # the hidden window's six, the visible one's eight
    assert region.visible_in_region_count == 14


def test_the_sibling_strip_finder_cannot_see_the_hidden_ticks_and_the_census_nominates_what_it_does_see(monkeypatch):
    """A three-panel strip drawn by the sibling shadow's own fixture, with a glass pair thin enough to hide its ticks."""
    import pb_source_plan_glazing_strip_callout_shadow as sibling

    floor_plan_viewport(monkeypatch)
    sheet = Sheet(size=(900.0, 700.0))
    sheet.strip("H", 100.0, 300.0, panels=3, frame_len=204.0, pane=(2.52, 3.0))
    sheet.strip("H", 100.0, 400.0, panels=3, frame_len=204.0)                        # the same strip with visible ticks
    source = SourceVisibilityProducer(producer_method="subfloor-census-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(document_id="sheet", source_bytes=sheet.pdf(), source_locator="memory://s.pdf")
    found = sibling.audit_plan_callout_to_glazing_strip_from_source(
        source, revision_id=published.revision.revision_id, plan_page_id=1, elevation_page_id=2, callout_mark_pattern=r"[WD]\d+",
        panel_token="FG", coordinate_quantum_pt=Q, dimension_quantum_mm=5.0).strips
    assert [s.band for s in found] == [pytest.approx((400.0, 405.52))]               # only the visible-tick strip is a strip
    shadow = C.SubFloorInkCensusShadow(source, enabled=True)
    visible_strip = shadow.census(revision_id=published.revision.revision_id, page_id=1, coordinate_quantum_pt=Q,
                                  nominated_observation_ids=found[0].ink_ids)
    assert visible_strip.sub_floor_items == () and len(visible_strip.cells) == 3 and all(c.visible_closed for c in visible_strip.cells)
    hidden_ids = ids_in(source, published, (100.0, 300.0, 304.0, 305.52))
    hidden_strip = shadow.census(revision_id=published.revision.revision_id, page_id=1, coordinate_quantum_pt=Q,
                                 nominated_observation_ids=hidden_ids)
    assert hidden_strip.status is CAND and len(hidden_strip.cells) == 3 and all(c.would_close_cell for c in hidden_strip.cells)
    assert len(hidden_strip.sub_floor_items) == 6 and hidden_strip.axis == "H"


# --- region mode ------------------------------------------------------------------------------------------------------------------


def test_an_explicit_region_censuses_the_same_items_without_evaluating_closure(monkeypatch):
    floor_plan_viewport(monkeypatch)
    _, meta, source, published, ids = hidden_window()
    box = meta["box"]
    got = census(source, published, region=(box[0] - 5.0, box[1] - 5.0, box[2] + 5.0, box[3] + 5.0))
    assert got.mode == "region" and got.status is ABST and got.reason_codes == (C.CLOSURE_NOT_EVALUATED_REGION_MODE,)
    assert [i.item_id for i in got.sub_floor_items] == ["d6i0", "d7i0"] and got.cells == () and got.would_close_cell is None
    assert got.axis is None and all(i.strip_relation is None and i.touches_band_edge is None for i in got.sub_floor_items)
    assert census(source, published, region=(500.0, 500.0, 600.0, 600.0)).sub_floor_items == ()
    # the same region read through a nomination names the same hidden items
    assert [i.item_id for i in census(source, published, ids).sub_floor_items] == ["d6i0", "d7i0"]


def test_region_endpoints_that_meet_visible_producer_ink_name_the_visible_observations(monkeypatch):
    floor_plan_viewport(monkeypatch)
    _, meta, source, published, ids = hidden_window()
    got = census(source, published, ids)
    vis = source.authority()
    geometry = {o: tuple(vis.resolve_visible(selector(published, o)).observation.geometry) for o in ids}
    for item in got.sub_floor_items:
        for end, listed in (((item.geometry[0], item.geometry[1]), item.endpoint_a_visible_ids),
                            ((item.geometry[2], item.geometry[3]), item.endpoint_b_visible_ids)):
            touching = sorted(o for o, g in geometry.items()
                              if any(abs(end[0] - gx) <= 0.06 and abs(end[1] - gy) <= 0.06 for gx, gy in ((g[0], g[1]), (g[2], g[3]))))
            assert list(listed) == touching and len(touching) == 1          # the one glass line that ends there
        assert item.endpoints_coincide_visible is True


# --- paint order ----------------------------------------------------------------------------------------------------------------


def _with_later_paint(paint):
    doc = Doc()
    meta = draw_window(doc)
    paint(doc, meta)
    source, published = publish(doc)
    ids = window_ids(source, published)
    assert len(ids) == 6
    return doc, meta, source, published, ids


def test_a_later_opaque_fill_that_contains_a_tick_covers_it_and_the_completion_abstains(monkeypatch):
    floor_plan_viewport(monkeypatch)
    doc, meta, source, published, ids = _with_later_paint(
        lambda d, m: d.rect(101.0, 299.0, 159.0, 307.0, fill=(1, 1, 1), color=None, width=0))
    got = census(source, published, ids)
    assert got.status is ABST and got.would_close_cell is True and got.reason_codes == (C.COMPLETION_COVERED_BY_LATER_FILL,)
    assert {i.paint_order for i in got.sub_floor_items} == {C.PAINT_COVERED}
    assert all(i.covering_drawing_indices == (8,) and i.paint_basis == C.PAINT_BASIS_COVER for i in got.sub_floor_items)
    assert got.cells[0].completion_paint == "covered"


def test_a_fill_painted_before_the_ticks_does_not_cover_them(monkeypatch):
    floor_plan_viewport(monkeypatch)
    doc = Doc()
    doc.rect(101.0, 299.0, 159.0, 307.0, fill=(1, 1, 1), color=None, width=0)
    draw_window(doc)
    source, published = publish(doc)
    got = census(source, published, window_ids(source, published, first=1))
    assert got.status is CAND and {i.paint_order for i in got.sub_floor_items} == {C.PAINT_CLEAR}


def test_the_paint_order_is_unproven_for_a_fill_that_may_not_cover_and_for_paint_that_is_not_a_black_stroke(monkeypatch):
    floor_plan_viewport(monkeypatch)
    cases = {
        "translucent_fill": lambda d, m: d.rect(101.0, 299.0, 159.0, 307.0, fill=(1, 1, 1), fill_opacity=0.5, color=None, width=0),
        "fill_that_clips_the_tick_edge": lambda d, m: d.rect(101.0, 302.6, 159.0, 307.0, fill=(1, 1, 1), color=None, width=0),
        "text_over_the_ticks": lambda d, m: d.text((101.0, 304.0), "WWWWWWWWWWWWWWWWWWWW", size=6),
        "white_stroke_through_a_tick": lambda d, m: d.rect(102.5, 301.0, 106.0, 304.0, fill=None, color=(1, 1, 1), width=0.25),
        "gray_stroke_through_a_tick": lambda d, m: d.line((102.5, 301.0), (102.5, 304.0), color=(0.5, 0.5, 0.5), width=0.25),
        "translucent_black_stroke_through_a_tick": lambda d, m: d.line((102.5, 301.0), (102.5, 304.0), opacity=0.5),
    }
    for name, paint in cases.items():
        _, _, source, published, ids = _with_later_paint(paint)
        got = census(source, published, ids)
        assert got.status is ABST and got.would_close_cell is True, name
        assert got.reason_codes == (C.COMPLETION_PAINT_ORDER_UNPROVEN,), (name, got.reason_codes)
        assert C.PAINT_UNPROVEN in {i.paint_order for i in got.sub_floor_items}, name
        assert not any(i.paint_order == C.PAINT_COVERED for i in got.sub_floor_items), name


def test_a_fill_that_covers_only_one_of_the_two_ticks_still_withdraws_the_completion(monkeypatch):
    floor_plan_viewport(monkeypatch)
    _, _, source, published, ids = _with_later_paint(
        lambda d, m: d.rect(101.0, 299.0, 130.0, 307.0, fill=(1, 1, 1), color=None, width=0))
    got = census(source, published, ids)
    assert [i.paint_order for i in got.sub_floor_items] == [C.PAINT_COVERED, C.PAINT_CLEAR]
    assert got.status is ABST and got.would_close_cell is True and got.reason_codes == (C.COMPLETION_COVERED_BY_LATER_FILL,)


def test_a_later_coloured_centre_line_across_one_tick_leaves_that_tick_unproven_and_the_other_clear(monkeypatch):
    """The mechanism seen on a real export: a thin red centre line drawn after the frame crosses one pane tick."""
    floor_plan_viewport(monkeypatch)
    _, _, source, published, ids = _with_later_paint(
        lambda d, m: d.line((95.0, 302.75), (125.0, 302.75), color=(1, 0, 0), width=0.25))
    got = census(source, published, ids)
    assert [i.paint_order for i in got.sub_floor_items] == [C.PAINT_UNPROVEN, C.PAINT_CLEAR]
    assert got.status is ABST and got.would_close_cell is True and got.reason_codes == (C.COMPLETION_PAINT_ORDER_UNPROVEN,)
    assert got.cells[0].completion_paint == "unproven"


def test_a_later_stroke_is_judged_by_where_it_is_drawn_not_by_its_bounding_box(monkeypatch):
    floor_plan_viewport(monkeypatch)
    # a white rectangle drawn around the ticks without touching them: its bounding box holds them, its stroke does not reach them
    _, _, source, published, ids = _with_later_paint(
        lambda d, m: d.rect(101.0, 301.0, 159.0, 304.0, fill=None, color=(1, 1, 1), width=0.25))
    got = census(source, published, ids)
    assert got.status is CAND and {i.paint_order for i in got.sub_floor_items} == {C.PAINT_CLEAR}


def test_a_later_opaque_black_stroke_cannot_hide_a_black_tick_even_when_it_runs_through_it(monkeypatch):
    """The cell-edge tick at the same station is drawn after the pane tick in about half of all exports."""
    floor_plan_viewport(monkeypatch)
    _, _, source, published, ids = _with_later_paint(lambda d, m: d.line((102.5, 301.0), (102.5, 304.0), width=1.0))
    got = census(source, published, ids)
    assert got.status is CAND and {i.paint_order for i in got.sub_floor_items} == {C.PAINT_CLEAR}
    # ... unless a blend mode exists anywhere in the document: then nothing about painting is assumed
    doc = Doc()
    draw_window(doc)
    doc.line((102.5, 301.0), (102.5, 304.0), width=1.0)
    doc.doc.update_object(doc.doc.get_new_xref(), "<</Type/ExtGState/BM/Multiply>>")
    source, published = publish(doc)
    blended = census(source, published, window_ids(source, published))
    assert blended.status is ABST and C.PAINT_UNPROVEN in {i.paint_order for i in blended.sub_floor_items}


def test_a_clip_that_cuts_a_tick_makes_its_paint_order_unproven_and_a_clip_that_contains_it_does_not(monkeypatch):
    floor_plan_viewport(monkeypatch)
    for clips, states, expected in (
            (((90.0, 290.0, 120.0, 320.0), (157.5, 290.0, 170.0, 320.0)), [C.PAINT_CLEAR, C.PAINT_UNPROVEN], ABST),
            (((90.0, 290.0, 120.0, 320.0), (140.0, 290.0, 170.0, 320.0)), [C.PAINT_CLEAR, C.PAINT_CLEAR], CAND)):
        doc = Doc()
        meta = draw_window(doc, ticks=False)
        (a, b), (p0, p1) = meta["cells"][0], meta["p"]
        doc.clipped_line((a, p0), (a, p1), clips[0])
        doc.clipped_line((b, p0), (b, p1), clips[1])
        source, published = publish(doc)
        got = census(source, published, window_ids(source, published))
        assert [i.paint_order for i in got.sub_floor_items] == states and got.status is expected, clips
        if expected is ABST:
            assert got.sub_floor_items[1].paint_basis == C.PAINT_BASIS_CLIP_UNPROVEN
            assert got.reason_codes == (C.COMPLETION_PAINT_ORDER_UNPROVEN,)


def test_blend_modes_and_soft_masks_anywhere_in_the_document_withdraw_every_cover_claim():
    doc = fitz.open()
    doc.new_page(width=100.0, height=100.0)
    assert C._blend_or_softmask_present(doc) is False
    normal = doc.get_new_xref()
    doc.update_object(normal, "<</Type/ExtGState/BM/Normal>>")
    assert C._blend_or_softmask_present(doc) is False
    multiply = doc.get_new_xref()
    doc.update_object(multiply, "<</Type/ExtGState/BM/Multiply>>")
    assert C._blend_or_softmask_present(doc) is True
    other = fitz.open()
    other.new_page(width=100.0, height=100.0)
    mask = other.get_new_xref()
    other.update_object(mask, "<</Type/ExtGState/SMask<</Type/Mask/S/Luminosity>>>>")
    assert C._blend_or_softmask_present(other) is True
    none_mask = fitz.open()
    none_mask.new_page(width=100.0, height=100.0)
    none_mask.update_object(none_mask.get_new_xref(), "<</Type/ExtGState/SMask/None>>")
    assert C._blend_or_softmask_present(none_mask) is False


def test_a_paint_log_that_does_not_line_up_with_the_drawings_decides_nothing(monkeypatch):
    floor_plan_viewport(monkeypatch)
    doc = Doc()
    doc.line((10.0, 10.0), (10.0, 20.0))
    with fitz.open(stream=doc.pdf(), filetype="pdf") as opened:
        page = opened[0]
        drawings = page.get_drawings()
        good = C._build_paint_log(page, drawings, {}, False)
        assert good.aligned and [o.kind for o in good.ops] == ["stroke-path"]

        class Stub:
            def __init__(self, log):
                self._log = log

            def get_bboxlog(self):
                return self._log

        assert not C._build_paint_log(Stub([("fill-path", (0.0, 0.0, 99.0, 99.0))]), drawings, {}, False).aligned
        assert not C._build_paint_log(Stub([]), drawings, {}, False).aligned
        assert not C._build_paint_log(Stub([("stroke-path", (50.0, 50.0, 60.0, 60.0))]), drawings, {}, False).aligned
        assert not C._build_paint_log(Stub([("stroke-path", (9.0, 9.0, 11.0, 21.0))]), [{**drawings[0], "seqno": None}], {}, False).aligned

        class Broken:
            def get_bboxlog(self):
                raise RuntimeError("no log")

        assert C._build_paint_log(Broken(), drawings, {}, False).unproven_reason == "paint_log_unavailable"


# --- invariance --------------------------------------------------------------------------------------------------------------------


def _summary(result, origin=(0.0, 0.0)):
    ox, oy = origin
    rel = lambda g: tuple(round(v - (ox if k % 2 == 0 else oy), 3) for k, v in enumerate(g))      # noqa: E731
    return (result.status, result.reason_codes, result.would_close_cell,
            sorted((i.kind, round(i.length, 3), i.orientation, rel(i.geometry), i.paint_order, i.endpoints_coincide_visible,
                    len(i.endpoint_a_visible_ids), len(i.endpoint_b_visible_ids), i.touches_band_edge, i.hidden_by)
                   for i in result.sub_floor_items),
            sorted((g.stroke_width, g.stroke_rgb, g.orientation, g.length_bucket, g.count) for g in result.groups),
            sorted((round(c.pane_lines[0] - oy, 3), round(c.pane_lines[1] - oy, 3), round(c.along[0] - ox, 3),
                    round(c.along[1] - ox, 3), c.lo_tick.support, c.hi_tick.support, c.would_close_cell, c.completion_paint)
                   for c in result.cells))


def _world(*, shift=(0.0, 0.0), order=None, extra=False, rotate=False):
    """The one-panel hidden-tick window, optionally shifted, redrawn in another stroke order, surrounded by unrelated
    content or on a page that carries /Rotate 90."""
    doc = Doc()
    meta = draw_window(doc, shift=shift, order=order)
    if extra:
        draw_window(doc, x=500.0, y=150.0, length=90.0, panels=2)                  # unrelated: another strip, hidden ticks
        doc.rect(600.0, 500.0, 700.0, 600.0, fill=(0.9, 0.9, 0.9))
        doc.text((520.0, 400.0), "NOTES")
    if rotate:
        doc.doc[0].set_rotation(90)
    source, published = publish(doc)
    return source, published, ids_in(source, published, meta["box"])


def test_translation_of_the_whole_drawing_does_not_change_the_census(monkeypatch):
    floor_plan_viewport(monkeypatch)
    base_source, base_published, base_ids = _world()
    base = _summary(census(base_source, base_published, base_ids))
    for shift in ((128.0, 96.0), (-64.0, 128.5), (256.0, -32.0)):
        source, published, ids = _world(shift=shift)
        assert _summary(census(source, published, ids), shift) == base, shift


def test_input_order_and_the_order_the_strokes_were_drawn_do_not_change_the_census(monkeypatch):
    floor_plan_viewport(monkeypatch)
    source, published, ids = _world()
    base = _summary(census(source, published, ids))
    rng = random.Random(11)
    for _ in range(4):
        shuffled = list(ids)
        rng.shuffle(shuffled)
        assert _summary(census(source, published, shuffled)) == base
    for seed in (1, 2, 3):
        rnd = random.Random(seed)
        source, published, ids = _world(order=lambda n, rnd=rnd: rnd.sample(range(n), n))
        got = census(source, published, ids)
        assert _summary(got) == base and got.status is CAND


def test_unrelated_content_and_viewport_expansion_change_nothing(monkeypatch):
    floor_plan_viewport(monkeypatch)
    source, published, ids = _world()
    quiet = _summary(census(source, published, ids))
    noisy_source, noisy_published, noisy_ids = _world(extra=True)
    assert _summary(census(noisy_source, noisy_published, noisy_ids)) == quiet
    floor_plan_viewport(monkeypatch, boxes=((0.0, 0.0, 900.0, 700.0),))
    assert _summary(census(noisy_source, noisy_published, noisy_ids)) == quiet


def test_a_rotated_page_is_read_in_native_coordinates_and_gives_the_same_census(monkeypatch):
    floor_plan_viewport(monkeypatch)
    source, published, ids = _world()
    base = census(source, published, ids)
    turned_source, turned_published, turned_ids = _world(rotate=True)
    with fitz.open(stream=turned_source._producer._store.source_bytes_by_revision[turned_published.revision.revision_id],
                   filetype="pdf") as opened:
        assert opened[0].rotation == 90 and opened[0].rect.width == pytest.approx(700.0)      # the page IS rotated
    turned = census(turned_source, turned_published, turned_ids)
    assert _summary(turned) == _summary(base) and turned.status is CAND
    assert raw_sub_floor_geometry(turned) == raw_sub_floor_geometry(base)


def test_replay_is_deterministic_and_ids_are_stable(monkeypatch):
    floor_plan_viewport(monkeypatch)
    source, published, ids = _world(extra=True)
    first, again = census(source, published, ids), census(source, published, tuple(reversed(ids)))
    assert first == again and first.record_id == again.record_id and first.nomination_id == again.nomination_id
    assert first.cells[0].cell_id == again.cells[0].cell_id
    assert first.evidence_atoms[0].evidence_id == again.evidence_atoms[0].evidence_id
    changed = Doc()
    meta = draw_window(changed, x=164.0)
    c_source, c_published = publish(changed)
    assert census(c_source, c_published, ids_in(c_source, c_published, meta["box"])).record_id != first.record_id


# --- the producer is untouched ----------------------------------------------------------------------------------------------------


def _shape(obj):
    shape = {k: (len(v) if isinstance(v, (dict, set, list, tuple)) else None)
             for k, v in sorted(vars(obj).items())
             if isinstance(v, (dict, set, list, tuple)) or hasattr(v, "keys")}
    shape["_physical_opening_authority_cache_present"] = obj._physical_opening_authority_cache is not None
    return shape


def test_the_census_changes_no_output_and_no_state_of_the_producer(monkeypatch):
    floor_plan_viewport(monkeypatch)
    _, _, source, published, ids = hidden_window()
    before_shape = _shape(source)
    before_snapshot = source.published_snapshot_for_revision(published.revision.revision_id)
    before_bytes = bytes(source._producer._store.source_bytes_by_revision[published.revision.revision_id])
    before_visible = tuple(published.visible_observation_ids)
    first = census(source, published, ids)
    census(source, published, region=(90.0, 290.0, 170.0, 315.0))
    assert first.status is CAND
    assert _shape(source) == before_shape and source._physical_opening_authority_cache is None
    assert source.published_snapshot_for_revision(published.revision.revision_id) == before_snapshot
    assert bytes(source._producer._store.source_bytes_by_revision[published.revision.revision_id]) == before_bytes
    assert tuple(published.visible_observation_ids) == before_visible
    # ... and the opening authority a consumer builds afterwards behaves exactly as on a producer never censused
    shared = source.physical_opening_authority()
    outputs = sorted((shared.prove_existence(selector(published, i)).status.value,
                      shared.prove_existence(selector(published, i)).reason_codes) for i in ids)
    _, _, fresh_source, fresh_published, fresh_ids = hidden_window()
    fresh = fresh_source.physical_opening_authority()
    fresh_outputs = sorted((fresh.prove_existence(selector(fresh_published, i)).status.value,
                            fresh.prove_existence(selector(fresh_published, i)).reason_codes) for i in fresh_ids)
    assert outputs == fresh_outputs


def test_positive_control_the_state_check_does_see_a_consumer_filling_the_producers_memos(monkeypatch):
    """The equality above is only meaningful if an ordinary consumer call WOULD change that state."""
    floor_plan_viewport(monkeypatch)
    _, _, source, published, ids = hidden_window()
    census(source, published, ids)
    before = _shape(source)
    source.physical_opening_authority().prove_existence(selector(published, ids[0]))
    assert _shape(source) != before


def test_the_result_type_cannot_be_mistaken_for_an_existence_record_or_a_host_candidate():
    names = {f.name for f in fields(C.SubFloorInkCensus)}
    assert not ({"aperture_bbox_pt", "structural_pattern", "host_candidate_id", "candidate_wall_ids_considered",
                 "existence_record", "source_geometry", "host_wall_id", "area_m2", "quantity", "count"} & names)
    assert "existence_record_issued" in names             # explicitly a False grant flag, never a record
    with pytest.raises(ValueError, match="cannot grant"):
        replace(C.SubFloorInkCensusShadow._failure("x"), physical_opening_granted=True)


# --- scope failures ------------------------------------------------------------------------------------------------------------------


def test_without_an_authenticated_floor_plan_viewport_there_is_no_verdict():
    _, _, source, published, ids = hidden_window()        # a synthetic page has no segmentation at all
    for got in (census(source, published, ids), census(source, published, region=(90.0, 290.0, 170.0, 315.0))):
        assert got.status is ABST and got.reason_codes == (OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,)
        assert got.sub_floor_items == () and got.viewport_id is None and got.cells == () and got.groups == ()


@pytest.mark.parametrize("kwargs", [
    dict(view_type="elevation"),
    dict(boxes=(VIEWPORT, (100.0, 100.0, 800.0, 600.0))),          # two floor plans own the strip
    dict(boxes=((10.0, 10.0, 130.0, 690.0),)),                    # the strip is cropped by the viewport
])
def test_non_floor_plan_competing_or_cropping_viewports_abstain(monkeypatch, kwargs):
    floor_plan_viewport(monkeypatch, **kwargs)
    _, _, source, published, ids = hidden_window()
    got = census(source, published, ids)
    assert got.status is ABST and got.reason_codes == (OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,)
    assert census(source, published, region=(100.0, 290.0, 170.0, 315.0)).reason_codes == (OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,)


# --- nomination and ownership failures --------------------------------------------------------------------------------------------------


def test_unknown_foreign_page_or_stale_inputs_abstain(monkeypatch):
    floor_plan_viewport(monkeypatch)
    _, _, source, published, ids = hidden_window()
    assert census(source, published, ids + ("not-an-observation",)).reason_codes == (C.NOMINATION_NOT_VISIBLE_ON_PAGE,)
    assert census(source, published, ()).reason_codes == (C.NOMINATION_NOT_VISIBLE_ON_PAGE,)
    assert census(source, published, ids + (ids[0],)).reason_codes == (C.NOMINATION_NOT_VISIBLE_ON_PAGE,)       # duplicates kept
    assert census(source, published, ids, page_id=9).reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)         # page not decoded
    assert census(source, published, ids, page_id=0).reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)
    shadow = C.SubFloorInkCensusShadow(source, enabled=True)
    unknown = shadow.census(revision_id="no-such-revision", page_id=1, coordinate_quantum_pt=Q, nominated_observation_ids=ids)
    assert unknown.status is ABST and unknown.reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)


def test_ids_of_another_page_are_not_visible_on_this_one(monkeypatch):
    floor_plan_viewport(monkeypatch)
    doc = Doc(pages=2)
    meta = draw_window(doc)
    draw_window(doc, page=1)
    source, published = publish(doc)
    page_two = ids_in(source, published, meta["box"], page="2")
    assert page_two and census(source, published, page_two, page_id=2).status is CAND
    assert census(source, published, page_two, page_id=1).reason_codes == (C.NOMINATION_NOT_VISIBLE_ON_PAGE,)
    assert census(source, published, ids_in(source, published, meta["box"]), page_id=2).reason_codes == (
        C.NOMINATION_NOT_VISIBLE_ON_PAGE,)


def test_a_nomination_of_ink_with_no_depth_or_not_axis_aligned_names_no_region(monkeypatch):
    floor_plan_viewport(monkeypatch)
    doc = Doc()
    doc.line((100.0, 300.0), (130.0, 300.0))
    doc.line((130.0, 300.0), (160.0, 300.0))
    doc.line((200.0, 300.0), (230.0, 340.0))
    source, published = publish(doc)
    flat = ids_in(source, published, (99.0, 299.0, 161.0, 301.0))
    assert len(flat) == 2 and census(source, published, flat).reason_codes == (C.NOMINATION_HAS_NO_DEPTH,)
    slanted = ids_in(source, published, (199.0, 299.0, 231.0, 341.0))
    assert census(source, published, slanted).reason_codes == (C.NOMINATION_NOT_AXIS_ALIGNED,)


def test_invalid_requests_are_refused_not_guessed(monkeypatch):
    floor_plan_viewport(monkeypatch)
    _, _, source, published, ids = hidden_window()
    shadow = C.SubFloorInkCensusShadow(source, enabled=True)
    good = dict(revision_id=published.revision.revision_id, page_id=1, coordinate_quantum_pt=Q)
    with pytest.raises(ValueError, match="exactly one"):
        shadow.census(**good)
    with pytest.raises(ValueError, match="exactly one"):
        shadow.census(**good, nominated_observation_ids=ids, region_bbox=(0.0, 0.0, 1.0, 1.0))
    for bad in (dict(revision_id=1), dict(page_id="1"), dict(page_id=True), dict(coordinate_quantum_pt=0.0),
                dict(coordinate_quantum_pt=float("nan")), dict(coordinate_quantum_pt=True)):
        with pytest.raises(ValueError):
            shadow.census(**{**good, **bad}, nominated_observation_ids=ids)
    for bad_ids in ("abc", (1,), ("",), b"abc"):
        with pytest.raises(ValueError):
            shadow.census(**good, nominated_observation_ids=bad_ids)
    for bad_region in ((5.0, 0.0, 1.0, 1.0), (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, float("nan"), 1.0), (0.0, 0.0, 1.0), "abcd",
                       (0.0, 0.0, True, 1.0), (0.0, 0.0, "2", 1.0)):
        with pytest.raises(ValueError):
            shadow.census(**good, region_bbox=bad_region)
    # a one-shot iterable of ids is read exactly once
    assert shadow.census(**good, nominated_observation_ids=(i for i in ids)).status is CAND


def test_a_later_revision_makes_the_earlier_nomination_stale(monkeypatch):
    floor_plan_viewport(monkeypatch)
    _, _, source, published, ids = hidden_window()
    other = Doc()
    draw_window(other, length=70.0)
    source.ingest_native_pdf_bytes(document_id=published.revision.document_id, source_bytes=other.pdf(),
                                   source_locator="memory://subfloor-census-2.pdf")
    got = census(source, published, ids)
    assert got.status is ABST and got.reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)


# --- source integrity ------------------------------------------------------------------------------------------------------------------


def test_source_bytes_that_fail_their_sha_check_give_no_census(monkeypatch):
    floor_plan_viewport(monkeypatch)
    _, _, source, published, ids = hidden_window()
    revision = published.revision.revision_id
    store = source._producer._store.source_bytes_by_revision
    monkeypatch.setitem(store, revision, bytes(store[revision]) + b"\n%tampered")
    got = census(source, published, ids)
    assert got.status is ABST and got.reason_codes == (C.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,) and got.ownership is None
    monkeypatch.delitem(store, revision)
    assert census(source, published, ids).reason_codes == (C.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)


def test_a_primitive_set_that_does_not_match_the_producers_floor_on_this_page_gives_no_census(monkeypatch):
    """The census pins the producer's floor on the very page it reads: an extraction that drops or adds anything is refused."""
    import pb_vector_geometry_v130 as extraction

    floor_plan_viewport(monkeypatch)
    _, _, source, published, ids = hidden_window()
    original = extraction.extract_native_page

    def dropping(page):
        out = original(page)
        return {**out, "segments": out["segments"][1:]}

    def adding(page):
        out = original(page)
        return {**out, "segments": out["segments"] + [{**out["segments"][0], "id": "d6i0"}]}

    for patched in (dropping, adding):
        with monkeypatch.context() as patch:
            patch.setattr(extraction, "extract_native_page", patched)
            got = census(source, published, ids)
        assert got.status is ABST and got.reason_codes == (C.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,), patched.__name__
    assert census(source, published, ids).status is CAND


class _Tampered:
    """Run the census with one visible observation replaced by a doctored authority result."""

    def __init__(self, monkeypatch, source, published):
        self.mp, self.source, self.published = monkeypatch, source, published

    def run(self, ids, victim, tamper, **kw):
        visibility = self.source.authority()
        original = visibility.resolve_visible

        def resolve(sel):
            result = original(sel)
            return tamper(result) if sel.observation_id == victim else result

        with self.mp.context() as patch:
            patch.setattr(visibility, "resolve_visible", resolve)
            patch.setattr(self.source, "authority", lambda: visibility)
            return census(self.source, self.published, ids, **kw)


def _window_with_a_rival():
    """The hidden-tick window plus one long stroke crossing the strip: visible producer ink the nomination does not name."""
    doc = Doc()
    meta = draw_window(doc)
    doc.line((130.0, 296.0), (130.0, 310.0))
    source, published = publish(doc)
    ids = ids_in(source, published, meta["box"])
    (rival,) = ids_in(source, published, (129.0, 295.0, 131.0, 311.0))
    assert rival not in ids and len(ids) == 6
    return source, published, ids, rival


def test_a_foreign_published_observation_cannot_be_laundered_into_the_page_census(monkeypatch):
    floor_plan_viewport(monkeypatch)
    source, published, ids, rival = _window_with_a_rival()
    assert census(source, published, ids).status is CAND
    tamper = _Tampered(monkeypatch, source, published)
    for victim in (rival, ids[0]):
        for field, value in (("observation_id", "foreign-observation"), ("document_id", "foreign-document"),
                             ("revision_id", "foreign-revision"), ("source_sha256", "0" * 64),
                             ("snapshot_id", "foreign-snapshot")):
            got = tamper.run(ids, victim, lambda r, f=field, v=value: replace(r, observation=replace(r.observation, **{f: v})))
            assert got.status is ABST and got.reason_codes == (C.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,), field
            assert got.ownership is None and got.sub_floor_items == ()


def test_a_published_observation_that_fails_its_own_resolution_blocks_a_candidate_but_not_the_census(monkeypatch):
    floor_plan_viewport(monkeypatch)
    source, published, ids, rival = _window_with_a_rival()
    visibility = source.authority()
    got = _Tampered(monkeypatch, source, published).run(
        ids, rival, lambda r: visibility._conflict("synthetic_visible_source_integrity_failure"))
    assert got.status is ABST and got.visible_inventory_complete is False and got.would_close_cell is True
    assert got.reason_codes == (C.VISIBLE_INVENTORY_INCOMPLETE,) and len(got.sub_floor_items) == 2
    assert census(source, published, ids).status is CAND


@pytest.mark.parametrize("malformed", [None, 17, ("bad", 2.0, 3.0, 4.0), (float("nan"), 2.0, 3.0, 4.0),
                                       (float("inf"), 2.0, 3.0, 4.0), (10 ** 1000, 2.0, 3.0, 4.0), (True, 2.0, 3.0, 4.0),
                                       (1.0, 2.0, 3.0)])
def test_a_malformed_published_rival_blocks_a_candidate_instead_of_crashing(monkeypatch, malformed):
    floor_plan_viewport(monkeypatch)
    source, published, ids, rival = _window_with_a_rival()
    got = _Tampered(monkeypatch, source, published).run(
        ids, rival, lambda r: replace(r, observation=replace(r.observation, geometry=malformed)))
    assert got.status is ABST and got.visible_inventory_complete is False
    assert got.reason_codes == (C.VISIBLE_INVENTORY_INCOMPLETE,) and got.would_close_cell is True
    assert len(got.sub_floor_items) == 2


def test_an_observation_shorter_than_the_producers_floor_means_the_floor_moved_and_gives_no_census(monkeypatch):
    floor_plan_viewport(monkeypatch)
    source, published, ids, rival = _window_with_a_rival()
    got = _Tampered(monkeypatch, source, published).run(
        ids, rival, lambda r: replace(r, observation=replace(r.observation, geometry=(100.0, 300.0, 100.0, 300.25))))
    assert got.status is ABST and got.reason_codes == (C.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,)


@pytest.mark.parametrize("field", ["source_primitive_ref", "geometry"])
def test_a_visible_observation_whose_primitive_join_fails_has_no_role_and_blocks_a_candidate(monkeypatch, field):
    floor_plan_viewport(monkeypatch)
    source, published, ids, rival = _window_with_a_rival()

    def tamper(r):
        o = r.observation
        o = (replace(o, source_primitive_ref="visible:segment:missing-original") if field == "source_primitive_ref"
             else replace(o, geometry=(o.geometry[0] + 0.125, *o.geometry[1:])))
        return replace(r, observation=o)

    rivalled = _Tampered(monkeypatch, source, published).run(ids, rival, tamper)
    assert rivalled.status is ABST and rivalled.visible_inventory_complete is False and rivalled.would_close_cell is True
    assert rivalled.reason_codes == (C.VISIBLE_INVENTORY_INCOMPLETE,)
    nominated = _Tampered(monkeypatch, source, published).run(ids, ids[0], tamper)
    assert nominated.status is ABST and nominated.reason_codes == (C.SOURCE_ROLE_UNPROVEN, C.SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE)


def test_a_visible_rival_that_is_not_ink_at_all_is_not_a_rival(monkeypatch):
    """A fill edge has no stroke: its join to the producer's primitive is proven, so it is neither ink nor an unknown."""
    floor_plan_viewport(monkeypatch)
    doc = Doc()
    meta = draw_window(doc)
    doc.rect(129.0, 296.0, 131.0, 310.0, fill=(0.8, 0.8, 0.8), color=None, width=0)
    source, published = publish(doc)
    ids = ids_in(source, published, meta["box"])
    got = census(source, published, ids)
    assert got.status is CAND and got.visible_inventory_complete is True and got.visible_in_region_count == 6 + 4


def test_ink_that_is_not_a_solid_opaque_black_stroke_never_closes_a_cell(monkeypatch):
    """Dashed, translucent or gray pane lines are visible producer ink, and still are not the finder's ink."""
    floor_plan_viewport(monkeypatch)
    for style in (dict(dashes="[2] 0"), dict(opacity=0.5), dict(color=(0.6, 0.6, 0.6))):
        doc = Doc()
        meta = draw_window(doc, styles={"pl0": style})
        source, published = publish(doc)
        got = census(source, published, ids_in(source, published, meta["box"]))
        assert got.status is ABST and got.would_close_cell is False and len(got.sub_floor_items) == 2, style


# --- the sibling glazing-strip finder's own reading of the same drawing, through the real producer -----------------------------------------


def test_the_diagnostic_matches_the_finders_reading_of_the_producers_ink_with_and_without_the_hidden_ticks(monkeypatch):
    import pb_source_plan_glazing_strip_callout_shadow as S

    floor_plan_viewport(monkeypatch)
    for glass, expected_new in ((HIDDEN_GLASS, True), (VISIBLE_GLASS, False)):
        _, meta, source, published, ids = hidden_window(glass=glass, panels=2, length=110.0)
        got = census(source, published, ids)
        scope = S.PlanCalloutStripScope(
            ownership=S.SourceOwnership("d", "r", "s", "a" * 64, S.PRODUCER_INPUT_PROVENANCE), plan_page_id="1",
            elevation_page_id="2", callout_mark_pattern=r"[WD]\d+", coordinate_quantum_pt=Q, dimension_quantum_mm=5.0,
            plan_viewports=(S.PlanViewportRef("v", VIEWPORT),))
        vis = source.authority()
        ink = []
        for oid in published.visible_observation_ids:
            g = vis.resolve_visible(selector(published, oid)).observation.geometry
            ink.append(S.PlanInkSegment(oid, *g, W, True))
        before = S.audit_plan_callout_to_glazing_strip_shadow(scope, ink=ink, words=[], elevation_types=[]).strips
        hidden_ink = [S.PlanInkSegment(i.item_id, *i.geometry, i.stroke_width, True) for i in got.sub_floor_items]
        after = S.audit_plan_callout_to_glazing_strip_shadow(scope, ink=ink + hidden_ink, words=[], elevation_types=[]).strips
        assert got.would_close_cell is expected_new is (len(after) > len(before)), glass
        assert len(got.cells) == 2
