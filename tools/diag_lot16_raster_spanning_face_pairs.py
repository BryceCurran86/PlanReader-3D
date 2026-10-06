from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
import pb_opening_host_binding_authority as host
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
)
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SOURCE_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def main() -> None:
    payload = PDF.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    if sha != EXPECTED_SOURCE_SHA:
        raise SystemExit(f"source sha mismatch: {sha}")

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_raster_spanning_face_pairs",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-raster-spanning-face-pairs",
        source_bytes=payload,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    published = source.published_snapshot_for_revision(published.revision.revision_id)
    assert published is not None

    walls = composition.physical_wall_candidate_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=PAGE_ID,
            decision_scope_id=f"wall-source:page-{PAGE_ID}",
        )
    )
    assert walls.scope_complete and walls.equivalence is not None
    equivalence = walls.equivalence
    group_lookup = host._equivalence_group_lookup(equivalence)

    semantic = composition.semantic_enumeration_result.record
    assert semantic is not None
    physical = composition.physical_opening_authority

    rows = []
    summary = Counter()
    seen = set()
    for observation_id in semantic.representative_observation_ids:
        result = physical.prove_existence(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        opening = result.existence_record
        if (
            result.proposition != PHYSICAL_OPENING_EXISTS
            or opening is None
            or opening.record_id in seen
            or opening.structural_pattern != RASTER_FRAMED_WALL_BAND_INTERRUPTION
        ):
            continue
        seen.add(opening.record_id)
        geometry = host._opening_geometry(physical, opening)
        assert geometry is not None
        edge_tol = max(0.5, min(2.0, geometry.length * 0.02))
        thickness_tol = max(0.75, geometry.thickness * 0.15)
        center_tol = max(host.DEFAULT_GAP_SNAP_TOLERANCE_PT, thickness_tol)

        raw = []
        for record in walls.records:
            data = host._candidate_axis_data(record, geometry)
            if data is None:
                continue
            u0, u1, offset = data
            if u0 < -edge_tol and u1 > geometry.length + edge_tol:
                identity = record.physical_identity
                raw.append({
                    "id": record.wall_candidate_id,
                    "u0": float(u0),
                    "u1": float(u1),
                    "offset": float(offset),
                    "candidate_identity_id": identity.candidate_identity_id,
                    "identity_usable": bool(identity.usable),
                    "equivalence_group": list(
                        group_lookup.get(
                            record.wall_candidate_id,
                            (record.wall_candidate_id,),
                        )
                    ),
                    "source_primitive_ids": list(identity.source_primitive_ids),
                    "representation": record.wall_candidate.representation,
                    "reason_codes": list(record.wall_candidate.reason_codes),
                })

        # Normalize exact SAME groups to one deterministic local representative,
        # matching production's existing role normalization rule.
        by_group = {}
        for item in raw:
            group = tuple(item["equivalence_group"])
            by_group.setdefault(group, []).append(item)
        normalized = []
        for group, members in sorted(by_group.items()):
            normalized.append(sorted(
                members,
                key=lambda item: (
                    abs(item["offset"]),
                    item["id"],
                ),
            )[0])

        pairs = []
        for i, first in enumerate(normalized):
            if not first["identity_usable"] or not first["candidate_identity_id"]:
                continue
            for second in normalized[i + 1:]:
                if not second["identity_usable"] or not second["candidate_identity_id"]:
                    continue
                separation = abs(second["offset"] - first["offset"])
                center = (second["offset"] + first["offset"]) / 2.0
                if abs(separation - geometry.thickness) > thickness_tol:
                    continue
                if abs(center) > center_tol:
                    continue
                pairs.append({
                    "ids": sorted((first["id"], second["id"])),
                    "offsets": sorted((first["offset"], second["offset"])),
                    "separation": separation,
                    "center": center,
                    "groups": sorted((
                        tuple(first["equivalence_group"]),
                        tuple(second["equivalence_group"]),
                    )),
                })

        if len(pairs) == 1:
            category = "unique_centered_spanning_face_pair"
        elif len(pairs) > 1:
            category = "multiple_centered_spanning_face_pairs"
        elif normalized:
            category = "spanning_candidates_but_no_face_pair"
        else:
            category = "no_spanning_candidates"
        summary[category] += 1
        rows.append({
            "opening_id": opening.record_id,
            "bbox": opening.aperture_bbox_pt,
            "length": geometry.length,
            "thickness": geometry.thickness,
            "edge_tol": edge_tol,
            "thickness_tol": thickness_tol,
            "center_tol": center_tol,
            "raw_spanning_count": len(raw),
            "normalized_spanning_count": len(normalized),
            "candidate_offsets": [
                {
                    "id": item["id"],
                    "offset": item["offset"],
                    "group": item["equivalence_group"],
                    "identity_usable": item["identity_usable"],
                    "representation": item["representation"],
                    "source_primitive_ids": item["source_primitive_ids"][:8],
                    "reason_codes": item["reason_codes"],
                }
                for item in sorted(normalized, key=lambda x: (x["offset"], x["id"]))
            ],
            "matching_pair_count": len(pairs),
            "matching_pairs": pairs,
            "category": category,
        })

    print(json.dumps({
        "source_sha256": sha,
        "wall_candidate_count": len(walls.records),
        "raster_opening_count": len(rows),
        "summary": dict(sorted(summary.items())),
        "rows": rows,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
