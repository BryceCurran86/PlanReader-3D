"""Q7 comparison wrapper v2 (scratch, read-only). Mirrors page_frame_wall_boundary_shadow_diff.run_shadow_diff
EXACTLY (same producers, same _page_report) but ingests once, times each page and captures per-page exceptions.
No thresholds, rules or filters are derived from the source."""
import hashlib, json, sys, time
repo, pdf, doc_id, pages, out, cls = sys.argv[1:7]
sys.path.insert(0, repo); sys.path.insert(0, repo + "/scripts")
import fitz
import page_frame_wall_boundary_shadow_diff as d
data = open(pdf, "rb").read()
res = {"source_class": cls, "document_id": doc_id, "sha256": hashlib.sha256(data).hexdigest(),
       "head_note": "PR #1143 head d389ae5b merged onto main c51b46e (scratch worktree); PRE-PATCH; selector uses REFRESHED snapshot (wrapper-level handling of the stale-snapshot defect)", "pages": []}
t0 = time.time()
src = d.SourceVisibilityProducer(producer_method=d.PRODUCER_METHOD, producer_version="1")
pub = src.ingest_native_pdf_bytes(document_id=doc_id, source_bytes=data, source_locator=d.SOURCE_LOCATOR)
auth = d.PhysicalWallCandidateProducer.from_source_visibility_producer(src).authority()
res["ingest_seconds"] = round(time.time() - t0, 1)
res["revision"] = pub.revision.revision_id
snap_before = pub.snapshot.snapshot_id
pub = src._published_by_revision[pub.revision.revision_id]  # refresh: producer augmentation publishes a NEW snapshot
res["snapshot_id_before_producer"] = snap_before; res["snapshot_id_used"] = pub.snapshot.snapshot_id
res["snapshot_changed_by_producer"] = snap_before != pub.snapshot.snapshot_id
print("ingest done", res["ingest_seconds"], "s", flush=True)
doc = fitz.open(stream=data, filetype="pdf")
for n in [int(x) for x in pages.split(",")]:
    t = time.time()
    try:
        pr = d._page_report(src=src, pub=pub, pdf_bytes=data, document=doc, page_no=n, auth=auth)
    except Exception as exc:
        pr = {"page_no": n, "harness_exception": f"{type(exc).__name__}: {str(exc)[:300]}"}
    pr["_seconds"] = round(time.time() - t, 1)
    res["pages"].append(pr)
    fr = pr.get("frame", {})
    print(n, "frame:", fr.get("status"), "| pipeline:", pr.get("pipeline_status", pr.get("harness_exception")),
          "| cross:", pr.get("cross_check"), "|", pr.get("summary"), "|", pr["_seconds"], "s", flush=True)
    json.dump(res, open(out, "w"), indent=1, sort_keys=True, default=str)
print("DONE", flush=True)
