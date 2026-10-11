"""Nonpublishing original G17 flank x full-positive source run census.

Every joined candidate retains original page/identity/pixel geometry. Dark ink,
an apparent host band, or a matching endpoint NEVER grants visible-wall,
physical equivalence, host, measurement, or takeoff authority.
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
from pb_source_visibility_authority import RASTER_RENDER_DPI
from pb_wall_room_topology_stage_a import DEFAULT_GAP_SNAP_TOLERANCE_PT
from tools.diag_gptmax_raster_host_source_membership import (
    _finite_coordinates, _finite_source_axis, _validate_aperture_basis,
)


def _indexed(rows, field, name):
    if not isinstance(rows, list) or len(rows) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
        raise ValueError("invalid bounded " + name)
    indexed = {}
    for r in rows:
        if not isinstance(r, dict):
            raise ValueError("malformed " + name)
        key = r.get(field)
        if not isinstance(key, str) or not key.strip() or key in indexed:
            raise ValueError("missing/duplicated " + name + " key")
        indexed[key] = r
    return indexed


def _read_pixel_runs(report, source_sha, page_id):
    if (report.get("inventory_kind") != "all_complete_original_foreground_runs"
            or report.get("source_sha256") != source_sha
            or report.get("page_id") != page_id
            or report.get("render_dpi") != RASTER_RENDER_DPI
            or report.get("original_source_render_reauthenticated") is not True
            or report.get("ordinary_visibility_rejects_shadow_kind") is not True
            or report.get("ordinary_source_snapshot_unchanged") is not True):
        raise ValueError("unavailable original full-foreground source scope")
    records = report.get("authenticated_pixel_source_records")
    if (not isinstance(records, list)
            or len(records) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
            or type(report.get("authenticated_pixel_source_count")) is not int
            or len(records) != report["authenticated_pixel_source_count"]):
        raise ValueError("incomplete full-foreground source inventory")
    seen = set()
    source = []
    for row in records:
        if (not isinstance(row, dict)
                or row.get("source_pixels_authenticated") is not True
                or row.get("ordinary_visible_segment_authority") is not False
                or row.get("physical_wall_authority") is not False
                or row.get("host_publication_allowed") is not False
                or row.get("proposition") != "source_observation_exists"):
            raise ValueError("pixel source lacks shadow-only ownership")
        item, proof = row.get("source_observation"), row.get("pixel_receipt")
        if not isinstance(item, dict) or not isinstance(proof, dict):
            raise ValueError("missing pixel source record/receipt")
        pid = item.get("observation_id")
        pixels = proof.get("pixel_geometry")
        axis = proof.get("orientation")
        if (not isinstance(pid, str) or not pid.strip() or pid in seen
                or item.get("source_sha256") != source_sha
                or item.get("page_id") != page_id
                or item.get("observation_kind") != "raster_full_foreground_run_shadow"
                or item.get("viewport_id") is not None
                or axis not in ("horizontal", "vertical")
                or not isinstance(pixels, (list, tuple)) or len(pixels) != 4
                or any(type(v) is not int or v < 0 for v in pixels)):
            raise ValueError("invalid original full-foreground source record")
        x0, y0, x1, y1 = pixels
        if not ((axis == "horizontal" and y0 == y1 and x1 > x0)
                or (axis == "vertical" and x0 == x1 and y1 > y0)):
            raise ValueError("noncomplete positive pixel run")
        if proof.get("run_pixel_count") != max(x1 - x0, y1 - y0) + 1:
            raise ValueError("positive scanline run count disagrees")
        coords = _finite_coordinates(item.get("geometry"), 4, "original source run")
        receipt = _finite_coordinates(proof.get("geometry"), 4, "pixel proof run")
        mapped = tuple(float(v) * 72.0 / RASTER_RENDER_DPI for v in pixels)
        if coords != receipt or coords != mapped:
            raise ValueError("original positive run pixel/page-space mismatch")
        if not all(isinstance(proof.get(k), str) and len(proof[k]) == 64
                   for k in ("foreground_sha256", "scanline_sha256")):
            raise ValueError("missing original scanline digest")
        seen.add(pid)
        source.append((pid, coords))
    return source


def full_foreground_flank_census(original_bytes: bytes, required: dict, pixels: dict,
                                 *, pdf_bytes: bytes, expected_source_sha: str):
    if not isinstance(original_bytes, bytes) or not isinstance(pdf_bytes, bytes):
        raise TypeError("exact original PDF/report must be immutable bytes")
    if sha256(pdf_bytes).hexdigest() != expected_source_sha:
        raise ValueError("actual source PDF SHA mismatch")
    original = json.loads(original_bytes)
    for label, report in (("original", original), ("required", required), ("pixels", pixels)):
        if (not isinstance(report, dict) or report.get("source_sha256") != expected_source_sha
                or report.get("host_publication_allowed") is not False
                or report.get("opening_count_publication_allowed") is not False
                or report.get("metric_quantity_publication_allowed") is not False
                or report.get("benchmark_accuracy") is not None):
            raise ValueError(label + " report provenance/publication disagreement")
    if (required.get("input_report_sha256") != sha256(original_bytes).hexdigest()
            or required.get("original_pdf_reauthenticated") is not False):
        raise ValueError("foreign required-flank report")
    page = original.get("page_id")
    if (not isinstance(page, str) or not page
            or page != required.get("page_id") or page != pixels.get("page_id")):
        raise ValueError("incompatible source page scope")
    openings = _indexed(original.get("opening_rows"), "opening_identity_id", "opening")
    requirements = _indexed(required.get("opening_rows"), "opening_identity_id", "required flank")
    if set(openings) != set(requirements):
        raise ValueError("incomplete original opening/required-flank universe")
    inventory = _read_pixel_runs(pixels, expected_source_sha, page)
    joined = []
    pixel_tol = _RASTER_WHOLE_WALL_CENTER_TOL_PT + _COORD_TOL
    snap_tol = DEFAULT_GAP_SNAP_TOLERANCE_PT + _COORD_TOL
    for opening_id in sorted(openings):
        basis = openings[opening_id].get("original_aperture_coordinate_basis")
        if not isinstance(basis, dict):
            raise ValueError("source opening coordinate basis unavailable")
        vectors = {k: _finite_coordinates(basis.get(k), 2, "source opening " + k)
                   for k in ("origin", "axis", "normal")}
        length, thickness = _finite_coordinates(
            (basis.get("length"), basis.get("thickness")), 2, "opening metric basis")
        opening = _OpeningGeometry(**vectors, length=length, thickness=thickness)
        _validate_aperture_basis(opening)
        requirement = requirements[opening_id]
        available = requirement.get("reported_flank_geometry_available")
        flanks = requirement.get("flanks")
        if type(available) is not bool or not isinstance(flanks, list) or len(flanks) != (2 if available else 0):
            raise ValueError("unsupported/contradictory G17 flank scope")
        matched = []
        roles = set()
        for flank in flanks:
            role = flank.get("role")
            if role not in ("left", "right") or role in roles:
                raise ValueError("missing/duplicated G17 flank side")
            roles.add(role)
            lo, hi = _finite_coordinates(flank.get("axis_span_pt"), 2, "G17 flank interval")
            cross_lo, cross_hi = _finite_coordinates(flank.get("normal_span_pt"), 2, "G17 band")
            (edge,) = _finite_coordinates((flank.get("end_axis_coordinate_pt"),), 1, "G17 flank end")
            if lo >= hi or cross_lo >= cross_hi:
                raise ValueError("malformed original flank geometry")
            candidates = []
            for source_id, line in inventory:
                _, projected, failure = _finite_source_axis(line, opening)
                if failure:
                    continue
                p_lo, p_hi, offset = projected
                endpoint = p_hi if role == "left" else p_lo
                if (abs(endpoint - edge) > snap_tol
                        or offset < cross_lo - pixel_tol or offset > cross_hi + pixel_tol
                        or min(p_hi, hi) - max(p_lo, lo) <= pixel_tol):
                    continue
                candidates.append({"source_observation_id": source_id,
                    "source_line_pt": list(line), "visible_wall_authority_proven": False,
                    "physical_wall_equivalence_proven": False, "host_publication_allowed": False})
            matched.append({"role": role, "pixel_run_candidates": sorted(candidates,
                key=lambda row: row["source_observation_id"]),
                "first_unproved_authority": ("ORIGINAL_VISIBLE_STRUCTURAL_WALL_LINE"
                    if candidates else "FULL_FOREGROUND_RUN_CANDIDATE_UNAVAILABLE"),
                "physical_host_proven": False, "host_publication_allowed": False})
        if available and roles != {"left", "right"}:
            raise ValueError("missing original flank role")
        joined.append({"opening_identity_id": opening_id,
                       "reported_flank_geometry_available": available,
                       "flanks": matched, "host_publication_allowed": False})
    return {"schema_version": "1.0.0", "source_sha256": expected_source_sha,
            "page_id": page, "input_foreground_source_count": len(inventory),
            "opening_rows": joined, "source_pdf_byte_sha_verified": True,
            "source_receipts_freshly_reauthenticated": False,
            "structural_source_universe_complete": False,
            "physical_equivalence_proven": False, "host_publication_allowed": False,
            "opening_count_publication_allowed": False,
            "metric_quantity_publication_allowed": False,
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
    result = full_foreground_flank_census(
        args.original_source_report.read_bytes(),
        json.loads(args.required_flank_report.read_bytes()),
        json.loads(args.foreground_source_report.read_bytes()),
        pdf_bytes=args.pdf.read_bytes(), expected_source_sha=args.expected_source_sha)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"source_pixel_runs": result["input_foreground_source_count"],
        "unhosted_openings_reported": len(result["opening_rows"]),
        "host_publication_allowed": False}))


if __name__ == "__main__":
    main()
