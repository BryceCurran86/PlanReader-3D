"""P2b: the preview builder's entry cap bounds the wall-candidate set, not the doorway/glazing evidence strokes.

Synthetic only; no private source. ``pb_next_wall_ring_preview.build_layered_wall_doorway_room_rings`` counted EVERY native item of
the rows inside the viewport union against 20,000. Since 3ce1d9b18 the source-wall selector also retains the doorway/glazing
EVIDENCE strokes (unfilled, visible, non-green, not wall support). The stroke-pair collector cannot use those unless their stroke
colour is a wall-stroke colour (``None`` or neutral dark), so a page carrying many mid-grey evidence strokes crossed the limit and
tiled or abstained with its walls well inside budget. The entry count now skips exactly the evidence-only rows; every row stays in
the clipped rows with its original path index and stays available to every closure search. Same 20,000, same reason code. The halo
functions (they bound a local neighbourhood for other callers) keep counting every item.
"""
from __future__ import annotations

import copy
import random

import fitz
import pytest

import pb_layered_wall_doorway_room_ring_shadow as layered
import pb_next_wall_ring_preview as nxt
from pb_migration_contracts import EvidenceResolutionStatus
from pb_next_wall_ring_preview import (
    REASON_PRIMITIVE_CAP,
    _entry_primitive_count,
    _selected_primitive_count,
    build_layered_wall_doorway_room_rings,
)

SHA = "ab" * 32
WALL = "Enclosure_WallInternal"
GRAY = (0.48, 0.48, 0.48)         # mid-grey: evidence, and not a colour the pair collector can use
DARK_GRAY = (0.10, 0.10, 0.10)    # neutral dark but not black: evidence by role, a colour the pair collector DOES use
RED = (0.8, 0.1, 0.1)
EVERYTHING = (-1e6, -1e6, 1e6, 1e6)


def _line(x0, y0, x1, y1):
    return ("l", fitz.Point(x0, y0), fitz.Point(x1, y1))


def _strip(x0, y0, x1, y1, layer=WALL):
    """A filled black wall strip as one closed four-line path (4 native items)."""
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return {"layer": layer, "fill": (0.0, 0.0, 0.0), "color": None,
            "items": [_line(*corners[i], *corners[(i + 1) % 4]) for i in range(4)]}


def _room(dx=0.0, dy=0.0):
    """Four black walls around a closed room (16 native items)."""
    return [_strip(dx, dy, dx + 100, dy + 4), _strip(dx, dy + 4, dx + 4, dy + 96),
            _strip(dx + 96, dy + 4, dx + 100, dy + 96), _strip(dx, dy + 96, dx + 100, dy + 100)]


def _black_stroke(items_per_row=1):
    return {"layer": "", "fill": None, "color": (0.0, 0.0, 0.0), "items": [_line(1, 1, 7, 1)] * items_per_row}


def _opaque_white():
    return {"layer": "", "fill": (1.0, 1.0, 1.0), "color": None, "items": [_line(0, 0, 5, 0)]}


def _evidence_rows(count, *, items_per_row=1, x0=1000.0, y0=1000.0, color=GRAY, layer="Notes"):
    """Unfilled visible strokes far from the room: doorway/glazing evidence."""
    rows = []
    for i in range(count):
        x, y = x0 + (i % 200) * 3.0, y0 + (i // 200) * 3.0
        rows.append({"layer": layer, "fill": None, "color": color, "items": [_line(x, y, x + 1.0, y)] * items_per_row})
    return rows


def _build(rows, **kw):
    return build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0, **kw)


def _candidates(result):
    return [r for r in result.rings if r.status is EvidenceResolutionStatus.CANDIDATE]


class _PastCap(Exception):
    """Raised by a spy that replaces the first collector after the entry cap checks."""


def _past_cap(_rows):
    raise _PastCap


# The three entry checks of the builder: the stroke-pair viewport branch, the plain branch, and the strict baseline.
def _run_plain(rows):
    return _build(rows)


def _run_viewport(rows):
    return _build(rows, stroke_pair_wall_faces=True, viewport_pdf_pts=EVERYTHING)


def _run_baseline(rows):
    inert = {"layer": "", "fill": None, "color": None, "items": ()}
    return _build([inert] * len(rows), stroke_pair_wall_faces=True, source_pair_baseline_drawings=rows)


ENTRY_CHECKS = [pytest.param(_run_plain, id="plain"), pytest.param(_run_viewport, id="viewport"), pytest.param(_run_baseline, id="baseline")]


# ---------------------------------------------------------------- the count itself

def test_entry_count_skips_exactly_the_evidence_only_rows():
    rows = [
        _black_stroke(items_per_row=2), _black_stroke(items_per_row=2),            # 4: wall support (black stroke)
        _opaque_white(),                                                          # 1: opaque fill
        _strip(0, 0, 10, 4),                                                      # 4: filled wall strip
        *_evidence_rows(3, color=DARK_GRAY),                                      # 3: evidence the pair collector CAN use
        *_evidence_rows(3, color=None),                                           # 3: default CAD stroke, also usable
        *_evidence_rows(5, color=GRAY),                                           # 0: evidence only
        *_evidence_rows(7, color=RED),                                            # 0: evidence only
        {"layer": "", "fill": None, "color": (0.0, 0.5, 0.0), "items": [_line(0, 0, 1, 0)]},   # 1: green is not evidence-only here
        {"layer": "", "fill": (0.6, 0.3, 0.3), "fill_opacity": 0.5, "color": None, "items": [_line(0, 0, 1, 0)]},  # 1: translucent fill
        {"layer": "", "fill": None, "color": GRAY, "stroke_opacity": 0.0, "items": [_line(0, 0, 1, 0)]},           # 1: invisible stroke
        {"layer": "", "fill": None, "color": GRAY, "items": ()},                  # 0: no items
        None,                                                                     # 0: not a row
    ]
    assert _entry_primitive_count(rows) == 4 + 1 + 4 + 3 + 3 + 1 + 1 + 1


def test_entry_count_stops_as_soon_as_it_passes_the_limit():
    rows = [_black_stroke(items_per_row=3)] * 10_000
    assert _entry_primitive_count(rows) == 20_001


def test_the_halo_count_and_its_callers_still_count_every_item():
    rows = _evidence_rows(20_001)
    assert _selected_primitive_count(rows) == 20_001                      # unchanged: every item
    assert _entry_primitive_count(rows) == 0                              # the entry count skips evidence-only rows
    assert nxt._clip_if_under_cap(rows, EVERYTHING) is None               # a halo is still refused above 20,000 items
    assert nxt._clip_if_under_cap(rows[:20_000], EVERYTHING) is not None


@pytest.mark.parametrize("seed", range(8))
def test_entry_count_equals_the_old_count_on_inputs_without_evidence_only_rows(seed):
    rng = random.Random(seed)
    makers = [
        lambda: _black_stroke(rng.randint(1, 3)),
        lambda: _opaque_white(),
        lambda: _strip(0, 0, 10, 4),
        lambda: _evidence_rows(1, color=DARK_GRAY)[0],
        lambda: _evidence_rows(1, color=None)[0],
        lambda: {"layer": "", "fill": None, "color": (0.0, 0.5, 0.0), "items": [_line(0, 0, 1, 0)]},
        lambda: {"layer": "", "fill": None, "color": GRAY, "items": ()},
    ]
    rows = [rng.choice(makers)() for _ in range(400)]
    assert _entry_primitive_count(rows) == _selected_primitive_count(rows)


@pytest.mark.parametrize("seed", range(8))
def test_entry_count_is_the_old_count_minus_the_evidence_only_items(seed):
    rng = random.Random(100 + seed)
    kept = [lambda: _black_stroke(rng.randint(1, 3)), lambda: _opaque_white(), lambda: _evidence_rows(1, color=DARK_GRAY, items_per_row=2)[0]]
    skipped = [lambda: _evidence_rows(1, color=GRAY, items_per_row=rng.randint(1, 3))[0],
               lambda: _evidence_rows(1, color=RED, items_per_row=rng.randint(1, 3))[0]]
    rows, expected = [], 0
    for _ in range(500):
        make = rng.choice(kept + skipped)
        row = make()
        rows.append(row)
        expected += len(row["items"]) if make in kept else 0
    assert _entry_primitive_count(rows) == expected
    assert _selected_primitive_count(rows) == sum(len(r["items"]) for r in rows)


# ---------------------------------------------------------------- the three entry checks of the builder

@pytest.mark.parametrize("run", ENTRY_CHECKS)
@pytest.mark.parametrize(
    "consumable,evidence,abstains",
    [(20_000, 0, False), (20_001, 0, True), (20_000, 50_000, False), (20_001, 50_000, True), (0, 60_000, False)],
)
def test_the_limit_applies_to_consumable_primitives_and_never_to_evidence_only_rows(monkeypatch, run, consumable, evidence, abstains):
    monkeypatch.setattr(nxt, "_collect_strips", _past_cap)
    rows = [_black_stroke()] * consumable + _evidence_rows(evidence)
    if abstains:
        result = run(rows)
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert result.reason_codes == (REASON_PRIMITIVE_CAP,) and REASON_PRIMITIVE_CAP == "page_primitive_cap_exceeded"
        assert result.rings == () and result.closures == () and result.wall_strip_count == 0
    else:
        with pytest.raises(_PastCap):
            run(rows)


@pytest.mark.parametrize("run", ENTRY_CHECKS)
def test_evidence_in_a_wall_stroke_colour_still_counts(monkeypatch, run):
    monkeypatch.setattr(nxt, "_collect_strips", _past_cap)
    for colour in (DARK_GRAY, None):
        assert run(_evidence_rows(20_001, color=colour)).reason_codes == (REASON_PRIMITIVE_CAP,)
        with pytest.raises(_PastCap):
            run(_evidence_rows(20_000, color=colour))
    for colour in (GRAY, RED):
        with pytest.raises(_PastCap):
            run(_evidence_rows(20_001, color=colour))


@pytest.mark.parametrize("run", ENTRY_CHECKS)
def test_opaque_fills_and_compound_rows_keep_counting(monkeypatch, run):
    monkeypatch.setattr(nxt, "_collect_strips", _past_cap)
    assert run([_opaque_white()] * 20_001).reason_codes == (REASON_PRIMITIVE_CAP,)
    compound = [_black_stroke(items_per_row=3)] * 6_666 + [_black_stroke(items_per_row=2)]     # 20,000 items in 6,667 rows
    with pytest.raises(_PastCap):
        run(compound + _evidence_rows(9_000, items_per_row=3))
    assert len(compound) + 1 < 20_000
    assert run(compound + [_opaque_white()] + _evidence_rows(9_000, items_per_row=3)).reason_codes == (REASON_PRIMITIVE_CAP,)


# ---------------------------------------------------------------- what the limit is for

def test_an_evidence_flood_before_an_in_budget_wall_set_still_closes_the_room_with_original_indices():
    flood = 25_000
    rows = _evidence_rows(flood) + _room()
    assert _selected_primitive_count(rows) > 20_000                       # the old count would have abstained
    result = _build(rows)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    (ring,) = _candidates(result)
    assert set(ring.bounding_wall_path_indices) == {flood, flood + 1, flood + 2, flood + 3}   # original indices, not renumbered


def test_a_genuinely_over_budget_wall_set_still_abstains_with_evidence_present():
    rows = _evidence_rows(30_000) + [_black_stroke()] * 20_001 + _room()
    result = _build(rows)
    assert result.status is EvidenceResolutionStatus.ABSTAINED and result.reason_codes == (REASON_PRIMITIVE_CAP,)


def test_one_pass_closes_a_room_that_a_tile_seam_would_cut(monkeypatch):
    """Evidence alone must not push a page into tile mode: a room across the seam of two viewports closes in one pass."""
    calls = []  # the builder's own per-viewport recursion goes through the module name, so only tile builds are recorded
    real = nxt.build_layered_wall_doorway_room_rings

    def spy(*args, **kwargs):
        calls.append(kwargs.get("viewport_pdf_pts"))
        return real(*args, **kwargs)

    monkeypatch.setattr(nxt, "build_layered_wall_doorway_room_rings", spy)
    rows = _room(dx=0.0) + _evidence_rows(25_000, x0=2000.0, y0=2000.0)
    left, right = (-1e6, -1e6, 50.0, 1e6), (50.0, -1e6, 1e6, 1e6)        # the seam at x = 50 cuts the room in two
    result = _build(rows, stroke_pair_wall_faces=True, viewport_pdf_pts=[left, right])
    assert calls == [], "one pass over the union of the viewports: no per-viewport build"
    assert result.status is EvidenceResolutionStatus.CANDIDATE and len(_candidates(result)) == 1


def test_a_viewport_union_over_budget_by_wall_primitives_still_tiles(monkeypatch):
    calls = []
    real = nxt.build_layered_wall_doorway_room_rings

    def spy(*args, **kwargs):
        calls.append(kwargs.get("viewport_pdf_pts"))
        return real(*args, **kwargs)

    monkeypatch.setattr(nxt, "build_layered_wall_doorway_room_rings", spy)
    monkeypatch.setattr(nxt, "_collect_strips", lambda rows: ([], []))
    left, right = (-1e6, -1e6, 50.0, 1e6), (50.0, -1e6, 1e6, 1e6)
    rows = [_black_stroke()] * 10_001 + [dict(_black_stroke(), items=[_line(900, 1, 907, 1)]) for _ in range(10_001)]
    _build(rows, stroke_pair_wall_faces=True, viewport_pdf_pts=[left, right])
    assert calls == [left, right], "the union is over budget, so each viewport is built on its own"


# ---------------------------------------------------------------- invariances

def _signature(result):
    return (result.status, result.reason_codes, result.wall_strip_count, result.wall_gap_count, len(result.rings), len(result.closures),
            tuple(sorted(r.bounding_wall_path_indices for r in result.rings)))


def test_translation_unrelated_content_and_viewport_expansion_do_not_change_the_result():
    base = _build(_evidence_rows(25_000) + _room())
    moved = _build(_evidence_rows(25_000, x0=1500.0, y0=-900.0) + _room(dx=37.0, dy=-21.0))
    more = _build(_evidence_rows(25_000) + _room() + _evidence_rows(15_000, x0=3000.0, y0=3000.0))   # unrelated ink after the room
    assert base.status is EvidenceResolutionStatus.CANDIDATE
    assert _signature(base) == _signature(moved) == _signature(more)
    small = _build(_evidence_rows(25_000) + _room(), stroke_pair_wall_faces=True, viewport_pdf_pts=(-10.0, -10.0, 120.0, 120.0))
    large = _build(_evidence_rows(25_000) + _room(), stroke_pair_wall_faces=True, viewport_pdf_pts=EVERYTHING)
    assert _signature(small) == _signature(large)


def test_building_never_mutates_the_rows_and_replays_deterministically():
    rows = _evidence_rows(25_000) + _room()
    before = copy.deepcopy(rows)
    first, second = _build(rows), _build(rows)
    assert rows == before
    assert _signature(first) == _signature(second)
    assert [r.record_id for r in first.rings] == [r.record_id for r in second.rings]


def test_the_role_vocabulary_is_the_layered_modules():
    # one definition of "evidence": the builder reuses the layered module's role function and constant, it does not restate them
    assert nxt._original_source_wall_ink_role is layered._source_wall_ink_role
    assert nxt._ORIGINAL_ROLE_EVIDENCE == layered._ROLE_EVIDENCE == "evidence"
