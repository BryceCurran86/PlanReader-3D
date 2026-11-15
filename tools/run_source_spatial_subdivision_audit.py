"""Read-only spatial subdivision & outside/courtyard census on native graph.

AntiGravity P4 audit tool on GPT1's research->repo handoff.
No customer quantities, no PDF copy, zero FIRM.
Use: py -3.13 tools/run_source_spatial_subdivision_audit.py --pdf house.pdf
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

from pb_source_spatial_subdivision_shadow import (  # noqa: E402
    build_source_spatial_subdivision,
)
from pb_new_numbered_space_key import (  # noqa: E402
    detect_numbered_space_key,
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
        fitz_page = doc[args.page]
        drawings = fitz_page.get_drawings()
        words = fitz_page.get_text("words")
        page_rect = (
            float(fitz_page.rect.x0),
            float(fitz_page.rect.y0),
            float(fitz_page.rect.x1),
            float(fitz_page.rect.y1),
        )
        space_key = None
        try:
            space_key = detect_numbered_space_key(
                fitz_page, page_index=args.page, source_sha256=sha
            )
        except Exception:
            space_key = None

    report = build_source_spatial_subdivision(
        drawings,
        page_rect=page_rect,
        space_key=space_key,
        text_words=words,
    ).to_dict()

    report["source_sha256"] = sha
    report["page_index_0based"] = args.page

    args.out_dir.mkdir(parents=True, exist_ok=True)
    dest = args.out_dir / f"page_{args.page + 1}_spatial_subdivision.json"
    dest.write_text(json.dumps(report, indent=2), encoding="utf-8")

    kinds_breakdown: dict[str, int] = {}
    for r in report["regions"]:
        kinds_breakdown[r["kind"]] = kinds_breakdown.get(r["kind"], 0) + 1

    faces_breakdown: dict[str, int] = {
        "exterior_envelope": sum(
            1 for f in report["boundary_faces"] if f["is_exterior_envelope"]
        ),
        "courtyard_envelope": sum(
            1 for f in report["boundary_faces"] if f["is_courtyard_envelope"]
        ),
        "interior_partition": sum(
            1 for f in report["boundary_faces"] if f["is_interior_partition"]
        ),
    }

    print(json.dumps({
        "wrote": str(dest),
        "sha": sha,
        "status": report["status"],
        "reason": report["reason"],
        "total_regions": report["total_region_count"],
        "interior_rooms": report["interior_room_count"],
        "courtyard_holes": report["courtyard_hole_count"],
        "attached_outdoor": report["attached_outdoor_count"],
        "disconnected_decoys": report["disconnected_decoy_count"],
        "primary_building_bodies": report["primary_building_body_count"],
        "regions_by_kind": kinds_breakdown,
        "boundary_faces_by_type": faces_breakdown,
        "measurement_authorized": False,
        "commercial_publishable": False,
        "official_frozen120_score_change": 0,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
