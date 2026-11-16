"""Private SHA census of bars outside the unique closed wall fragment.

No customer quantities. No 2.5 pt snap. No x-crop of right-house ink.
Use: py -3.13 tools/run_source_outer_house_continuity_census.py --pdf house.pdf --page 2 --out-dir C:\\private\\outer-house
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pb_source_outer_house_continuity_shadow import (  # noqa: E402
    census_source_outside_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--page", required=True, type=int)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    raw = args.pdf.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    import fitz
    with fitz.open(stream=raw, filetype="pdf") as doc:
        page = doc[args.page]
        drawings = page.get_drawings()
        words = page.get_text("words")
    report = census_source_outside_candidate(
        drawings, source_words=words, page_index=args.page,
    )
    report["source_sha256"] = sha
    args.out_dir.mkdir(parents=True, exist_ok=True)
    dest = args.out_dir / f"page_{args.page + 1}_outer_house_continuity.json"
    dest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "wrote": str(dest),
        "sha": sha,
        "preflight": report["preflight_reason"],
        "outside": report["outside_bar_count"],
        "structural_outside": report["structural_outside_count"],
        "outdoor_or_post": report["proven_outdoor_or_post_count"],
        "seams": len(report["outer_house_seams"]),
        "near_miss": report["near_miss_seam_count"],
        "joined_seams": report["joined_seam_count"],
        "sliding": report["sliding_bridge_count"],
        "grey_seams": report["neutral_grey_seam_count"],
        "left_only_loop_rejected": report["left_only_closed_loop_rejected"],
        "unbounded_walk": report.get("unbounded_exterior_walk_reason"),
        "unbounded_closed_candidate": report.get("unbounded_exterior_closed_candidate"),
        "interior_divider_count": len(report.get("unbounded_interior_divider_path_ids") or ()),
        "interior_divider_path_sample": list(report.get("unbounded_interior_divider_path_ids") or ())[:16],
        "measurement_authorized": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
