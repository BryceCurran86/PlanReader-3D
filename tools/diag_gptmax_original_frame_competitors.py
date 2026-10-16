"""Read-only first-gate census for original raster opening host-frame competitors.

This audits an original horizontal PDF-point stripe; it does not replace
OpeningHostFrameProducer or grant wall, frame, metric or quantity authority.
Unrecorded equivalence is never positive DISTINCT proof.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path

_TARGET_REASON = "opening_host_frame_aligned_fragment_distinctness_unproven"
_DISTINCT = "distinct_physical_walls"


def original_frame_competitor_census(
    report: dict, *, source_sha256: str, snapshot_id: str,
    physical_opening_ids: tuple[str, ...], source_render_dpi: int = 144,
    opening_render_dpi: int = 300,
) -> dict:
    """Inspect producer-issued receipts only; do not expand their authority."""
    if not physical_opening_ids or len(set(physical_opening_ids)) != len(physical_opening_ids):
        raise ValueError("explicit unique physical opening identities required")
    if (not source_sha256 or not snapshot_id
            or report.get("source_sha256") != source_sha256
            or report.get("snapshot_id") != snapshot_id):
        raise ValueError("selected source sha/snapshot mismatch")
    if (type(source_render_dpi) is not int or type(opening_render_dpi) is not int
            or min(source_render_dpi, opening_render_dpi) <= 0):
        raise ValueError("positive source DPI required")
    b = report["baseline_receipts"]
    wall_scopes = b["walls"]
    if len(wall_scopes) != 1:
        raise ValueError("exactly one original wall decision scope required")
    scope = wall_scopes[0]
    if (not scope["scope_complete"] or scope["source_sha256"] != source_sha256
            or scope["snapshot_id"] != snapshot_id):
        raise ValueError("unsealed or cross-root wall scope")
    records = {r["wall_candidate_id"]: r for r in scope["records"]}
    if len(records) != len(scope["records"]):
        raise ValueError("duplicate wall candidate id")
    relation_rows = scope["equivalence"]["pair_classifications"]
    relations = {tuple(sorted((a, z))): relation for a, z, relation in relation_rows}
    if len(relations) != len(relation_rows):
        raise ValueError("duplicate producer equivalence pair")
    canonical = {r["physical_opening_id"]: r for r in b["canonical"]}
    hosts = {r["opening_identity_id"]: r for r in b["hosts"]}
    frames = {r["opening_identity_id"]: r for r in b["frames"]}
    if (len(canonical) != len(b["canonical"]) or len(hosts) != len(b["hosts"])
            or len(frames) != len(b["frames"])):
        raise ValueError("duplicate opening receipt")
    # The source replay contains identical physical gap geometry at both
    # pre-augmentation and selected source snapshots.  Never silently alias
    # those roots: use only original raw receipts in this exact sealed scope.
    raw = [
        gap for gap in report["baseline_source_audit"]["raw_registered_gaps"]
        if gap["source_scope"]["snapshot_id"] == snapshot_id
        and gap["source_scope"]["source_sha256"] == source_sha256
        and gap["source_scope"]["document_id"] == scope["document_id"]
        and gap["source_scope"]["revision_id"] == scope["revision_id"]
        and gap["source_scope"]["page_id"] == scope["page_id"]
    ]
    target_rows = []
    members = set()
    ybands = set()
    for identity in sorted(physical_opening_ids):
        c, h, f = canonical[identity], hosts[identity], frames[identity]
        if (c["source_sha256"] != source_sha256 or c["snapshot_id"] != snapshot_id
                or h["status"] != "corroborated" or not h["host_wall_id"]
                or f["status"] != "abstained" or f["record_id"] is not None
                or _TARGET_REASON not in f["reason_codes"]):
            raise ValueError("target is not original hosted, frame-blocked opening")
        wall_members = h["member_wall_candidate_ids"]
        if len(wall_members) != 2 or any(w not in records for w in wall_members):
            raise ValueError("original host member wall evidence incomplete")
        # G17 original raw raster support, not an aperture identity grant.
        obs = set(c["source_observation_ids"])
        overlap = [(len(obs.intersection(r["source_observation_ids"])), r) for r in raw]
        best = max((n for n, _ in overlap), default=0)
        if best < 6:
            raise ValueError("insufficient original six-observation raster gap witness")
        selected_raw = [r for n, r in overlap if n == best]
        bands = {tuple(r["aperture_bbox_pt"][1::2]) for r in selected_raw}
        if len(bands) != 1:
            raise ValueError("competing source-owned opening gap bands")
        band = next(iter(bands))
        if len(band) != 2 or not (float(band[0]) < float(band[1])):
            raise ValueError("invalid original source gap stripe")
        ybands.add(band)
        members.update(wall_members)
        target_rows.append({
            "physical_opening_id": identity,
            "host_wall_candidate_ids": sorted(wall_members),
            "original_gap_y_bounds_pt": list(band),
            "max_shared_raw_gap_observations": best,
            "selected_source_root_only": snapshot_id,
            "original_raw_candidate_ids": sorted(r["raw_candidate_id"] for r in selected_raw),
        })
    if len(ybands) != 1:
        raise ValueError("selected openings do not share source-owned horizontal stripe")
    y0, y1 = next(iter(ybands))
    center = (y0 + y1) / 2
    allowance = 72.0 / source_render_dpi + 72.0 / opening_render_dpi
    parallel = math.sin(math.radians(5))
    aligned = []
    for candidate_id, record in sorted(records.items()):
        source = record["physical_identity"]
        if source["viewport_id"] != scope["decision_scope_id"]:
            continue
        pts = record["wall_candidate"]["centerline_pts"]
        hits = []
        for a, z in zip(pts, pts[1:]):
            dx, dy = float(z[0]) - float(a[0]), float(z[1]) - float(a[1])
            distance = math.hypot(dx, dy)
            if distance <= 1e-6 or abs(dy / distance) > parallel or abs(dy) > allowance:
                continue
            if abs((float(a[1]) + float(z[1])) / 2 - center) <= (y1 - y0) / 2 + allowance + 1e-6:
                hits.append([list(a), list(z)])
        if not hits:
            continue
        pairs = [{
            "member_id": m,
            "producer_relation": relations.get(tuple(sorted((candidate_id, m))), "UNRECORDED"),
            "distinctness_proven": relations.get(tuple(sorted((candidate_id, m)))) == _DISTINCT,
        } for m in sorted(members) if m != candidate_id]
        aligned.append({
            "wall_candidate_id": candidate_id,
            "connected_host_member": candidate_id in members,
            "original_source_primitive_ids": source["source_primitive_ids"],
            "original_w4_edge_ids": source["edge_ids"],
            "aligned_segments_pt": hits,
            "member_relations": pairs,
            "all_member_relations_distinct": bool(pairs) and all(
                p["distinctness_proven"] for p in pairs),
        })
    if any(member not in {r["wall_candidate_id"] for r in aligned} for member in members):
        raise ValueError("selected source host geometry not in original stripe")
    unproven = [r for r in aligned if not r["connected_host_member"]
                and not r["all_member_relations_distinct"]]
    return {
        "status": "UNPUBLISHED_ORIGINAL_SOURCE_FRAME_COMPETITOR_DIAGNOSTIC",
        "source_sha256": source_sha256,
        "snapshot_id": snapshot_id,
        "decision_scope_id": scope["decision_scope_id"],
        "producer_wall_candidate_count": len(records),
        "producer_equivalence_pair_count": len(relations),
        "horizontal_stripe_y_bounds_pt": [y0, y1],
        "horizontal_source_dpi": source_render_dpi,
        "opening_source_dpi": opening_render_dpi,
        "target_hosted_unframed_openings": target_rows,
        "connected_host_candidate_ids": sorted(members),
        "locally_aligned_source_wall_candidates": aligned,
        "unproven_noncomponent_fragments": unproven,
        "unproven_noncomponent_fragment_count": len(unproven),
        "authority_grants": {k: False for k in (
            "distinct_wall", "frame", "metric", "quantity", "customer", "count")},
        "limitation": (
            "Read-only stripe prefilter: does not replace full host-frame projection; "
            "no unrecorded or ambiguous relation is DISTINCT. No wall identity, "
            "quantity or count grant."
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-report", required=True, type=Path)
    p.add_argument("--sha256", required=True)
    p.add_argument("--snapshot", required=True)
    p.add_argument("--physical-id", action="append", required=True)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    source = args.source_report.read_bytes()
    output = original_frame_competitor_census(
        json.loads(source),
        source_sha256=args.sha256,
        snapshot_id=args.snapshot,
        physical_opening_ids=tuple(args.physical_id),
    )
    output["original_source_report_sha256"] = sha256(source).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print({
        "status": output["status"],
        "unproven_fragment_count": output["unproven_noncomponent_fragment_count"],
    })


if __name__ == "__main__":
    main()
