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
    merge_intervals, interval_iou, D4,
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
        if (
            not isinstance(segment, Mapping)
            or any(
                key not in segment
                or type(segment[key]) not in (float, int)
                or not math.isfinite(segment[key])
                for key in ("x1", "y1", "x2", "y2")
            )
        ):
            # A corrupt indexed native primitive is a missing source record,
            # never a reason to silently obtain a cleaner-looking side.
            raise ValueError("invalid indexed original PDF source segment")
        a, b, c, d = (
            float(segment[k]) for k in ("x1", "y1", "x2", "y2")
        )
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



_MAX_RANKED_HYPOTHESES = 128


def ranked_original_registrations(
    contenders: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Keep every ranked D4/scale result and its distinct translation.

    The upstream vote search is deliberately finite and NOT an exhaustive
    registration proof. An absent alternative is never positive uniqueness.
    This report is an inventory, not a selection of physical correspondence.
    """
    if isinstance(contenders, (str, bytes)) or not isinstance(contenders, Sequence):
        raise ValueError("invalid registration candidate universe")
    hypotheses = []
    for record in contenders:
        if not isinstance(record, Mapping):
            raise ValueError("invalid registration hypothesis")
        orientation = record.get("orientation")
        scale = record.get("scale")
        dx, dy = record.get("dx"), record.get("dy")
        if (
            orientation not in D4
            or any(type(v) not in (int, float) or not math.isfinite(v)
                   for v in (scale, dx, dy))
            or scale <= 0
        ):
            raise ValueError("invalid registration hypothesis")
        support = record.get("min_support_pt")
        if type(support) not in (int, float) or not math.isfinite(support) or support < 0:
            raise ValueError("invalid registration support")
        alternative = record.get("next_distinct_translation")
        rows = [("best", float(dx), float(dy), float(support))]
        if alternative is not None:
            if (
                type(alternative) not in (list, tuple) or len(alternative) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v)
                       for v in alternative)
            ):
                raise ValueError("invalid competing source registration")
            next_support = record.get("next_distinct_min_support_pt")
            if (
                type(next_support) not in (int, float)
                or not math.isfinite(next_support) or next_support < 0
            ):
                raise ValueError("invalid competing registration support")
            if (float(alternative[0]), float(alternative[1])) != (float(dx), float(dy)):
                rows.append((
                    "next_distinct", float(alternative[0]),
                    float(alternative[1]), float(next_support),
                ))
        for role, cx, cy, strength in rows:
            hypotheses.append({
                "orientation": orientation,
                "scale": float(scale),
                "dx": cx,
                "dy": cy,
                "min_support_pt": strength,
                "translation_role": role,
                "candidate_not_authenticated_registration": True,
            })
            if len(hypotheses) > _MAX_RANKED_HYPOTHESES:
                raise ValueError("registration candidate inventory over safety bound")
    return sorted(
        hypotheses,
        key=lambda r: (
            -r["min_support_pt"], r["orientation"], r["scale"],
            r["dx"], r["dy"], r["translation_role"],
        ),
    )


def registration_side_geometry(
    box: Sequence[float], side: str, candidate: Mapping[str, Any],
) -> tuple[tuple[float, float, float, float], str, float, float]:
    """Map an original source side under ALL D4 and uniform-scale candidates.

    The returned affine formula maps the original PDF-point along-side value
    to the target side. It is invertible, so the target original ink can be
    compared in the support sheet's original coordinates without a heuristic
    nearest-wall match or a change to either source PDF.
    """
    if (
        type(box) not in (tuple, list) or len(box) != 4
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
        or box[2] <= box[0] or box[3] <= box[1]
    ):
        raise ValueError("unresolved native figured box")
    if side not in ("x0", "x1", "y0", "y1"):
        raise ValueError("unknown figured side")
    orientation = candidate.get("orientation")
    if orientation not in D4:
        raise ValueError("unknown original registration orientation")
    scale = candidate.get("scale")
    dx, dy = candidate.get("dx"), candidate.get("dy")
    if (
        any(type(v) not in (int, float) or not math.isfinite(v)
            for v in (scale, dx, dy)) or scale <= 0
    ):
        raise ValueError("invalid source registration transform")
    a, b, c, d = D4[orientation]
    scale, dx, dy = float(scale), float(dx), float(dy)

    def move(point):
        x, y = point
        return (scale * (a*x+b*y)+dx, scale * (c*x+d*y)+dy)

    x0, y0, x1, y1 = map(float, box)
    transformed = [move(p) for p in (
        (x0,y0), (x0,y1), (x1,y0), (x1,y1),
    )]
    target_box = (
        min(p[0] for p in transformed), min(p[1] for p in transformed),
        max(p[0] for p in transformed), max(p[1] for p in transformed),
    )
    source_ends = {
        "x0": ((x0,y0),(x0,y1)),
        "x1": ((x1,y0),(x1,y1)),
        "y0": ((x0,y0),(x1,y0)),
        "y1": ((x0,y1),(x1,y1)),
    }
    start, end = source_ends[side]
    first, last = move(start), move(end)
    if abs(first[0]-last[0]) <= 1e-8:
        fixed = (first[0]+last[0])/2
        target_side = "x0" if abs(fixed-target_box[0]) < 1e-8 else "x1"
        target_values = (first[1],last[1])
    elif abs(first[1]-last[1]) <= 1e-8:
        fixed = (first[1]+last[1])/2
        target_side = "y0" if abs(fixed-target_box[1]) < 1e-8 else "y1"
        target_values = (first[0],last[0])
    else:
        raise ValueError("non orthogonal source side transform")
    original_values = (
        (start[1], end[1]) if side[0] == "x" else (start[0],end[0])
    )
    slope = (target_values[1]-target_values[0]) / (
        original_values[1]-original_values[0]
    )
    offset = target_values[0]-slope*original_values[0]
    if abs(slope) <= 1e-12 or not all(
        map(math.isfinite, (*target_box, slope, offset))
    ):
        raise ValueError("degenerate source side registration")
    return target_box, target_side, slope, offset


def compare_side_under_affine(
    support: Sequence[Mapping[str, Any]],
    target: Sequence[Mapping[str, Any]],
    *,
    slope: float, offset: float,
) -> dict[str, Any]:
    """Compare every source span with every target span under one hypothesis.

    This normalizes the target's original PDF coordinate into support
    coordinates, preserving negative slopes and complete source multiplicity.
    """
    if (
        any(type(v) not in (int, float) or not math.isfinite(v)
            for v in (slope, offset)) or slope == 0
    ):
        raise ValueError("noninvertible original source registration")
    def in_support(row):
        lo, hi = row["source_clipped_interval_pdf_pts"]
        return sorted(((lo-offset)/slope, (hi-offset)/slope))
    source_intervals = merge_intervals(
        row["source_clipped_interval_pdf_pts"] for row in support
    )
    target_intervals = merge_intervals(in_support(row) for row in target)
    matches = []
    for left in support:
        for right in target:
            low, high = in_support(right)
            lo = max(left["source_clipped_interval_pdf_pts"][0], low)
            hi = min(left["source_clipped_interval_pdf_pts"][1], high)
            if hi > lo:
                matches.append({
                    "support_original_native_primitive_id":left["native_primitive_id"],
                    "target_original_native_primitive_id":right["native_primitive_id"],
                    "exact_intersection_in_support_pdf_pts":[lo,hi],
                    "original_source_only_not_physical_wall":True,
                })
    unowned = {
        "support":[r["native_primitive_id"] for r in support
                   if r["source_w4_candidate_count"]==0],
        "target":[r["native_primitive_id"] for r in target
                  if r["source_w4_candidate_count"]==0],
    }
    multiowner = {
        "support":[r["native_primitive_id"] for r in support
                   if r["source_w4_candidate_count"]>1],
        "target":[r["native_primitive_id"] for r in target
                  if r["source_w4_candidate_count"]>1],
    }
    grid = {
        "support":[r["native_primitive_id"] for r in support
                   if r["typed_grid_opposed_owner_ids"]],
        "target":[r["native_primitive_id"] for r in target
                  if r["typed_grid_opposed_owner_ids"]],
    }
    blockers = []
    if not support or not target:
        blockers.append("indexed_original_side_ink_missing")
    if unowned["support"] or unowned["target"]:
        blockers.append("indexed_original_source_unowned_by_w4")
    if multiowner["support"] or multiowner["target"]:
        blockers.append("indexed_original_source_multiowned_by_w4")
    if grid["support"] or grid["target"]:
        blockers.append("typed_grid_opposition_present")
    if not matches:
        blockers.append("no_exact_original_native_overlap_after_registration")
    blockers.append("cross_page_physical_structural_wall_equivalence_unproven")
    return {
        "source_native_ink_interval_iou":interval_iou(source_intervals,target_intervals),
        "original_support_native_fragments":list(support),
        "original_target_native_fragments":list(target),
        "all_original_native_ink_overlap_pairs":matches,
        "native_unowned_ids":unowned,
        "native_multiowner_ids":multiowner,
        "typed_grid_opposed_ids":grid,
        "source_role_first_failure_reasons":blockers,
        "physical_wall_or_room_equivalence_granted":False,
        "new_metric_or_material_quantity":False,
    }


def audit_registration_candidate_sides(
    box: Sequence[float], candidate: Mapping[str, Any],
    *,
    native_support: Mapping[str, Mapping[str, Any]],
    native_target: Mapping[str, Mapping[str, Any]],
    owners_support: Mapping[str, Sequence[str]],
    owners_target: Mapping[str, Sequence[str]],
    grid_support: Mapping[str, bool],
    grid_target: Mapping[str, bool],
) -> dict[str, Any]:
    """Every original native side/owner/grid rival for one registered box."""
    sides = {}
    for side in ("x0","x1","y0","y1"):
        target_box, target_side, slope, offset = registration_side_geometry(
            box, side, candidate,
        )
        before = source_fragments_on_documented_side(
            box, side, native_support, owners_support, grid_support
        )
        after = source_fragments_on_documented_side(
            target_box, target_side, native_target, owners_target, grid_target
        )
        row = compare_side_under_affine(
            before, after, slope=slope, offset=offset,
        )
        row["target_side_name"] = target_side
        row["source_to_target_along_affine"] = [slope, offset]
        sides[side] = row
    return {
        "registration_hypothesis":dict(candidate),
        "source_original_wall_side_provenance":sides,
        "candidate_physical_registration_elected":False,
        "cross_page_physical_room_equivalence_granted":False,
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
    all_hypotheses = ranked_original_registrations(contenders)
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
        alternatives = [
            audit_registration_candidate_sides(
                box, candidate,
                native_support=native[MARK_PAGE],
                native_target=native[SOURCE_PAGE],
                owners_support=evidence[str(MARK_PAGE)]["primitive_owners"],
                owners_target=evidence[str(SOURCE_PAGE)]["primitive_owners"],
                grid_support=evidence[str(MARK_PAGE)]["grid_flags"],
                grid_target=evidence[str(SOURCE_PAGE)]["grid_flags"],
            )
            for candidate in all_hypotheses
        ]
        reports.append({
            "original_source_registration_competing_side_reports": alternatives,
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
        "all_ranked_registration_hypotheses":all_hypotheses,
        "hypothesis_search_exhaustive":False,
        "physical_registration_elected":False,
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
