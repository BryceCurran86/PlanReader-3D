"""Read-only: which translation takes the regions of one sheet onto the regions of another, by exact corner coincidences?

Two sheets of the same building (a floor plan and its finishes-and-partitions plan) share walls. Given the region polygons that
``tools/diag_structural_room_region_overlay`` wrote for each sheet, this tool lets every corner of sheet A vote for every
translation that would land it on a corner of sheet B, keeps the best-supported translations, and reports for each how many corners
coincide within 0.05 pt and which whole regions coincide exactly. It is evidence only:

* it never selects a translation: every candidate with its own count is reported, a tie is reported as a tie, and ``unambiguous`` is
  only the statement that the best candidate has at least ``UNAMBIGUOUS_RATIO`` times the corner coincidences of the best other one;
* a region of one sheet is "identical after the shift" to a region of the other only when the two polygons coincide as shapes
  (symmetric difference within ``IDENTICAL_REGION_TOL_PT2``), whatever extra collinear vertices a chord left on either;
* it uses no label text, no title-block scale, no plausibility and no expected value: only polygon corners (page points, native frame);
* it handles translation only (no rotation, no scale): two sheets drawn in different orientations are reported as having no
  supported translation rather than being rotated into agreement.

usage: python -m tools.diag_region_translation_vote --a SHEET_A.json --b SHEET_B.json [--json OUT.json]
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from shapely.affinity import translate
from shapely.geometry import Polygon

MAX_SHIFT_PT = 400.0
BUCKET_PT = 0.25                    # votes are pooled in buckets this wide before refinement
COINCIDENCE_TOL_PT = 0.05           # a corner coincides when it lands this close to a corner of the other sheet
MERGE_TOL_PT = 0.5                  # candidates closer than this are one candidate (the better supported is kept)
TOP_BUCKETS = 24
UNAMBIGUOUS_RATIO = 3.0
IDENTICAL_REGION_TOL_PT2 = 1.0      # two regions are the same shape after the shift when their symmetric difference is this small

Corner = Tuple[float, float]


def _rings(rows: Sequence[Mapping[str, Any]]) -> List[Tuple[int, List[Corner]]]:
    out = []
    for position, row in enumerate(rows):
        ring = [(float(p[0]), float(p[1])) for p in row.get("polygon", ())]
        if ring:
            out.append((int(row.get("index", position)), ring))
    return out


def _coincidences(a_corners: Sequence[Corner], b_keys: set, shift: Corner) -> int:
    count = 0
    for x, y in a_corners:
        if (round((x + shift[0]) / COINCIDENCE_TOL_PT), round((y + shift[1]) / COINCIDENCE_TOL_PT)) in b_keys:
            count += 1
    return count


def vote_translations(rows_a: Sequence[Mapping[str, Any]], rows_b: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    rings_a, rings_b = _rings(rows_a), _rings(rows_b)
    a_corners = [c for _, ring in rings_a for c in ring]
    b_corners = [c for _, ring in rings_b for c in ring]
    pooled: Dict[Tuple[int, int], List[Corner]] = defaultdict(list)
    for ax, ay in a_corners:
        for bx, by in b_corners:
            dx, dy = bx - ax, by - ay
            if abs(dx) <= MAX_SHIFT_PT and abs(dy) <= MAX_SHIFT_PT:
                pooled[(round(dx / BUCKET_PT), round(dy / BUCKET_PT))].append((dx, dy))
    ranked = sorted(pooled.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:TOP_BUCKETS]
    b_keys = {(round(x / COINCIDENCE_TOL_PT), round(y / COINCIDENCE_TOL_PT)) for x, y in b_corners}
    candidates: List[Dict[str, Any]] = []
    for _, members in ranked:
        shift = (sum(m[0] for m in members) / len(members), sum(m[1] for m in members) / len(members))
        candidates.append({"dx": round(shift[0], 3), "dy": round(shift[1], 3), "votes": len(members),
                           "coincident_corners": _coincidences(a_corners, b_keys, shift)})
    candidates.sort(key=lambda c: (-c["coincident_corners"], -c["votes"], c["dx"], c["dy"]))
    kept: List[Dict[str, Any]] = []
    for cand in candidates:
        if all(abs(cand["dx"] - k["dx"]) > MERGE_TOL_PT or abs(cand["dy"] - k["dy"]) > MERGE_TOL_PT for k in kept):
            kept.append(cand)
    polygons_a = [(index, Polygon(ring)) for index, ring in rings_a if len(ring) >= 3]
    polygons_b = [(index, Polygon(ring)) for index, ring in rings_b if len(ring) >= 3]
    for cand in kept:
        shift = (cand["dx"], cand["dy"])
        matches = []
        for index_a, poly_a in polygons_a:
            moved = translate(poly_a, shift[0], shift[1])
            for index_b, poly_b in polygons_b:
                if moved.bounds[0] > poly_b.bounds[2] or poly_b.bounds[0] > moved.bounds[2]                         or moved.bounds[1] > poly_b.bounds[3] or poly_b.bounds[1] > moved.bounds[3]:
                    continue
                if moved.symmetric_difference(poly_b).area <= IDENTICAL_REGION_TOL_PT2:
                    matches.append({"region_a": index_a, "region_b": index_b})
        cand["regions_identical_after_shift"] = matches
        cand["of_corners_a"] = len(a_corners)
        cand["of_corners_b"] = len(b_corners)
    best = kept[0] if kept else None
    others = kept[1:]
    second = max((c["coincident_corners"] for c in others), default=0)
    return {
        "candidates": kept[:8],
        "corners_a": len(a_corners),
        "corners_b": len(b_corners),
        "unambiguous": bool(best and best["coincident_corners"] > 0
                            and best["coincident_corners"] >= UNAMBIGUOUS_RATIO * max(second, 1)),
        "selected_by_this_tool": None,
        "translation_only": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--a", type=Path, required=True, help="overlay JSON of the first sheet")
    parser.add_argument("--b", type=Path, required=True, help="overlay JSON of the second sheet")
    parser.add_argument("--json", type=Path, dest="out")
    args = parser.parse_args()
    result = vote_translations(json.loads(args.a.read_text(encoding="utf-8")).get("region_rows", ()),
                               json.loads(args.b.read_text(encoding="utf-8")).get("region_rows", ()))
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
