"""Read-only: what does the physical scale producer say for one page, with and without forcing the viewport bbox?

usage: python scale_probe.py <repo_checkout> <pdf_path> <page_number>

Shows whether the viewport gate is the only blocker. The bbox-forced run swaps one static method in the
running process; nothing is written to the checkout.
"""
import hashlib
import sys
from pathlib import Path

sys.dont_write_bytecode = True
repo, pdf_path, page_no = sys.argv[1:4]
sys.path.insert(0, repo)

import fitz  # noqa: E402

import pb_physical_scale_authority as ps  # noqa: E402
import pb_physical_wall_candidate_authority as pw  # noqa: E402
from pb_live_physical_net_wall_integration import (  # noqa: E402
    LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
)
from pb_source_visibility_authority import SourceVisibilityProducer  # noqa: E402
from pb_viewport_segmentation import segment_page_viewports  # noqa: E402

payload = Path(pdf_path).read_bytes()
sha = hashlib.sha256(payload).hexdigest()
source = SourceVisibilityProducer(
    producer_method="live-physical-net-wall",
    producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
)
published = source.ingest_native_pdf_bytes(
    document_id=f"live-source:{sha[:32]}",
    source_bytes=payload,
    source_locator="memory://x.pdf",
    page_ids=(str(page_no),),
)
now = source.published_snapshot_for_revision(published.revision.revision_id)
page = fitz.open(stream=payload, filetype="pdf")[int(page_no) - 1]
viewports = segment_page_viewports(page, page_number=int(page_no))
authenticated = pw._authenticated_viewports_from_rows(viewports)
print("viewports:", [(v.view_id, v.status) for v in viewports],
      "| F.07-eligible:", [v.view_id for v in (authenticated[1] if authenticated else [])])
viewport = viewports[0]


def run(label, force_bbox):
    producer = ps.PhysicalScaleProducer.from_source_visibility_producer(source)
    original = ps.PhysicalScaleProducer._scope_bbox
    if force_bbox:
        ps.PhysicalScaleProducer._scope_bbox = staticmethod(
            lambda selector, source_bytes: (tuple(float(x) for x in viewport.bounding_box), None)
        )
    try:
        for viewport_id in (None, str(viewport.view_id)):
            selector = ps.PhysicalScaleSelector(
                document_id=now.revision.document_id,
                revision_id=now.revision.revision_id,
                source_sha256=now.revision.source_sha256,
                snapshot_id=now.snapshot.snapshot_id,
                page_id=str(page_no),
                viewport_id=viewport_id,
            )
            result = producer.publish_scope(selector)
            evidence = result.evidence
            print(label, "viewport_id=", viewport_id, "->", result.status.value,
                  list(result.reason_codes), ("points_per_mm=%s" % evidence.points_per_mm if evidence else ""))
    finally:
        ps.PhysicalScaleProducer._scope_bbox = original


run("production ", False)
run("bbox-forced", True)
