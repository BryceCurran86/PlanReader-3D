"""The dimension-calibration search is fast and returns exactly what the full scan returned.

pb_drawing_reading_v1226.detect_dimension_calibration paired every
dimension-like word with every line on the page and, for each nearby line,
counted endpoint witness marks by scanning every line again. On a dense sheet
(13,000 lines) one page took ~17 s. The search now only visits lines a grid
index can place near the word or endpoint, memoises witness counts per line,
and choose_dimension_calibration counts consensus through a sorted window.
None of this may change a result: these tests compare against the full scans.
"""
from __future__ import annotations

import math
import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fitz

import pb_auto_geometry_v1219 as auto
import pb_drawing_reading_v1226 as reading
import pb_planreader_3d_app as app_mod

REPO = Path(__file__).resolve().parents[1]


def _random_lines(rng: random.Random, count: int):
    lines = []
    for _ in range(count):
        x, y = rng.uniform(0, 2400), rng.uniform(0, 1700)
        kind = rng.random()
        if kind < 0.45:
            lines.append((x, y, x + rng.uniform(-400, 400), y))              # horizontal
        elif kind < 0.9:
            lines.append((x, y, x, y + rng.uniform(-400, 400)))              # vertical
        elif kind < 0.98:
            lines.append((x, y, x + rng.uniform(-90, 90), y + rng.uniform(-90, 90)))  # short diagonal tick
        else:
            lines.append((x, y, rng.uniform(0, 2400), rng.uniform(0, 1700)))  # long diagonal
    lines.append((float("nan"), 10.0, 20.0, 10.0))
    return lines


class _FullScan:
    """The old behaviour: every query sees every line."""

    def __init__(self, lines):
        self.lines = list(lines)

    def near(self, *_box):
        return list(self.lines)


def _original_choose(candidates, expected_px_per_m=0.0):
    """choose_dimension_calibration before the sorted consensus window."""
    valid = [dict(c) for c in candidates if 5.0 <= auto._num(c.get("px_per_m")) <= 5000.0]
    if not valid:
        return None
    for candidate in valid:
        pxpm = auto._num(candidate.get("px_per_m"))
        candidate["consensus"] = sum(1 for other in valid if abs(auto._num(other.get("px_per_m")) - pxpm) / max(pxpm, 1e-9) <= 0.07)
        candidate["rank"] = auto._num(candidate.get("score")) + min(candidate["consensus"], 4) * 2.0
        if expected_px_per_m > 0:
            rel = abs(pxpm - expected_px_per_m) / expected_px_per_m
            candidate["rank"] += 5.0 if rel <= 0.10 else (2.0 if rel <= 0.25 else 0.0)
    best = max(valid, key=lambda item: (auto._num(item.get("rank")), auto._num(item.get("score"))))
    group = [c for c in valid if abs(auto._num(c.get("px_per_m")) - auto._num(best.get("px_per_m"))) / max(auto._num(best.get("px_per_m")), 1e-9) <= 0.07]
    weights = [max(1.0, auto._num(c.get("score"), 1.0)) for c in group]
    result = dict(best)
    result["px_per_m"] = round(sum(auto._num(c.get("px_per_m")) * w for c, w in zip(group, weights)) / sum(weights), 4)
    result["consensus"] = len(group)
    result["confidence"] = "High" if len(group) >= 2 or auto._num(best.get("rank")) >= 10 else "Medium"
    return result


class LineIndexTests(unittest.TestCase):
    def test_near_returns_every_overlapping_line_in_original_order(self):
        rng = random.Random(7)
        lines = _random_lines(rng, 3000)
        index = reading._LineIndex(lines)
        for _ in range(300):
            x0, y0 = rng.uniform(-50, 2400), rng.uniform(-50, 1700)
            box = (x0, y0, x0 + rng.uniform(0, 120), y0 + rng.uniform(0, 120))
            got = index.near(*box)
            positions = [lines.index(line) if line == line else len(lines) - 1 for line in got]
            self.assertEqual(positions, sorted(positions), "original order")
            for line in lines:
                x1, y1, x2, y2 = line
                if not all(math.isfinite(v) for v in line):
                    continue
                if min(x1, x2) <= box[2] and max(x1, x2) >= box[0] and min(y1, y2) <= box[3] and max(y1, y2) >= box[1]:
                    self.assertIn(line, got)
            self.assertLess(len(got), len(lines) // 5, "a small box must not return most of the page")

    def test_witness_counts_match_the_full_scan(self):
        rng = random.Random(11)
        lines = _random_lines(rng, 2500)
        index = reading._LineIndex(lines)
        for base_line in rng.sample(lines[:-1], 400):
            self.assertEqual(reading._witness_count(base_line, lines, index=index), reading._witness_count(base_line, lines))


class ChooserTests(unittest.TestCase):
    def test_consensus_window_matches_the_quadratic_count(self):
        rng = random.Random(3)
        for trial in range(300):
            base = rng.uniform(5, 5000)
            candidates = [{"px_per_m": base * rng.choice([1.0, 1.07, 0.93, 1.0700001, 0.9299999, rng.uniform(0.8, 1.2)])
                           if rng.random() < 0.7 else rng.uniform(1, 6000), "score": rng.uniform(0, 14)}
                          for _ in range(rng.randint(1, 60))]
            expected = rng.choice([0.0, base, base * 1.2])
            with self.subTest(trial=trial):
                self.assertEqual(auto.choose_dimension_calibration(candidates, expected), _original_choose(candidates, expected))


class RealPageTests(unittest.TestCase):
    def test_dense_real_plan_gives_the_full_scan_result(self):
        pdf = REPO / "benchmarks" / "sources" / "lamu-ishakani-ecd-classrooms-boq.pdf"
        if not pdf.exists():
            self.skipTest("source drawing not available")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, patch.object(app_mod, "DB_PATH", Path(tmp) / "db.sqlite"):
            app_mod.init_local_db()
            app_mod.lexecute("INSERT INTO workspaces(id,job_name,created_at,updated_at) VALUES(1,'x','x','x')")
            app_mod.lexecute("INSERT INTO documents(id,workspace_id,file_name,path,page_count) VALUES(1,1,'lamu.pdf',?,0)", (str(pdf),))
            app = SimpleNamespace(lquery=app_mod.lquery, auto_detect_scale=app_mod.auto_detect_scale, fitz=fitz)
            page = {"id": 41, "document_id": 1, "page_no": 41, "render_zoom": 2.0}
            fast = reading.detect_dimension_calibration(app, dict(page), lambda a, p: None)
            with patch.object(reading, "_LineIndex", _FullScan):
                full = reading.detect_dimension_calibration(app, dict(page), lambda a, p: None)
        self.assertEqual(fast, full)


if __name__ == "__main__":
    unittest.main()
