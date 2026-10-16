"""Aggregate a py-spy ``--format raw`` profile (one ``frame;frame;...;frame count`` line per stack) into a stage/function summary.

Measurement helper only; reads one file, prints Markdown.  Frames look like ``function (path/to/file.py:123)``.
"""
from __future__ import annotations

import re
import sys
from collections import Counter

STAGES = [
    ("source ingest / visibility / snapshots", ("pb_source_visibility_authority", "pb_source_observation_authority", "pb_pdf_text_integrity_authority", "pb_native_pdf_ingest")),
    ("raster (render, OCR, ink, G17)", ("pb_raster", "pb_g17", "pytesseract", "tesseract", "PIL", "pb_portable_raster")),
    ("W2/W3/W4 topology and wall candidates", ("pb_wall_room_topology", "pb_physical_wall_candidate_authority", "pb_wall_topology", "shapely")),
    ("openings (G17/host/frame/label)", ("pb_physical_opening_authority", "pb_opening_", "pb_semantic_opening", "pb_schedule_opening")),
    ("rooms / floors / canonical objects", ("pb_source_room", "pb_live_canonical", "pb_cross_view_room", "pb_same_view_room", "pb_room_")),
    ("measurement / scale / dimensions", ("pb_figured_dimension", "pb_physical_scale", "pb_page_scale", "pb_native_dimension", "pb_dimension_")),
    ("quantity generation / publication", ("pb_live_floor", "pb_live_ceiling", "pb_live_opening", "quantity")),
    ("sealing / customer verification", ("pb_source_closed_run_export", "pb_customer_output_verification", "pb_quantity_takeoff_adapter")),
    ("viewport / title segmentation", ("pb_viewport_segmentation", "pb_page_title")),
]
FRAME = re.compile(r"^(?P<fn>.*?) \((?P<file>[^:()]+):(?P<line>\d+)\)$")


def main(path: str) -> int:
    total = 0
    inclusive_fn: Counter = Counter()
    self_fn: Counter = Counter()
    stage: Counter = Counter()
    stage_self: Counter = Counter()
    other = 0
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            stack, _, count_text = line.rpartition(" ")
            try:
                count = int(count_text)
            except ValueError:
                continue
            frames = stack.split(";")
            total += count
            seen_fn: set = set()
            seen_stage: set = set()
            for frame in frames:
                match = FRAME.match(frame)
                if not match:
                    continue
                key = f"{match['fn']} ({match['file'].split('/')[-1]})"
                if key not in seen_fn:
                    inclusive_fn[key] += count
                    seen_fn.add(key)
                for name, needles in STAGES:
                    if name not in seen_stage and any(n in match["file"] for n in needles):
                        stage[name] += count
                        seen_stage.add(name)
            leaf = FRAME.match(frames[-1])
            if leaf:
                self_fn[f"{leaf['fn']} ({leaf['file'].split('/')[-1]}:{leaf['line']})"] += count
                for name, needles in STAGES:
                    if any(n in leaf["file"] for n in needles):
                        stage_self[name] += count
                        break
                else:
                    other += count
    print(f"# Profile summary: {total} samples\n")
    print("## Inclusive time per pipeline stage (a sample counts once per stage it passes through)\n")
    print("| stage | inclusive | share |\n|---|---|---|")
    for name, c in stage.most_common():
        print(f"| {name} | {c} | {100 * c / max(total, 1):.1f}% |")
    print("\n## Self time by owning stage (leaf frame)\n")
    print("| stage | self | share |\n|---|---|---|")
    for name, c in stage_self.most_common():
        print(f"| {name} | {c} | {100 * c / max(total, 1):.1f}% |")
    print(f"| other / stdlib / third-party leaf | {other} | {100 * other / max(total, 1):.1f}% |")
    print("\n## Top 45 functions by inclusive samples (pb_/tools only)\n")
    print("| function | inclusive | share |\n|---|---|---|")
    shown = 0
    for key, c in inclusive_fn.most_common(400):
        if "pb_" not in key and "tools" not in key and "run_source" not in key:
            continue
        print(f"| {key} | {c} | {100 * c / max(total, 1):.1f}% |")
        shown += 1
        if shown >= 45:
            break
    print("\n## Top 30 leaf (self) lines\n")
    print("| leaf | self | share |\n|---|---|---|")
    for key, c in self_fn.most_common(30):
        print(f"| {key} | {c} | {100 * c / max(total, 1):.1f}% |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
