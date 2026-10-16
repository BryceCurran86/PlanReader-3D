"""Original shared G17 dual-ended four-edge W2/W3/W4 comparison.

Never a physical wall or host: the *existing* W2/W3/W4 graph is replayed
in an isolated source scope with original four producer-authenticated edges.
"""
from __future__ import annotations

from hashlib import sha256
import json

from pb_wall_room_topology_stage_a import DEFAULT_GAP_SNAP_TOLERANCE_PT
from tools.diag_gptmax_g17_original_w2_w4_source_shadow import _isolated_graph


def _real_original_four_edge_segments(shared, observed):
    ids=shared.get("source_closed_source_observation_ids")
    if (not shared.get("source_closed_pier_candidate") or not isinstance(ids,list)
            or len(ids)!=4 or len(set(ids))!=4):
        raise ValueError("no unique original dual-ended G17 pier source")
    rows=[]
    kind_counts={}
    for sid in sorted(ids):
        receipts=[members[sid] for members in observed.values() if sid in members]
        if not receipts or any(item!=receipts[0] for item in receipts):
            raise ValueError("same source ID has competing geometries or parents")
        receipt=receipts[0]
        ref=receipt.get("source_primitive_ref")
        if not isinstance(ref,str) or not ref.startswith("visible:raster_opening_primitive:"):
            raise ValueError("missing original producer-issued G17 source reference")
        parents=receipt.get("parents")
        if not isinstance(parents,list) or len(parents)!=1 or not parents[0]:
            raise ValueError("original source primitive has no unique signed parent")
        p=receipt["geometry_pdf_pts"]
        if (not isinstance(p,list) or len(p)!=4 or any(
            type(v) not in (int,float) for v in p)):
            raise ValueError("invalid producer primitive")
        kind=receipt["kind"]
        kind_counts[kind]=kind_counts.get(kind,0)+1
        rows.append({
            "id":ref.removeprefix("visible:"),
            "x1":p[0],"y1":p[1],"x2":p[2],"y2":p[3],
            "kind":"line","kind_present":True,
            "width":0.0,"width_present":False,"layer":"","dashes":"",
            "source_observation_id":sid,
            "source_parent_observation_id":parents[0],
            "source_kind":kind,
        })
    if kind_counts!={"raster_wall_band_face":2,"raster_wall_band_end":2}:
        raise ValueError("original G17 pair does not own exactly four face/end edges")
    if len({s["id"] for s in rows})!=4:
        raise ValueError("duplicate original source primitive references")
    return rows


def isolated_original_dual_end_w2_w4(shared_pier,original_opening_sources,*,source_sha,page_id):
    if not (isinstance(source_sha,str) and len(source_sha)==64
            and isinstance(page_id,str) and page_id.isdecimal()):
        raise ValueError("missing original scope")
    if len(shared_pier.get("opening_ids",()))!=2:
        raise ValueError("two distinct physical source owners required")
    ids=shared_pier["opening_ids"]
    if ids[0]==ids[1] or any(x not in original_opening_sources for x in ids):
        raise ValueError("source owner identity unavailable")
    segments=_real_original_four_edge_segments(shared_pier,original_opening_sources)
    scope=sha256(json.dumps({
        "source_sha256":source_sha,"page_id":page_id,
        "opening_ids":sorted(ids),"source_observations":sorted(
            shared_pier["source_closed_source_observation_ids"])},
        sort_keys=True,separators=(",",":")).encode()).hexdigest()[:32]
    runs={}
    for name,snap in (
        ("original_default_2_5pt_snap",DEFAULT_GAP_SNAP_TOLERANCE_PT),
        ("original_zero_snap_source_comparison",0.0),
    ):
        runs[name]=_isolated_graph(
            segments,source_sha=source_sha,
            physical_id="g17-two-ended-source:"+scope,
            side="source-compound-not-a-host",
            page_id=page_id,tolerance=snap)
        if any(runs[name][key] for key in (
            "canonical_w4_wall_id_granted","structural_wall_role_granted",
            "host_binding_granted")):
            raise ValueError("source-local graph granted forbidden wall authority")
    return {
        "original_physical_opening_ids":sorted(ids),
        "source_pier_primitive_observation_ids":sorted(
            shared_pier["source_closed_source_observation_ids"]),
        "source_pier_primitive_parent_ids":sorted(
            s["source_parent_observation_id"] for s in segments),
        "source_pier_original_primitive_refs":sorted(s["id"] for s in segments),
        "isolated_source_graphs":runs,
        "source_rectangle_role_proven":False,
        "original_source_wall_equivalence_granted":False,
        "original_W4_structural_member_granted":False,
        "original_host_binding_granted":False,
        "metric_width_height_granted":False,
    }
