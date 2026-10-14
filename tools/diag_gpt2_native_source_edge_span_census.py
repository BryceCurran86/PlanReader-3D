"""Read-only W2-survivor vs W4-snapped edge audit for #2731.

SourceEdgeFragments are producer-owned SURVIVING W2 GRAPH facts that retain
original native primitive *IDs*, not independently verified PDF paint or raw
native primitive geometry. This tool makes no native-ink proof: a positive W2
span does not establish a literal native source span or physical wall role.
Only a separate original-PDF primitive reader can prove native ink. An absent
W2 fragment is not proof of absent original ink. No room, quantity or customer
publication is permitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from pb_source_room_face_authority import (
    _NDIGITS,
    _collinear_overlap_edge,
    _edge,
    _edge_contains_edge,
    _finite_source_edge,
)

TOL = 4.0 * math.sqrt(2.0) * 10.0 ** -_NDIGITS
ZERO = "surviving_w2_zero_coverage"
ONE = "surviving_w2_single_coverage"
MULTIPLE = "surviving_w2_double_coverage"
UNKNOWN = "surviving_w2_unavailable"


def _native_edge(raw):
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        values = tuple(float(value) for value in raw)
        if not all(math.isfinite(value) for value in values):
            return None
        edge = _edge((values[0], values[1]), (values[2], values[3]))
    except (ValueError, TypeError, OverflowError):
        return None
    return edge if edge[0] != edge[1] and _finite_source_edge(edge) else None


def _contested_edge(raw):
    try:
        if len(raw) != 2 or any(len(point) != 2 for point in raw):
            return None
        p1, p2 = (tuple(float(v) for v in point) for point in raw)
        if not all(math.isfinite(v) for p in (p1, p2) for v in p):
            return None
        edge = _edge(p1, p2)
        return edge if edge[0] != edge[1] and _finite_source_edge(edge) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _candidate_support(candidate, child):
    """One W2 source-lineage fragment or continuous same-parent-ID W2 split chain.

    A surviving-W2 gap, crossing, or adjacency *between different wall candidates*
    cannot turn into shared source coverage. Split fragments with different
    source primitive IDs cannot silently be glued together.
    """
    fragments = candidate.get("source_edge_fragments")
    ancestors = candidate.get("source_primitive_ids")
    if (
        not isinstance(fragments, (list, tuple)) or not fragments
        or not isinstance(ancestors, (list, tuple)) or not ancestors
        or any(not isinstance(a, str) or not a for a in ancestors)
    ):
        return None, ()
    owned_ids = set(ancestors)
    per_native = {}
    witnesses = set()
    a, b = child
    vx, vy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(vx, vy)
    if length <= TOL:
        return None, ()
    ux, uy = vx / length, vy / length
    directly_covered = False

    for fragment in fragments:
        if not isinstance(fragment, dict):
            return None, ()
        parent = _native_edge(fragment.get("geometry"))
        ids = fragment.get("source_primitive_ids")
        if (
            parent is None or not isinstance(ids, (tuple, list)) or not ids
            or any(not isinstance(value, str) or value not in owned_ids for value in ids)
        ):
            return None, ()
        # Native containment contract, not a nearest-wall or gap extension.
        direct = _edge_contains_edge(parent, child)
        overlap = _collinear_overlap_edge(parent, child)
        if direct:
            directly_covered = True
            witnesses.update(ids)
        if overlap is None:
            continue
        p, q = overlap
        lo, hi = sorted((
            (p[0] - a[0]) * ux + (p[1] - a[1]) * uy,
            (q[0] - a[0]) * ux + (q[1] - a[1]) * uy,
        ))
        if hi - lo <= TOL:
            continue
        for source_id in ids:
            per_native.setdefault(source_id, []).append((lo, hi))

    if directly_covered:
        return True, tuple(sorted(witnesses))
    for source_id, intervals in sorted(per_native.items()):
        intervals.sort()
        if not intervals or intervals[0][0] > TOL:
            continue
        covered_end = intervals[0][1]
        for lo, hi in intervals[1:]:
            if lo > covered_end + TOL:
                break  # Uncovered W2 interval: never invent a native source span.
            covered_end = max(covered_end, hi)
        if covered_end >= length - TOL:
            return True, (source_id,)
    return False, ()


def inspect_competing_source_edge(row):
    """Keep W2 contenders and ancestry, not independent native ink proof."""
    child = _contested_edge(row.get("competing_planar_edge"))
    contenders = row.get("candidate_walls")
    if child is None or not isinstance(contenders, (list, tuple)) or not contenders:
        raise ValueError("contested_edge_or_contenders_invalid")
    observed_ids = []
    results = []
    unknown = False
    for contender in contenders:
        if not isinstance(contender, dict):
            raise ValueError("original_source_contender_invalid")
        wall_id = contender.get("wall_id")
        if not isinstance(wall_id, str) or not wall_id or wall_id in observed_ids:
            raise ValueError("duplicate_or_invalid_source_wall_id")
        observed_ids.append(wall_id)
        if contender.get("w4_record_unavailable") is True:
            proven, receipts = None, ()
        else:
            proven, receipts = _candidate_support(contender, child)
        unknown |= proven is None
        results.append({
            "wall_id": wall_id,
            "full_surviving_w2_span_supported": proven,
            "witness_source_primitive_ids": receipts,
            "source_edge_fragments_retained": contender.get("source_edge_fragments", ()),
            "structural_wall_role_granted": False,
        })
    supported = tuple(sorted(item["wall_id"] for item in results
                             if item["full_surviving_w2_span_supported"] is True))
    status = (UNKNOWN if unknown else MULTIPLE if len(supported) > 1
              else ONE if len(supported) == 1 else ZERO)
    return {
        "face_id": row.get("face_id"),
        "competing_planar_edge": row["competing_planar_edge"],
        "surviving_w2_span_support_status": status,
        "observed_supported_wall_ids": supported,
        "all_wall_contenders": tuple(sorted(results, key=lambda item: item["wall_id"])),
        "independent_original_pdf_ink_proven": False,
        "original_source_wall_equivalence_granted": False,
        "physical_room_publication_granted": False,
        "commercial_projection_allowed": False,
    }


def inspect_source_room_report(report):
    if (not isinstance(report, dict)
            or report.get("source_snapshot_preserved") is not True
            or report.get("new_commercial_quantities") != []
            or not isinstance(report.get("source_sha256"), str)
            or len(report["source_sha256"]) != 64
            or not isinstance(report.get("scopes"), list)):
        raise ValueError("producer_original_source_report_untrusted")
    scopes = []
    for scope in report["scopes"]:
        if scope.get("source_sha256") != report["source_sha256"]:
            raise ValueError("source_scope_sha_mismatch")
        edges = scope.get("competing_source_edges")
        if not isinstance(edges, list):
            raise ValueError("source_competing_edge_universe_missing")
        scopes.append({
            "source_sha256": scope["source_sha256"],
            "revision_id": scope["revision_id"],
            "snapshot_id": scope["snapshot_id"],
            "page_id": scope["page_id"],
            "decision_scope_id": scope["decision_scope_id"],
            "w4_scope_complete": scope["w4_scope_complete"],
            "source_room_face_record_count_unchanged": scope["source_room_face_record_count"],
            "contested_source_edges": tuple(
                inspect_competing_source_edge(row) for row in edges
            ),
            "quantity_publication_granted": False,
        })
    return {
        "source_sha256": report["source_sha256"],
        "source_snapshot_preserved": True,
        "original_source_scope_count": len(scopes),
        "scopes": tuple(scopes),
        "new_commercial_quantities": [],
        "frozen_evaluation_run": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    data = args.source_report.read_bytes()
    original = json.loads(data)
    audit = inspect_source_room_report(original)
    audit["input_report_sha256"] = hashlib.sha256(data).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2, sort_keys=True))
    print(json.dumps({
        "original_sha": audit["source_sha256"],
        "contested_edge_statuses": [
            edge["surviving_w2_span_support_status"]
            for scope in audit["scopes"]
            for edge in scope["contested_source_edges"]
        ],
        "commercial_projection_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
