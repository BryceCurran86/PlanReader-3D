"""Block-style scale bar shadow: a bar is accepted only on equally spaced numerals with a unit AND block edges under them."""
from __future__ import annotations

import copy
import random

import pytest

import pb_scale_block_bar_shadow as bar
from pb_scale_block_bar_shadow import MM_PER_POINT_AT_1_TO_1, detect_block_scale_bars

STEP_PT = 10 / MM_PER_POINT_AT_1_TO_1          # one metre at 1:100, in points (28.3465)


def word(ident, text, cx, cy, w=8.0, h=6.0):
    return {"id": ident, "text": text, "bbox": [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]}


def edge(ident, x, y_lo, y_hi):
    return {"id": ident, "x1": x, "y1": y_lo, "x2": x, "y2": y_hi}


def horizontal_bar(x0=870.75, y_labels=760.0, n=10, step=STEP_PT, unit="m", with_edges=True, edge_ids="e"):
    words = []
    segs = []
    for k in range(n + 1):
        text = str(k) if k < n else f"{k}{unit}"
        words.append(word(f"w{k}", text, x0 + k * step, y_labels))
        if with_edges:
            segs.append(edge(f"{edge_ids}{k}", x0 + k * step, y_labels - 12.0, y_labels - 6.0))
    return segs, words


def vertical_bar(y0=870.75, x_labels=760.0, n=10, step=STEP_PT, unit="m"):
    segs, words = [], []
    for k in range(n + 1):
        text = str(k) if k < n else f"{k}{unit}"
        words.append(word(f"w{k}", text, x_labels, y0 + k * step))
        segs.append({"id": f"e{k}", "x1": x_labels - 12.0, "y1": y0 + k * step, "x2": x_labels - 6.0, "y2": y0 + k * step})
    return segs, words


# ---------------------------------------------------------------- positives
def test_a_horizontal_block_bar_is_measured_with_residuals():
    segs, words = horizontal_bar()
    report = detect_block_scale_bars(segs, words)
    assert len(report.candidates) == 1
    c = report.candidates[0]
    assert c.axis == "x" and c.label_texts[0] == "0" and c.label_texts[-1] == "10m"
    assert c.physical_span_mm == 10000.0
    assert c.points_per_mm == pytest.approx(1.0 / (MM_PER_POINT_AT_1_TO_1 * 100.0), rel=1e-6)
    assert c.span_pt == pytest.approx(10 * STEP_PT, rel=1e-6)
    assert c.label_residual_pt < 0.01 and c.edge_residual_pt < 0.01 and c.matched_edge_count == 11
    assert report.shadow_only is True and report.scale_authority_granted is False


def test_a_vertical_bar_on_a_rotated_sheet_is_found_in_the_native_frame():
    segs, words = vertical_bar()
    c = detect_block_scale_bars(segs, words).candidates[0]
    assert c.axis == "y" and c.physical_span_mm == 10000.0
    assert c.points_per_mm == pytest.approx(1.0 / (MM_PER_POINT_AT_1_TO_1 * 100.0), rel=1e-6)


def test_a_printed_ratio_corroborates_or_contradicts_but_never_creates_the_scale():
    segs, words = horizontal_bar()
    near = detect_block_scale_bars(segs, words + [word("r", "1:100", 600.0, 790.0, w=24.0)]).candidates[0]
    assert near.printed_ratio_candidates == (100.0,) and near.printed_ratio_relative_difference[0] < 1e-4
    far = detect_block_scale_bars(segs, words + [word("r", "1:50", 600.0, 790.0, w=24.0)]).candidates[0]
    assert far.printed_ratio_candidates == (50.0,) and far.printed_ratio_relative_difference[0] == pytest.approx(0.5, abs=1e-3)
    none = detect_block_scale_bars(segs, words).candidates[0]
    assert none.printed_ratio_candidates == ()                  # no ratio on the sheet: the bar still stands alone


def test_a_bar_in_centimetres_and_a_step_of_five_metres_are_measured_in_their_own_units():
    segs, words = horizontal_bar(n=4, step=40.0, unit="cm")     # 0 1 2 3 4cm, 40 pt per centimetre
    c = detect_block_scale_bars(segs, words).candidates[0]
    assert c.physical_span_mm == 40.0 and c.points_per_mm == pytest.approx(4.0, rel=1e-6)
    words5 = []
    segs5 = []
    for k, text in enumerate(["0", "5", "10", "15", "20m"]):
        words5.append(word(f"w{k}", text, 100 + k * 56.69, 500.0))
        segs5.append(edge(f"e{k}", 100 + k * 56.69, 488.0, 494.0))
    c5 = detect_block_scale_bars(segs5, words5).candidates[0]
    assert c5.physical_span_mm == 20000.0 and c5.points_per_mm == pytest.approx(56.69 / 5000.0, rel=1e-5)


# ---------------------------------------------------------------- look-alike negatives
def test_numerals_without_block_edges_are_not_a_bar():
    segs, words = horizontal_bar(with_edges=False)
    assert detect_block_scale_bars(segs, words).candidates == ()


def test_only_a_few_edges_under_many_labels_is_not_a_bar():
    segs, words = horizontal_bar()
    assert detect_block_scale_bars(segs[:3], words).candidates == ()


def test_numerals_without_a_unit_or_with_conflicting_units_are_not_a_bar():
    segs, words = horizontal_bar()
    no_unit = [dict(w, text=w["text"].rstrip("m")) for w in words]
    assert detect_block_scale_bars(segs, no_unit).candidates == ()
    conflict = [dict(w) for w in words]
    conflict[3]["text"] = "3cm"
    assert detect_block_scale_bars(segs, conflict).candidates == ()


def test_a_row_that_does_not_start_at_zero_or_has_unequal_spacing_is_not_a_bar():
    segs, words = horizontal_bar()
    shifted = [dict(w, text=str(int(w["text"].rstrip("m")) + 1) + ("m" if w["text"].endswith("m") else "")) for w in words]
    assert detect_block_scale_bars(segs, shifted).candidates == ()
    uneven = copy.deepcopy(words)
    for i in range(2, 11):
        uneven[i]["bbox"] = [v + (4.0 if j % 2 == 0 else 0.0) for j, v in enumerate(uneven[i]["bbox"])]
    segs_u = [dict(s) for s in segs]
    result = detect_block_scale_bars(segs_u, uneven)
    assert all(c.label_texts[-1] != "10m" for c in result.candidates)


def test_a_dimension_string_of_ticks_and_figures_is_not_a_bar():
    # figured dimensions between extension lines: not an arithmetic progression from zero
    words = [word(f"d{k}", text, 100 + 60 * k, 300.0) for k, text in enumerate(["3640", "90", "3560", "220", "4200"])]
    segs = [edge(f"x{k}", 70 + 60 * k, 290.0, 297.0) for k in range(6)]
    assert detect_block_scale_bars(segs, words).candidates == ()


# ---------------------------------------------------------------- invariance and bounds
def test_input_order_translation_and_determinism():
    segs, words = horizontal_bar()
    base = detect_block_scale_bars(segs, words)
    shuffled_s, shuffled_w = list(segs), list(words)
    rng = random.Random(11)
    rng.shuffle(shuffled_s)
    rng.shuffle(shuffled_w)
    assert detect_block_scale_bars(shuffled_s, shuffled_w) == base
    assert detect_block_scale_bars(segs, words) == base
    moved_s, moved_w = horizontal_bar(x0=870.75 + 123.4, y_labels=760.0 + 55.5)
    moved = detect_block_scale_bars(moved_s, moved_w).candidates[0]
    assert moved.points_per_mm == base.candidates[0].points_per_mm and moved.span_pt == base.candidates[0].span_pt


def test_a_uniformly_larger_drawing_scales_points_per_millimetre():
    segs, words = horizontal_bar(step=2 * STEP_PT)
    c = detect_block_scale_bars(segs, words).candidates[0]
    assert c.points_per_mm == pytest.approx(2.0 / (MM_PER_POINT_AT_1_TO_1 * 100.0), rel=1e-6)


def test_inputs_are_not_mutated_and_bad_input_is_ignored_not_fatal():
    segs, words = horizontal_bar()
    frozen = (copy.deepcopy(segs), copy.deepcopy(words))
    detect_block_scale_bars(segs, words)
    assert (segs, words) == frozen
    junk_words = [{"text": "5"}, {"id": "x", "text": "7", "bbox": [1, 2, float("nan"), 4]}, {"id": "y", "text": "m", "bbox": [0, 0, 0, 0]}]
    junk_segs = [{"id": "s"}, {"id": "t", "x1": "a", "y1": 0, "x2": 0, "y2": 1}]
    assert detect_block_scale_bars(junk_segs, junk_words).candidates == ()
    assert detect_block_scale_bars([], []).candidates == ()


def test_irregular_spacing_is_not_a_bar_even_when_every_edge_sits_under_its_label():
    segs, words = horizontal_bar()
    # displace the label (and its block edge) for value 2 by 5 pt: the progression is broken, the edges still match
    for w in words:
        if w["text"] == "2":
            w["bbox"] = [v + (5.0 if j % 2 == 0 else 0.0) for j, v in enumerate(w["bbox"])]
    for e in segs:
        if e["id"] == "e2":
            e["x1"] += 5.0
            e["x2"] += 5.0
    assert detect_block_scale_bars(segs, words).candidates == ()


def test_three_labelled_edges_are_not_enough_to_call_a_bar():
    segs, words = horizontal_bar(n=2)                     # 0 1 2m only
    assert detect_block_scale_bars(segs, words).candidates == ()
    segs4, words4 = horizontal_bar(n=3)                   # 0 1 2 3m: the smallest accepted bar
    assert len(detect_block_scale_bars(segs4, words4).candidates) == 1


def test_a_row_that_starts_at_one_is_not_a_bar():
    segs, words = horizontal_bar()
    shifted = [dict(w, text=str(int(w["text"].rstrip("m")) + 1) + ("m" if w["text"].endswith("m") else "")) for w in words]
    assert detect_block_scale_bars(segs, shifted).candidates == ()
