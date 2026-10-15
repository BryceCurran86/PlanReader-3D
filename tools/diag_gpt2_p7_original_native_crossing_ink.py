"""Original PDF exact native line/rectangle ink census for source W4 edge queries.

Caller provides already source-receipted atom edge coordinates. No physical
wall identity, room polygon, area or customer output is issued by this tool.
A negative concerns original indexed LINE/RECT spans only; curved/filled raster
ink and its source-visible status are separate independent authorities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz
from tools.diag_gpt2_native_w2_ink_source_role import (
    _valid_edge, read_native_ink_receipt,
)


def census_original_native_linear_ink(drawings, *, source_atoms):
    if not isinstance(drawings, (list, tuple)) or not drawings:
        raise ValueError("original_native_drawing_universe_unavailable")
    atoms=[]
    for source_atom in source_atoms:
        atom=_valid_edge(source_atom)
        if atom in atoms:
            raise ValueError("duplicate_original_producer_atom_query")
        atoms.append(atom)
    if not atoms:
        raise ValueError("missing_original_producer_atom_queries")
    unsupported=0
    searchable=0
    degenerate_original_linear_refs=set()
    reports=[]
    for atom in atoms:
        matches=[]
        for path, drawing in enumerate(drawings):
            for index, item in enumerate(drawing.get("items") or []):
                if not item or item[0] not in ("l","re"):
                    unsupported+=1
                    continue
                edge_indexes = (None,) if item[0]=="l" else (0,1,2,3)
                for side in edge_indexes:
                    primitive_id=f"d{path}i{index}"
                    if side is not None:
                        primitive_id+=f"e{side}"
                    try:
                        receipt=read_native_ink_receipt(drawings,primitive_id,atom)
                    except ValueError as exc:
                        # Original PDF can contain zero-area rectangles and
                        # same-endpoint lines. Retain exact rejected source ID,
                        # without treating it as a missing real ink witness.
                        if str(exc)!="selected native wall edge invalid":
                            raise
                        degenerate_original_linear_refs.add(primitive_id)
                        continue
                    searchable+=1
                    if receipt["native_stroke_fully_covers_atomic_wall_candidate"]:
                        matches.append(receipt)
                        if len(matches)>10000:
                            raise ValueError("original_native_linear_ink_candidate_safety_bound")
        matches.sort(key=lambda x:(
            x["original_path_index"],x["original_item_index"],
            -1 if x["original_rectangle_edge_index"] is None
            else x["original_rectangle_edge_index"]))
        reports.append({
            "original_source_candidate_atom_pdf_pts":[list(p) for p in atom],
            "original_indexed_linear_native_full_span_count":len(matches),
            "original_indexed_native_linear_receipts":matches,
            "native_full_span_observed_not_structural_authority":True,
            "source_structural_wall_role_authenticated":False,
            "source_room_ring_closed":False,
            "metric_quantity_published":False,
        })
    return {
        "source_query_atom_count":len(atoms),
        "original_native_indexed_drawing_path_count":len(drawings),
        "original_linear_rect_source_primitive_checks":searchable,
        "original_indexed_degenerate_linear_source_ids":sorted(
            degenerate_original_linear_refs
        ),
        "original_indexed_degenerate_linear_source_count":len(
            degenerate_original_linear_refs
        ),
        "other_native_element_count_not_assessed":unsupported,
        "source_native_linear_ink_queries":reports,
        "all_original_source_line_rect_items_examined":True,
        "complete_native_ink_universe_including_curves_raster":False,
        "source_role_or_room_authentication_granted":False,
        "new_commercial_quantities":[],
        "frozen_benchmark_scored":False,
        "diagnostic_only":True,
    }




def census_original_native_partial_linear_ink(drawings, *, source_atoms):
    """Report *all* original indexed line/rect parts on queried atom spans.

    Completeness is only for this native geometric subuniverse. Even a
    zero-gap stroke-painted union does not authenticate wall/room roles.
    """
    import math

    if not isinstance(drawings, (list, tuple)) or not drawings:
        raise ValueError("original_native_drawing_universe_unavailable")
    atoms = [_valid_edge(atom) for atom in source_atoms]
    if not atoms:
        raise ValueError("missing_original_producer_atom_queries")
    if len(set(atoms)) != len(atoms):
        raise ValueError("duplicate_original_producer_atom_query")
    eps = 0.0001

    def coverage(parts, length):
        intervals = sorted(
            (float(row["overlap_start_pt"]), float(row["overlap_end_pt"]))
            for row in parts
        )
        gaps = []
        reached = 0.
        for lo, hi in intervals:
            if lo > reached + eps:
                gaps.append([reached, lo])
            reached = max(reached, hi)
        if reached < length - eps:
            gaps.append([reached, length])
        return {
            "source_part_interval_count": len(intervals),
            "source_query_gaps_pt": gaps,
            "source_query_geometrically_covered_diagnostic_only": (
                len(gaps) == 0
            ),
        }

    original = []
    invalid = set()
    for path, drawing in enumerate(drawings):
        for idx, item in enumerate(drawing.get("items") or ()):
            if not item or item[0] not in ("l", "re"):
                continue
            shape = str(item[0])
            sides = (None,) if shape == "l" else (0, 1, 2, 3)
            for side in sides:
                src_id = f"d{path}i{idx}" + (
                    "" if side is None else f"e{side}"
                )
                try:
                    if shape == "l":
                        points = (
                            (float(item[1].x), float(item[1].y)),
                            (float(item[2].x), float(item[2].y)),
                        )
                    else:
                        box = fitz.Rect(item[1])
                        vertices = (
                            (float(box.x0), float(box.y0)),
                            (float(box.x1), float(box.y0)),
                            (float(box.x1), float(box.y1)),
                            (float(box.x0), float(box.y1)),
                        )
                        points = (vertices[side], vertices[(side + 1) % 4])
                    a, b = _valid_edge(points)
                except (IndexError, KeyError, AttributeError, TypeError, ValueError,
                        OverflowError):
                    invalid.add(src_id)
                    continue
                original.append((src_id, a, b, drawing))
    reports = []
    for start, stop in atoms:
        vx = stop[0] - start[0]
        vy = stop[1] - start[1]
        length = math.hypot(vx, vy)
        ux, uy = vx / length, vy / length
        parts = []
        for ref, p, q, drawing in original:
            normal_p = abs((p[0] - start[0]) * uy - (p[1] - start[1]) * ux)
            normal_q = abs((q[0] - start[0]) * uy - (q[1] - start[1]) * ux)
            if max(normal_p, normal_q) > eps:
                continue
            t0 = (p[0] - start[0]) * ux + (p[1] - start[1]) * uy
            t1 = (q[0] - start[0]) * ux + (q[1] - start[1]) * uy
            lo, hi = max(0., min(t0, t1)), min(length, max(t0, t1))
            if hi - lo <= eps:
                continue
            ink_kind = str(drawing.get("type") or "")
            parts.append({
                "original_native_primitive_ref": ref,
                "native_source_edge_pdf_pts": [list(p), list(q)],
                "overlap_start_pt": lo,
                "overlap_end_pt": hi,
                "native_drawing_kind": ink_kind,
                "source_ink_stroked": ink_kind in ("s", "fs"),
                "source_ink_fill_only": ink_kind == "f",
                "native_stroke_color": drawing.get("color"),
                "native_fill_color": drawing.get("fill"),
                "native_layer": drawing.get("layer"),
                "original_ink_segment_not_structural_role": True,
            })
            if len(parts) > 10000:
                raise ValueError("original_native_partial_source_safety_bound")
        parts.sort(key=lambda row: (
            row["overlap_start_pt"], row["overlap_end_pt"],
            row["original_native_primitive_ref"],
        ))
        stroke_parts = [p for p in parts if p["source_ink_stroked"]]
        reports.append({
            "original_source_candidate_atom_pdf_pts": [list(start), list(stop)],
            "original_native_linear_partial_receipts": parts,
            "all_native_paint_geometric_coverage": coverage(parts, length),
            "stroke_only_geometric_coverage": coverage(stroke_parts, length),
            "source_structural_wall_role_authenticated": False,
            "source_room_ring_closed": False,
            "metric_quantity_published": False,
        })
    return {
        "source_query_atom_count": len(atoms),
        "original_indexed_native_line_rect_primitive_count": len(original),
        "original_invalid_native_line_rect_refs": sorted(invalid),
        "all_original_native_line_rect_items_examined": True,
        "complete_ink_universe_including_raster_clip_and_curves": False,
        "source_native_linear_partial_queries": reports,
        "source_structural_wall_role_authenticated": False,
        "new_commercial_quantities": [],
        "diagnostic_only": True,
    }


def census_original_native_cubic_ink(drawings, *, source_atoms):
    """Enumerate complete indexed cubic ink, not walls or room boundaries.

    Only an exactly straight-equivalent cubic whose source-native endpoints
    bracket both queried atom endpoints can be a candidate. No inference
    from bounding boxes, chord-only comparisons or stroked appearance.
    """
    import math

    if not isinstance(drawings, (list, tuple)) or not drawings:
        raise ValueError("original_native_drawing_universe_unavailable")
    atoms = [_valid_edge(value) for value in source_atoms]
    if not atoms:
        raise ValueError("missing_original_producer_atom_queries")
    if len(set(atoms)) != len(atoms):
        raise ValueError("duplicate_original_producer_atom_query")

    # Source's existing exact primitive span check uses 0.0001 PDF pt.
    # The same bound is applied to the FULL cubic control polygon.
    eps = 0.0001
    originals = []
    malformed_ids = []
    for path, drawing in enumerate(drawings):
        for index, item in enumerate(drawing.get("items") or ()):
            if not item or item[0] != "c":
                continue
            source_id = f"d{path}i{index}"
            try:
                if len(item) != 5:
                    raise ValueError("unexpected_cubic_format")
                points = tuple(
                    (float(point.x), float(point.y)) for point in item[1:5]
                )
                if not all(math.isfinite(v) for point in points for v in point):
                    raise ValueError("nonfinite_cubic_source")
            except (AttributeError, ValueError, TypeError, OverflowError):
                malformed_ids.append(source_id)
                continue
            originals.append((source_id, points, drawing))

    rows = []
    for atom in atoms:
        start, stop = atom
        dx = stop[0] - start[0]
        dy = stop[1] - start[1]
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        matches = []
        for source_id, points, drawing in originals:
            along = tuple(
                (point[0] - start[0]) * ux + (point[1] - start[1]) * uy
                for point in points
            )
            normal = tuple(
                abs((point[0] - start[0]) * uy - (point[1] - start[1]) * ux)
                for point in points
            )
            # Bezier lies along the queried line *only* if all controls do;
            # two actual endpoints must span the entire atom, not merely the
            # control polygon's bounding box.
            if (
                max(normal) > eps
                or min(along[0], along[3]) > eps
                or max(along[0], along[3]) < length - eps
                or abs(along[0] - along[3]) <= eps
            ):
                continue
            kind = str(drawing.get("type", ""))
            matches.append({
                "original_native_curve_ref": source_id,
                "native_control_points_pdf_pts": [list(p) for p in points],
                "native_drawing_kind": kind,
                "source_layer": drawing.get("layer"),
                "source_stroke": drawing.get("color"),
                "source_fill": drawing.get("fill"),
                "original_stroked_cubic": kind in ("s", "fs"),
                "strict_collinear_fullspan_candidate_not_wall": True,
            })
            if len(matches) > 10000:
                raise ValueError("original_native_curve_candidate_safety_bound")
        rows.append({
            "queried_original_atom_pdf_pts": [list(p) for p in atom],
            "original_indexed_cubic_full_span_count": len(matches),
            "original_indexed_cubic_candidate_receipts": sorted(
                matches, key=lambda q: q["original_native_curve_ref"]
            ),
            "physical_wall_or_room_role_granted": False,
        })
    return {
        "source_query_atom_count": len(atoms),
        "all_original_native_cubic_items_examined": True,
        "original_native_cubic_item_count": len(originals) + len(malformed_ids),
        "invalid_native_cubic_source_ids": sorted(malformed_ids),
        "source_native_cubic_ink_queries": rows,
        "complete_source_universe_including_raster_or_clip": False,
        "physical_wall_or_room_role_granted": False,
        "metric_quantities_published": 0,
        "diagnostic_only": True,
    }


def replay_original_source(pdf_bytes: bytes,*, original_sha256: str,
                           page_no: int, source_atoms):
    if type(pdf_bytes) is not bytes or type(page_no) is not int or page_no<1:
        raise ValueError("original_source_pdf_bytes_and_page_required")
    actual=hashlib.sha256(pdf_bytes).hexdigest()
    if actual!=original_sha256:
        raise ValueError("original_source_sha_mismatch")
    with fitz.open(stream=pdf_bytes,filetype="pdf") as doc:
        if page_no>doc.page_count:
            raise ValueError("original_source_page_missing")
        native_drawings=doc[page_no-1].get_drawings()
        result=census_original_native_linear_ink(
            native_drawings,source_atoms=source_atoms
        )
        result["original_native_cubic_ink_shadow"]=census_original_native_cubic_ink(
            native_drawings,source_atoms=source_atoms
        )
        result["original_native_linear_partial_ink_shadow"]=census_original_native_partial_linear_ink(
            native_drawings,source_atoms=source_atoms
        )
        result["original_pdf_page_count"]=doc.page_count
    result["original_source_sha256"]=actual
    result["original_page"]=page_no
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf",type=Path,required=True)
    p.add_argument("--sha",required=True)
    p.add_argument("--page",type=int,required=True)
    p.add_argument("--original-w4-edges-json",required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    report=replay_original_source(
        args.pdf.read_bytes(), original_sha256=args.sha,page_no=args.page,
        source_atoms=json.loads(args.original_w4_edges_json),
    )
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("GPT2_ORIGINAL_P7_W4_NATIVE_LINEAR_FIRSTGATE",json.dumps({
        "source_sha256":report["original_source_sha256"],
        "page":report["original_page"],
        "indexed_source_fullspan_counts":[
            row["original_indexed_linear_native_full_span_count"]
            for row in report["source_native_linear_ink_queries"]
        ],
        "source_structural_wall_role_authenticated":False,
        "indexed_exact_native_cubic_fullspan_counts":[
            row["original_indexed_cubic_full_span_count"]
            for row in report["original_native_cubic_ink_shadow"]["source_native_cubic_ink_queries"]
        ],
        "indexed_native_stroke_only_partial_gap_counts":[
            len(row["stroke_only_geometric_coverage"]["source_query_gaps_pt"])
            for row in report["original_native_linear_partial_ink_shadow"]["source_native_linear_partial_queries"]
        ],
        "new_commercial_quantities":[],
    },sort_keys=True))


if __name__=="__main__":
    main()
