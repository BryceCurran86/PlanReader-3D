"""Read-only: page wall scopes against authenticated plan-view scopes on chosen source pages. Keep outputs local."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION  # noqa: E402
from pb_source_visibility_authority import SourceVisibilityProducer  # noqa: E402
from pb_wall_plan_view_scope_report import NO_PLAN_VIEW, VIEW_VARIANTS, wall_plan_view_scope_report  # noqa: E402

COUNTS = ("scope_complete", "candidates", "boundary_tainted", "primitives_crossing_boundary", "primitives_ownership_ambiguous",
          "resolved_walls", "room_faces", "room_faces_with_all_walls_resolved")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page-id", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = args.pdf.read_bytes()
    page_ids = tuple(sorted(set(args.page_id), key=int))
    source = SourceVisibilityProducer(producer_method="live-physical-net-wall",
                                      producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{hashlib.sha256(data).hexdigest()[:32]}", source_bytes=data,
        source_locator="memory://wall-plan-view-scope-source.pdf", page_ids=page_ids)
    result = wall_plan_view_scope_report(source, revision_id=published.revision.revision_id, page_ids=page_ids)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for page in result["pages"]:
        for name in ("page_scope", *VIEW_VARIANTS):
            scopes = page[name]
            if scopes == NO_PLAN_VIEW:
                print(f"page {page['page_id']} {name}: {NO_PLAN_VIEW}")
                continue
            for scope in [scopes] if isinstance(scopes, dict) else scopes:
                print(f"page {page['page_id']} {name}: " + ", ".join(f"{key}={scope[key]}" for key in COUNTS))


if __name__ == "__main__":
    main()
