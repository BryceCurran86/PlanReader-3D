"""Read-only: enclosures strictly inside room faces on chosen source pages (counts and page-space areas). Keep local."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION  # noqa: E402
from pb_physical_wall_candidate_authority import (  # noqa: E402
    PhysicalWallCandidateProducer,
    _build_authenticated_viewport_scope_results,
    _decision_scope_id,
    PhysicalWallCandidateSelector,
)
from pb_room_face_hole_report_shadow import room_face_hole_report  # noqa: E402
from pb_source_room_face_authority import _derive_scope  # noqa: E402
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
        source_locator="memory://room-face-hole-source.pdf", page_ids=page_ids)
    authority = PhysicalWallCandidateProducer.from_source_visibility_producer(source, page_ids=page_ids).authority()
    published = source.published_snapshot_for_revision(published.revision.revision_id)
    output = []
    for page_id in page_ids:
        page_scope = authority.resolve_scope(PhysicalWallCandidateSelector(
            document_id=published.revision.document_id, revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
            page_id=page_id, decision_scope_id=_decision_scope_id(page_id)))
        views = _build_authenticated_viewport_scope_results(source_producer=source, published=published,
                                                            source_bytes=data, page_id=page_id)
        for scope in (page_scope, *views):
            report = room_face_hole_report(scope, _derive_scope(scope))
            report["scope"] = scope.viewport_view_type or "page"
            output.append(report)
            holes = sum(len(face["holes"]) for face in report["faces"])
            print(f"page {page_id} {report['scope']}: room faces {len(report['faces'])}, with enclosures "
                  f"{report['faces_with_holes']}, enclosures {holes}")
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
