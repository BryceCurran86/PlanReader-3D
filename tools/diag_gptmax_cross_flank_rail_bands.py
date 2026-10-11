"""Read-only candidate pairing of original-positive source ink on BOTH opening flanks.

No original pixel run proves a physical wall, structural visibility, W2/W3
survival, W4 physical equivalence, a host, quantity, or opening count. Preserve
all geometrically valid alternatives; never choose nearest or first.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import itertools
import json
from math import isfinite
from pathlib import Path

from pb_opening_host_binding_authority import (
    _COORD_TOL, _RASTER_WHOLE_WALL_CENTER_TOL_PT, _OpeningGeometry,
)
from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from tools.diag_gptmax_raster_host_source_membership import (
    _finite_coordinates, _finite_source_axis, _validate_aperture_basis,
)


def _rows(rows, *, label):
    if not isinstance(rows, list) or len(rows) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
        raise ValueError(f"invalid bounded {label} row inventory")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"invalid {label} row")
        oid = row.get("opening_identity_id")
        if not isinstance(oid, str) or not oid.strip() or oid in result:
            raise ValueError(f"missing or duplicate {label} source opening")
        result[oid] = row
    return result


def _opening_geometry(row):
    basis = row.get("original_aperture_coordinate_basis")
    if not isinstance(basis, dict):
        raise ValueError("unavailable original native/raster opening coordinate basis")
    values = {k: _finite_coordinates(basis.get(k), 2, "aperture vector")
              for k in ("origin", "axis", "normal")}
    thickness, length = _finite_coordinates(
        (basis.get("thickness"), basis.get("length")), 2, "aperture dimensions")
    geometry = _OpeningGeometry(**values, length=length, thickness=thickness)
    _validate_aperture_basis(geometry)
    return geometry


def _side_candidates(row, role, opening):
    if not isinstance(row, dict) or row.get("role") != role:
        raise ValueError("reported flange side ownership unavailable")
    candidates = row.get("pixel_run_candidates")
    if not isinstance(candidates, list) or len(candidates) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
        raise ValueError("unbounded source-run flank inventory")
    source_ids = set()
    side = []
    ox, oy = opening.origin
    nx, ny = opening.normal
    for c in candidates:
        if not isinstance(c, dict):
            raise ValueError("missing exact source-run candidate")
        oid = c.get("source_observation_id")
        if not isinstance(oid, str) or not oid.strip() or oid in source_ids:
            raise ValueError("invalid or repeated original positive source observation")
        source_ids.add(oid)
        if any(c.get(k) is not False for k in (
                "host_publication_allowed", "visible_wall_authority_proven",
                "physical_wall_equivalence_proven")):
            raise ValueError("pixel candidate wrongly claims source wall authority")
        coords = _finite_coordinates(c.get("source_line_pt"), 4, "source pixel-run line")
        _, axis, fail = _finite_source_axis(coords, opening)
        if fail:
            raise ValueError("pixel source-run does not follow opening wall axis")
        mx, my = ((coords[0]+coords[2])*0.5, (coords[1]+coords[3])*0.5)
        offset = (mx-ox)*nx + (my-oy)*ny
        if not isfinite(offset):
            raise ValueError("nonfinite source normal offset")
        side.append((oid, offset, coords))
    return tuple(sorted(side))


def _paired_rails(rows, thickness, tol):
    rail_pairs = []
    for a, b in itertools.combinations(rows, 2):
        if abs(abs(a[1]-b[1])-thickness) <= tol:
            pair = tuple(sorted((a, b), key=lambda x:(x[1],x[0])))
            rail_pairs.append(pair)
    return tuple(rail_pairs)


def inspect_cross_flank_rails(original_bytes, foreground, pdf_bytes, *, expected_sha):
    """Read existing source evidence; a paired pixel band is NEVER host proof."""
    if type(original_bytes) is not bytes or type(pdf_bytes) is not bytes:
        raise TypeError("original reports and source PDF must be immutable byte strings")
    if sha256(pdf_bytes).hexdigest() != expected_sha:
        raise ValueError("original source PDF bytes do not match pinned SHA")
    original = json.loads(original_bytes)
    if not isinstance(foreground, dict):
        raise ValueError("original source flank report unavailable")
    for label, d in (("G17", original), ("foreground", foreground)):
        if d.get("source_sha256") != expected_sha or d.get("host_publication_allowed") is not False:
            raise ValueError(f"{label} source/report authority mismatch")
        if d.get("benchmark_accuracy") is not None:
            raise ValueError(f"{label} must not claim benchmark accuracy")
    if (foreground.get("source_pdf_byte_sha_verified") is not True
            or foreground.get("source_receipts_freshly_reauthenticated") is not False
            or foreground.get("physical_equivalence_proven") is not False
            or foreground.get("structural_source_universe_complete") is not False
            or foreground.get("opening_count_publication_allowed") is not False
            or foreground.get("metric_quantity_publication_allowed") is not False):
        raise ValueError("source-positive foreground report falsely claims physical authority")
    if original.get("page_id") != foreground.get("page_id"):
        raise ValueError("original page scope disagrees with source-run flanks")
    original_rows = _rows(original.get("opening_rows"), label="G17")
    flank_rows = _rows(foreground.get("opening_rows"), label="foreground")
    if set(flank_rows) != set(original_rows):
        raise ValueError("G17/foreground missing source opening identities")
    tol = _RASTER_WHOLE_WALL_CENTER_TOL_PT + _COORD_TOL
    observations = []
    for oid, f in sorted(flank_rows.items()):
        opening = _opening_geometry(original_rows[oid])
        if not isinstance(f.get("flanks"), list) or len(f["flanks"]) != 2:
            raise ValueError("original left/right source flanks incomplete")
        flanks = {r.get("role"):r for r in f["flanks"] if isinstance(r, dict)}
        if set(flanks) != {"left", "right"} or len(f["flanks"]) != len(flanks):
            raise ValueError("conflicting left/right source flank scope")
        left = _side_candidates(flanks["left"], "left", opening)
        right = _side_candidates(flanks["right"], "right", opening)
        side_pairs = {role: _paired_rails(rows, opening.thickness, tol)
                      for role, rows in (("left",left),("right",right))}
        four_line_alternatives = []
        for a, b in itertools.product(side_pairs["left"], side_pairs["right"]):
            la,lb = a
            ra,rb = b
            sources = (la[0],lb[0],ra[0],rb[0])
            # Shared line across an aperture can be printed annotation ink;
            # it cannot be independent left/right physical flank support.
            if len(set(sources)) != 4:
                continue
            errors = (abs(la[1]-ra[1]), abs(lb[1]-rb[1]))
            if max(errors) > tol:
                continue
            four_line_alternatives.append({
                "left_source_observation_ids": [la[0],lb[0]],
                "right_source_observation_ids": [ra[0],rb[0]],
                "source_normal_offsets_pt": {
                    "left": [la[1],lb[1]], "right":[ra[1],rb[1]]},
                "max_cross_flank_rail_displacement_pt": max(errors),
                "source_pixel_ink_present_on_four_runs": True,
                "source_visible_wall_line_proven": False,
                "physical_wall_pair_equivalence_proven": False,
                "physical_host_publication_allowed": False,
            })
        four_line_alternatives.sort(key=lambda a:(
            tuple(a["left_source_observation_ids"]),
            tuple(a["right_source_observation_ids"])))
        observations.append({
            "opening_identity_id":oid,
            "source_run_count_by_side":{"left":len(left),"right":len(right)},
            "paired_source_rails_by_side":{
                role:len(side_pairs[role]) for role in ("left","right")},
            "cross_flank_source_pixel_band_alternatives":four_line_alternatives,
            "geometric_pixel_rail_alternatives_complete_for_reported_source_runs":True,
            "first_unproved_authority":"VISIBLE_STRUCTURAL_WALL_ROLE_AND_PHYSICAL_EQUIVALENCE"
                if four_line_alternatives else "FOUR_RAIL_SOURCE_GEOMETRY_UNPROVEN",
            "authenticated_physical_host":False,
            "host_publication_allowed":False,
        })
    return {
        "schema_version":"1.0.0", "source_sha256":expected_sha,
        "page_id":original["page_id"], "opening_rows":observations,
        "physical_source_render_ink_reauthenticated_by_this_join":False,
        "original_pdf_byte_sha_verified":True,
        "source_pixel_band_geometry_only":True,
        "source_universe_completeness_proven":False,
        "host_publication_allowed":False,
        "physical_equivalence_proven":False,
        "opening_count_publication_allowed":False,
        "metric_quantity_publication_allowed":False,
        "benchmark_accuracy":None,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf",type=Path,required=True)
    parser.add_argument("--original-g17-report",type=Path,required=True)
    parser.add_argument("--source-flank-report",type=Path,required=True)
    parser.add_argument("--expected-source-sha",required=True)
    parser.add_argument("--output",type=Path,required=True)
    a=parser.parse_args()
    result=inspect_cross_flank_rails(
        a.original_g17_report.read_bytes(),
        json.loads(a.source_flank_report.read_text()),
        a.pdf.read_bytes(),expected_sha=a.expected_source_sha)
    a.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"source_flanks":len(result["opening_rows"]),
                      "four_rail_alternatives":sum(
                          len(r["cross_flank_source_pixel_band_alternatives"])
                          for r in result["opening_rows"]),
                      "host_publication_allowed":False}))


if __name__=="__main__":
    main()
