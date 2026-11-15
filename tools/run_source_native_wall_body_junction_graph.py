"""Read-only wall-body / junction census on the #4347 native graph.

No customer quantities, no PDF copy, no collinear snap.
Use: py -3.13 tools/run_source_native_wall_body_junction_graph.py --pdf house.pdf --page 2 --out-dir C:\\private\\wall-graph
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

from pb_source_native_wall_body_junction_graph_shadow import (  # noqa: E402
    build_source_native_wall_body_junction_graph,
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
        drawings = doc[args.page].get_drawings()
    report = build_source_native_wall_body_junction_graph(drawings)
    report["source_sha256"] = sha
    report["page_index_0based"] = args.page
    args.out_dir.mkdir(parents=True, exist_ok=True)
    dest = args.out_dir / f"page_{args.page + 1}_wall_body_junction_graph.json"
    dest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    kinds: dict[str, int] = {}
    for item in report["junctions"]:
        kinds[item["junction_kind"]] = kinds.get(item["junction_kind"], 0) + 1
    print(json.dumps({
        "wrote": str(dest),
        "sha": sha,
        "exterior": report["exterior_preflight_status"],
        "bodies": report["body_count"],
        "junctions": report["junction_count"],
        "kinds": kinds,
        "collinear_unsnapped": report["collinear_gap_unsnapped_count"],
        "inferred_joins": report["inferred_join_count"],
        "joined_candidates": report["joined_candidate_count"],
        "measurement_authorized": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
