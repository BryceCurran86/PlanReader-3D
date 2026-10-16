"""Observe genuine authenticated G17 face/end source through isolated W2/W3/W4.

Source PDF and complete original-stage report are inputs, not benchmark truth.
Only the original G17 source receipts that pass an independently replayed,
source-sha-matched 300-DPI one-ended original-ink shadow may be graphed.
A W4 shape here is a *candidate*, NEVER a canonical wall or opening host.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from pb_wall_room_topology_stage_a import (
    DEFAULT_GAP_SNAP_TOLERANCE_PT, build_wall_graph_for_viewport,
)
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_wall_assembly import assemble_wall_candidates
from tools.diag_gptmax_g17_source_only_flanks import source_only_closed_flanks


def _original_flank_lines(receipt: Mapping[str, Any], flank: Mapping[str, Any]) -> list[dict]:
    """Use three EXPLICIT original G17 face/end observations, no centerline."""
    source_rows = receipt.get("source_g17_observations")
    ids = flank.get("source_observation_ids")
    if (not isinstance(source_rows, list) or not isinstance(ids, list)
            or len(ids) != 3 or len(set(ids)) != 3):
        raise ValueError("original face/end source receipt universe unavailable")
    source_by_id: dict[str, Mapping[str, Any]] = {}
    for row in source_rows:
        oid = row.get("observation_id")
        if not isinstance(oid, str) or not oid or oid in source_by_id:
            raise ValueError("duplicate or malformed original source id")
        source_by_id[oid] = row
    if not set(ids) <= set(source_by_id):
        raise ValueError("G17 source observation outside physical opening")
    segments = []
    kinds = []
    for oid in sorted(ids):
        row = source_by_id[oid]
        kind = row.get("observation_kind")
        parents = row.get("authenticated_source_parents")
        line = row.get("geometry_pdf_pts")
        if (kind not in ("raster_wall_band_face", "raster_wall_band_end")
                or not isinstance(parents, list) or len(parents) != 1
                or not isinstance(parents[0], Mapping)
                or not parents[0].get("observation_id")
                or not isinstance(line, list) or len(line) != 4
                or any(type(v) not in (int,float) or not math.isfinite(v) for v in line)
                or math.hypot(float(line[2])-float(line[0]),
                              float(line[3])-float(line[1])) <= 0):
            raise ValueError("original source face/end primitive not independently owned")
        kinds.append(kind)
        segments.append({
            "id": "g17-original-source:" + oid,
            "x1": float(line[0]), "y1": float(line[1]),
            "x2": float(line[2]), "y2": float(line[3]),
            "kind":"line", "kind_present":True,
            "width":0.0, "width_present":False,
            "layer":"", "dashes":"",
            "source_observation_id":oid,
            "source_parent_observation_id":str(parents[0]["observation_id"]),
            "source_kind":kind,
        })
    if sorted(kinds) != ["raster_wall_band_end","raster_wall_band_face","raster_wall_band_face"]:
        raise ValueError("G17 original one-ended flank primitive structure invalid")
    return segments


def _isolated_graph(segments: list[dict], *,
                    source_sha: str, physical_id: str, side: str,
                    page_id: str, tolerance: float) -> dict[str, Any]:
    """Execute original W2→W3→W4 for source facts, NEVER publish candidates."""
    viewport_id = "g17-isolated-shadow:" + physical_id + ":" + side
    graph=build_wall_graph_for_viewport(
        segments, gap_snap_tolerance_pt=tolerance,
        exact_endpoint_index_shadow=(tolerance == 0.0),
        exact_split_parent_lineage_shadow=True,
    )
    junctions, relationships=classify_junctions(
        graph, document_id="original-pdf-sha:"+source_sha,
        page_id=page_id, viewport_id=viewport_id,
    )
    walls, edge_owners=assemble_wall_candidates(
        graph, junctions, relationships,
        viewport_id=viewport_id,
        identity_abstention_shadow=True,
        abstained_chain_rows=[],
    )
    source_ids=sorted(s["source_observation_id"] for s in segments)
    return {
        "source_observation_ids":source_ids,
        "source_parent_observation_ids":sorted(
            s["source_parent_observation_id"] for s in segments),
        "w2_nodes":len(graph["nodes"]),
        "w2_surviving_edges":len(graph["edges"]),
        "w2_excluded_source_segments":len(graph["excluded_segments"]),
        "w2_snap_collapsed_fragments":len(graph["snap_collapsed_fragments"]),
        "w2_surviving_edge_geometry_pt":[
            [e["x1"],e["y1"],e["x2"],e["y2"]] for e in graph["edges"]],
        "w2_surviving_source_fragment_ids":[str(e.get("id")) for e in graph["edges"]],
        "w3_junction_types":sorted(j.junction_type.value for j in junctions),
        "w3_relationship_count":len(relationships),
        "w4_shadow_candidate_ids":sorted(w.candidate_id for w in walls),
        "w4_shadow_candidate_source_edges":sorted(edge_owners),
        "canonical_w4_wall_id_granted":False,
        "structural_wall_role_granted":False,
        "host_binding_granted":False,
    }


def original_g17_w2_w4_source_shadow(
    original_pdf: bytes, original_report: Mapping[str, Any],
    paint_report: Mapping[str, Any], *, page_id: str,
) -> dict[str, Any]:
    sha=hashlib.sha256(original_pdf).hexdigest()
    if (original_report.get("source_sha256")!=sha
            or paint_report.get("source_sha256")!=sha
            or original_report.get("primitive_safety_cap")!=20_000
            or paint_report.get("page_id")!=page_id):
        raise ValueError("original source SHA/cap/page contradictory")
    originals=original_report.get("unhosted_raster_flank_source_receipts")
    painted=paint_report.get("source_openings")
    if not isinstance(originals,list) or not isinstance(painted,list):
        raise ValueError("original authenticated G17 source report absent")
    source={r.get("physical_opening_id"):r for r in originals
            if r.get("page_id")==page_id}
    ink={r.get("physical_opening_id"):r for r in painted}
    if not source or set(source)!=set(ink) or len(source)!=len(originals) or len(ink)!=len(painted):
        raise ValueError("physical G17 identity/scope changed between original reports")
    if (paint_report.get("canonical_snapshot_modified") is not False
            or paint_report.get("physical_host_granted") is not False
            or paint_report.get("metric_area_or_count_granted") is not False):
        raise ValueError("source paint report purported to promote physical authority")
    output=[]
    for physical_id in sorted(source):
        original=source[physical_id]
        if original.get("source_sha256")!=sha or original.get("snapshot_id")!=original_report.get("snapshot_id"):
            raise ValueError("original source G17 snapshot not authenticated")
        flanks=source_only_closed_flanks(original)
        if not flanks["closed_source_flank_nomination"]:
            raise ValueError("original face/end graph incomplete")
        ink_rows=ink[physical_id].get("flanks")
        if not isinstance(ink_rows,list) or len(ink_rows)!=2:
            raise ValueError("incomplete original source ink proof")
        ink_by_source={tuple(sorted(v.get("source_observation_ids",()))):v
                       for v in ink_rows}
        if len(ink_by_source)!=2:
            raise ValueError("duplicate original paint face/end owners")
        sides=[]
        for flank in flanks["source_flank_boxes"]:
            ids=tuple(sorted(flank["source_observation_ids"]))
            if ids not in ink_by_source:
                raise ValueError("source observation G17 flank changed between proof stages")
            painted_side=ink_by_source[ids]
            if painted_side.get("source_bbox_pdf_pts") != flank.get("source_bbox_pdf_pts"):
                raise ValueError("original G17 source ink footprint changed")
            witness=painted_side.get("one_ended_G17_original_source_paint")
            if (not isinstance(witness,Mapping)
                    or sorted(witness.get("original_source_observation_ids",())) != list(ids)
                    or witness.get("structural_W2_or_W4_proven") is not False
                    or witness.get("host_or_frame_granted") is not False):
                raise ValueError("untrusted or promoted original G17 source paint")
            observation={
                "side":flank["side_in_original_source_order"],
                "source_observation_ids":list(ids),
                "source_ink_shadow_eligible":witness.get("source_one_end_shadow_eligible") is True,
                "source_ink_first_failure":witness.get("source_shadow_first_failure"),
                "default_w2_w3_w4":None,
                "exact_coordinate_w2_w3_w4":None,
                "source_wall_or_host_granted":False,
            }
            if observation["source_ink_shadow_eligible"]:
                if not (witness.get("source_original_rgb_solid") is True
                        and witness.get("source_vs_full_rgb_identical") is True
                        and witness.get("original_image_region_owned") is True):
                    raise ValueError("original source paint sign-off contradicted")
                lines=_original_flank_lines(original,flank)
                for name,tol in (("default_w2_w3_w4",DEFAULT_GAP_SNAP_TOLERANCE_PT),
                                 ("exact_coordinate_w2_w3_w4",0.0)):
                    observation[name]=_isolated_graph(
                        lines,source_sha=sha, physical_id=physical_id,
                        side=observation["side"],page_id=page_id,tolerance=tol)
            sides.append(observation)
        output.append({"physical_opening_id":physical_id,"flanks":sides,
                       "complete_host_proven":False,"metric_area_granted":False})
    return {
        "source_sha256":sha,"page_id":page_id,
        "original_g17_physical_openings":len(output),
        "individual_flanks":sum(len(v["flanks"]) for v in output),
        "source_flank_w2_w4_shadows":output,
        "global_w4_or_snapshot_modified":False,
        "physical_wall_or_opening_host_granted":False,
        "metric_quantity_or_count_granted":False,
        "sealed_customer_output_modified":False,
        "benchmark_accuracy_granted":False,
    }


def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf",type=Path,required=True)
    parser.add_argument("--source-report",type=Path,required=True)
    parser.add_argument("--source-paint-report",type=Path,required=True)
    parser.add_argument("--page-id",default="3")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    output=original_g17_w2_w4_source_shadow(
        args.pdf.read_bytes(),
        json.loads(args.source_report.read_text(encoding="utf-8")),
        json.loads(args.source_paint_report.read_text(encoding="utf-8")),
        page_id=args.page_id)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"sha":output["source_sha256"],
                      "source_flanks":output["individual_flanks"],
                      "source_wall_or_host_granted":False},sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
