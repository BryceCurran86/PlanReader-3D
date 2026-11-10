"""A filled path is read as the closed rectangles it actually draws, never as its bounding box (review 5834419211, defect 1)."""
from __future__ import annotations

import hashlib
import random

import fitz
import pytest

import pb_elevation_source_owned_witness_adapter as adapter
from pb_source_visibility_authority import SourceVisibilityProducer

FILL = (0.3, 0.3, 0.3)


def edges_of(points, fill=FILL, prefix="e"):
    """Closed polyline -> edge tuples (x0, y0, x1, y1, fill, id)."""
    out = []
    for i in range(len(points)):
        a, b = points[i], points[(i + 1) % len(points)]
        out.append((a[0], a[1], b[0], b[1], fill, f"{prefix}{i}"))
    return out


def rect_pts(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# ------------------------------------------------------------------------------------------------ pure
def test_one_rectangle_is_one_rectangle_with_its_own_four_receipts():
    (r,) = adapter.rectangle_components(edges_of(rect_pts(200.0, 200.0, 220.0, 250.0)))
    assert r[:5] == (200.0, 200.0, 220.0, 250.0, FILL) and r[5] == ("e0", "e1", "e2", "e3")


def test_two_disjoint_rectangles_in_one_path_stay_two_rectangles_and_never_span_the_gap():
    edges = edges_of(rect_pts(200.0, 200.0, 220.0, 250.0), prefix="a") + edges_of(rect_pts(250.0, 200.0, 270.0, 250.0), prefix="b")
    rects = adapter.rectangle_components(edges)
    assert [r[:4] for r in rects] == [(200.0, 200.0, 220.0, 250.0), (250.0, 200.0, 270.0, 250.0)]
    assert [r[5] for r in rects] == [("a0", "a1", "a2", "a3"), ("b0", "b1", "b2", "b3")]       # receipts describe the outline drawn
    assert not any(r[0] <= 200.0 and r[2] >= 270.0 for r in rects)                              # no phantom enclosing box


def test_an_l_shaped_loop_is_not_a_rectangle():
    l_shape = [(200.0, 200.0), (240.0, 200.0), (240.0, 220.0), (220.0, 220.0), (220.0, 250.0), (200.0, 250.0)]
    assert adapter.rectangle_components(edges_of(l_shape)) == []


def test_a_rectangle_beside_a_nonrectangular_loop_in_one_path_is_kept_alone():
    l_shape = [(400.0, 200.0), (440.0, 200.0), (440.0, 220.0), (420.0, 220.0), (420.0, 250.0), (400.0, 250.0)]
    rects = adapter.rectangle_components(edges_of(rect_pts(200.0, 200.0, 220.0, 250.0), prefix="a") + edges_of(l_shape, prefix="l"))
    assert [r[:4] for r in rects] == [(200.0, 200.0, 220.0, 250.0)]
    assert all(i.startswith("a") for i in rects[0][5])


def test_a_diagonal_edge_or_an_open_chain_is_not_a_rectangle():
    triangle = [(0.0, 0.0), (30.0, 0.0), (0.0, 40.0)]
    assert adapter.rectangle_components(edges_of(triangle)) == []
    open_chain = edges_of(rect_pts(0.0, 0.0, 10.0, 10.0))[:3]                                    # three sides only
    assert adapter.rectangle_components(open_chain) == []


def test_two_rectangles_touching_at_a_corner_are_not_guessed_apart():
    a = edges_of(rect_pts(0.0, 0.0, 10.0, 10.0), prefix="a")
    b = edges_of(rect_pts(10.0, 10.0, 20.0, 20.0), prefix="b")                                   # shares the corner (10, 10)
    assert adapter.rectangle_components(a + b) == []


def test_a_side_split_into_collinear_pieces_is_still_the_same_rectangle():
    pts = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]                       # the bottom side drawn in two pieces
    (r,) = adapter.rectangle_components(edges_of(pts))
    assert r[:4] == (0.0, 0.0, 10.0, 10.0) and len(r[5]) == 5


def test_a_duplicate_closing_edge_is_one_edge_and_mixed_fills_are_refused():
    edges = edges_of(rect_pts(0.0, 0.0, 10.0, 10.0))
    dup = edges + [(edges[-1][2], edges[-1][3], edges[-1][0], edges[-1][1], FILL, "dup")]       # the closing edge drawn again, reversed
    (r,) = adapter.rectangle_components(dup)
    assert r[:4] == (0.0, 0.0, 10.0, 10.0) and "dup" in r[5]
    mixed = [(*e[:4], (0.9, 0.9, 0.9) if i == 0 else FILL, e[5]) for i, e in enumerate(edges)]
    assert adapter.rectangle_components(mixed) == []


def test_zero_length_edges_draw_nothing_and_do_not_break_a_rectangle():
    edges = edges_of(rect_pts(0.0, 0.0, 10.0, 10.0)) + [(5.0, 5.0, 5.0, 5.0, FILL, "dot")]
    (r,) = adapter.rectangle_components(edges)
    assert "dot" not in r[5] and r[:4] == (0.0, 0.0, 10.0, 10.0)


def test_corner_coincidence_tolerance():
    edges = edges_of(rect_pts(0.0, 0.0, 10.0, 10.0))

    def with_second_edge_end_moved(dy):
        return [(a, b, c, d + dy, f, i) if k == 1 else (a, b, c, d, f, i) for k, (a, b, c, d, f, i) in enumerate(edges)]
    assert len(adapter.rectangle_components(with_second_edge_end_moved(0.004))) == 1              # 0.004 pt: the same corner
    assert adapter.rectangle_components(with_second_edge_end_moved(0.5)) == []                    # 0.5 pt: an open corner, not a closed box


def test_rotation_translation_and_mirror_invariance():
    edges = edges_of(rect_pts(0.0, 0.0, 10.0, 10.0))
    for fn in (lambda x, y: (x + 1234.5, y - 987.25), lambda x, y: (-y, x), lambda x, y: (-x, y)):
        moved = [(*fn(e[0], e[1]), *fn(e[2], e[3]), e[4], e[5]) for e in edges]
        (r,) = adapter.rectangle_components(moved)
        assert r[2] - r[0] == pytest.approx(10.0) and r[3] - r[1] == pytest.approx(10.0)


def test_a_bowtie_with_two_diagonals_and_two_verticals_is_not_a_rectangle():
    # four corners on two distinct x and two distinct y, but two of its edges are diagonals: an hourglass, not a box
    bowtie = [(0.0, 0.0), (10.0, 10.0), (10.0, 0.0), (0.0, 10.0)]
    assert adapter.rectangle_components(edges_of(bowtie)) == []


def test_a_rectangle_with_a_tail_or_a_junction_is_not_a_rectangle():
    edges = edges_of(rect_pts(0.0, 0.0, 10.0, 10.0))
    assert adapter.rectangle_components(edges + [(10.0, 10.0, 20.0, 10.0, FILL, "tail")]) == []                # a pendant edge
    split = edges_of([(0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)])
    assert adapter.rectangle_components(split + [(5.0, 0.0, 5.0, -5.0, FILL, "spur")]) == []                  # a spur off a split point
    crossing = edges + [(5.0, 0.0, 5.0, -5.0, FILL, "crossing")]                                              # touches a side mid-edge only
    assert [r[:4] for r in adapter.rectangle_components(crossing)] == [(0.0, 0.0, 10.0, 10.0)]                # no shared corner: separate


def test_a_zero_length_edge_at_a_corner_does_not_hide_the_rectangle():
    edges = edges_of(rect_pts(0.0, 0.0, 10.0, 10.0)) + [(10.0, 10.0, 10.0, 10.0, FILL, "dot")]
    (r,) = adapter.rectangle_components(edges)
    assert r[:4] == (0.0, 0.0, 10.0, 10.0) and "dot" not in r[5]


def test_edge_order_does_not_change_the_rectangles():
    edges = edges_of(rect_pts(200.0, 200.0, 220.0, 250.0), prefix="a") + edges_of(rect_pts(250.0, 200.0, 270.0, 250.0), prefix="b")
    ref = adapter.rectangle_components(edges)
    rng = random.Random(9)
    for _ in range(30):
        shuffled = edges[:]
        rng.shuffle(shuffled)
        assert adapter.rectangle_components(shuffled) == ref


def test_inputs_are_not_mutated():
    edges = edges_of(rect_pts(0.0, 0.0, 10.0, 10.0))
    snapshot = list(edges)
    adapter.rectangle_components(edges)
    assert edges == snapshot


# ------------------------------------------------------------------------------------------------ the real producer (the reviewer's counterexample)
def _compound_pdf(polygons) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    shape = page.new_shape()
    for pts in polygons:
        shape.draw_polyline(list(pts) + [pts[0]])
    shape.finish(fill=FILL, color=None, closePath=True)
    shape.commit()
    return doc.tobytes()


def _page_rects(payload: bytes):
    source = SourceVisibilityProducer(producer_method="live-physical-net-wall", producer_version="1")
    sha = hashlib.sha256(payload).hexdigest()
    initial = source.ingest_native_pdf_bytes(document_id=f"live-source:{sha[:32]}", source_bytes=payload,
                                             source_locator="memory://compound.pdf", page_ids=(1,))
    page = adapter.read_source_owned_page(source, revision_id=initial.revision.revision_id, page_id="1")
    return page.rects


def test_a_compound_filled_path_through_the_real_producer_gives_two_rectangles_not_their_bounding_box():
    rects = _page_rects(_compound_pdf([rect_pts(200.0, 200.0, 220.0, 250.0), rect_pts(250.0, 200.0, 270.0, 250.0)]))
    assert sorted(r[:4] for r in rects) == [(200.0, 200.0, 220.0, 250.0), (250.0, 200.0, 270.0, 250.0)]
    assert not any(r[0] <= 200.0 + 0.01 and r[2] >= 270.0 - 0.01 for r in rects)           # nothing spans the blank 30 pt gap
    ids = [set(r[5]) for r in rects]
    assert all(len(i) == 4 for i in ids) and ids[0].isdisjoint(ids[1])                       # receipts are each outline's own edges


def test_an_l_shaped_filled_path_through_the_real_producer_is_no_rectangle():
    l_shape = [(200.0, 200.0), (240.0, 200.0), (240.0, 220.0), (220.0, 220.0), (220.0, 250.0), (200.0, 250.0)]
    assert list(_page_rects(_compound_pdf([l_shape]))) == []
    rects = _page_rects(_compound_pdf([l_shape, rect_pts(300.0, 200.0, 320.0, 250.0)]))
    assert [r[:4] for r in rects] == [(300.0, 200.0, 320.0, 250.0)]


def test_a_single_filled_rectangle_through_the_real_producer_is_unchanged():
    rects = _page_rects(_compound_pdf([rect_pts(200.0, 200.0, 220.0, 250.0)]))
    assert [r[:4] for r in rects] == [(200.0, 200.0, 220.0, 250.0)] and len(rects[0][5]) == 4


# ------------------------------------------------------------------------------------------------ thin strips (the producer drops short sides)
def sides(x0, x1, y_a, y_b, fill=FILL, prefix="s"):
    """The two long horizontal sides of a thin strip (its short sides are below the producer's edge floor)."""
    return [(x0, y_a, x1, y_a, fill, f"{prefix}a"), (x1, y_b, x0, y_b, fill, f"{prefix}b")]


def test_two_parallel_sides_closer_than_the_edge_floor_are_one_strip_with_their_own_receipts():
    (rect,) = adapter.rectangle_components(sides(100.0, 134.0, 277.29, 277.57))
    assert rect[:4] == (100.0, 277.29, 134.0, 277.57) and rect[4] == FILL and rect[5] == ("sa", "sb")


def test_a_vertical_strip_is_read_the_same_way():
    edges = [(648.7, 247.8, 648.7, 277.6, FILL, "va"), (649.13, 277.6, 649.13, 247.8, FILL, "vb")]
    assert [r[:4] for r in adapter.rectangle_components(edges)] == [(648.7, 247.8, 649.13, 277.6)]


def test_sides_at_or_beyond_the_edge_floor_are_not_a_strip():
    assert adapter.rectangle_components(sides(100.0, 134.0, 277.0, 277.5)) == []       # exactly the floor: the producer keeps such short sides
    assert adapter.rectangle_components(sides(100.0, 134.0, 277.0, 278.0)) == []


def test_the_edge_floor_is_the_producers_edge_floor():
    assert adapter.SUB_FLOOR_PT == 0.5


def test_a_lone_side_and_sides_of_different_extent_or_fill_are_no_rectangle():
    assert adapter.rectangle_components(sides(100.0, 134.0, 277.29, 277.57)[:1]) == []
    other_extent = [(100.0, 277.29, 134.0, 277.29, FILL, "a"), (100.0, 277.57, 133.0, 277.57, FILL, "b")]
    assert adapter.rectangle_components(other_extent) == []
    other_fill = [(100.0, 277.29, 134.0, 277.29, FILL, "a"), (100.0, 277.57, 134.0, 277.57, (0.9, 0.9, 0.9), "b")]
    assert adapter.rectangle_components(other_fill) == []


def test_sides_that_share_only_one_end_of_their_extent_are_no_strip():
    shifted_start = [(100.0, 277.29, 134.0, 277.29, FILL, "a"), (110.0, 277.57, 134.0, 277.57, FILL, "b")]
    assert adapter.rectangle_components(shifted_start) == []
    shifted_end = [(100.0, 277.29, 134.0, 277.29, FILL, "a"), (100.0, 277.57, 120.0, 277.57, FILL, "b")]
    assert adapter.rectangle_components(shifted_end) == []


def test_a_horizontal_and_a_vertical_side_of_the_same_extent_never_pair():
    mixed = [(100.0, 277.0, 134.0, 277.0, FILL, "h"), (277.2, 100.0, 277.2, 134.0, FILL, "v")]
    assert adapter.rectangle_components(mixed) == []
    assert adapter.rectangle_components(list(reversed(mixed))) == []


def test_three_sides_within_the_floor_are_an_ambiguous_pairing_and_yield_nothing():
    three = sides(100.0, 134.0, 277.0, 277.2) + [(100.0, 277.4, 134.0, 277.4, FILL, "sc")]
    assert adapter.rectangle_components(three) == []
    assert adapter.rectangle_components(list(reversed(three))) == []


def test_two_strips_of_the_same_extent_far_apart_are_two_strips():
    both = sides(100.0, 134.0, 200.0, 200.3, prefix="t") + sides(100.0, 134.0, 277.29, 277.57, prefix="u")
    assert [r[:4] for r in adapter.rectangle_components(both)] == [(100.0, 200.0, 134.0, 200.3), (100.0, 277.29, 134.0, 277.57)]
    assert [r[5] for r in adapter.rectangle_components(both)] == [("ta", "tb"), ("ua", "ub")]       # receipts never cross strips


def test_a_strip_beside_a_closed_rectangle_in_one_path_keeps_both():
    mixed = edges_of(rect_pts(200.0, 200.0, 220.0, 250.0), prefix="r") + sides(100.0, 134.0, 277.29, 277.57)
    assert sorted(r[:4] for r in adapter.rectangle_components(mixed)) == [(100.0, 277.29, 134.0, 277.57), (200.0, 200.0, 220.0, 250.0)]


def test_strip_reading_is_order_translation_and_split_invariant():
    base = sides(100.0, 134.0, 277.29, 277.57)
    shifted = [(x0 + 37.0, y0 - 11.5, x1 + 37.0, y1 - 11.5, f, i) for x0, y0, x1, y1, f, i in base]
    assert [tuple(round(v, 2) for v in r[:4]) for r in adapter.rectangle_components(shifted)] == [(137.0, 265.79, 171.0, 266.07)]
    assert adapter.rectangle_components(list(reversed(base)))[0][:4] == adapter.rectangle_components(base)[0][:4]
    assert adapter.rectangle_components(base + base) == adapter.rectangle_components(base)           # a duplicated side is one side


def test_a_strip_never_borrows_a_side_of_a_closed_rectangle():
    # the long side of a closed rectangle is not a lone side: it shares corners with its own loop
    rect = edges_of(rect_pts(100.0, 277.0, 134.0, 290.0), prefix="r")
    assert [r[:4] for r in adapter.rectangle_components(rect + [(100.0, 277.2, 134.0, 277.2, FILL, "x")])] == [(100.0, 277.0, 134.0, 290.0)]


# ------------------------------------------------------------------------------------------------ the real producer's floor
def _strip_pdf(thickness: float) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    shape = page.new_shape()
    shape.draw_polyline(rect_pts(100.0, 200.0, 134.0, 200.0 + thickness) + [(100.0, 200.0)])       # m/l edges, as a CAD export draws them
    shape.finish(fill=FILL, color=None, closePath=True)
    shape.commit()
    return doc.tobytes()


def _line_facts(payload: bytes):
    source = SourceVisibilityProducer(producer_method="live-physical-net-wall", producer_version="1")
    sha = hashlib.sha256(payload).hexdigest()
    initial = source.ingest_native_pdf_bytes(document_id=f"live-source:{sha[:32]}", source_bytes=payload,
                                             source_locator="memory://strip.pdf", page_ids=(1,))
    page = adapter.read_source_owned_page(source, revision_id=initial.revision.revision_id, page_id="1")
    return page.rects, page.lines


def test_the_real_producer_keeps_the_short_sides_of_a_thick_strip_and_drops_those_of_a_thin_one():
    # pins SUB_FLOOR_PT to the producer: a drift in its 0.5 pt edge floor would break the strip rule silently
    thick_rects, thick_lines = _line_facts(_strip_pdf(0.6))
    thin_rects, thin_lines = _line_facts(_strip_pdf(0.4))
    assert len(thick_lines) == 4 and len(thin_lines) == 2
    assert [tuple(round(v, 2) for v in r[:4]) for r in thick_rects] == [(100.0, 200.0, 134.0, 200.6)]
    assert [tuple(round(v, 2) for v in r[:4]) for r in thin_rects] == [(100.0, 200.0, 134.0, 200.4)]


def test_a_compound_path_of_two_thin_strips_through_the_real_producer_gives_two_strips():
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    shape = page.new_shape()
    shape.draw_polyline(rect_pts(100.0, 200.0, 134.0, 200.3) + [(100.0, 200.0)])
    shape.draw_polyline(rect_pts(100.0, 277.0, 134.0, 277.3) + [(100.0, 277.0)])
    shape.finish(fill=FILL, color=None, closePath=True)
    shape.commit()
    rects, _lines = _line_facts(doc.tobytes())
    assert [tuple(round(v, 2) for v in r[:4]) for r in rects] == [(100.0, 200.0, 134.0, 200.3), (100.0, 277.0, 134.0, 277.3)]
