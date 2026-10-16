"""Read-only: classify the boundary-tainted wall candidates of one original plan page.

usage: python trace_tainted_walls.py <repo_checkout> <pdf_path> <expected_sha256> <page_number> <out_dir>

Uses the same ingest/compose path that reproduces the CI source-gate numbers. Writes
walls_meta.json (one row per W4 candidate, with source graphic metadata) and prints
class tables. Changes nothing; counterfactual scripts in this directory read walls_meta.json.
"""
import collections
import hashlib
import json
import math
import re
import statistics as st
import sys
from pathlib import Path

sys.dont_write_bytecode = True
repo, pdf_path, expected_sha, page_no, out_dir = sys.argv[1:6]
sys.path.insert(0, repo)

import fitz  # noqa: E402

from pb_live_physical_net_wall_integration import (  # noqa: E402
    LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
)
from pb_live_wall_opening_authority_composition import (  # noqa: E402
    compose_live_wall_opening_authority,
)
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector  # noqa: E402
from pb_source_visibility_authority import SourceVisibilityProducer  # noqa: E402
from pb_vector_geometry_v130 import extract_native_page  # noqa: E402

payload = Path(pdf_path).read_bytes()
sha = hashlib.sha256(payload).hexdigest()
assert sha == expected_sha, "original PDF bytes differ from the expected SHA-256"
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
composition = compose_live_wall_opening_authority(
    source_visibility_producer=source,
    revision_id=published.revision.revision_id,
    page_ids=(str(page_no),),
    evidence_page_ids=(),
)
now = source.published_snapshot_for_revision(published.revision.revision_id)
selector = PhysicalWallCandidateSelector(
    document_id=now.revision.document_id,
    revision_id=now.revision.revision_id,
    source_sha256=now.revision.source_sha256,
    snapshot_id=now.snapshot.snapshot_id,
    page_id=str(page_no),
    decision_scope_id=f"wall-source:page-{page_no}",
)
scope = composition.physical_wall_candidate_authority.resolve_scope(selector)
tainted = set(scope.boundary_evaluation.boundary_tainted_wall_candidate_ids)
print("records", len(scope.records), "tainted", len(tainted), "complete", scope.scope_complete)

page = fitz.open(stream=payload, filetype="pdf")[int(page_no) - 1]
segments = {s["id"]: s for s in extract_native_page(page)["segments"]}


def meta(pid):
    s = segments.get(pid)
    if s is None:
        return {"missing": True}
    return {
        "layer": s.get("layer"),
        "width": s.get("width"),
        "dashes": s.get("dashes"),
        "fill": s.get("fill"),
        "kind": s["kind"],
    }


rows = []
for record in scope.records:
    wall = record.wall_candidate
    junctions = [str(getattr(j, "value", j)) for j in wall.junction_types]
    pts = [(float(p[0]), float(p[1])) for p in wall.centerline_pts]
    metas = [meta(p) for p in record.physical_identity.source_primitive_ids]
    layers = sorted({str(m.get("layer")) for m in metas if not m.get("missing")})
    dangling = (
        [pts[i] for i, j in ((0, junctions[0]), (len(pts) - 1, junctions[-1])) if j == "endpoint"]
        if len(junctions) == 2 and len(pts) >= 2
        else []
    )
    rows.append({
        "id": record.wall_candidate_id,
        "tainted": record.wall_candidate_id in tainted,
        "length": round(math.dist(pts[0], pts[-1]), 2) if len(pts) >= 2 else 0.0,
        "pts": pts,
        "jts": junctions,
        "dangling": dangling,
        "layers": layers,
        "missing_prims": sum(1 for m in metas if m.get("missing")),
    })
Path(out_dir).mkdir(parents=True, exist_ok=True)
(Path(out_dir) / "walls_meta.json").write_text(json.dumps(rows), encoding="utf-8")


def layer_class(row):
    named = [layer for layer in row["layers"] if layer]
    if not named:
        return "no-layer / raster-derived"
    if all(re.search("wall", layer, re.I) for layer in named):
        return "wall-named layers only"
    if any(re.search("wall", layer, re.I) for layer in named):
        return "mixed (wall + other layers)"
    return "non-wall layers"


table = collections.defaultdict(collections.Counter)
for row in rows:
    table[layer_class(row)]["total"] += 1
    table[layer_class(row)]["tainted"] += row["tainted"]
print(f"{'class':32s}{'total':>7}{'tainted':>9}")
for name, counts in sorted(table.items(), key=lambda kv: -kv[1]["total"]):
    print(f"{name:32s}{counts['total']:>7}{counts['tainted']:>9}")

taint_rows = [r for r in rows if r["tainted"]]
print("tainted length median %.1f max %.1f" % (
    st.median(r["length"] for r in taint_rows), max(r["length"] for r in taint_rows)))


def point_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length_sq))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


nearest = []
for row in taint_rows:
    for end in row["dangling"]:
        best = min(
            (point_segment(end, other["pts"][i], other["pts"][i + 1])
             for other in rows if other["id"] != row["id"]
             for i in range(len(other["pts"]) - 1)),
            default=float("inf"),
        )
        nearest.append(best)
nearest.sort()
print("free ends:", len(nearest), "nearest other-wall centerline (pt): median %.2f; <=1pt %d, <=3pt %d, <=6pt %d" % (
    st.median(nearest), sum(d <= 1 for d in nearest), sum(d <= 3 for d in nearest), sum(d <= 6 for d in nearest)))
