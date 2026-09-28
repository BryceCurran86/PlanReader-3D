"""Real-source representative census with double-face publication check.

Runs the production W4 pipeline on one page and reports the equivalence
census, plus an explicit search for two faces of one wall body both reaching
representative status.

Read-only diagnostic. Page numbers are CLI arguments; nothing is
special-cased. No benchmark expected values, scoring, or tolerances.
"""
from __future__ import annotations

import math
import sys
from collections import Counter
from pathlib import Path

import fitz

from pb_physical_wall_identity import (
    PhysicalEquivalenceClass,
    _parallel_overlap_separation,
    _segments,
    collect_physical_wall_identities,
    max_plausible_wall_body_separation_pt,
    resolve_physical_wall_equivalence,
)
from pb_vector_geometry_v130 import extract_native_page
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    is_authoritative_derived_viewport,
    segment_page_viewports,
    validate_non_overlapping_viewports,
)
from pb_wall_room_topology_junction_classifier import (
    DEFAULT_COLLINEAR_ANGLE_TOLERANCE_DEG,
    classify_junctions,
)
from pb_wall_room_topology_stage_a import (
    DEFAULT_GAP_SNAP_TOLERANCE_PT,
    build_wall_graph_for_viewport,
)
from pb_wall_room_topology_wall_assembly import assemble_wall_topology

SAME = PhysicalEquivalenceClass.SAME_PHYSICAL_WALL.value
DISTINCT = PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS.value
AMBIGUOUS = PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value


def _inside(seg, bbox):
    x0, y0, x1, y1 = bbox
    return (
        x0 <= float(seg["x1"]) <= x1
        and y0 <= float(seg["y1"]) <= y1
        and x0 <= float(seg["x2"]) <= x1
        and y0 <= float(seg["y2"]) <= y1
    )


def _seg_len(seg):
    return math.hypot(seg[2] - seg[0], seg[3] - seg[1])


def _double_face_representatives(identities_by_id, representatives):
    """Published representative pairs sharing wall-body-like geometry.

    Returns (genuine, marginal).

    ``genuine`` is a conservative potential double-face signature:
    parallel published representatives whose longitudinal overlap is
    meaningful.  This read-only census has no producer-owned physical scale,
    so it deliberately applies no absolute source-space separation cutoff.

    ``marginal`` is a parallel pair whose overlap is at or below the snap
    tolerance -- typically adjacent hatch strokes clipping each other's ends.
    Reported for completeness, not a face pair.
    """
    band = max_plausible_wall_body_separation_pt(None)
    assert band is None
    genuine = []
    marginal = []
    reps = sorted(representatives)
    for index, left_id in enumerate(reps):
        for right_id in reps[index + 1 :]:
            left = identities_by_id.get(left_id)
            right = identities_by_id.get(right_id)
            if left is None or right is None:
                continue
            lp = tuple(left.path_fingerprint or ())
            rp = tuple(right.path_fingerprint or ())
            if len(lp) < 2 or len(rp) < 2:
                continue
            best = None
            for a in _segments(lp):
                for b in _segments(rp):
                    relation = _parallel_overlap_separation(
                        a,
                        b,
                        angle_tolerance_deg=DEFAULT_COLLINEAR_ANGLE_TOLERANCE_DEG,
                    )
                    if relation is None:
                        continue
                    overlap, separation = relation
                    if overlap <= 0.0 or separation <= 0.0:
                        continue
                    shorter = min(_seg_len(a), _seg_len(b)) or 1.0
                    fraction = overlap / shorter
                    if best is None or overlap > best[0]:
                        best = (overlap, separation, fraction)
            if best is None:
                continue
            overlap, separation, fraction = best
            record = (
                left_id,
                right_id,
                round(overlap, 2),
                round(separation, 2),
                round(fraction, 3),
            )
            if overlap > DEFAULT_GAP_SNAP_TOLERANCE_PT and fraction >= 0.5:
                genuine.append(record)
            else:
                marginal.append(record)
    return genuine, marginal


def main(pdf_path: Path, page_no: int) -> None:
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_no - 1)
    native = extract_native_page(page)
    viewports = tuple(segment_page_viewports(page, page_number=page_no))
    non_overlap = validate_non_overlapping_viewports(viewports)
    eligible = [
        v
        for v in viewports
        if v.bounding_box is not None
        and (
            v.status == ViewportSegmentationStatus.RESOLVED.value
            or (non_overlap and is_authoritative_derived_viewport(v))
        )
    ]

    print("=" * 78)
    print(f"CENSUS  page={page_no}  src={pdf_path.name}")
    print("=" * 78)

    totals = Counter()
    grand_candidates = 0
    grand_reps = 0
    grand_total_pairs = 0
    grand_considered = 0
    grand_excluded = 0
    grand_double = []
    grand_marginal = []
    reason_totals = Counter()

    for viewport in eligible:
        segments = [
            dict(s)
            for s in native.get("segments") or ()
            if _inside(s, viewport.bounding_box)
        ]
        if not segments:
            continue
        graph = build_wall_graph_for_viewport(segments)
        junctions, rels = classify_junctions(
            graph,
            document_id="diag:census",
            page_id=str(page_no),
            viewport_id=str(viewport.view_id),
        )
        walls, _ = assemble_wall_topology(
            graph, junctions, rels, viewport_id=str(viewport.view_id)
        )
        if not walls:
            continue
        identities = collect_physical_wall_identities(walls, graph)
        ordered = tuple(
            identities[w.candidate_id]
            for w in walls
            if w.candidate_id in identities
        )
        resolution = resolve_physical_wall_equivalence(
            ordered, walls_by_id={w.candidate_id: w for w in walls}
        )
        counts = Counter(c for _, _, c in resolution.pair_classifications)
        audit = resolution.candidate_pair_audit
        by_id = {i.wall_candidate_id: i for i in ordered}
        doubles, marginal = _double_face_representatives(
            by_id, resolution.representative_wall_ids
        )

        print()
        print(
            f"  viewport {viewport.view_id} "
            f"({getattr(viewport, 'view_type', '?')})"
        )
        print(f"    candidates            : {len(walls)}")
        print(f"    pairs total           : {audit.total_pairs}")
        print(f"    pairs considered      : {audit.considered_pairs}")
        print(f"    pairs excluded        : {audit.excluded_pairs}")
        print(f"    SAME                  : {counts.get(SAME, 0)}")
        print(f"    DISTINCT              : {counts.get(DISTINCT, 0)}")
        print(f"    AMBIGUOUS             : {counts.get(AMBIGUOUS, 0)}")
        print(f"    representatives       : {len(resolution.representative_wall_ids)}")
        print(f"    equivalence_groups    : {len(resolution.equivalence_groups)}")
        print(f"    double-face GENUINE   : {len(doubles)}")
        print(f"    double-face marginal  : {len(marginal)}")
        for reason, count in sorted(audit.exclusion_reason_counts.items()):
            print(f"      {reason}: {count}")
            reason_totals[reason] += count
        for hit in doubles[:5]:
            print(f"      !! {hit}")

        totals.update(counts)
        grand_candidates += len(walls)
        grand_reps += len(resolution.representative_wall_ids)
        grand_total_pairs += audit.total_pairs
        grand_considered += audit.considered_pairs
        grand_excluded += audit.excluded_pairs
        grand_double.extend(doubles)
        grand_marginal.extend(marginal)

    print()
    print("-" * 78)
    print(f"PAGE {page_no} TOTALS")
    print("-" * 78)
    print(f"  candidates       : {grand_candidates}")
    print(f"  pairs total      : {grand_total_pairs}")
    print(f"  pairs considered : {grand_considered}")
    print(f"  pairs excluded   : {grand_excluded}")
    print(f"  SAME             : {totals.get(SAME, 0)}")
    print(f"  DISTINCT         : {totals.get(DISTINCT, 0)}")
    print(f"  AMBIGUOUS        : {totals.get(AMBIGUOUS, 0)}")
    print(f"  REPRESENTATIVES  : {grand_reps}")
    print(f"  DOUBLE-FACE GENUINE : {len(grand_double)}")
    print(f"  DOUBLE-FACE MARGINAL: {len(grand_marginal)}")
    for hit in grand_double[:10]:
        print(f"    !! GENUINE {hit}")
    for reason, count in sorted(reason_totals.items()):
        print(f"    {reason}: {count}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: diag_representative_census.py <source.pdf> <page_no>")
    main(Path(sys.argv[1]), int(sys.argv[2]))
