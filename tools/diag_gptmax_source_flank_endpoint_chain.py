"""Nonpublishing original G17 flank vs W2/W4 endpoint-chain verification.

The ledger is an archived producer-issued source receipt, NOT a new PDF authority.
Only a separately SHA-checked original-PDF producer replay may corroborate it.
No W4 wall, host, physical identity, dimension or quantity is created.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path

from pb_opening_host_binding_authority import (
    _COORD_TOL, _OpeningGeometry, _RASTER_WHOLE_WALL_CENTER_TOL_PT,
    _source_line_axis_data,
)
from pb_wall_room_topology_stage_a import DEFAULT_GAP_SNAP_TOLERANCE_PT

SOURCE_ONLY = "original_source_host_flank_endpoint_chain_shadow"
_MISSING = frozenset({
    "raster_source_band_left_source_primitive_unmapped",
    "raster_source_band_right_source_primitive_unmapped",
})


def _valid_id(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("invalid source identity")
    return value


def _finite(value, size):
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError("invalid original source geometry")
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in value):
        raise ValueError("nonfinite original source geometry")
    return tuple(float(x) for x in value)


def _opening(basis):
    geometry = _OpeningGeometry(
        origin=_finite(basis["origin"], 2),
        axis=_finite(basis["axis"], 2),
        normal=_finite(basis["normal"], 2),
        length=_finite([basis["length"]], 1)[0],
        thickness=_finite([basis["thickness"]], 1)[0],
    )
    if (geometry.length <= _COORD_TOL or geometry.thickness <= _COORD_TOL
            or abs(math.hypot(*geometry.axis) - 1.) > _COORD_TOL
            or abs(math.hypot(*geometry.normal) - 1.) > _COORD_TOL
            or abs(sum(a*b for a, b in zip(geometry.axis, geometry.normal))) > _COORD_TOL):
        raise ValueError("invalid original opening coordinate basis")
    return geometry


def _projection(point, origin, basis):
    return (point[0] - origin[0])*basis[0] + (point[1] - origin[1])*basis[1]


def _original_flanks(observations, opening):
    kinds = Counter(x.get("observation_kind") for x in observations)
    if len(observations) != 8 or kinds["raster_wall_band_face"] != 4 or kinds["raster_wall_band_end"] != 2:
        raise ValueError("incomplete original sealed G17 flank support")
    ids = [_valid_id(x["observation_id"]) for x in observations]
    if len(set(ids)) != 8:
        raise ValueError("ambiguous original G17 source observation identities")
    by_interval = {}
    for obs in observations:
        if obs["observation_kind"] != "raster_wall_band_face":
            continue
        data = _source_line_axis_data(_finite(obs["geometry_pdf_pts"], 4), opening)
        if data is None:
            raise ValueError("source face not parallel to its own opening")
        lo, hi, offset = data
        by_interval.setdefault((lo, hi), []).append((offset, obs["observation_id"]))
    if len(by_interval) != 2 or any(len(v) != 2 for v in by_interval.values()):
        raise ValueError("original source face pairs incomplete")
    pixel = _RASTER_WHOLE_WALL_CENTER_TOL_PT + _COORD_TOL
    ends = []
    for obs in observations:
        if obs["observation_kind"] != "raster_wall_band_end":
            continue
        x0, y0, x1, y1 = _finite(obs["geometry_pdf_pts"], 4)
        ends.append((
            sorted(_projection(p, opening.origin, opening.axis)
                   for p in ((x0, y0), (x1, y1))),
            sorted(_projection(p, opening.origin, opening.normal)
                   for p in ((x0, y0), (x1, y1))),
            obs["observation_id"],
        ))
    flanks = {}
    for (lo, hi), values in by_interval.items():
        values = sorted(values)
        cross_lo, cross_hi = values[0][0], values[1][0]
        if cross_hi - cross_lo <= _COORD_TOL or cross_lo > pixel or cross_hi < -pixel:
            raise ValueError("original flank does not bracket its opening")
        if lo < -pixel and abs(hi) <= pixel:
            role, boundary = "left", hi
        elif hi > opening.length + pixel and abs(lo-opening.length) <= pixel:
            role, boundary = "right", lo
        else:
            raise ValueError("G17 source flank cannot be allocated without guessing")
        own_ends = [oid for along, cross, oid in ends
            if all(abs(v-boundary) <= _COORD_TOL for v in along)
            and abs(cross[0]-cross_lo) <= _COORD_TOL
            and abs(cross[1]-cross_hi) <= _COORD_TOL]
        if len(own_ends) != 1 or role in flanks:
            raise ValueError("G17 source end is missing or competing")
        flanks[role] = {
            "role": role, "axis_interval_pt": [lo, hi],
            "band_normal_offsets_pt": [cross_lo, cross_hi],
            "flank_end_axis_pt": boundary,
            "original_source_faces": sorted(id for _, id in values),
            "original_source_end": own_ends[0],
        }
    if set(flanks) != {"left", "right"}:
        raise ValueError("original signed G17 left/right flank incomplete")
    return flanks


def original_flank_endpoint_census(ledger, *, expected_source_sha):
    if ledger.get("source_sha256") != expected_source_sha:
        raise ValueError("original source hash mismatch")
    for key in ("snapshot_id", "decision_scope_id"):
        _valid_id(ledger.get(key))
    counts = ledger.get("baseline_summary", {})
    if tuple(counts.get(k) for k in (
        "canonical_opening_records", "authenticated_hosts",
        "resolved_source_frames", "canonical_opening_area_records")) != (21, 15, 9, 8):
        raise ValueError("historical original signed producer baseline changed")
    sealed = ledger.get("current_main_sealed_handoff") or {}
    if (sealed.get("quantity_count") != 8
            or sealed.get("sealed_quantity_ids") != sealed.get("customer_verified_quantity_ids")
            or len(sealed.get("sealed_quantity_ids", [])) != 8):
        raise ValueError("signed customer quantity inventory changed")
    if any(value is not False for value in ledger.get("authority_grants", {}).values()):
        raise ValueError("archived source ledger falsely grants new authority")
    cases = ledger.get("case_evidence")
    if not isinstance(cases, list):
        raise ValueError("source case inventory missing")
    rows = []
    for case in cases:
        host = case.get("host_binding", {})
        if host.get("status") != "abstained":
            continue
        reasons = set(host.get("reason_codes", []))
        missing = reasons.intersection(_MISSING)
        if len(missing) != 1 or host.get("record_id") is not None:
            raise ValueError("host abstention and exact first failure disagree")
        opening_id = _valid_id(case["physical_opening_id"])
        if host.get("opening_identity_id") != opening_id:
            raise ValueError("host versus opening identity mismatch")
        opening = _opening(case["original_aperture_coordinate_basis"])
        flanks = _original_flanks(case["source_g17_observations"], opening)
        raw = case["source_w4_ancestry_audit"].get("diagnostic_local_raster_lines", [])
        source_ids = [line["source_primitive_id"] for line in raw]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("duplicate reported original source parent")
        by_role = {}
        for role, flank in flanks.items():
            lo, hi = flank["axis_interval_pt"]
            cross_lo, cross_hi = flank["band_normal_offsets_pt"]
            edge = flank["flank_end_axis_pt"]
            pixel = _RASTER_WHOLE_WALL_CENTER_TOL_PT + _COORD_TOL
            snap = DEFAULT_GAP_SNAP_TOLERANCE_PT + _COORD_TOL
            local = []
            for line in raw:
                parent = _valid_id(line["source_primitive_id"])
                source = _source_line_axis_data(
                    _finite(line["original_source_line_pt"], 4), opening)
                if source is None:
                    raise ValueError("reported original local source not parallel")
                p_lo, p_hi, offset = source
                original_member = (
                    abs((p_hi if role == "left" else p_lo)-edge) <= snap
                    and cross_lo-pixel <= offset <= cross_hi+pixel
                    and min(p_hi, hi) - max(p_lo, lo) > pixel
                )
                source_w4 = line["exact_positive_ancestry_w4_candidate_ids"]
                if len(set(source_w4)) != len(source_w4):
                    raise ValueError("duplicate original W4 identity addresses")
                source_w4 = sorted(_valid_id(v) for v in source_w4)
                fragments = []
                for fragment in line.get("w2_source_fragment_geometry_by_w4_candidate", []):
                    fid = _valid_id(fragment["wall_candidate_id"])
                    if fid not in source_w4:
                        raise ValueError("W2 fragment invented an unissued W4 parent")
                    s = _source_line_axis_data(
                        _finite(fragment["producer_w2_fragment_geometry_pt"], 4),
                        opening)
                    if s is None:
                        raise ValueError("reported W2 fragment is not original parallel source")
                    s_lo, s_hi, s_offset = s
                    local_end = s_hi if role == "left" else s_lo
                    source_contained = fragment.get(
                        "source_parent_contains_w2_fragment_geometry") is True
                    reaches = (
                        source_contained and original_member
                        and abs(local_end-edge) <= snap
                        and cross_lo-snap <= s_offset <= cross_hi+snap
                        and min(s_hi,p_hi,hi)-max(s_lo,p_lo,lo) > pixel
                    )
                    fragments.append({
                        "original_w2_edge_id": _valid_id(fragment["source_edge_id"]),
                        "original_w4_wall_id": fid,
                        "source_parent_contains_original_w2_fragment": source_contained,
                        "original_endpoint_and_band_chain_candidate": bool(reaches),
                        "original_fragment_axis_interval_pt": [s_lo, s_hi],
                        "original_fragment_normal_offset_pt": s_offset,
                    })
                # Preserve every competing authenticated source parent, even
                # when it fails geometry; a "nearest eligible" filter could
                # silently discard real structural negative evidence.
                local.append({
                    "source_primitive_id": parent,
                    "original_parent_meets_existing_host_band_predicate": bool(original_member),
                    "all_original_w4_candidate_addresses": source_w4,
                    "source_parent_endpoint_axis_pt": p_hi if role == "left" else p_lo,
                    "source_parent_normal_offset_pt": offset,
                    "original_w2_fragments": sorted(fragments,
                          key=lambda f: (f["original_w2_edge_id"], f["original_w4_wall_id"])),
                    "positive_local_original_w4_chain_corroborated": False,
                    "host_publication_allowed": False,
                })
            by_role[role] = {
                **flank, "reported_parent_candidates": sorted(
                    local,key=lambda x:x["source_primitive_id"]),
                "all_competing_w4_identities_preserved": True,
                "original_parent_source_band_predicate_positive_count": sum(
                    bool(p["original_parent_meets_existing_host_band_predicate"])
                    for p in local),
                "physical_local_wall_ownership_proven": False,
            }
        rows.append({
            "opening_identity_id": opening_id,
            "existing_original_host_reasons": sorted(reasons),
            "first_unmapped_flank": sorted(missing)[0],
            "original_flanks": by_role,
            "original_W4_host_record_granted": False,
            "new_frame_granted": False,
            "measured_width_height_granted": False,
            "customer_quantity_granted": False,
        })
    if len(rows) != counts["canonical_opening_records"]-counts["authenticated_hosts"]:
        raise ValueError("six-case original unhosted universe changed")
    if len({r["opening_identity_id"] for r in rows}) != len(rows):
        raise ValueError("same original opening duplicated")
    return {
        "status": SOURCE_ONLY,
        "original_source_sha256": expected_source_sha,
        "reported_source_snapshot_id": ledger["snapshot_id"],
        "reported_decision_scope_id": ledger["decision_scope_id"],
        "source_rows": sorted(rows,key=lambda x:x["opening_identity_id"]),
        "archived_ledger_only_not_fresh_producer_receipt": True,
        "original_pdf_reauthenticated_by_this_function": False,
        "host_authority_granted": False, "frame_authority_granted": False,
        "opening_count_granted": False, "ordered_dimensions_granted": False,
        "customer_quantity_granted": False,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger",type=Path,required=True)
    parser.add_argument("--sha256",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    payload=args.ledger.read_bytes()
    result=original_flank_endpoint_census(
        json.loads(payload),expected_source_sha=args.sha256)
    result["archived_ledger_sha256"]=sha256(payload).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n",
                           encoding="utf-8")
    print("Original archived unhosted source cases:",len(result["source_rows"]))
    for row in result["source_rows"]:
        print(row["opening_identity_id"],row["first_unmapped_flank"],
              {side:len(row["original_flanks"][side]["reported_parent_candidates"])
               for side in ("left","right")})


if __name__ == "__main__":
    main()
