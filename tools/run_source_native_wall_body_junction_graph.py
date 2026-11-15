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


def _write_private_overlay(report: dict, dest: Path) -> None:
    bodies = report.get("bodies") or []
    opens = (report.get("exterior_cycle") or {}).get("open_endpoints") or []
    xs = [pt for body in bodies for pt in body["bounds_pdf_pts"][0::2]]
    ys = [pt for body in bodies for pt in body["bounds_pdf_pts"][1::2]]
    if not xs or not ys:
        dest.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
        return
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    parts = [
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox="
        f"'0 0 {width:.3f} {height:.3f}'>",
    ]
    for body in bodies:
        x0, y0, x1, y1 = body["bounds_pdf_pts"]
        parts.append(
            f"<rect x='{x0 - min_x:.3f}' y='{y0 - min_y:.3f}' "
            f"width='{max(x1 - x0, 0.2):.3f}' height='{max(y1 - y0, 0.2):.3f}' "
            "fill='none' stroke='#222' stroke-width='0.4'/>"
        )
    for row in opens:
        tip = row.get("tip_pdf_pts") or [0, 0]
        parts.append(
            f"<circle cx='{float(tip[0]) - min_x:.3f}' "
            f"cy='{float(tip[1]) - min_y:.3f}' r='1.2' fill='#c00'/>"
        )
    parts.append("</svg>")
    dest.write_text("".join(parts), encoding="utf-8")
    report["private_overlay_path"] = str(dest)


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
    report = build_source_native_wall_body_junction_graph(
        drawings, page_index=args.page,
    )
    report["source_sha256"] = sha
    report["page_index_0based"] = args.page
    args.out_dir.mkdir(parents=True, exist_ok=True)
    dest = args.out_dir / f"page_{args.page + 1}_wall_body_junction_graph.json"
    dest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    overlay = args.out_dir / f"page_{args.page + 1}_wall_body_junction_graph.svg"
    _write_private_overlay(report, overlay)
    kinds: dict[str, int] = {}
    for item in report["junctions"]:
        kinds[item["junction_kind"]] = kinds.get(item["junction_kind"], 0) + 1
    first = report.get("first_unclosed_endpoint")
    print(json.dumps({
        "wrote": str(dest),
        "overlay": str(overlay),
        "sha": sha,
        "exterior": report["exterior_preflight_status"],
        "bodies": report["body_count"],
        "junctions": report["junction_count"],
        "kinds": kinds,
        "collinear_unsnapped": report["collinear_gap_unsnapped_count"],
        "inferred_joins": report["inferred_join_count"],
        "joined_candidates": report["joined_candidate_count"],
        "refused_joins": report["refused_join_count"],
        "components": report["component_count"],
        "open_endpoints": report["open_endpoint_count"],
        "candidate_outer_cycles": report["candidate_outer_cycle_count"],
        "window_continuity_candidates": report["window_continuity_candidate_count"],
        "first_unclosed": first,
        "measurement_authorized": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
