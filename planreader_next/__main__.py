"""PlanReader Next: native PDF discovery, reviewed bindings, measured draft.

  python -m planreader_next inspect --pdf drawing.pdf --page 0
  python -m planreader_next suggest --pdf drawing.pdf --page 0 --project-id demo --revision-id r1 --output suggestions.json
  # Inspect suggestions; confirm internal finished wall faces before changing
  # boundary_basis from REVIEW_REQUIRED to internal_finished_wall_face.
  python -m planreader_next measure --pdf drawing.pdf --selection reviewed.json --output takeoff-draft.json

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
    suggest = sub.add_parser("suggest", help="Find conservative reviewed-room candidates")
    suggest.add_argument("--pdf", type=Path, required=True)
    suggest.add_argument("--page", type=int, default=0)
    suggest.add_argument("--project-id", required=True)
    suggest.add_argument("--revision-id", required=True)
    suggest.add_argument("--output", type=Path, required=True)
    measure = sub.add_parser("measure", help="Compute source-backed room draft")
    measure.add_argument("--pdf", type=Path, required=True)
    measure.add_argument("--selection", type=Path, required=True)
    measure.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.mode == "inspect":
            result = inspect_page(load_native_page(args.pdf, args.page))
        elif args.mode == "suggest":
            result = suggest_room_bindings(load_native_page(args.pdf, args.page))
            result["project_id"] = args.project_id
            result["revision_id"] = args.revision_id
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
                    "review_required": True,
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
