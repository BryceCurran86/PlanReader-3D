"""Read-only, opt-in checks on candidate source-owned floor-finish zones.

This is *not* a source producer, area resolver, physical-identity binder or
quantity issuer. Its inputs are untrusted diagnostic proposals. Passing every
check grants CANDIDATE only, never CORROBORATED / FIRM, and is not consumed by
commercial or live quantity paths. No source PDF or gold evaluator is read.

The ten independently callable checks are intentionally kept separate to let
source owners test positive, negative and conflict examples before proposing
any authority bridge. Source-role labels in input cannot authenticate anything.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import math
import re
from typing import Mapping, Sequence

from shapely.geometry import Polygon

from pb_migration_contracts import EvidenceResolutionStatus


SHA_RE = re.compile(r"[0-9a-f]{64}\Z")


def _id(value):
    return type(value) is str and bool(value) and value == value.strip()


def _num(value):
    if type(value) not in (int, float):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _point(value):
    if type(value) not in (tuple, list) or len(value) != 2:
        return None
    v = tuple(_num(x) for x in value)
    return v if all(x is not None for x in v) else None


def _area(value):
    if type(value) not in (str, int, float, Decimal) or type(value) is bool:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, OverflowError):
        return None
    return number if number.is_finite() and number > 0 else None


def check_source_scope(scope: Mapping, records: Sequence[Mapping]) -> tuple[str, ...]:
    """01: source hash, revision, snapshot and decision scope must agree."""
    if not isinstance(scope, Mapping):
        return ("source_scope_missing",)
    keys = ("document_id", "revision_id", "source_sha256", "snapshot_id", "decision_scope_id")
    if any(not _id(scope.get(k)) for k in keys) or not SHA_RE.fullmatch(scope["source_sha256"]):
        return ("source_scope_incomplete",)
    for r in records:
        if not isinstance(r, Mapping) or any(r.get(k) != scope[k] for k in keys):
            return ("source_scope_conflict",)
    return ()


def check_unique_source_edges(edges: Sequence[Mapping]) -> tuple[str, ...]:
    """02: require original path/parent IDs and unique nonzero source segments."""
    if type(edges) not in (tuple, list) or not edges:
        return ("source_edge_inventory_empty",)
    ids = []
    observation_ids = []
    primitive_keys = []
    for e in edges:
        if not isinstance(e, Mapping) or any(not _id(e.get(k)) for k in (
            "id", "source_observation_id", "primitive_id", "source_parent_id",
            "page_id", "viewport_id",
        )):
            return ("source_edge_witness_incomplete",)
        p, q = _point(e.get("p0")), _point(e.get("p1"))
        if p is None or q is None or p == q:
            return ("source_edge_geometry_invalid",)
        ids.append(e["id"])
        observation_ids.append(e["source_observation_id"])
        primitive_keys.append((e["page_id"], e["primitive_id"]))
    if (len(set(ids)) != len(ids) or len(set(primitive_keys)) != len(primitive_keys)
            or len(set(observation_ids)) != len(observation_ids)):
        return ("source_edge_duplicate",)
    return ()


def check_page_view_ownership(edges: Sequence[Mapping], floor: Mapping,
                              projection: Mapping, zones: Sequence[Mapping]) -> tuple[str, ...]:
    """03: do not substitute page or viewport from a different plan view."""
    for owner in (floor, projection, *zones):
        if not isinstance(owner, Mapping) or any(not _id(owner.get(k)) for k in ("page_id", "viewport_id")):
            return ("source_viewport_missing",)
    index = {e["id"]: e for e in edges}
    for owner in (floor, projection, *zones):
        edge_ids = owner.get("edge_ids")
        if type(edge_ids) not in (tuple, list) or any(not _id(i) for i in edge_ids):
            return ("source_edge_list_invalid",)
        for eid in edge_ids:
            edge = index.get(eid)
            if (edge is None or edge.get("page_id") != owner["page_id"]
                    or edge.get("viewport_id") != owner["viewport_id"]):
                return ("source_viewport_edge_conflict",)
    if floor["page_id"] == projection["page_id"] and floor["viewport_id"] != projection["viewport_id"]:
        return ("physical_projection_viewport_conflict",)
    return ()


def check_explicit_correspondence(floor: Mapping, projection: Mapping,
                                  pairings: Sequence[Mapping]) -> tuple[str, ...]:
    """04: correspondence requires one receipt per source-owned floor side.

    Even a passing set is UNAUTHENTICATED: we do not verify PDF content, wall
    structural role, or whether the source issuer actually signed the receipt.
    """
    a, b = floor.get("edge_ids", ()), projection.get("edge_ids", ())
    if (type(a) not in (tuple, list) or type(b) not in (tuple, list)
            or type(pairings) not in (tuple, list) or not a or not b or not pairings):
        return ("cross_sheet_correspondence_unavailable",)
    left = Counter(); right = Counter(); receipts = set()
    for row in pairings:
        if (not isinstance(row, Mapping)
                or not _id(row.get("source_correspondence_receipt_id"))
                or not _id(row.get("floor_edge_id"))
                or not _id(row.get("projection_edge_id"))):
            return ("cross_sheet_correspondence_receipt_missing",)
        if row["source_correspondence_receipt_id"] in receipts:
            return ("cross_sheet_correspondence_receipt_duplicate",)
        receipts.add(row["source_correspondence_receipt_id"])
        left[row.get("floor_edge_id")] += 1
        right[row.get("projection_edge_id")] += 1
    if (set(left) != set(a) or set(right) != set(b)
            or any(n != 1 for n in left.values()) or any(n != 1 for n in right.values())
            or len(a) != len(b)):
        return ("cross_sheet_correspondence_ambiguous",)
    return ()


def check_closed_source_loop(edge_ids: Sequence[str], edges: Mapping[str, Mapping]) -> tuple[str, ...]:
    """05: exact (not snapped) source segment graph is a single 2-regular loop."""
    if type(edge_ids) not in (tuple, list) or len(edge_ids) < 3:
        return ("source_loop_incomplete",)
    if any(not _id(x) for x in edge_ids) or len(set(edge_ids)) != len(edge_ids):
        return ("source_loop_reused_edge",)
    adjacency = defaultdict(list)
    for eid in edge_ids:
        row = edges.get(eid)
        if row is None:
            return ("source_loop_edge_missing",)
        p, q = _point(row.get("p0")), _point(row.get("p1"))
        if p is None or q is None or p == q:
            return ("source_loop_edge_invalid",)
        adjacency[p].append(q); adjacency[q].append(p)
    if any(len(links) != 2 for links in adjacency.values()):
        return ("source_loop_unclosed_or_branching",)
    seen = set(); frontier = [next(iter(adjacency))]
    while frontier:
        v = frontier.pop()
        if v in seen:
            continue
        seen.add(v); frontier.extend(adjacency[v])
    if len(seen) != len(adjacency) or len(adjacency) != len(edge_ids):
        return ("source_loop_disconnected",)
    return ()


def _ring(edge_ids: Sequence[str], edges: Mapping[str, Mapping]):
    if check_closed_source_loop(edge_ids, edges):
        return None
    adj = defaultdict(list)
    for eid in edge_ids:
        edge = edges[eid]
        p, q = _point(edge["p0"]), _point(edge["p1"])
        adj[p].append(q); adj[q].append(p)
    start = min(adj)
    first = min(adj[start]); vertices = [start, first]; prev, at = start, first
    while at != start:
        other = [p for p in adj[at] if p != prev]
        if len(other) != 1:
            return None
        nxt = other[0]
        if nxt != start and nxt in vertices:
            return None
        vertices.append(nxt); prev, at = at, nxt
    return vertices


def check_simple_source_polygon(edge_ids: Sequence[str], edges: Mapping[str, Mapping]) -> tuple[str, ...]:
    """06: reject zero-area, overlapping, doubled-back or crossed ink rings."""
    vertices = _ring(edge_ids, edges)
    if vertices is None:
        return ("source_polygon_unclosed",)
    polygon = Polygon(vertices)
    if polygon.is_empty or polygon.area <= 0 or not polygon.is_valid:
        return ("source_polygon_self_crossing_or_degenerate",)
    return ()


def check_zones_inside_floor(projection: Mapping, zones: Sequence[Mapping],
                             edges: Mapping[str, Mapping]) -> tuple[str, ...]:
    """07: zone material surface must be contained in its source-drawn floor."""
    f = _ring(projection.get("edge_ids", ()), edges)
    if f is None or not Polygon(f).is_valid:
        return ("source_floor_projection_unresolved",)
    floor = Polygon(f)
    for z in zones:
        ring = _ring(z.get("edge_ids", ()), edges)
        if ring is None or not Polygon(ring).is_valid or not floor.covers(Polygon(ring)):
            return ("finish_zone_outside_floor",)
    return ()


def check_zones_nonoverlapping(zones: Sequence[Mapping], edges: Mapping[str, Mapping]) -> tuple[str, ...]:
    """08: shared real boundaries okay, positive interior overlap is not."""
    polygons = []
    for z in zones:
        ring = _ring(z.get("edge_ids", ()), edges)
        if ring is None or not Polygon(ring).is_valid:
            return ("finish_zone_polygon_unresolved",)
        polygons.append(Polygon(ring))
    for i, left in enumerate(polygons):
        for right in polygons[i + 1:]:
            if left.intersection(right).area > 0:
                return ("finish_zone_interiors_overlap",)
    return ()


def check_finish_occurrence_ownership(zones: Sequence[Mapping]) -> tuple[str, ...]:
    """09: occurrence cannot be silently assigned to two different zones."""
    zone_ids, occurrences = [], []
    for z in zones:
        keys = ("zone_id", "occurrence_record_id", "definition_record_id", "occurrence_evidence_id")
        if not isinstance(z, Mapping) or any(not _id(z.get(k)) for k in keys):
            return ("finish_occurrence_or_definition_unavailable",)
        zone_ids.append(z["zone_id"]); occurrences.append(z["occurrence_record_id"])
    if len(set(zone_ids)) != len(zone_ids) or len(set(occurrences)) != len(occurrences):
        return ("finish_occurrence_multiple_owners",)
    return ()


def check_metric_partition(floor: Mapping, projection: Mapping,
                           zones: Sequence[Mapping], edges: Mapping[str, Mapping]) -> tuple[str, ...]:
    """10: exact FULL polygon cover and independently supplied metric receipts.

    Does not derive metric area from page points², and explicitly DOES NOT
    authenticate the caller-supplied receipt claims. Shadow only.
    """
    base = _area(floor.get("metric_area_m2"))
    if base is None or not _id(floor.get("metric_area_evidence_id")):
        return ("floor_metric_receipt_unavailable",)
    metric = []
    for z in zones:
        area = _area(z.get("metric_area_m2"))
        if area is None or not _id(z.get("metric_area_evidence_id")):
            return ("zone_metric_receipt_unavailable",)
        metric.append(area)
    if not metric or sum(metric) != base:
        return ("zone_metric_partition_incomplete_or_conflicting",)
    r = _ring(projection.get("edge_ids", ()), edges)
    if r is None:
        return ("source_floor_projection_unresolved",)
    floor_poly = Polygon(r)
    covered = None
    for z in zones:
        zring = _ring(z["edge_ids"], edges)
        if zring is None or not Polygon(zring).is_valid:
            return ("source_finish_partition_invalid_zone",)
        p = Polygon(zring)
        covered = p if covered is None else covered.union(p)
    if covered is None or not covered.equals(floor_poly):
        return ("source_finish_partition_gap_or_excess",)
    return ()


def inspect_candidate_finish_zone_bundle(bundle: Mapping) -> dict:
    """Run ten guards; positive results are strictly candidate tier forever."""
    if (not isinstance(bundle, Mapping) or not isinstance(bundle.get("floor"), Mapping)
            or not isinstance(bundle.get("floor_projection"), Mapping)
            or type(bundle.get("zones")) not in (list, tuple)
            or type(bundle.get("edges")) not in (list, tuple)
            or type(bundle.get("source_correspondences")) not in (list, tuple)
            or any(not isinstance(z, Mapping) for z in bundle["zones"])):
        return {"status": EvidenceResolutionStatus.ABSTAINED.value,
                "authority_granted": False, "quantity_granted": False,
                "scope": "shadow_only", "reason_codes": ("shadow_input_invalid",),
                "checks": {"00_input": ["shadow_input_invalid"]}}
    scope = bundle.get("scope", {})
    floor = bundle.get("floor", {})
    projection = bundle.get("floor_projection", {})
    zones = tuple(bundle.get("zones", ()))
    all_edges = tuple(bundle.get("edges", ()))
    pairs = tuple(bundle.get("source_correspondences", ()))
    reports: dict[str, tuple[str, ...]] = {}
    reports["01_scope"] = check_source_scope(scope, (floor, projection, *zones, *all_edges, *pairs))
    reports["02_edges"] = check_unique_source_edges(all_edges)
    if reports["02_edges"]:
        # Do not turn bad IDs into an arbitrary last-write-wins lookup.
        for i in range(3, 11):
            reports[f"{i:02d}_blocked"] = ("source_edge_inventory_unavailable",)
    else:
        index = {e["id"]: e for e in all_edges}
        reports["03_view"] = check_page_view_ownership(all_edges, floor, projection, zones)
        reports["04_cross_sheet"] = check_explicit_correspondence(floor, projection, pairs)
        all_rings = [floor.get("edge_ids", ()), projection.get("edge_ids", ())]
        all_rings.extend(z.get("edge_ids", ()) for z in zones)
        reports["05_rings"] = tuple(sorted({reason for ring in all_rings for reason in check_closed_source_loop(ring, index)}))
        reports["06_simple"] = tuple(sorted({reason for ring in all_rings for reason in check_simple_source_polygon(ring, index)}))
        if reports["05_rings"] or reports["06_simple"]:
            for name in ("07_inside", "08_nonoverlap", "10_metric"):
                reports[name] = ("source_polygon_unresolved",)
        else:
            reports["07_inside"] = check_zones_inside_floor(projection, zones, index)
            reports["08_nonoverlap"] = check_zones_nonoverlapping(zones, index)
            reports["10_metric"] = check_metric_partition(floor, projection, zones, index)
        reports["09_material"] = check_finish_occurrence_ownership(zones)
    reasons = tuple(sorted({x for codes in reports.values() for x in codes}))
    status = (EvidenceResolutionStatus.CONFLICT if any("conflict" in x or "overlap" in x or "duplicate" in x
                                                     or "multiple_owners" in x for x in reasons)
              else EvidenceResolutionStatus.ABSTAINED if reasons
              else EvidenceResolutionStatus.CANDIDATE)
    return {"status": status.value, "authority_granted": False, "quantity_granted": False,
            "scope": "shadow_only", "reason_codes": reasons,
            "checks": {key: list(value) for key, value in sorted(reports.items())}}