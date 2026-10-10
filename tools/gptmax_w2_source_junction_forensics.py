"""Read-only W2 source-edge/junction forensic report for retained wall candidates.

Input is a pair of source-owned wall candidate record arrays, or the archived
compact-capture experiment report containing baseline/experiment arrays.
This module deliberately NEVER supplies missing geometry, closes a source gap,
proves an opening host, or issues QuantityEvidence. All numeric measurements
are diagnostic PDF-page coordinate distances, not metric construction units.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


_DIAGNOSTIC_COORD_EPS = 1e-6  # floating point comparison ONLY; not a physical tolerance


def _finite_point(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 2):
        raise ValueError("invalid 2D point")
    try:
        p = (float(value[0]), float(value[1]))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("non-numeric point") from exc
    if not all(math.isfinite(v) for v in p):
        raise ValueError("non-finite point")
    return p


def _line(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("invalid source edge geometry")
    return _finite_point(value[:2]), _finite_point(value[2:])


def _parents(record):
    identity = record.get("physical_identity") or {}
    parents = identity.get("source_primitive_ids")
    if not isinstance(parents, (list, tuple)) or not parents or any(
        not isinstance(p, str) or not p for p in parents
    ) or len(set(parents)) != len(parents):
        raise ValueError("missing, duplicated or malformed source ancestry")
    return tuple(sorted(parents))


def _unique_records(records, label):
    if not isinstance(records, list):
        raise ValueError(f"{label} must be a list")
    indexed = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(f"{label}: invalid wall record")
        key = _parents(record)
        fragments = record.get("source_edge_fragments") or ()
        if not isinstance(fragments, (list, tuple)):
            raise ValueError(f"{label}: invalid source-edge inventory")
        seen_edges, lineage = set(), set()
        for fragment in fragments:
            if not isinstance(fragment, dict):
                raise ValueError(f"{label}: malformed source-edge fragment")
            edge_id = fragment.get("edge_id")
            parents = fragment.get("source_primitive_ids")
            if (not isinstance(edge_id, str) or not edge_id or edge_id in seen_edges
                    or not isinstance(parents, (list, tuple)) or not parents
                    or any(not isinstance(p, str) or not p for p in parents)
                    or len(set(parents)) != len(parents)
                    or not set(parents) <= set(key)):
                raise ValueError(f"{label}: duplicate edge or foreign/unknown source lineage")
            seen_edges.add(edge_id)
            lineage.update(parents)
        if fragments and lineage != set(key):
            raise ValueError(f"{label}: incomplete source-edge ancestry")
        indexed.setdefault(key, []).append(record)
    return indexed


def _basis(records):
    # An observed edge (not the W4 snapped chain) determines diagnostic axis.
    # Choose the longest actual source-edge fragment; its choice is stable to
    # input/segment ordering, and no parent extent is guessed or extended.
    candidates = []
    for record in records:
        for f in record.get("source_edge_fragments") or []:
            a, b = _line(f.get("geometry"))
            distance = math.dist(a, b)
            if distance > _DIAGNOSTIC_COORD_EPS:
                candidates.append((distance, a, b))
    if not candidates:
        return None
    _, a, b = sorted(candidates, key=lambda v: (-v[0], v[1], v[2]))[0]
    direction = ((b[0] - a[0]) / math.dist(a, b),
                 (b[1] - a[1]) / math.dist(a, b))
    return a, direction, (-direction[1], direction[0])


def _coordinates(point, basis):
    origin, axis, normal = basis
    v = (point[0] - origin[0], point[1] - origin[1])
    return v[0] * axis[0] + v[1] * axis[1], v[0] * normal[0] + v[1] * normal[1]


def _interval_diagnostic(record, basis):
    spans = []
    noncollinear = []
    for f in record.get("source_edge_fragments") or []:
        a, b = _line(f.get("geometry"))
        pa, pb = _coordinates(a, basis), _coordinates(b, basis)
        # The report diagnoses *only* fragments on this one source axis.
        # Different offsets or slopes are shown but not forcibly joined.
        if abs(pa[1]) > _DIAGNOSTIC_COORD_EPS or abs(pb[1]) > _DIAGNOSTIC_COORD_EPS:
            noncollinear.append(str(f.get("edge_id")))
            continue
        if abs(pb[0] - pa[0]) > _DIAGNOSTIC_COORD_EPS:
            spans.append((min(pa[0], pb[0]), max(pa[0], pb[0])))
    merged = []
    for lo, hi in sorted(spans):
        if merged and lo <= merged[-1][1] + _DIAGNOSTIC_COORD_EPS:
            merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
        else:
            merged.append((lo, hi))
    gaps = [(a[1], b[0]) for a, b in zip(merged, merged[1:])
            if b[0] > a[1] + _DIAGNOSTIC_COORD_EPS]
    points = [_finite_point(p) for p in (record.get("wall_candidate") or {}).get("centerline_pts") or []]
    return {
        "wall_candidate_id": record.get("wall_candidate_id"),
        "source_edge_count": len(record.get("source_edge_fragments") or []),
        "source_aligned_intervals_page_pt": merged,
        "unproven_source_gaps_page_pt": gaps,
        "off_axis_fragment_edge_ids": sorted(noncollinear),
        "snapped_path_offsets_page_pt": [
            {"point": p, "axis_position_pt": _coordinates(p, basis)[0],
             "signed_normal_offset_pt": _coordinates(p, basis)[1]}
            for p in points],
        "snap_collapsed_fragment_count": len(record.get("source_snap_collapsed_fragments") or []),
    }


def compare_wall_records(baseline, candidate):
    """Compare only exact uniquely shared ancestry and expose unproven gaps.

    Identities with multiple candidate owners are *ambiguous*, not resolved by
    sorting, position, name, approximate distance, or nearest-wall preference.
    """
    old, new = _unique_records(baseline, "baseline"), _unique_records(candidate, "candidate")
    rows, unresolved = [], []
    for parents in sorted(set(old) | set(new)):
        b, n = old.get(parents, []), new.get(parents, [])
        if len(b) != 1 or len(n) != 1:
            unresolved.append({"source_primitive_ids": parents,
                               "baseline_candidate_count": len(b),
                               "candidate_candidate_count": len(n),
                               "reason": "unmatched_or_ambiguous_source_owner"})
            continue
        basis = _basis(b)
        if basis is None:
            unresolved.append({"source_primitive_ids": parents,
                               "reason": "no_source_edge_axis"})
            continue
        rows.append({"source_primitive_ids": parents,
                     "baseline": _interval_diagnostic(b[0], basis),
                     "candidate": _interval_diagnostic(n[0], basis),
                     "continuity_authenticated": False,
                     "physical_host_authenticated": False,
                     "purpose": "read_only_topology_diagnostic"})
    return {"matched_source_ancestries": rows, "unmatched_or_ambiguous": unresolved,
            "may_publish_hosts": False, "may_publish_quantities": False,
            "may_change_opening_counts": False, "benchmark_accuracy": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True,
                        help="Archived source experiment report, not frozen benchmark truth")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.input.read_text())
    if not isinstance(data, dict):
        parser.error("input must be a JSON object")
    required = ("baseline_local_source_wall_records", "experiment_local_source_wall_records")
    if any(k not in data for k in required):
        parser.error("missing source-owned wall record arrays")
    result = compare_wall_records(data[required[0]], data[required[1]])
    result["input_source_sha256"] = data.get("source_sha256")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"matched": len(result["matched_source_ancestries"]),
                      "ambiguous": len(result["unmatched_or_ambiguous"]),
                      "may_publish_hosts": False}, sort_keys=True))


if __name__ == "__main__":
    main()
