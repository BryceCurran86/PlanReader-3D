"""P1 of the A110 cap regression (MAX item 3): the dark-painted layered ring counts STRUCTURAL primitives.

Synthetic only; no private source. The 20,000-primitive cap of the opt-in dark-painted layered ring bounds the structural wall
hypothesis: wall-support rows (named wall layer, black stroke, near-black fill) and the opaque fills that can hide them. The
doorway/glazing EVIDENCE strokes that ``_source_wall_ink_candidate_drawings`` retains (unfilled, visible, non-green, not wall
support) stay available to the closure searches with their original path indices, but are not counted: they never mint a wall
strip. Green ink is excluded and never counts. Nothing here is a wall, a measurement or a quantity.
"""
from __future__ import annotations

import math
import random

import fitz
import pytest

import pb_layered_wall_doorway_room_ring_shadow as mod
from pb_layered_wall_doorway_room_ring_shadow import (
    KIND_STROKE,
    REASON_UNLABELLED_SOURCE_PRIMITIVE_CAP,
    build_layered_wall_doorway_room_rings,
)
from pb_migration_contracts import EvidenceResolutionStatus

SHA = "ab" * 32
WALL = "Enclosure_WallInternal"
CAP_REASON = "unlabelled_dark_wall_page_exceeds_20000_primitive_cap_needs_bounded_viewport"
GRAY = (0.48, 0.48, 0.48)
GREEN = (0.0, 0.5, 0.0)


def _line_item(x0, y0, x1, y1):
    return ("l", fitz.Point(x0, y0), fitz.Point(x1, y1))


def _strip(x0, y0, x1, y1, layer=WALL):
    """A filled black strip as one closed four-line path (4 native primitives)."""
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    items = [_line_item(*corners[i], *corners[(i + 1) % 4]) for i in range(4)]
    return {"layer": layer, "fill": (0.0, 0.0, 0.0), "items": items}


def _room():
    """Four black walls around a closed 92 x 92 room (16 structural primitives)."""
    return [_strip(0, 0, 100, 4), _strip(0, 4, 4, 96), _strip(96, 4, 100, 96), _strip(0, 96, 100, 100)]


def _black_stroke(items_per_row=1):
    return {"layer": "", "fill": None, "color": (0.0, 0.0, 0.0),
            "items": [_line_item(1, 1, 7, 1)] * items_per_row}


def _opaque_white():
    return {"layer": "", "fill": (1.0, 1.0, 1.0), "color": None, "items": [_line_item(0, 0, 5, 0)]}


def _evidence_rows(count, *, items_per_row=1, x0=1000.0, y0=1000.0, color=GRAY, layer="Notes"):
    """Mid-gray unfilled strokes far from the room: doorway/glazing evidence, never wall."""
    rows = []
    for i in range(count):
        x, y = x0 + (i % 200) * 3.0, y0 + (i // 200) * 3.0
        rows.append({"layer": layer, "fill": None, "color": color,
                     "items": [_line_item(x, y, x + 1.0, y)] * items_per_row})
    return rows


def _green_rows(count):
    return [{"layer": "", "fill": None, "color": GREEN, "items": [_line_item(2000, 2000, 2003, 2000)]}
            for _ in range(count)]


def _build(rows, **kw):
    return build_layered_wall_doorway_room_rings(
        rows, source_sha256=SHA, page_index=0, dark_painted_wall_source=True, **kw,
    )


def _candidates(result):
    return [r for r in result.rings if r.status is EvidenceResolutionStatus.CANDIDATE]


class _PastCap(Exception):
    """Raised by a spy that replaces the first collector after the cap check."""


# ---------------------------------------------------------------- the count itself


def test_count_is_wall_support_plus_opaque_fill_primitives_only():
    rows = [
        _black_stroke(items_per_row=2), _black_stroke(items_per_row=2), _black_stroke(items_per_row=2),  # 6 support
        _opaque_white(), _opaque_white(),                                                               # 2 opaque
        *_evidence_rows(5),                                                                             # evidence
        *_green_rows(4),                                                                                # green
        {"layer": "", "fill": (0.6, 0.3, 0.3), "fill_opacity": 0.5, "color": None, "items": [_line_item(0, 0, 1, 0)]},  # translucent, not dark
        {"layer": "", "fill": None, "color": (0.0, 0.0, 0.0), "stroke_opacity": 0.0, "items": [_line_item(0, 0, 1, 0)]},  # invisible stroke
        None, 7,                                                                                        # not rows
    ]
    assert mod.structural_native_primitive_count(rows) == 8


@pytest.mark.parametrize(
    "structural,evidence,abstains",
    [(20_000, 0, False), (20_001, 0, True), (20_000, 50_000, False), (20_001, 50_000, True), (0, 60_000, False)],
)
def test_cap_boundary_counts_structural_primitives_and_never_evidence(monkeypatch, structural, evidence, abstains):
    def past_cap(_rows):
        raise _PastCap

    monkeypatch.setattr(mod, "_collect_strips", past_cap)
    rows = [_black_stroke()] * structural + _evidence_rows(evidence)
    if abstains:
        result = _build(rows)
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert result.reason_codes == (CAP_REASON,)
        assert result.rings == () and result.closures == () and result.wall_strip_count == 0
    else:
        with pytest.raises(_PastCap):
            _build(rows)


def test_cap_boundary_with_compound_rows_opaque_fills_and_evidence(monkeypatch):
    def past_cap(_rows):
        raise _PastCap

    monkeypatch.setattr(mod, "_collect_strips", past_cap)
    # 6,666 three-item strokes + 1 two-item stroke + 0 opaque = 20,000 structural primitives; evidence rows are compound too.
    compound = [_black_stroke(items_per_row=3)] * 6_666 + [_black_stroke(items_per_row=2)]
    with pytest.raises(_PastCap):
        _build(compound + _evidence_rows(9_000, items_per_row=3))
    # One more opaque fill makes it 20,001: abstain even though the PDF path count is far below 20,000.
    assert len(compound) + 1 < 20_000
    result = _build(compound + [_opaque_white()] + _evidence_rows(9_000, items_per_row=3))
    assert result.reason_codes == (CAP_REASON,)


def test_opaque_fills_keep_counting_as_they_did_before_evidence_was_retained():
    rows = [_opaque_white()] * 20_001
    result = _build(rows)
    assert result.status is EvidenceResolutionStatus.ABSTAINED and result.reason_codes == (CAP_REASON,)
    assert mod.structural_native_primitive_count(rows) == 20_001


def test_green_ink_never_counts_and_never_enters():
    rows = _room() + _green_rows(25_000)
    assert mod.structural_native_primitive_count(rows) == 16
    result = _build(rows)
    assert result.reason_codes != (CAP_REASON,)
    assert len(_candidates(result)) == 1
    assert result.rings[0].bbox_pdf_pts == (4, 4, 96, 96)


# ---------------------------------------------------------------- evidence coexists with an in-budget wall set


def test_evidence_beyond_the_cap_value_coexists_with_an_in_budget_wall_set_and_keeps_original_path_indices():
    evidence = _evidence_rows(25_000)
    rows = evidence + _room()
    assert sum(len(r["items"]) for r in rows) > 20_000  # the pre-change cap counted all of this and abstained
    result = _build(rows)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.reason_codes != (CAP_REASON,)
    ring = _candidates(result)
    assert len(ring) == 1 and ring[0].bbox_pdf_pts == (4, 4, 96, 96)
    # Evidence rows came first, so every wall path index is shifted by exactly their count: indices were never renumbered.
    assert set(ring[0].bounding_wall_path_indices) == {25_000, 25_001, 25_002, 25_003}
    assert all(not r.metric_area_issued and not r.commercial_projection_allowed for r in result.rings)


def test_over_budget_structural_set_still_abstains_with_evidence_present():
    rows = _evidence_rows(5_000) + [_black_stroke()] * 20_001
    result = _build(rows)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (CAP_REASON,)
    assert result.rings == () and result.closures == ()
    assert (result.wall_strip_count, result.wall_gap_count, result.unresolved_gap_count) == (0, 0, 0)


def test_mid_gray_glazing_evidence_still_closes_a_host_window_gap_with_the_evidence_flood_present():
    """The Acacia glazing fixture (3ce1d9b18) with more than 20,000 unrelated evidence strokes added."""
    rows = [_strip(0, 0, 100, 2), _strip(0, 2, 2, 98), _strip(98, 2, 100, 98), _strip(0, 98, 30, 100), _strip(60, 98, 100, 100)]
    glazing = {"layer": "Window_Glazing", "fill": None, "color": (0.48, 0.48, 0.48), "items": [_line_item(30, 98, 60, 98)]}
    alone = _build(rows + [glazing])
    flooded = _build(_evidence_rows(20_001) + rows + [glazing])
    assert alone.unresolved_gap_count == 0 and KIND_STROKE in {c.kind for c in alone.closures}
    assert flooded.reason_codes != (CAP_REASON,)
    assert flooded.unresolved_gap_count == 0
    assert KIND_STROKE in {c.kind for c in flooded.closures}
    assert len(_candidates(flooded)) == len(_candidates(alone)) == 1
    assert flooded.closures[0].gap_interval == alone.closures[0].gap_interval
    # Without the glazing stroke the same wall set stays open: the evidence, not the flood, closes the gap.
    assert _build(_evidence_rows(20_001) + rows).unresolved_gap_count >= 1


def test_default_off_path_has_no_cap_and_ignores_the_roles():
    rows = [_black_stroke()] * 25_000
    result = build_layered_wall_doorway_room_rings(rows, source_sha256=SHA, page_index=0)
    assert result.reason_codes != (CAP_REASON,)


def test_cap_reason_code_is_unchanged():
    assert REASON_UNLABELLED_SOURCE_PRIMITIVE_CAP == CAP_REASON


# ---------------------------------------------------------------- the selector is unchanged (differential oracle)


def _reference_selector(drawings):
    """The selector exactly as it was before P1 (current main 33eba1c61), used as an oracle."""
    blank = {"layer": "", "fill": None, "color": None, "items": ()}
    kept, supported, green_excluded = [], 0, 0
    for row in drawings:
        if not isinstance(row, dict):
            kept.append(blank)
            continue
        fill, stroke = row.get("fill"), row.get("color")
        if mod._owner_excluded_green_ink(fill) or mod._owner_excluded_green_ink(stroke):
            kept.append(blank)
            green_excluded += 1
            continue
        if mod._is_source_wall_support_row(row):
            supported += 1
            kept.append(row)
        elif row.get("fill") is not None and mod._opaque(row):
            kept.append(row)
        elif fill is None and row.get("items") and mod._visible_source_stroke_paint(row):
            kept.append(row)
        else:
            kept.append(blank)
    return tuple(kept), supported, green_excluded


_PAINTS = [None, (0.0, 0.0, 0.0), (0.04, 0.04, 0.04), (0.195, 0.195, 0.195), (0.25, 0.25, 0.25), GRAY, (0.7, 0.7, 0.7),
           (1.0, 1.0, 1.0), (0.8, 0.1, 0.1), GREEN, (0.465088, 0.730469, 0.465088), (0.589844, 0.792969, 0.589844)]
_LAYERS = ["", WALL, "A-WALL", "Window_Glazing", "Notes"]
_OPACITIES = [None, 1.0, 0.5, 0.0, float("nan"), True, "1"]


def _fuzz_rows(seed, count=600):
    rng = random.Random(seed)
    rows = []
    for _ in range(count):
        kind = rng.random()
        if kind < 0.03:
            rows.append(rng.choice([None, 7, "row", ()]))
            continue
        row = {"layer": rng.choice(_LAYERS), "fill": rng.choice(_PAINTS), "color": rng.choice(_PAINTS)}
        if rng.random() < 0.4:
            row["fill_opacity"] = rng.choice(_OPACITIES)
        if rng.random() < 0.4:
            row["stroke_opacity"] = rng.choice(_OPACITIES)
        row["items"] = [_line_item(rng.uniform(0, 500), rng.uniform(0, 500), rng.uniform(0, 500), rng.uniform(0, 500))
                        for _ in range(rng.choice([0, 1, 1, 2, 3]))]
        rows.append(row)
    return rows


@pytest.mark.parametrize("seed", range(8))
def test_selector_output_is_identical_to_the_pre_change_selector(seed):
    rows = _fuzz_rows(seed)
    kept, supported, green = mod._source_wall_ink_candidate_drawings(rows)
    ref_kept, ref_supported, ref_green = _reference_selector(rows)
    assert (supported, green) == (ref_supported, ref_green)
    assert len(kept) == len(rows) == len(ref_kept)
    for index, (new, old) in enumerate(zip(kept, ref_kept)):
        assert new is old or new == old, index


@pytest.mark.parametrize("seed", range(8))
def test_every_row_has_exactly_one_role_consistent_with_the_selector(seed):
    rows = _fuzz_rows(seed)
    roles = [mod._source_wall_ink_role(r) for r in rows]
    assert set(roles) <= {"green", "wall_support", "opaque_fill", "evidence", "blank"}
    kept, supported, green = mod._source_wall_ink_candidate_drawings(rows)
    assert roles.count("wall_support") == supported
    assert roles.count("green") == green
    for role, row, out in zip(roles, rows, kept):
        if role in ("wall_support", "opaque_fill", "evidence"):
            assert out is row
        else:
            assert out == {"layer": "", "fill": None, "color": None, "items": ()}


@pytest.mark.parametrize("seed", range(8))
def test_count_matches_an_independent_statement_of_the_rule(seed):
    rows = _fuzz_rows(seed)
    expected = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if mod._owner_excluded_green_ink(row.get("fill")) or mod._owner_excluded_green_ink(row.get("color")):
            continue
        if mod._is_source_wall_support_row(row) or (row.get("fill") is not None and mod._opaque(row)):
            expected += len(row.get("items", ()))
    assert mod.structural_native_primitive_count(rows) == expected


@pytest.mark.parametrize("seed", range(8))
def test_count_is_idempotent_over_the_selector_order_invariant_and_translation_invariant(seed):
    rows = _fuzz_rows(seed)
    count = mod.structural_native_primitive_count(rows)
    assert mod.structural_native_primitive_count(mod._source_wall_ink_candidate_drawings(rows)[0]) == count
    shuffled = list(rows)
    random.Random(seed + 100).shuffle(shuffled)
    assert mod.structural_native_primitive_count(shuffled) == count
    moved = []
    for row in rows:
        if isinstance(row, dict):
            row = dict(row, items=[("l", fitz.Point(a.x + 123.5, a.y - 77.25), fitz.Point(b.x + 123.5, b.y - 77.25))
                                   for (_k, a, b) in row["items"]])
        moved.append(row)
    assert mod.structural_native_primitive_count(moved) == count
    # Evidence never changes the count: dropping every evidence row leaves it identical.
    without = [r for r in rows if mod._source_wall_ink_role(r) != "evidence"]
    assert mod.structural_native_primitive_count(without) == count


def test_count_never_mutates_its_input():
    rows = _fuzz_rows(3)
    before = [dict(r) if isinstance(r, dict) else r for r in rows]
    mod.structural_native_primitive_count(rows)
    mod._source_wall_ink_candidate_drawings(rows)
    assert all((a == b) if not isinstance(a, dict) or not any(isinstance(v, float) and math.isnan(v) for v in a.values())
               else True for a, b in zip(rows, before))
    assert len(rows) == len(before)
