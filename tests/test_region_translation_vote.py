"""The translation vote reports every supported translation with its own corner count and never selects one."""
from __future__ import annotations

import copy
import json
import random
import sys

from tools.diag_region_translation_vote import UNAMBIGUOUS_RATIO, main, vote_translations


def rect(index, x0, y0, x1, y1):
    ring = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
    return {"index": index, "polygon": ring}


SHEET_A = [rect(0, 100.0, 200.0, 300.0, 380.0), rect(1, 400.0, 200.0, 520.0, 330.0), rect(2, 100.0, 500.0, 260.0, 640.0)]


def shifted(rows, dx, dy, start=0):
    return [{"index": start + k, "polygon": [[x + dx, y + dy] for x, y in row["polygon"]]} for k, row in enumerate(rows)]


def test_a_shared_building_gives_one_sharply_supported_translation_with_whole_regions_identical():
    # a larger region of sheet B that shares one corner with the shifted first region is not that region
    sheet_b = shifted(SHEET_A, 78.0, 0.0) + [rect(3, 900.0, 900.0, 960.0, 980.0), rect(4, 178.0, 200.0, 378.0, 500.0)]
    result = vote_translations(SHEET_A, sheet_b)
    best = result["candidates"][0]
    assert (best["dx"], best["dy"]) == (78.0, 0.0)
    assert best["coincident_corners"] == 15 and result["corners_a"] == 15 and result["corners_b"] == 25
    assert sorted((m["region_a"], m["region_b"]) for m in best["regions_identical_after_shift"]) == [(0, 0), (1, 1), (2, 2)]
    assert result["unambiguous"] is True and result["selected_by_this_tool"] is None and result["translation_only"] is True


def test_regions_are_identical_by_shape_whatever_collinear_vertices_a_chord_left_on_one_sheet():
    plain = rect(0, 100.0, 200.0, 300.0, 380.0)
    with_chord_vertices = {"index": 0, "polygon": [[100.0, 200.0], [200.0, 200.0], [300.0, 200.0], [300.0, 380.0], [100.0, 380.0], [100.0, 200.0]]}
    result = vote_translations([plain], shifted([with_chord_vertices], 78.0, 0.0))
    best = result["candidates"][0]
    assert (best["dx"], best["dy"]) == (78.0, 0.0)
    assert [(m["region_a"], m["region_b"]) for m in best["regions_identical_after_shift"]] == [(0, 0)]
    notched = {"index": 0, "polygon": [[100.0, 200.0], [300.0, 200.0], [300.0, 300.0], [200.0, 300.0], [200.0, 380.0], [100.0, 380.0], [100.0, 200.0]]}
    other = vote_translations([plain], shifted([notched], 78.0, 0.0))["candidates"][0]
    assert other["coincident_corners"] >= 3 and other["regions_identical_after_shift"] == []       # shares corners, is another shape


def test_two_equally_supported_translations_are_both_reported_and_neither_is_selected():
    one = [rect(0, 100.0, 100.0, 220.0, 190.0)]
    sheet_b = shifted(one, 50.0, 0.0) + shifted(one, 120.0, 40.0, start=1)
    result = vote_translations(one, sheet_b)
    shifts = {(c["dx"], c["dy"]): c["coincident_corners"] for c in result["candidates"] if c["coincident_corners"] >= 5}
    assert shifts == {(50.0, 0.0): 5, (120.0, 40.0): 5}
    assert result["unambiguous"] is False and result["selected_by_this_tool"] is None


def test_a_rival_with_a_minority_of_the_support_is_listed_with_its_own_count():
    sheet_b = shifted(SHEET_A, 78.0, 0.0) + shifted(SHEET_A[:1], 43.92 + 0.0, 0.0, start=3)
    result = vote_translations(SHEET_A, sheet_b)
    by_shift = {(c["dx"], c["dy"]): c["coincident_corners"] for c in result["candidates"]}
    assert by_shift[(78.0, 0.0)] == 15 and by_shift[(43.92, 0.0)] == 5
    assert result["unambiguous"] is True                                    # 15 is at least three times 5


def test_near_duplicate_translations_are_one_candidate_and_support_is_exact_coincidence_not_near_misses():
    sheet_b = shifted(SHEET_A[:2], 78.0, 0.0) + shifted(SHEET_A[2:], 77.8, 0.0, start=2)
    result = vote_translations(SHEET_A, sheet_b)
    near = [c for c in result["candidates"] if abs(c["dx"] - 78.0) < 1.0 and abs(c["dy"]) < 1.0]
    assert len(near) == 1 and (near[0]["dx"], near[0]["dy"]) == (78.0, 0.0)            # the 77.8 pt group is merged into it
    # every corner of sheet B is 0.1 pt off a 50 pt shift (alternating sides): many votes, no exact coincidence; one region matches exactly at 200 pt
    jittered = []
    for k, row in enumerate(SHEET_A):
        jittered.append({"index": k, "polygon": [[x + 50.0 + (0.1 if (k + m) % 2 == 0 else -0.1), y] for m, (x, y) in enumerate(row["polygon"])]})
    jittered += shifted(SHEET_A[:1], 200.0, 0.0, start=3)
    got = vote_translations(SHEET_A, jittered)
    assert (got["candidates"][0]["dx"], got["candidates"][0]["dy"]) == (200.0, 0.0) and got["candidates"][0]["coincident_corners"] == 5
    assert all(c["coincident_corners"] == 0 for c in got["candidates"] if abs(c["dx"] - 50.0) < 0.5 and c["dy"] == 0.0)


def test_unrelated_sheets_and_a_rotated_sheet_have_no_supported_translation():
    unrelated = [rect(0, 1000.0, 1000.0, 1100.0, 1090.0)]
    assert vote_translations(SHEET_A, unrelated)["candidates"] == []        # farther apart than the maximum shift
    turned = [{"index": k, "polygon": [[-y + 700.0, x] for x, y in row["polygon"]]} for k, row in enumerate(SHEET_A)]
    result = vote_translations(SHEET_A, turned)
    assert result["translation_only"] is True and result["unambiguous"] is False
    assert all(c["coincident_corners"] < result["corners_a"] for c in result["candidates"])


def test_empty_sheets_and_a_single_corner_never_claim_an_unambiguous_translation():
    assert vote_translations([], SHEET_A) == {"candidates": [], "corners_a": 0, "corners_b": 15, "unambiguous": False,
                                              "selected_by_this_tool": None, "translation_only": True}
    assert vote_translations(SHEET_A, [])["unambiguous"] is False


def test_the_result_is_deterministic_order_invariant_and_does_not_mutate_its_input():
    sheet_b = shifted(SHEET_A, 78.0, 0.0) + shifted(SHEET_A[:2], 10.0, 7.0, start=3)
    before = copy.deepcopy((SHEET_A, sheet_b))
    first = vote_translations(SHEET_A, sheet_b)
    assert (SHEET_A, sheet_b) == before and vote_translations(SHEET_A, sheet_b) == first
    a, b = list(SHEET_A), list(sheet_b)
    random.Random(4).shuffle(a)
    random.Random(5).shuffle(b)
    again = vote_translations(a, b)
    assert [(c["dx"], c["dy"], c["coincident_corners"]) for c in again["candidates"]] == [
        (c["dx"], c["dy"], c["coincident_corners"]) for c in first["candidates"]]


def test_the_ratio_constant_is_the_only_statement_of_unambiguity():
    assert UNAMBIGUOUS_RATIO == 3.0


def test_the_cli_reads_overlay_json_and_writes_the_ranked_candidates(tmp_path, capsys):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps({"region_rows": SHEET_A}), encoding="utf-8")
    b.write_text(json.dumps({"region_rows": shifted(SHEET_A, 78.0, 0.0)}), encoding="utf-8")
    out = tmp_path / "nested" / "votes.json"
    argv = sys.argv
    sys.argv = ["tool", "--a", str(a), "--b", str(b), "--json", str(out)]
    try:
        assert main() == 0
    finally:
        sys.argv = argv
    printed = json.loads(capsys.readouterr().out)
    assert printed["candidates"][0]["dx"] == 78.0 and json.loads(out.read_text(encoding="utf-8")) == printed
