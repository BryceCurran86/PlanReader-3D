"""Original native source-primitive correspondence for measured plan room side ink.

Read-only first-failure audit. A native line, W4 wall candidate, translation
or exact geometric match is NOT a structural physical wall identity. No
material, metric, quantity, customer identity or frozen benchmark publication.
Never filters source candidates using target room names, finish codes or areas.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from tools.diag_ft3_p11_p7_floor_correspondence import (
    AXIS_TOL, COORD_TOL, MARK_PAGE, SOURCE_PAGE,
    _capture_measured_floors, _native_segments, _verify_source,
    _w4_non_grid_evidence, build_lines, rank_registrations,
    merge_intervals, interval_iou,
)


def indexed_original_native_primitives(
    segments: Sequence[Mapping[str, Any]],
) -> Mapping[str, Mapping[str, Any]]:
    """Never overwrite different PDF native primitives with the same address."""
    out = {}
    for segment in segments:
        identity = segment.get("id")
        if type(identity) is not str or not identity or identity in out:
            raise ValueError("missing or duplicate original indexed PDF primitive")
        out[identity] = segment
    return out


def source_fragments_on_documented_side(
    box: Sequence[float], side: str,
    originals: Mapping[str, Mapping[str, Any]],
    native_owners: Mapping[str, Sequence[str]],
    grid_opposition: Mapping[str, bool],
) -> list[dict[str, Any]]:
    """Retain EVERY indexed original segment along one figured box side."""
    if (
        len(box) != 4 or
        any(type(x) not in (float, int) or not math.isfinite(x) for x in box) or
        box[2] <= box[0] or box[3] <= box[1]
    ):
        raise ValueError("unresolved native figured box")
    x0, y0, x1, y1 = map(float, box)
    positions = {
        "x0": ("V", x0, y0, y1),
        "x1": ("V", x1, y0, y1),
        "y0": ("H", y0, x0, x1),
        "y1": ("H", y1, x0, x1),
    }
    if side not in positions:
        raise ValueError("unknown figured side")
    axis, fixed, low, high = positions[side]
    found = []
    for original_id, segment in sorted(originals.items()):
        a, b, c, d = (
            float(segment[k]) for k in ("x1", "y1", "x2", "y2")
        )
        if not all(map(math.isfinite, (a, b, c, d))):
            continue
        if axis == "V":
            if abs(a-c) > AXIS_TOL or abs(a-fixed) > COORD_TOL:
                continue
            lo, hi = sorted((b, d))
        else:
            if abs(b-d) > AXIS_TOL or abs(b-fixed) > COORD_TOL:
                continue
            lo, hi = sorted((a, c))
        lo, hi = max(low,lo), min(high,hi)
        if hi <= lo:
            continue
        owners = sorted(set(native_owners.get(original_id, ())))
        found.append({
            "native_primitive_id": original_id,
            "source_clipped_interval_pdf_pts": [lo,hi],
            "exact_original_w4_candidate_ids": owners,
            "source_w4_candidate_count": len(owners),
            "typed_grid_opposed_owner_ids": [
                candidate for candidate in owners
                if grid_opposition.get(candidate, False)
            ],
            "source_physical_wall_role_granted": False,
        })
    return found


def compare_indexed_original_side(
    support: Sequence[Mapping[str, Any]],
    target: Sequence[Mapping[str, Any]],
    *,
    shift_along_side: float,
) -> dict[str, Any]:
    """Every overlapping native ink hypothesis; no closest/winner election."""
    if not math.isfinite(float(shift_along_side)):
        raise ValueError("non-finite source registration")
    source_intervals = merge_intervals(
        row["source_clipped_interval_pdf_pts"] for row in support
    )
    target_intervals = merge_intervals(
        [lo - shift_along_side, hi - shift_along_side]
        for row in target
        for lo,hi in (row["source_clipped_interval_pdf_pts"],)
    )
    matches = []
    for a in support:
        for b in target:
            lo = max(a["source_clipped_interval_pdf_pts"][0],
                     b["source_clipped_interval_pdf_pts"][0] - shift_along_side)
            hi = min(a["source_clipped_interval_pdf_pts"][1],
                     b["source_clipped_interval_pdf_pts"][1] - shift_along_side)
            if hi > lo:
                matches.append({
                    "support_original_native_primitive_id": a["native_primitive_id"],
                    "target_original_native_primitive_id": b["native_primitive_id"],
                    "exact_intersection_in_support_pdf_pts": [lo,hi],
                    "original_source_only_not_physical_wall": True,
                })
    unowned = {
        "support": [r["native_primitive_id"] for r in support if r["source_w4_candidate_count"] == 0],
        "target": [r["native_primitive_id"] for r in target if r["source_w4_candidate_count"] == 0],
    }
    ambiguous = {
        "support": [r["native_primitive_id"] for r in support if r["source_w4_candidate_count"] > 1],
        "target": [r["native_primitive_id"] for r in target if r["source_w4_candidate_count"] > 1],
    }
    grid = {
        "support": [r["native_primitive_id"] for r in support if r["typed_grid_opposed_owner_ids"]],
        "target": [r["native_primitive_id"] for r in target if r["typed_grid_opposed_owner_ids"]],
    }
    blockers = []
    if not support or not target:
        blockers.append("indexed_original_side_ink_missing")
    if unowned["support"] or unowned["target"]:
        blockers.append("indexed_original_source_unowned_by_w4")
    if ambiguous["support"] or ambiguous["target"]:
        blockers.append("indexed_original_source_multiowned_by_w4")
    if grid["support"] or grid["target"]:
        blockers.append("typed_grid_opposition_present")
    if not matches:
        blockers.append("no_exact_original_native_overlap_after_registration")
    # Perfect geometric overlap never authenticates structural wall role,
    # and segment multiplicity cannot be silently collapsed into one owner.
    blockers.append("cross_page_physical_structural_wall_equivalence_unproven")
    return {
        "source_native_ink_interval_iou": interval_iou(source_intervals,target_intervals),
        "original_support_native_fragments": list(support),
        "original_target_native_fragments": list(target),
        "all_original_native_ink_overlap_pairs": matches,
        "native_unowned_ids": unowned,
        "native_multiowner_ids": ambiguous,
        "typed_grid_opposed_ids": grid,
        "source_role_first_failure_reasons": blockers,
        "physical_wall_or_room_equivalence_granted": False,
        "new_metric_or_material_quantity": False,
    }


def original_source_side_pair_census(
    pdf: Path, *, expected_sha256: str,
) -> dict[str, Any]:
    """One SHA-pinned original-source pass; source text never elects a wall."""
    payload,sha = _verify_source(pdf)
    if sha != expected_sha256:
        raise ValueError("original source sha mismatch")
    evidence = _w4_non_grid_evidence(payload,sha)
    native = {
        page:indexed_original_native_primitives(_native_segments(payload,page))
        for page in (SOURCE_PAGE,MARK_PAGE)
    }
    lines = {
        page:build_lines(
            native[page][identity] for identity in evidence[str(page)]["primitive_ids"]
            if identity in native[page]
        ) for page in (SOURCE_PAGE,MARK_PAGE)
    }
    contenders = rank_registrations(lines[MARK_PAGE],lines[SOURCE_PAGE])
    if not contenders:
        raise ValueError("no source-owned registration candidate")
    best=contenders[0]
    translation = (best["dx"],best["dy"])
    measured=_capture_measured_floors(pdf)
    reports=[]
    for area in measured["measured_rooms"]:
        box=area.get("source_dimension_box_pdf_pts")
        if str(area.get("source_dimension_page_id"))!=str(MARK_PAGE) or not box:
            continue
        if best["orientation"]!="identity" or best["scale"]!=1.0:
            reports.append({
                "canonical_floor_id":area["canonical_floor_id"],
                "reason":"original_wall_registration_not_identity_unit",
                "physical_floor_correspondence_granted":False,
            })
            continue
        target_box=[
            float(box[0])+translation[0],float(box[1])+translation[1],
            float(box[2])+translation[0],float(box[3])+translation[1],
        ]
        sides={}
        for side in ("x0","x1","y0","y1"):
            before=source_fragments_on_documented_side(
                box,side,native[MARK_PAGE],
                evidence[str(MARK_PAGE)]["primitive_owners"],
                evidence[str(MARK_PAGE)]["grid_flags"],
            )
            after=source_fragments_on_documented_side(
                target_box,side,native[SOURCE_PAGE],
                evidence[str(SOURCE_PAGE)]["primitive_owners"],
                evidence[str(SOURCE_PAGE)]["grid_flags"],
            )
            sides[side]=compare_indexed_original_side(
                before,after,
                shift_along_side=translation[1] if side[0]=="x" else translation[0],
            )
        reports.append({
            "original_floor_area_source_evidence_id":area["area_evidence_id"],
            "source_room_face_record_id":area["source_room_face_record_id"],
            "canonical_floor_id":area["canonical_floor_id"],
            "original_support_dimension_box_pdf_pts":box,
            "native_wall_registration_candidate":translation,
            "original_w4_source_pages_scope_complete":{
                str(page):bool(evidence[str(page)]["w4_scope_complete"])
                for page in (SOURCE_PAGE,MARK_PAGE)
            },
            "source_original_wall_side_provenance":sides,
            "physical_floor_correspondence_granted":False,
            "material_occurrence_granted":False,
        })
    return {
        "source_sha256":sha,
        "source_pages":[SOURCE_PAGE,MARK_PAGE],
        "source_evidence_only":True,
        "wall_registration_candidate":best,
        "all_source_measured_room_side_reports":reports,
        "new_physical_wall_or_room_equivalence_granted":False,
        "new_floor_finish_quantities":0,
        "new_signed_customer_rows":0,
        "frozen_v2_expected_or_truth_used":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf",type=Path,required=True)
    p.add_argument("--sha256",required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    result=original_source_side_pair_census(args.pdf,expected_sha256=args.sha256)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({
        "sha":result["source_sha256"],
        "measured_original_room_reports":len(result["all_source_measured_room_side_reports"]),
        "floor_by_floor_side_blockers":[{
            "canonical_floor_id":room["canonical_floor_id"],
            "sides":{key:val["source_role_first_failure_reasons"] for key,val in
                room.get("source_original_wall_side_provenance",{}).items()},
        } for room in result["all_source_measured_room_side_reports"]],
        "source_wall_or_room_equivalence_granted":False,
        "quantities":0,
    },sort_keys=True))


if __name__=="__main__":
    main()
