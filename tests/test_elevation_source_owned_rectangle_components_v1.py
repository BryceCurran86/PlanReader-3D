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
