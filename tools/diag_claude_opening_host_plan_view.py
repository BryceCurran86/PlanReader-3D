"""Read-only: floor-plan view ownership of every opening host binding on chosen source pages. Keep outputs local.

Uses the same ingestion and composition as tools/diag_opening_wall_face_preservation.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION  # noqa: E402
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority  # noqa: E402
from pb_opening_host_plan_view_shadow import opening_host_plan_view_report  # noqa: E402
from pb_source_visibility_authority import SourceVisibilityProducer  # noqa: E402


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
        source_locator="memory://opening-host-plan-view-source.pdf", page_ids=page_ids)
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=published.revision.revision_id, page_ids=page_ids)
    report = opening_host_plan_view_report(composition, source)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for page in report["pages"]:
        print(f"page {page['page_id']}: views {page['plan_views']}, host bindings {page['host_bindings']}, "
              f"ownership {page['ownership']}")


if __name__ == "__main__":
    main()
