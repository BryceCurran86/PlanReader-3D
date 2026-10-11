"""Read-only original opening-flank × independently nominated pixel-run ledger.

These input JSON reports are not fresh source authority. Even with the original
PDF SHA checked, this join NEVER promotes pixel runs into visible wall lines,
W4 physical identities, opening hosts, counts, quantities or benchmark scoring.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_opening_host_binding_authority import (
    _COORD_TOL, _RASTER_WHOLE_WALL_CENTER_TOL_PT, _OpeningGeometry,
)
from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from pb_wall_room_topology_stage_a import DEFAULT_GAP_SNAP_TOLERANCE_PT
from tools.diag_gptmax_raster_host_source_membership import (
    _finite_coordinates, _finite_source_axis, _validate_aperture_basis,
)


def _rows_by_id(rows, key, label):
    if not isinstance(rows, list) or len(rows) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
        raise ValueError(f"invalid bounded {label}")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"invalid {label} entry")
        address = row.get(key)
        if not isinstance(address, str) or not address.strip() or address in result:
            raise ValueError(f"missing or duplicate {label} identity")
        result[address] = row
    return result


def _nonpublishing(report, label):
    if not isinstance(report, dict):
        raise ValueError(f"invalid {label} report")
    for key in ("host_publication_allowed", "opening_count_publication_allowed",
                "metric_quantity_publication_allowed"):
        if report.get(key) is not False:
            raise ValueError(f"{label} unexpectedly claims publication authority")
    if report.get("benchmark_accuracy") is not None:
        raise ValueError(f"{label} unexpectedly claims benchmark accuracy")


def _opening_basis(row):
    basis = row.get("original_aperture_coordinate_basis")
    if not isinstance(basis, dict):
        raise ValueError("original aperture basis unavailable")
    vectors = {name: _finite_coordinates(basis.get(name), 2, "original aperture vector")
               for name in ("origin", "axis", "normal")}
    length, thickness = _finite_coordinates(
        (basis.get("length"), basis.get("thickness")), 2, "original aperture dimensions")
    opening = _OpeningGeometry(**vectors, length=length, thickness=thickness)
    _validate_aperture_basis(opening)
    return opening


def _pixel_inventory(report, source_sha, page_id):
    if report.get("ordinary_visibility_rejects_shadow_kind") is not True:
        raise ValueError("pixel shadow visibility exclusion unavailable")
    if report.get("ordinary_source_snapshot_unchanged") is not True:
        raise ValueError("ordinary source snapshot retention unavailable")
    if report.get("source_universe_completeness_proven") is not False:
        raise ValueError("pixel shadow completeness status unavailable")
    records = report.get("authenticated_pixel_source_records")
    if not isinstance(records, list) or len(records) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
        raise ValueError("invalid bounded pixel source inventory")
    if type(report.get("authenticated_pixel_source_count")) is not int or (
            report["authenticated_pixel_source_count"] != len(records)):
        raise ValueError("pixel report source inventory count mismatch")
    verified = {}
    for item in records:
        if not isinstance(item, dict) or item.get("source_pixels_authenticated") is not True:
            raise ValueError("pixel report lacks self-declared source receipt")
        if item.get("ordinary_visible_segment_authority") is not False or (
                item.get("host_publication_allowed") is not False):
            raise ValueError("pixel report promotes a shadow receipt")
        row, proof = item.get("source_observation"), item.get("pixel_receipt")
        if not isinstance(row, dict) or not isinstance(proof, dict):
            raise ValueError("pixel source record/receipt unavailable")
        oid = row.get("observation_id")
        if not isinstance(oid, str) or not oid.strip() or oid in verified:
            raise ValueError("invalid or duplicate pixel source observation")
        if (row.get("source_sha256") != source_sha or row.get("page_id") != page_id
                or row.get("observation_kind") != "raster_positive_pixel_run_shadow"
                or row.get("viewport_id") is not None):
            raise ValueError("pixel source observation outside shadow document/page")
        coords = _finite_coordinates(row.get("geometry"), 4, "pixel source geometry")
        receipt_coords = _finite_coordinates(proof.get("geometry"), 4, "pixel receipt geometry")
        if coords != receipt_coords or coords[:2] == coords[2:]:
            raise ValueError("pixel source/receipt geometry disagreement")
        verified[oid] = coords
    return verified


def _ancestry(report, pixel_ids):
    graph = report.get("experimental_w2_w4")
    if not isinstance(graph, dict) or graph.get("host_publication_allowed") is not False:
        raise ValueError("unavailable nonpublishing experimental W2/W4 inventory")
    edges = _rows_by_id(graph.get("all_w2_edges"), "edge_id", "experimental W2 edge")
    collapsed = _rows_by_id(graph.get("all_snap_collapsed_fragments"), "fragment_id",
                            "experimental W2 collapsed fragment")
    census = _rows_by_id(graph.get("source_parent_census"), "source_observation_id",
                         "experimental source parent")
    if any(oid not in census for oid in pixel_ids):
        raise ValueError("pixel source observation missing experimental W2 census")
    # W4 addresses are observed candidate alternatives, never physical owners.
    # Geometric W4 address collisions are permitted, but an edge cannot cite
    # an address absent from every corresponding experimental W4 member row.
    members = {}
    walls = graph.get("all_experimental_w4_candidates")
    if not isinstance(walls, list) or len(walls) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
        raise ValueError("invalid experimental W4 candidate inventory")
    for wall in walls:
        if not isinstance(wall, dict):
            raise ValueError("invalid experimental W4 candidate row")
        cid = wall.get("candidate_id")
        owned = wall.get("w2_edge_ids")
        if (not isinstance(cid, str) or not cid.strip()
                or not isinstance(owned, list) or not owned
                or any(not isinstance(eid, str) or eid not in edges for eid in owned)
                or len(set(owned)) != len(owned)):
            raise ValueError("invalid experimental W4 edge membership")
        members.setdefault(cid, set()).update(owned)
    mapped = {}
    for oid in pixel_ids:
        row = census[oid]
        edge_ids = row.get("w2_edge_ids")
        collapsed_ids = row.get("snap_collapsed_fragment_ids")
        if (not isinstance(edge_ids, list) or len(edge_ids) != len(set(edge_ids))
                or not isinstance(collapsed_ids, list)
                or len(collapsed_ids) != len(set(collapsed_ids))):
            raise ValueError("invalid pixel-to-W2 source lineage")
        if any(e not in edges or oid not in edges[e].get("source_observation_ids", [])
               for e in edge_ids):
            raise ValueError("W2 edge does not claim pixel source parent")
        if any(c not in collapsed or oid not in collapsed[c].get("source_observation_ids", [])
               for c in collapsed_ids):
            raise ValueError("collapsed fragment does not claim pixel source parent")
        w4 = sorted({owner for eid in edge_ids for owner in
                     edges[eid].get("experimental_w4_candidate_ids", [])
                     if isinstance(owner, str) and owner.strip()})
        if any(not isinstance(w, str) or not w.strip()
               for eid in edge_ids for w in edges[eid].get("experimental_w4_candidate_ids", [])):
            raise ValueError("invalid experimental W4 address")
        if any(eid not in members.get(cid, set())
               for eid in edge_ids for cid in edges[eid].get("experimental_w4_candidate_ids", [])):
            raise ValueError("unbacked experimental W4 edge address")
        mapped[oid] = {"w2_edge_ids": sorted(edge_ids),
                       "snap_collapsed_fragment_ids": sorted(collapsed_ids),
                       "experimental_w4_candidate_alternatives": w4}
    return mapped


def join_flank_pixel_evidence(original_report_bytes: bytes, required_report: dict,
                              pixel_report: dict, *, expected_source_sha: str,
                              original_pdf_bytes: bytes):
    """Join every reported flank with all qualifying pixel runs; no owner chosen."""
    if not isinstance(original_report_bytes, bytes):
        raise TypeError("original diagnostic report must be raw immutable bytes")
    original = json.loads(original_report_bytes)
    for label, report in (("original", original), ("flank", required_report),
                          ("pixel", pixel_report)):
        _nonpublishing(report, label)
        if report.get("source_sha256") != expected_source_sha:
            raise ValueError(f"{label} source SHA mismatch")
    if not isinstance(original_pdf_bytes, bytes):
        raise TypeError("original PDF must be immutable bytes")
    if sha256(original_pdf_bytes).hexdigest() != expected_source_sha:
        raise ValueError("original PDF byte SHA does not match source reports")
    if required_report.get("input_report_sha256") != sha256(original_report_bytes).hexdigest():
        raise ValueError("required flank report does not match exact source report bytes")
    if required_report.get("original_pdf_reauthenticated") is not False:
        raise ValueError("flank report misstates original PDF authentication")
    page_id = original.get("page_id")
    if (not isinstance(page_id, str) or not page_id
            or required_report.get("page_id") != page_id
            or pixel_report.get("page_id") != page_id):
        raise ValueError("opening and pixel page scope mismatch")
    openings = _rows_by_id(original.get("opening_rows"), "opening_identity_id",
                           "original opening")
    requirements = _rows_by_id(required_report.get("opening_rows"), "opening_identity_id",
                                "required opening flank")
    if set(openings) != set(requirements):
        raise ValueError("original opening and required-flank universes disagree")
    pixel_geometry = _pixel_inventory(pixel_report, expected_source_sha, page_id)
    ancestry = _ancestry(pixel_report, pixel_geometry)
    joined = []
    snap_tol = DEFAULT_GAP_SNAP_TOLERANCE_PT + _COORD_TOL
    band_tol = _RASTER_WHOLE_WALL_CENTER_TOL_PT + _COORD_TOL
    for oid in sorted(openings):
        opening = _opening_basis(openings[oid])
        requirement = requirements[oid]
        flanks = requirement.get("flanks")
        visible_flanks = requirement.get("reported_flank_geometry_available")
        if (type(visible_flanks) is not bool or not isinstance(flanks, list)
                or len(flanks) != (2 if visible_flanks else 0)):
            raise ValueError("reported flank completeness/geometry disagreement")
        output = []
        seen_roles = set()
        for flank in flanks:
            role = flank.get("role") if isinstance(flank, dict) else None
            if role not in ("left", "right") or role in seen_roles:
                raise ValueError("invalid or duplicate reported flank role")
            seen_roles.add(role)
            lo, hi = _finite_coordinates(flank.get("axis_span_pt"), 2, "source flank axis")
            cross_lo, cross_hi = _finite_coordinates(
                flank.get("normal_span_pt"), 2, "source flank normal band")
            (endpoint,) = _finite_coordinates(
                (flank.get("end_axis_coordinate_pt"),), 1, "source flank endpoint")
            if lo >= hi or cross_lo >= cross_hi:
                raise ValueError("invalid reported source flank bounds")
            candidates = []
            for pid, coords in pixel_geometry.items():
                _, data, failure = _finite_source_axis(coords, opening)
                if failure:
                    continue
                p_lo, p_hi, offset = data
                observed_endpoint = p_hi if role == "left" else p_lo
                if (abs(observed_endpoint-endpoint) > snap_tol
                        or offset < cross_lo-band_tol or offset > cross_hi+band_tol
                        or min(p_hi, hi)-max(p_lo, lo) <= band_tol):
                    continue
                candidates.append({
                    "pixel_source_observation_id": pid,
                    "source_line_pt": list(coords),
                    "experimental_lineage": ancestry[pid],
                    "original_visible_wall_line_authority_proven": False,
                    "physical_wall_equivalence_proven": False,
                    "host_publication_allowed": False,
                })
            output.append({"role": role, "pixel_run_candidates": sorted(
                candidates, key=lambda r: r["pixel_source_observation_id"]),
                "first_unproved_authority": (
                    "ORIGINAL_VISIBLE_WALL_LINE_AUTHORITY"
                    if candidates else "PIXEL_SOURCE_FLANK_CANDIDATE_UNAVAILABLE"),
                "physical_host_proven": False, "host_publication_allowed": False})
        if visible_flanks and seen_roles != {"left", "right"}:
            raise ValueError("complete reported flanks must contain both roles")
        joined.append({
            "opening_identity_id": oid,
            "reported_original_binding_reason_codes":
                openings[oid].get("original_binding_reason_codes", []),
            "flank_geometry_reported": visible_flanks,
            "flanks": output,
            "source_report_is_independent_production_proof": False,
            "host_publication_allowed": False,
        })
    return {
        "schema_version": "1.0.0", "source_sha256": expected_source_sha,
        "page_id": page_id, "opening_rows": joined,
        "original_pdf_byte_sha_verified": True,
        "diagnostic_report_join_only": True,
        "source_receipts_freshly_reauthenticated": False,
        "source_universe_completeness_proven": False,
        "physical_equivalence_proven": False,
        "host_publication_allowed": False,
        "opening_count_publication_allowed": False,
        "metric_quantity_publication_allowed": False,
        "benchmark_accuracy": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--original-source-report", required=True, type=Path)
    parser.add_argument("--required-flank-report", required=True, type=Path)
    parser.add_argument("--pixel-source-report", required=True, type=Path)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    original = args.original_source_report.read_bytes()
    required = json.loads(args.required_flank_report.read_bytes())
    pixel = json.loads(args.pixel_source_report.read_bytes())
    result = join_flank_pixel_evidence(
        original, required, pixel, expected_source_sha=args.expected_source_sha,
        original_pdf_bytes=args.pdf.read_bytes())
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"opening_rows": len(result["opening_rows"]),
                      "host_publication_allowed": False}))


if __name__ == "__main__":
    main()
