"""Fresh original-source pixel, W2, W3 and W4 audit for every opening flank.

Each input report is reproduced from immutable PDF bytes before any join.
Graph candidates never authenticate structural wall roles or physical hosts.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path

from pb_opening_host_binding_authority import (
    _COORD_TOL, _RASTER_WHOLE_WALL_CENTER_TOL_PT, _OpeningGeometry,
)
from pb_wall_room_topology_stage_a import DEFAULT_GAP_SNAP_TOLERANCE_PT
from tools.diag_gptmax_full_foreground_flank import full_foreground_flank_census
from tools.diag_gptmax_full_foreground_run_source import original_full_foreground_report
from tools.diag_gptmax_raster_host_source_membership import (
    original_raster_host_ancestry_census, _finite_source_axis,
)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fresh_source_reports(pdf_bytes, original, foreground, source_sha):
    """Reproduce all records and graph outcomes; do not trust JSON assertions."""
    if not isinstance(pdf_bytes, bytes) or sha256(pdf_bytes).hexdigest() != source_sha:
        raise ValueError("immutable original source PDF SHA mismatch")
    page = original.get("page_id")
    if not isinstance(page, str) or page != foreground.get("page_id"):
        raise ValueError("original source page scope mismatch")
    fresh_original = original_raster_host_ancestry_census(pdf_bytes,
        page_id=page, expected_source_sha=source_sha)
    if _json(fresh_original) != _json(original):
        raise ValueError("G17 original-source report differs from fresh production replay")
    fresh_foreground = original_full_foreground_report(pdf_bytes,
        page_id=page, expected_source_sha=source_sha, trace=True)
    if _json(fresh_foreground) != _json(foreground):
        raise ValueError("foreground source receipts or topology differ from fresh replay")
    return fresh_original, fresh_foreground


def _contacts(line, opening, flank):
    """Observe existing G17 projection predicates; never pick an owner."""
    _, projected, failure = _finite_source_axis(line, opening)
    if failure:
        return False
    lo, hi, offset = projected
    start, end = flank["axis_span_pt"]
    cross_lo, cross_hi = flank["normal_span_pt"]
    endpoint = hi if flank["role"] == "left" else lo
    pixel_tol = _RASTER_WHOLE_WALL_CENTER_TOL_PT + _COORD_TOL
    return (abs(endpoint - flank["end_axis_coordinate_pt"]) <= DEFAULT_GAP_SNAP_TOLERANCE_PT + _COORD_TOL
        and cross_lo - pixel_tol <= offset <= cross_hi + pixel_tol
        and min(hi, end) - max(lo, start) > pixel_tol)


def _flank_stage_rows(joined, original, required, graph):
    """Consume a freshly reproduced graph; retain all alternatives and losses."""
    original_by_id = {r["opening_identity_id"]: r for r in original["opening_rows"]}
    required_by_id = {r["opening_identity_id"]: r for r in required["opening_rows"]}
    parents = {r["source_observation_id"]: r for r in graph["source_parent_census"]}
    edges = {r["edge_id"]: r for r in graph["all_w2_edges"]}
    collapsed = {r["fragment_id"]: r for r in graph["all_snap_collapsed_fragments"]}
    walls = defaultdict(list)
    for row in graph["all_experimental_w4_candidates"]:
        walls[row["candidate_id"]].append(row)
    output = []
    for row in joined["opening_rows"]:
        identity = row["opening_identity_id"]
        opening = _OpeningGeometry(**original_by_id[identity]["original_aperture_coordinate_basis"])
        flank_by_role = {f["role"]: f for f in required_by_id[identity]["flanks"]}
        flanks = []
        for flank in sorted(row["flanks"], key=lambda f: f["role"]):
            requirement = flank_by_role[flank["role"]]
            source_rows = []
            for pixel in sorted(flank["pixel_run_candidates"], key=lambda r: r["source_observation_id"]):
                source_id = pixel["source_observation_id"]
                parent = parents[source_id]
                edge_rows = []
                for eid in sorted(parent["w2_edge_ids"]):
                    edge = edges[eid]
                    local = _contacts(edge["w2_fragment_geometry_pt"], opening, requirement)
                    # A retained candidate ID may name several actual producer
                    # records. Preserve every record; never silently index one.
                    alternatives = [w for wid in edge["experimental_w4_candidate_ids"]
                                    for w in walls[wid]]
                    edge_rows.append({**edge,
                        "matches_original_required_flank_geometry": local,
                        "experimental_w4_records": alternatives,
                        "w4_candidate_address_ambiguous": any(
                            len(walls[wid]) != 1 for wid in edge["experimental_w4_candidate_ids"]),
                        "source_parent_transfer_allowed": False,
                        "physical_host_authority": False})
                collapse_rows = [{**collapsed[fid],
                    "matches_original_required_flank_geometry": _contacts(
                        collapsed[fid]["source_fragment_geometry_pt"], opening, requirement)}
                    for fid in sorted(parent["snap_collapsed_fragment_ids"])]
                local_edges = [e for e in edge_rows if e["matches_original_required_flank_geometry"]]
                retained = [e for e in local_edges if e["w3_retained"]]
                if not edge_rows and not collapse_rows:
                    barrier = "W2_SOURCE_PARENT_UNMAPPED"
                elif not local_edges:
                    barrier = "W2_NO_SURVIVING_REQUIRED_FLANK_FRAGMENT"
                elif not retained:
                    barrier = "W3_NODE_PAIR_DEDUP_REMOVED_REQUIRED_FLANK"
                elif any(e["w4_candidate_address_ambiguous"] for e in retained):
                    barrier = "W4_CANDIDATE_ADDRESS_COLLISION"
                elif not any(e["experimental_w4_records"] for e in retained):
                    barrier = "W4_LOCAL_SOURCE_OWNER_UNAVAILABLE"
                else:
                    barrier = "W4_LOCAL_CANDIDATES_AWAIT_WALL_ROLE_AND_EQUIVALENCE"
                source_rows.append({**pixel,
                    "source_pixel_receipt_freshly_reauthenticated": True,
                    "actual_w2_edge_rows": edge_rows,
                    "actual_snap_collapsed_rows": collapse_rows,
                    "observed_geometry_barrier": barrier,
                    "first_unproved_authority": "ORIGINAL_VISIBLE_STRUCTURAL_WALL_LINE",
                    "physical_equivalence_proven": False,
                    "host_publication_allowed": False})
            flanks.append({"role": flank["role"], "source_run_rows": source_rows,
                "observed_geometry_barrier_counts": dict(sorted(Counter(
                    x["observed_geometry_barrier"] for x in source_rows).items())),
                "first_unproved_authority": flank["first_unproved_authority"],
                "physical_host_proven": False, "host_publication_allowed": False})
        output.append({"opening_identity_id": identity, "flanks": flanks,
            "host_publication_allowed": False})
    return sorted(output, key=lambda r: r["opening_identity_id"])


def cross_opening_source_usage(opening_rows):
    """Read-only census of original pixel parents reused by distinct G17 opens.

    Sharing a painted original source observation is not proof that opening
    identities, wall hosts or physical geometry are interchangeable.
    """
    if not isinstance(opening_rows, list):
        raise ValueError("source-owned opening rows must be a list")
    observations = defaultdict(list)
    unique_openings = set()
    for opening in opening_rows:
        if not isinstance(opening, dict):
            raise ValueError("malformed source opening row")
        opening_id = opening.get("opening_identity_id")
        if (not isinstance(opening_id, str) or not opening_id.strip()
                or opening_id in unique_openings):
            raise ValueError("missing or duplicate source opening identity")
        unique_openings.add(opening_id)
        flanks = opening.get("flanks")
        if not isinstance(flanks, list):
            raise ValueError("missing source-owned opening flanks")
        roles = set()
        for flank in flanks:
            if not isinstance(flank, dict):
                raise ValueError("malformed source-owned opening flank")
            role = flank.get("role")
            if (not isinstance(role, str) or not role.strip() or role in roles):
                raise ValueError("ambiguous source opening flank role")
            roles.add(role)
            rows = flank.get("source_run_rows")
            if not isinstance(rows, list):
                raise ValueError("missing original pixel source observation rows")
            seen = set()
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError("malformed original pixel source row")
                source_id = row.get("source_observation_id")
                if (not isinstance(source_id, str) or not source_id.strip()
                        or source_id in seen):
                    raise ValueError("duplicate or missing original pixel source parent")
                seen.add(source_id)
                coords = row.get("source_line_pt")
                if (not isinstance(coords, (list, tuple)) or len(coords) != 4
                        or any(type(v) not in (int, float) or
                               not math.isfinite(v) for v in coords)):
                    raise ValueError("invalid original source line geometry")
                a, b = tuple(coords[:2]), tuple(coords[2:])
                if a == b:
                    raise ValueError("degenerate original pixel source line")
                if (row.get("source_pixel_receipt_freshly_reauthenticated") is not True
                        or row.get("host_publication_allowed") is not False
                        or row.get("physical_equivalence_proven") is not False):
                    raise ValueError("source parent lacks original nonpublishing receipt")
                observations[source_id].append({
                    "opening_identity_id": opening_id,
                    "flank_role": role,
                    "source_line_pt": list(coords),
                })
    shared = []
    for source_id, uses in sorted(observations.items()):
        identities = {use["opening_identity_id"] for use in uses}
        if len(identities) < 2:
            continue
        # One source observation cannot own two different original geometries.
        originals = {
            tuple(sorted((tuple(u["source_line_pt"][:2]),
                          tuple(u["source_line_pt"][2:]))))
            for u in uses
        }
        if len(originals) != 1:
            raise ValueError("same source observation has inconsistent original geometry")
        shared.append({
            "source_observation_id": source_id,
            "opening_identity_ids": sorted(identities),
            "source_uses": sorted(uses, key=lambda u: (
                u["opening_identity_id"], u["flank_role"])),
            "physical_equivalence_proven": False,
            "source_parent_transfer_allowed": False,
            "host_publication_allowed": False,
            "opening_count_publication_allowed": False,
        })
    return shared


def full_foreground_stage_report(original_bytes, required, foreground, *, pdf_bytes, expected_source_sha):
    original = json.loads(original_bytes)
    # The existing reader validates complete required-flank ownership and all
    # publication boundaries before any expensive original-source replay.
    joined = full_foreground_flank_census(original_bytes, required, foreground,
        pdf_bytes=pdf_bytes, expected_source_sha=expected_source_sha)
    original, foreground = _fresh_source_reports(pdf_bytes, original, foreground, expected_source_sha)
    graph = foreground["experimental_w2_w4"]
    rows = _flank_stage_rows(joined, original, required, graph)
    shared_original_source = cross_opening_source_usage(rows)
    return {"schema_version": "1.0.0", "source_sha256": expected_source_sha,
        "cross_opening_shared_original_pixel_sources": shared_original_source,
        "cross_opening_source_parent_transfer_allowed": False,
        "page_id": original["page_id"], "opening_rows": rows,
        "original_source_and_topology_freshly_reproduced": True,
        "input_source_primitive_count": graph["input_source_count"],
        "source_primitive_safety_cap": foreground["primitive_safety_cap"],
        "w4_candidate_address_collisions": graph["w4_candidate_address_collisions"],
        "full_page_graph_has_authenticated_floor_plan_scope": False,
        "first_unproved_authority": "ORIGINAL_VISIBLE_STRUCTURAL_WALL_LINE",
        "structural_source_universe_complete": False,
        "physical_equivalence_proven": False, "host_publication_allowed": False,
        "opening_count_publication_allowed": False, "metric_quantity_publication_allowed": False,
        "benchmark_accuracy": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--original-source-report", type=Path, required=True)
    parser.add_argument("--required-flank-report", type=Path, required=True)
    parser.add_argument("--foreground-source-report", type=Path, required=True)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = full_foreground_stage_report(args.original_source_report.read_bytes(),
        json.loads(args.required_flank_report.read_bytes()),
        json.loads(args.foreground_source_report.read_bytes()),
        pdf_bytes=args.pdf.read_bytes(), expected_source_sha=args.expected_source_sha)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"openings": len(report["opening_rows"]),
        "source_inputs": report["input_source_primitive_count"],
        "fresh_source_and_graph_replay": True, "host_publication_allowed": False}))


if __name__ == "__main__":
    main()
