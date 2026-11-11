"""PlanReader Next: native PDF discovery, reviewed bindings, measured draft.

  python -m planreader_next inspect --pdf drawing.pdf --page 0
  python -m planreader_next suggest --pdf drawing.pdf --page 0 --project-id demo --revision-id r1 --output suggestions.json
  # Inspect suggestions; confirm internal finished wall faces before changing
  # boundary_basis from REVIEW_REQUIRED to internal_finished_wall_face.
  python -m planreader_next measure --pdf drawing.pdf --selection reviewed.json --output takeoff-draft.json
  python -m planreader_next takeoff --pdf combined.pdf --selection reviewed-building.json --output building-draft.json

All file output is create-only. Drafts are NOT approved commercial quantities.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import inspect_page, load_native_page, measure_page, SourceConflict
from .suggest import suggest_room_bindings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    inspect = sub.add_parser("inspect", help="List native drawing references")
    inspect.add_argument("--pdf", type=Path, required=True)
    inspect.add_argument("--page", type=int, default=0)
    inspect.add_argument("--include-segments", action="store_true", help="List source line refs for manual polygon review")
    suggest = sub.add_parser("suggest", help="Find conservative reviewed-room candidates")
    suggest.add_argument("--pdf", type=Path, required=True)
    suggest.add_argument("--page", type=int, default=0)
    suggest.add_argument("--project-id", required=True)
    suggest.add_argument("--revision-id", required=True)
    suggest.add_argument("--output", type=Path, required=True)
    suggest.add_argument("--with-boundaries", action="store_true",
                         help="Opt in to slower source-attested door/window wall-closure room polygons")
    suggest.add_argument("--skip-opening-closures", action="store_true",
                         help="Legacy override: skip topology-only virtual wall closures")
    boundaries = sub.add_parser("boundaries", help="Temporarily close verified openings to suggest room polygons")
    boundaries.add_argument("--pdf", type=Path, required=True)
    boundaries.add_argument("--page", type=int, default=0)
    boundaries.add_argument("--output", type=Path, required=True)
    boundaries.add_argument("--skip-sliding", action="store_true",
                            help="Do not include source-attested sliding-leaf closures")
    measure = sub.add_parser("measure", help="Compute source-backed room draft")
    measure.add_argument("--pdf", type=Path, required=True)
    measure.add_argument("--selection", type=Path, required=True)
    measure.add_argument("--output", type=Path, required=True)
    takeoff = sub.add_parser("takeoff", help="Reviewed walls, ceiling finishes, doors and frames")
    takeoff.add_argument("--pdf", type=Path, required=True)
    takeoff.add_argument("--selection", type=Path, required=True)
    takeoff.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.mode == "inspect":
            result = inspect_page(load_native_page(args.pdf, args.page), include_segments=args.include_segments)
        elif args.mode == "suggest":
            page = load_native_page(args.pdf, args.page)
            result = suggest_room_bindings(page)
            if args.with_boundaries and not args.skip_opening_closures:
                from .enclosure import propose_room_enclosures
                result["enclosure_preview"] = propose_room_enclosures(page, args.pdf)
            result["project_id"] = args.project_id
            result["revision_id"] = args.revision_id
        elif args.mode == "boundaries":
            from .enclosure import propose_room_enclosures
            page = load_native_page(args.pdf, args.page)
            result = propose_room_enclosures(
                page, args.pdf, include_sliding=not args.skip_sliding,
            )
        elif args.mode == "takeoff":
            from .building import measure_building_components
            selected = json.loads(args.selection.read_text(encoding="utf-8"))
            required_pages: set[int] = set()
            for kind in ("rooms", "ceilings", "walls"):
                for claim in selected.get(kind, []):
                    required_pages.add(claim["page_index"])
                    if kind == "walls":
                        required_pages.add(claim["height_source_page_index"])
            for claim in selected.get("doors", []):
                required_pages.add(claim["plan_page_index"])
                required_pages.add(claim["schedule_page_index"])
            if not required_pages:
                raise SourceConflict("no_source_page_receipts_selected")
            pages = {n: load_native_page(args.pdf, n) for n in sorted(required_pages)}
            result = measure_building_components(pages, selected)
        else:
            selected = json.loads(args.selection.read_text(encoding="utf-8"))
            result = measure_page(
                load_native_page(args.pdf, selected["page_index"]), selected
            )
        payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
        if args.mode == "inspect":
            print(payload)
        else:
            with args.output.open("x", encoding="utf-8") as output:
                output.write(payload + "\n")
            if args.mode == "suggest":
                print(json.dumps({
                    "proposals": len(result["rooms"]),
                    "abstentions": len(result["abstentions"]),
                    "candidate_enclosed_regions": result.get("enclosure_preview", {}).get(
                        "candidate_enclosed_regions", 0
                    ),
                    "virtual_wall_fills": result.get("enclosure_preview", {}).get(
                        "virtual_fill_count", 0
                    ),
                    "review_required": True,
                }, sort_keys=True))
            elif args.mode == "boundaries":
                print(json.dumps({
                    "candidate_enclosed_regions": result["candidate_enclosed_regions"],
                    "single_room_shape_hints": result["single_room_shape_hints"],
                    "unresolved_regions": result["unresolved_regions"],
                    "virtual_wall_fills": result["virtual_fill_count"],
                    "review_required": True,
                    "commercial_publishable": False,
                }, sort_keys=True))
            else:
                print(json.dumps({
                    "draft_quantity_count": len(result["quantities"]),
                    "abstention_count": len(result["abstentions"]),
                    "status": "DRAFT_REVIEW_REQUIRED",
                }, sort_keys=True))
    except (SourceConflict, ValueError, KeyError, OSError, TypeError) as exc:
        parser.exit(status=2, message=f"Source input rejected: {type(exc).__name__}: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
