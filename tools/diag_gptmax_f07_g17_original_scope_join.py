"""Compare original F07 floor-plan and G17 raw/hostless geometry without root alias.

A source-confirmed plan region in one snapshot NEVER supplies membership in a
different source snapshot. Original bounded geometry is diagnostic only.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path


def _box(value):
    if type(value) not in (list, tuple) or len(value) != 4:
        raise ValueError("original four-coordinate geometry required")
    box = tuple(float(v) for v in value)
    if (not all(math.isfinite(v) for v in box)
            or box[0] > box[2] or box[1] > box[3]):
        raise ValueError("finite correctly ordered original rectangle required")
    return box


def _relative_to_view(box, view):
    x1, y1, x2, y2 = box
    vx1, vy1, vx2, vy2 = view
    if x1 >= vx1 and y1 >= vy1 and x2 <= vx2 and y2 <= vy2:
        return "GEOMETRICALLY_INSIDE_OTHER_SNAPSHOT_VIEW"
    if x2 < vx1 or x1 > vx2 or y2 < vy1 or y1 > vy2:
        return "GEOMETRICALLY_DISJOINT_OTHER_SNAPSHOT_VIEW"
    return "INTERSECTS_OTHER_SNAPSHOT_VIEW_NO_ROLE_AUTHORITY"


def original_f07_g17_source_join_shadow(
    view_report: dict, opening_report: dict, *,
    source_sha256: str, page_id: str,
) -> dict:
    if (type(source_sha256) is not str or len(source_sha256) != 64
            or type(page_id) is not str or not page_id.isdecimal()
            or int(page_id) < 1 or str(int(page_id)) != page_id):
        raise ValueError("exact original SHA and canonical page required")
    if (view_report.get("source_sha256") != source_sha256
            or opening_report.get("source_sha256") != source_sha256
            or view_report.get("revision_id") is None
            or view_report["revision_id"] != opening_report["baseline_receipts"]["walls"][0]["revision_id"]
            or opening_report.get("snapshot_id") is None
            or view_report.get("snapshot_id") is None
            or view_report.get("page_number") != int(page_id)
            or view_report.get("authoritative_plan_view_count") != 1
            or view_report.get("default_segmentation_unchanged") is not True
            or view_report.get("published_snapshot_unchanged") is not True
            or view_report.get("metric_authority_granted") is not False
            or opening_report.get("production_activation_granted") is not False):
        raise ValueError("original F07/G17 producer scope or preservation invalid")
    views = [v for v in view_report["viewports"] if v["authoritative"]]
    if (len(views) != 1 or views[0]["view_type"] != "floor_plan"
            or views[0]["status"] != "derived"
            or views[0].get("downstream_migration") is None
            or views[0]["provenance"].get("source_owned_plan_view_proven") is not True):
        raise ValueError("unique independent original F07 plan source proof required")
    view = views[0]
    bounds = _box(view["bounding_box"])
    wall_scopes = opening_report["baseline_receipts"]["walls"]
    if len(wall_scopes) != 1:
        raise ValueError("single exact selected W4 source scope required")
    wall = wall_scopes[0]
    if (wall["source_sha256"] != source_sha256 or wall["page_id"] != page_id
            or wall["snapshot_id"] != opening_report["snapshot_id"]
            or wall["scope_complete"] is not True):
        raise ValueError("original W4 wall scope not complete or matched")
    raw_scope = opening_report["baseline_source_audit"]
    closure = raw_scope["raster_candidate_closure"]
    if closure["candidate_universe_complete"] is not False:
        raise ValueError("cannot turn unproven original candidate universe complete")
    raw = [
        g for g in raw_scope["raw_registered_gaps"]
        if g["source_scope"]["source_sha256"] == source_sha256
        and g["source_scope"]["snapshot_id"] == wall["snapshot_id"]
        and g["source_scope"]["revision_id"] == wall["revision_id"]
        and g["source_scope"]["page_id"] == page_id
        and g["source_scope"]["document_id"] == wall["document_id"]
    ]
    raw_by_id = {g["raw_candidate_id"]: g for g in raw}
    if (len(raw_by_id) != len(raw)
            or len(raw_by_id) != closure["raw_candidate_count"]):
        raise ValueError("complete unique selected-root raw inventory required")
    unresolved_ids = closure["unresolved_candidate_ids"]
    if (len(unresolved_ids) != len(set(unresolved_ids))
            or len(unresolved_ids) + closure["resolved_candidate_count"] != len(raw)):
        raise ValueError("raw closure identity count conflict")
    unresolved = []
    for rid in sorted(unresolved_ids):
        if rid not in raw_by_id:
            raise ValueError("unresolved raw id absent from original source")
        original = raw_by_id[rid]
        b = _box(original["aperture_bbox_pt"])
        unresolved.append({
            "raw_candidate_id": rid,
            "original_bbox_pt": list(b),
            "source_observation_ids": sorted(original["source_observation_ids"]),
            "relation": _relative_to_view(b, bounds),
            "typed_nonplan_role_proven": False,
            "physical_nonexistence_proven": False,
        })
    originals = opening_report["baseline_receipts"]["canonical"]
    can = {c["physical_opening_id"]: c for c in originals}
    hosts = opening_report["baseline_receipts"]["hosts"]
    host_ids = {h["opening_identity_id"]: h for h in hosts}
    if len(can) != len(originals) or len(host_ids) != len(hosts):
        raise ValueError("duplicate physical identity or host")
    hostless = []
    for physical_id, host in sorted(host_ids.items()):
        if "no_authenticated_host_wall_band" not in host["reason_codes"]:
            continue
        c = can.get(physical_id)
        if (c is None or c["snapshot_id"] != wall["snapshot_id"]
                or c["source_sha256"] != source_sha256
                or host["record_id"] is not None or host["host_wall_id"] is not None):
            raise ValueError("foreign or fabricated unhosted source receipt")
        source_lines = c["source_geometries"]
        if not source_lines:
            raise ValueError("hostless original G17 source support missing")
        rects = [_box(seg) for seg in source_lines]
        all_box = (
            min(b[0] for b in rects), min(b[1] for b in rects),
            max(b[2] for b in rects), max(b[3] for b in rects),
        )
        hostless.append({
            "physical_opening_id": physical_id,
            "source_support_bbox_pt": list(all_box),
            "relation": _relative_to_view(all_box, bounds),
            "source_host_granted": False,
            "cross_snapshot_physical_ownership_granted": False,
        })
    return {
        "status": "UNPUBLISHED_F07_G17_DIFFERENT_SNAPSHOT_GEOMETRY_AUDIT",
        "source_sha256": source_sha256,
        "revision_id": wall["revision_id"],
        "page_id": page_id,
        "view_source_snapshot_id": view_report["snapshot_id"],
        "opening_source_snapshot_id": wall["snapshot_id"],
        "same_snapshot": view_report["snapshot_id"] == wall["snapshot_id"],
        "view_id": view["view_id"],
        "original_f07_bbox_pt": list(bounds),
        "unresolved_raw": unresolved,
        "original_hostless_openings": hostless,
        "reason_codes": ["cross_snapshot_source_role_correspondence_not_proven",
                         "raw_physical_candidate_universe_incomplete"],
        "authority_grants": {x: False for x in (
            "cross_snapshot_view_identity", "typed_nonplan", "physical_absence",
            "opening_count", "host", "frame", "metric", "quantity", "customer")},
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--f07-source-report", type=Path, required=True)
    p.add_argument("--g17-source-report", type=Path, required=True)
    p.add_argument("--sha256", required=True)
    p.add_argument("--page", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    f07 = args.f07_source_report.read_bytes()
    g17 = args.g17_source_report.read_bytes()
    r = original_f07_g17_source_join_shadow(
        json.loads(f07), json.loads(g17),
        source_sha256=args.sha256, page_id=args.page,
    )
    r["input_report_sha256s"] = {
        "f07": sha256(f07).hexdigest(), "g17": sha256(g17).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(r, indent=2, sort_keys=True) + "\n")
    print({"unresolved_raw": len(r["unresolved_raw"]),
           "hostless": len(r["original_hostless_openings"]),
           "same_snapshot": r["same_snapshot"]})


if __name__ == "__main__":
    main()
