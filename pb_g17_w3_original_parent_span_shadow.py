"""Original G17 source-parent span audit for W3 short-arm demotion.

A source-painted long parent is not a structural wall, and a W3 CONTINUES_AS
relationship through an AMBIGUOUS junction must remain blocked at W4. This
module is diagnostic only; it accepts a serialized source report and does NOT
reauthenticate original bytes or grant any physical/metric authority.
"""
from __future__ import annotations

from math import hypot, isfinite

_EPS = 1e-6


def _line(raw):
    if not isinstance(raw, (tuple, list)) or len(raw) != 4:
        return None
    if any(type(v) not in (int, float) or not isfinite(v) for v in raw):
        return None
    line = tuple(float(v) for v in raw)
    return line if hypot(line[2]-line[0], line[3]-line[1]) > _EPS else None


def _positive_original_interval_contains_child(parent, child):
    """No snap: every true child endpoint lies along the actual raw parent."""
    p, c = _line(parent), _line(child)
    if p is None or c is None:
        return False
    ux, uy = p[2]-p[0], p[3]-p[1]
    size = hypot(ux, uy)
    unit_x, unit_y = ux/size, uy/size
    scalars = []
    for x, y in ((c[0], c[1]), (c[2], c[3])):
        dx, dy = x-p[0], y-p[1]
        if abs(unit_x*dy-unit_y*dx) > _EPS:
            return False
        scalars.append(unit_x*dx+unit_y*dy)
    return min(scalars) >= -_EPS and max(scalars) <= size+_EPS


def audit_g17_w3_short_arm_source_parents(source_plan_report: dict) -> dict:
    """Only source report observations. Never override W3 or W4 abstentions."""
    root = source_plan_report
    rows = {}
    for row in tuple(root.get("source_primitive_dispositions") or ()):
        ref = row.get("source_primitive_id")
        if not ref or not row.get("observation_id"):
            raise ValueError("original source observation address unavailable")
        rows.setdefault(ref, []).append(row)
    results = {}
    for mode in ("default_w2_w3_w4", "exact_coordinate_w2_w3_w4"):
        graph = root.get(mode)
        if not isinstance(graph, dict):
            results[mode] = []
            continue
        edges = {str(e["edge_id"]): e for e in graph.get("w2_edges", ())}
        decisions = []
        for j in graph.get("w3_junctions", ()):
            reasons = tuple(j.get("reason_codes") or ())
            if "short_isolated_arm_present" not in reasons:
                continue
            targets = tuple(sorted(s.split(":",1)[1] for s in reasons
                                   if s.startswith("suspect_edge_id:")))
            for suspect in targets:
                child = edges.get(suspect)
                raw = tuple(child.get("source_primitive_ids") or ()) if child else ()
                geometry = child.get("geometry") if child else None
                child_geom = _line(geometry)
                child_len = (hypot(child_geom[2]-child_geom[0],
                                   child_geom[3]-child_geom[1]) if child_geom else None)
                parents = []
                for source_id in sorted(raw):
                    original_rows = tuple(rows.get(source_id, ()))
                    for source_row in original_rows:
                        original = _line(source_row.get("geometry"))
                        orig_len = (hypot(original[2]-original[0],
                                          original[3]-original[1]) if original else None)
                        contained = _positive_original_interval_contains_child(
                            source_row.get("geometry"), geometry)
                        paint = bool((source_row.get("source_paint") or {}).get(
                            "original_solid_and_unchanged"))
                        parents.append(dict(
                            source_primitive_id=source_id,
                            source_observation_id=source_row["observation_id"],
                            source_geometry_pt=original,
                            source_full_ink_positive=paint,
                            child_interval_originally_contained=contained,
                            original_source_length_pt=orig_len,
                            child_length_pt=child_len,
                            genuinely_longer_original_parent=bool(
                                contained and orig_len is not None
                                and child_len is not None and orig_len>child_len+_EPS),
                            structural_wall_role_granted=False,
                        ))
                    if not original_rows:
                        parents.append(dict(
                            source_primitive_id=source_id,
                            source_observation_id=None,
                            source_geometry_pt=None,
                            source_full_ink_positive=False,
                            child_interval_originally_contained=False,
                            original_source_length_pt=None,
                            child_length_pt=child_len,
                            genuinely_longer_original_parent=False,
                            structural_wall_role_granted=False,
                        ))
                decisions.append(dict(
                    W3_junction_id=j.get("node_id"),
                    W3_junction_status=j.get("status"),
                    W3_junction_type=j.get("junction_type"),
                    W3_reason_codes=reasons,
                    W3_junction_position_pt=j.get("position_pt"),
                    W2_suspect_edge_id=suspect,
                    W2_child_geometry_pt=child_geom,
                    W2_child_length_pt=child_len,
                    source_parents=tuple(parents),
                    any_full_painted_original_parent_longer_than_child=any(
                        p["genuinely_longer_original_parent"] and p["source_full_ink_positive"]
                        for p in parents),
                    W3_short_arm_abstention_preserved=True,
                    W4_union_granted=False,
                    physical_wall_role_granted=False,
                    physical_opening_host_granted=False,
                ))
        decisions.sort(key=lambda x:(str(x["W3_junction_id"]),str(x["W2_suspect_edge_id"])))
        results[mode] = decisions
    return dict(source_sha256=root.get("source_sha256"),snapshot_id=root.get("snapshot_id"),
                source_authentication_reperformed=False,
                candidate_only_short_child_original_parent_results=results,
                W3_junctions_and_W4_candidates_unchanged=True,
                physical_wall_equivalence_granted=False,
                opening_host_granted=False,
                opening_count_granted=False,
                metric_quantity_granted=False)
