"""Adversarial/mutation tests for pb_dimension_chain_topology_authority.

All fixtures are synthetic PDFs built directly with PyMuPDF drawing
primitives -- no benchmark project geometry, page numbers, or expected
quantities appear anywhere in this file.
"""
from __future__ import annotations

import fitz
import pytest

from pb_dimension_chain_topology_authority import (
    ChainCorroborationStatus,
    resolve_structured_dimension_chains,
)

PAGE_W, PAGE_H = 640.0, 500.0
FRAME = (40.0, 40.0, 560.0, 460.0)


def _new_page() -> fitz.Page:
    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    return page


def _draw_frame(page: fitz.Page, rect=FRAME, *, title="GROUND FLOOR PLAN") -> None:
    x0, y0, x1, y1 = rect
    page.draw_rect(fitz.Rect(x0, y0, x1, y1))
    page.insert_text((x0 + 10, y1 - 10), title, fontsize=10)


def _draw_continuous_vertical_chain(
    page: fitz.Page,
    *,
    x: float,
    y_start: float,
    values_mm: list[int],
    px_per_segment: float = 40.0,
    fragmented: bool = False,
) -> None:
    """Draw one continuous vertical dimension chain: N+1 tick marks and
    either one continuous line (fragmented=False) or one line fragment per
    sub-interval (fragmented=True, matching some real CAD exporters that
    split the dimension line at every tick)."""
    n = len(values_mm)
    ys = [y_start + i * px_per_segment for i in range(n + 1)]
    for y in ys:
        page.draw_line((x - 6, y), (x + 6, y))
    if fragmented:
        for i in range(n):
            page.draw_line((x, ys[i]), (x, ys[i + 1]))
    else:
        page.draw_line((x, ys[0]), (x, ys[-1]))
    for i, val in enumerate(values_mm):
        mid = (ys[i] + ys[i + 1]) / 2.0
        page.insert_text((x + 8, mid + 3), str(val), fontsize=9, rotate=90)


def _draw_continuous_horizontal_chain(
    page: fitz.Page,
    *,
    y: float,
    x_start: float,
    values_mm: list[int],
    px_per_segment: float = 40.0,
    fragmented: bool = False,
) -> None:
    n = len(values_mm)
    xs = [x_start + i * px_per_segment for i in range(n + 1)]
    for x in xs:
        page.draw_line((x, y - 6), (x, y + 6))
    if fragmented:
        for i in range(n):
            page.draw_line((xs[i], y), (xs[i + 1], y))
    else:
        page.draw_line((xs[0], y), (xs[-1], y))
    for i, val in enumerate(values_mm):
        mid = (xs[i] + xs[i + 1]) / 2.0
        page.insert_text((mid - 10, y - 8), str(val), fontsize=9)


def _draw_overall(page: fitz.Page, *, x: float, y0: float, y1: float, value_mm: int) -> None:
    """An outer, independently-figured overall dimension parallel to (and
    outside) a vertical chain -- its own dimension line + ticks, offset
    further out along the perpendicular axis."""
    page.draw_line((x - 6, y0), (x + 6, y0))
    page.draw_line((x - 6, y1), (x + 6, y1))
    page.draw_line((x, y0), (x, y1))
    page.insert_text((x - 30, (y0 + y1) / 2.0 + 3), str(value_mm), fontsize=9, rotate=90)


def _bytes(page: fitz.Page) -> bytes:
    doc = page.parent
    data = doc.tobytes()
    doc.close()
    return data


def _resolve(data: bytes):
    doc = fitz.open(stream=data, filetype="pdf")
    page = doc[0]
    return resolve_structured_dimension_chains(page, page_num=1)


def test_two_segment_continuous_chain_corroborated_by_overall():
    page = _new_page()
    _draw_frame(page)
    _draw_continuous_vertical_chain(page, x=100.0, y_start=100.0, values_mm=[2200, 3000])
    _draw_overall(page, x=70.0, y0=100.0, y1=180.0, value_mm=5200)
    chains = _resolve(_bytes(page))
    assert len(chains) == 1
    ch = chains[0]
    assert ch.orientation == "vertical"
    assert ch.segment_count == 2
    assert ch.status == ChainCorroborationStatus.CORROBORATED_BY_OVERALL.value
    assert [s.value_m for s in ch.segments] == [2.2, 3.0]


def test_five_segment_continuous_chain_corroborated_by_overall():
    page = _new_page()
    _draw_frame(page)
    values = [200, 6100, 200, 1500, 200]
    _draw_continuous_vertical_chain(page, x=100.0, y_start=100.0, values_mm=values, px_per_segment=40.0)
    _draw_overall(page, x=70.0, y0=100.0, y1=100.0 + 40.0 * 5, value_mm=sum(values))
    chains = _resolve(_bytes(page))
    assert len(chains) == 1
    ch = chains[0]
    assert ch.segment_count == 5
    assert ch.status == ChainCorroborationStatus.CORROBORATED_BY_OVERALL.value
    assert ch.value_at_ordinal(3) == pytest.approx(1.5)


def test_horizontal_chain_orientation():
    page = _new_page()
    _draw_frame(page)
    _draw_continuous_horizontal_chain(page, y=100.0, x_start=100.0, values_mm=[1000, 2200, 1000])
    chains = _resolve(_bytes(page))
    assert len(chains) == 1
    assert chains[0].orientation == "horizontal"
    assert [s.value_m for s in chains[0].segments] == [1.0, 2.2, 1.0]


def test_vertical_chain_orientation():
    page = _new_page()
    _draw_frame(page)
    _draw_continuous_vertical_chain(page, x=100.0, y_start=100.0, values_mm=[1000, 2200, 1000])
    chains = _resolve(_bytes(page))
    assert len(chains) == 1
    assert chains[0].orientation == "vertical"


def test_chain_without_overall_is_ordered_uncorroborated():
    page = _new_page()
    _draw_frame(page)
    _draw_continuous_vertical_chain(page, x=100.0, y_start=100.0, values_mm=[2200, 3000])
    chains = _resolve(_bytes(page))
    assert len(chains) == 1
    ch = chains[0]
    assert ch.status == ChainCorroborationStatus.ORDERED_UNCORROBORATED.value
    assert ch.overall_value_m is None
    # Uncorroborated chains must not expose segment values via the
    # convenience accessor -- callers needing them must read `segments`
    # directly and treat them as diagnostic only.
    assert ch.value_at_ordinal(0) is None


def test_translated_chain_same_result():
    values = [2200, 3000, 1500]
    page_a = _new_page()
    _draw_frame(page_a)
    _draw_continuous_vertical_chain(page_a, x=100.0, y_start=100.0, values_mm=values)
    _draw_overall(page_a, x=70.0, y0=100.0, y1=100.0 + 40.0 * 3, value_mm=sum(values))
    chains_a = _resolve(_bytes(page_a))

    page_b = _new_page()
    _draw_frame(page_b)
    _draw_continuous_vertical_chain(page_b, x=140.0, y_start=180.0, values_mm=values)
    _draw_overall(page_b, x=110.0, y0=180.0, y1=180.0 + 40.0 * 3, value_mm=sum(values))
    chains_b = _resolve(_bytes(page_b))

    assert len(chains_a) == len(chains_b) == 1
    assert [s.value_m for s in chains_a[0].segments] == [s.value_m for s in chains_b[0].segments]
    assert chains_a[0].status == chains_b[0].status == ChainCorroborationStatus.CORROBORATED_BY_OVERALL.value


def test_scaled_chain_same_result():
    """A chain drawn at a different pixel-per-segment spacing (a different
    drawing scale) resolves identically -- the authority never depends on
    absolute pixel spacing, only on relative ordering/topology."""
    values = [2200, 3000, 1500]
    page_a = _new_page()
    _draw_frame(page_a)
    _draw_continuous_vertical_chain(page_a, x=100.0, y_start=100.0, values_mm=values, px_per_segment=40.0)
    _draw_overall(page_a, x=70.0, y0=100.0, y1=100.0 + 40.0 * 3, value_mm=sum(values))
    chains_a = _resolve(_bytes(page_a))

    page_b = _new_page()
    _draw_frame(page_b)
    _draw_continuous_vertical_chain(page_b, x=100.0, y_start=100.0, values_mm=values, px_per_segment=60.0)
    _draw_overall(page_b, x=70.0, y0=100.0, y1=100.0 + 60.0 * 3, value_mm=sum(values))
    chains_b = _resolve(_bytes(page_b))

    assert len(chains_a) == len(chains_b) == 1
    assert chains_a[0].status == chains_b[0].status == ChainCorroborationStatus.CORROBORATED_BY_OVERALL.value


def test_unrelated_nearby_numeric_text_excluded():
    """A grid label and a scale notation near the chain must never be
    absorbed into it -- typed-token classification rejects them upstream,
    and this proves the chain authority doesn't independently re-admit
    them."""
    page = _new_page()
    _draw_frame(page)
    _draw_continuous_vertical_chain(page, x=100.0, y_start=100.0, values_mm=[2200, 3000])
    _draw_overall(page, x=70.0, y0=100.0, y1=180.0, value_mm=5200)
    page.insert_text((100.0, 220.0), "GRID A", fontsize=9)
    page.insert_text((100.0, 240.0), "1:100", fontsize=9)
    chains = _resolve(_bytes(page))
    assert len(chains) == 1
    assert chains[0].segment_count == 2


def test_two_parallel_chains_resolved_independently():
    page = _new_page()
    _draw_frame(page, rect=(20.0, 20.0, 600.0, 480.0))
    _draw_continuous_vertical_chain(page, x=100.0, y_start=60.0, values_mm=[2200, 3000])
    _draw_overall(page, x=70.0, y0=60.0, y1=140.0, value_mm=5200)
    _draw_continuous_vertical_chain(page, x=400.0, y_start=60.0, values_mm=[1000, 1000, 1000])
    _draw_overall(page, x=370.0, y0=60.0, y1=180.0, value_mm=3000)
    chains = _resolve(_bytes(page))
    assert len(chains) == 2
    counts = sorted(ch.segment_count for ch in chains)
    assert counts == [2, 3]
    for ch in chains:
        assert ch.status == ChainCorroborationStatus.CORROBORATED_BY_OVERALL.value


def test_crossing_chains_not_merged():
    """A horizontal chain and a vertical chain crossing near the same
    region never merge into one chain."""
    page = _new_page()
    _draw_frame(page)
    _draw_continuous_vertical_chain(page, x=150.0, y_start=100.0, values_mm=[2200, 3000])
    _draw_continuous_horizontal_chain(page, y=300.0, x_start=250.0, values_mm=[1000, 1000])
    chains = _resolve(_bytes(page))
    orientations = sorted(ch.orientation for ch in chains)
    assert orientations == ["horizontal", "vertical"]


def test_zero_witness_anchor_chain_is_not_returned():
    """Text-only figures with no drawn dimension-line/witness geometry at
    all must never become a chain, no matter how tidy their layout looks."""
    page = _new_page()
    _draw_frame(page)
    for i, val in enumerate([200, 6100, 200, 1500, 200]):
        page.insert_text((100.0, 100.0 + i * 20.0), str(val), fontsize=9, rotate=90)
    chains = _resolve(_bytes(page))
    assert chains == []


def test_duplicate_dimension_text_elsewhere_does_not_corrupt_chain():
    page = _new_page()
    _draw_frame(page, rect=(20.0, 20.0, 600.0, 480.0))
    _draw_continuous_vertical_chain(page, x=100.0, y_start=60.0, values_mm=[2200, 3000])
    _draw_overall(page, x=70.0, y0=60.0, y1=140.0, value_mm=5200)
    # An unrelated duplicate "2200" far away in the same viewport, on its
    # own unconnected axis column -- must not be pulled into the chain.
    page.insert_text((400.0, 400.0), "2200", fontsize=9)
    chains = _resolve(_bytes(page))
    assert len(chains) == 1
    assert chains[0].segment_count == 2


def test_conflicting_overall_dimension_yields_conflict():
    page = _new_page()
    _draw_frame(page)
    _draw_continuous_vertical_chain(page, x=100.0, y_start=100.0, values_mm=[2200, 3000])
    # A positionally-plausible "overall" that does NOT match 2200+3000=5200.
    _draw_overall(page, x=70.0, y0=100.0, y1=180.0, value_mm=6000)
    chains = _resolve(_bytes(page))
    assert len(chains) == 1
    assert chains[0].status == ChainCorroborationStatus.CONFLICT.value
    assert chains[0].value_at_ordinal(0) is None


def test_different_viewports_kept_separate():
    page = _new_page()
    _draw_frame(page, rect=(20.0, 20.0, 280.0, 460.0), title="GROUND FLOOR PLAN")
    _draw_continuous_vertical_chain(page, x=80.0, y_start=60.0, values_mm=[2200, 3000])
    _draw_overall(page, x=55.0, y0=60.0, y1=140.0, value_mm=5200)

    _draw_frame(page, rect=(320.0, 20.0, 600.0, 460.0), title="FIRST FLOOR PLAN")
    _draw_continuous_vertical_chain(page, x=380.0, y_start=60.0, values_mm=[1500, 1500])
    _draw_overall(page, x=355.0, y0=60.0, y1=140.0, value_mm=3000)

    chains = _resolve(_bytes(page))
    assert len(chains) == 2
    view_ids = {ch.view_id for ch in chains}
    assert len(view_ids) == 2


def test_same_values_in_unrelated_locations_not_merged():
    """Two identical-looking single dimension figures far apart (different
    viewports) never combine into a fabricated multi-segment chain."""
    page = _new_page()
    _draw_frame(page, rect=(20.0, 20.0, 280.0, 460.0), title="GROUND FLOOR PLAN")
    page.draw_line((80.0, 60.0), (80.0, 100.0))
    page.draw_line((74.0, 60.0), (86.0, 60.0))
    page.draw_line((74.0, 100.0), (86.0, 100.0))
    page.insert_text((88.0, 83.0), "1500", fontsize=9, rotate=90)

    _draw_frame(page, rect=(320.0, 20.0, 600.0, 460.0), title="FIRST FLOOR PLAN")
    page.draw_line((380.0, 300.0), (380.0, 340.0))
    page.draw_line((374.0, 300.0), (386.0, 300.0))
    page.draw_line((374.0, 340.0), (386.0, 340.0))
    page.insert_text((388.0, 323.0), "1500", fontsize=9, rotate=90)

    chains = _resolve(_bytes(page))
    # Each is a single isolated dimension with no chain partner (only one
    # other observation shares its column: none) -- neither forms a
    # >=2-member chain, and they must never be merged with each other.
    assert chains == []


def test_interior_segment_ambiguous_between_two_fragment_candidates():
    """Reproduces the real defect this module exists to fix: a dimension
    line drawn as one fragment per sub-interval (some CAD exporters split
    it at every tick) makes an interior observation's own per-observation
    binding AMBIGUOUS (two equally-near fragment candidates). The chain
    authority must still recover the full ordered chain using topology
    (ordering + a real witness anchor + overall corroboration) rather than
    requiring every interior member to independently win its own tie-break.
    """
    page = _new_page()
    _draw_frame(page)
    values = [2200, 3000, 1500]
    _draw_continuous_vertical_chain(
        page, x=100.0, y_start=100.0, values_mm=values, px_per_segment=40.0, fragmented=True
    )
    _draw_overall(page, x=70.0, y0=100.0, y1=100.0 + 40.0 * 3, value_mm=sum(values))
    chains = _resolve(_bytes(page))
    assert len(chains) == 1
    ch = chains[0]
    assert ch.segment_count == 3
    assert [round(v, 3) for v in (2.2, 3.0, 1.5)] == [round(s.value_m, 3) for s in ch.segments]
