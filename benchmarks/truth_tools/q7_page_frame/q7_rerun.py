"""Q7 rerun through the PATCHED #1143 script's public run_shadow_diff (no wrapper, no private calls)."""
import hashlib, json, sys, time
repo, pdf, doc_id, out = sys.argv[1:5]
sys.path.insert(0, repo)
from scripts import page_frame_wall_boundary_shadow_diff as D
data = open(pdf, "rb").read()
t = time.time()
report = D.run_shadow_diff(data, document_id=doc_id)
report["_seconds"] = round(time.time() - t, 1)
report["_input_file_sha256"] = hashlib.sha256(data).hexdigest()
json.dump(report, open(out, "w"), indent=1, sort_keys=True)
print("DONE", report["_seconds"], "s | unresolved_pages:", report["unresolved_pages"], flush=True)
