"""Read-only: page-level source-owned W4 wall scopes for original Maryborough pages 7 and 11, with wall geometry.

Runs the same producer path the live pipeline uses for page 7 (page-addressed scope), and the identical path for page 11
(no viewport, no title). Nothing is published; output is evidence for the registration analysis.
"""
import dataclasses
import hashlib
import json
import sys
import time

sys.modules["rapidocr"] = None
sys.modules["onnxruntime"] = None
repo, out = sys.argv[1], sys.argv[2]
sys.path.insert(0, repo)

from pathlib import Path  # noqa: E402

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION  # noqa: E402
from pb_physical_wall_candidate_authority import (  # noqa: E402
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
    _decision_scope_id,
)
from pb_source_visibility_authority import SourceVisibilityProducer  # noqa: E402

PDF = Path(f"{repo}/documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
payload = PDF.read_bytes()
sha = hashlib.sha256(payload).hexdigest()
source = SourceVisibilityProducer(producer_method="live-physical-net-wall", producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
t0 = time.time()
pub = source.ingest_native_pdf_bytes(
    document_id=f"live-source:{sha[:32]}", source_bytes=payload, source_locator="memory://x.pdf", page_ids=("7", "11")
)
print("ingest", round(time.time() - t0, 1), "s")
res = {"source_sha256": sha, "pages": {}}
for page_id in ("7", "11"):
    t1 = time.time()
    producer = PhysicalWallCandidateProducer.from_source_visibility_producer(source, page_ids=(page_id,))
    authority = producer.authority()
    published = source.published_snapshot_for_revision(pub.revision.revision_id)
    selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        decision_scope_id=_decision_scope_id(page_id),
    )
    scope = authority.resolve_scope(selector)
    records = []
    for r in scope.records:
        w = r.wall_candidate
        records.append({
            "wall_candidate_id": r.wall_candidate_id,
            "centerline_pts": [list(map(float, p)) for p in getattr(w, "centerline_pts", ())],
            "thickness_pt": getattr(w, "thickness_pt", None),
            "status": getattr(getattr(w, "status", None), "value", str(getattr(w, "status", None))),
            "source_primitive_ids": list(r.physical_identity.source_primitive_ids),
            "edge_ids": list(r.physical_identity.edge_ids),
            "candidate_identity_id": r.physical_identity.candidate_identity_id,
            "edge_fragments": [
                {"edge_id": f.edge_id, "geometry": [float(v) for v in f.geometry], "source_primitive_ids": list(f.source_primitive_ids)}
                for f in getattr(r, "source_edge_fragments", ())
            ],
        })
    res["pages"][page_id] = {
        "status": scope.status.value,
        "scope_complete": scope.scope_complete,
        "reason_codes": list(scope.reason_codes),
        "record_count": len(records),
        "decision_scope_id": scope.decision_scope_id,
        "snapshot_id": scope.snapshot_id,
        "records": records,
        "elapsed_s": round(time.time() - t1, 1),
    }
    print("page", page_id, scope.status.value, "complete", scope.scope_complete, "records", len(records), "reasons", list(scope.reason_codes)[:6], round(time.time() - t1, 1), "s")
json.dump(res, open(out, "w"))
print("saved", out)
