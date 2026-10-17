"""Opening-local original-source witness for aligned-fragment DISTINCT failure.

Diagnostic only. Does not publish a frame, quantity, count, or FIRM value.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_frame_authority import (
    OpeningHostFrameProducer,
    _COORD_TOL,
    _pair_lookup,
)
from pb_opening_host_binding_authority import (
    RASTER_WALL_BAND_HOST_PATTERNS,
    _candidate_axis_data,
    _opening_geometry,
    _source_line_axis_data,
    _RASTER_WHOLE_WALL_CENTER_TOL_PT,
)
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_physical_wall_identity import (
    PhysicalEquivalenceClass,
    classify_physical_wall_pair,
    physical_wall_pair_identity_candidacy,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

TARGET = "physical_opening_existence_2c31ccb074d8eae86cac281c0fde1176"


def _dot(point, axis):
    return point[0] * axis[0] + point[1] * axis[1]


def _identity_row(record):
    identity = record.physical_identity
    return {
        "wall_candidate_id": record.wall_candidate_id,
        "candidate_identity_id": identity.candidate_identity_id,
        "source_primitive_ids": list(identity.source_primitive_ids),
        "edge_ids": list(identity.edge_ids),
        "path_fingerprint": list(identity.path_fingerprint or ()),
        "centerline_pts": [list(pt) for pt in record.wall_candidate.centerline_pts],
        "source_edge_fragments": [
            {
                "edge_id": fragment.edge_id,
                "source_primitive_ids": list(fragment.source_primitive_ids),
                "geometry": list(fragment.geometry),
            }
            for fragment in (record.source_edge_fragments or ())
        ],
    }


def witness(pdf: bytes, *, page_id: str, expected_sha256: str, target: str) -> dict:
    if sha256(pdf).hexdigest() != expected_sha256:
        raise ValueError("original source SHA mismatch")
    src = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    pub = src.ingest_native_pdf_bytes(
        document_id=f"live-source:{expected_sha256[:32]}",
        source_bytes=pdf,
        source_locator="memory://cursor-aligned-fragment.pdf",
        page_ids=(int(page_id),),
    )
    comp = compose_live_wall_opening_authority(
        source_visibility_producer=src,
        revision_id=pub.revision.revision_id,
        page_ids=(page_id,),
    )
    published = src.published_snapshot_for_revision(pub.revision.revision_id)
    producer = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=comp.physical_opening_authority,
        host_binding_authority=comp.opening_host_binding_authority,
        physical_wall_candidate_authority=comp.physical_wall_candidate_authority,
        raster_split_frame_shadow=True,
    )
    trace = next(row for row in comp.opening_bindings if row.opening_identity_id == target)
    selector = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=expected_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=trace.representative_observation_id,
    )
    opening = comp.physical_opening_authority.prove_existence(selector).existence_record
    binding = comp.opening_host_binding_authority.resolve(
        comp.binding_selectors[target]
    ).record
    geometry = _opening_geometry(comp.physical_opening_authority, opening)
    frame = producer.publish(
        opening_selector=selector,
        host_binding_selector=comp.binding_selectors[target],
    )
    wall_scope = producer._walls.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=binding.document_id,
            revision_id=binding.revision_id,
            source_sha256=binding.source_sha256,
            snapshot_id=binding.snapshot_id,
            page_id=binding.page_id,
            decision_scope_id=binding.decision_scope_id,
        )
    )
    records_by_id = {record.wall_candidate_id: record for record in wall_scope.records}
    component_ids = tuple(binding.member_wall_candidate_ids)
    axis = (float(geometry.axis[0]), float(geometry.axis[1]))
    normal = (float(geometry.normal[0]), float(geometry.normal[1]))
    wall_thickness = float(geometry.thickness)
    center_n = _dot(geometry.origin, normal)
    pair_lookup = _pair_lookup(wall_scope.equivalence)
    component_set = set(component_ids)
    competitors = []
    for record in wall_scope.records:
        wall_id = record.wall_candidate_id
        if wall_id in component_set:
            continue
        allowance = _RASTER_WHOLE_WALL_CENTER_TOL_PT + _COORD_TOL
        points = record.wall_candidate.centerline_pts
        aligned_segments = []
        for start, end in zip(points, points[1:]):
            data = _source_line_axis_data((*start, *end), geometry)
            if data is not None and abs(data[2]) <= wall_thickness / 2.0 + allowance:
                aligned_segments.append({
                    "start": list(start),
                    "end": list(end),
                    "along_min": data[0],
                    "along_max": data[1],
                    "offset": data[2],
                })
        if not aligned_segments:
            continue
        pair_rows = []
        missing_distinct = False
        for member_id in component_ids:
            key = tuple(sorted((wall_id, member_id)))
            stored = pair_lookup.get(key)
            live = classify_physical_wall_pair(
                records_by_id[wall_id].physical_identity,
                records_by_id[member_id].physical_identity,
            )
            eligible, candidacy_reason = physical_wall_pair_identity_candidacy(
                records_by_id[wall_id].physical_identity,
                records_by_id[member_id].physical_identity,
            )
            if stored is not PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS:
                missing_distinct = True
            pair_rows.append({
                "member_id": member_id,
                "stored_classification": None if stored is None else stored.value,
                "live_classification": live.value,
                "identity_candidate": eligible,
                "identity_candidacy_reason": candidacy_reason,
            })
        competitors.append({
            "blocks_frame": missing_distinct,
            "wall": _identity_row(record),
            "aligned_segments": aligned_segments,
            "pairs": pair_rows,
        })
    return {
        "status": "UNPUBLISHED_ALIGNED_FRAGMENT_WITNESS",
        "source_sha256": expected_sha256,
        "snapshot_id": published.snapshot.snapshot_id,
        "page_id": page_id,
        "physical_opening_id": target,
        "host_reason_codes": list(trace.reason_codes),
        "host_member_ids": list(component_ids),
        "host_members": [_identity_row(records_by_id[wall_id]) for wall_id in component_ids],
        "opening_origin": list(geometry.origin),
        "opening_axis": list(geometry.axis),
        "opening_normal": list(geometry.normal),
        "opening_length": geometry.length,
        "opening_thickness": geometry.thickness,
        "shadow_frame_status": frame.status.value,
        "shadow_frame_reason_codes": list(frame.reason_codes),
        "shadow_frame_record_id": None if frame.evidence is None else frame.evidence.record_id,
        "aligned_competitors": competitors,
        "blocking_competitors": [
            row["wall"]["wall_candidate_id"]
            for row in competitors
            if row["blocks_frame"]
        ],
        "quantity_or_metric_area_published": False,
        "diagnostic_only": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--opening-id", default=TARGET)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = witness(
        args.pdf.read_bytes(),
        page_id=args.page_id,
        expected_sha256=args.sha256,
        target=args.opening_id,
    )
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print({
        "status": report["status"],
        "shadow_frame_reason_codes": report["shadow_frame_reason_codes"],
        "host_member_ids": report["host_member_ids"],
        "blocking_competitors": report["blocking_competitors"],
        "aligned_competitor_count": len(report["aligned_competitors"]),
    })


if __name__ == "__main__":
    main()
