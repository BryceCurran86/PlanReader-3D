from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import pb_physical_opening_authority as g17
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def state(value):
    return str(getattr(value, "value", value))


def main() -> None:
    source_bytes = PDF.read_bytes()
    actual = hashlib.sha256(source_bytes).hexdigest()
    assert actual == EXPECTED_SHA

    source = SourceVisibilityProducer(
        producer_method="diag-gptmax-lot16-raster-swing-gates",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag-gptmax-lot16-raster-swing:{EXPECTED_SHA[:24]}",
        source_bytes=source_bytes,
        source_locator="memory://lot16-raster-swing-gates.pdf",
        page_ids=(PAGE_ID,),
    )
    published = source.augment_with_raster_opening_primitives(
        published.revision.revision_id,
        page_ids=(PAGE_ID,),
    )

    ratio_calls = []
    solution_calls = []
    original_ratio = g17._raster_swing_perpendicular_scale_ratio
    original_solutions = g17._raster_door_swing_solutions

    current = {"gap_box_pt": None, "axis": None, "ratio": None}

    def traced_ratio(gap_box_pt, axis, placements):
        ratio = original_ratio(gap_box_pt, axis, placements)
        row = {
            "gap_box_pt": [float(v) for v in gap_box_pt],
            "axis": str(axis),
            "placement_count": len(tuple(placements)),
            "ratio": None if ratio is None else float(ratio),
        }
        ratio_calls.append(row)
        current["gap_box_pt"] = tuple(float(v) for v in gap_box_pt)
        current["axis"] = str(axis)
        current["ratio"] = ratio
        return ratio

    def traced_solutions(
        thin_mask,
        pair,
        *,
        dpi,
        perpendicular_scale_ratio,
        along_scale=1.0,
    ):
        solutions = original_solutions(
            thin_mask,
            pair,
            dpi=dpi,
            perpendicular_scale_ratio=perpendicular_scale_ratio,
            along_scale=along_scale,
        )
        solution_calls.append({
            "gap_box_pt": (
                None if current["gap_box_pt"] is None
                else [float(v) for v in current["gap_box_pt"]]
            ),
            "axis": current["axis"],
            "ratio": (
                None if current["ratio"] is None
                else float(current["ratio"])
            ),
            "gap_length_px": int(pair.gap_x1 - pair.gap_x0 + 1),
            "pair_rows_px": [int(pair.row0), int(pair.row1)],
            "solution_count": len(solutions),
            "solutions": [
                {
                    "hinge_end": str(item.hinge_end),
                    "side": int(item.side),
                    "radius_px": int(item.radius_px),
                    "perpendicular_radius_px": int(item.perpendicular_radius_px),
                    "arc_coverage": float(item.arc_coverage),
                    "leaf_coverage": float(item.leaf_coverage),
                }
                for item in solutions
            ],
        })
        return solutions

    g17._raster_swing_perpendicular_scale_ratio = traced_ratio
    g17._raster_door_swing_solutions = traced_solutions
    try:
        authority = source.physical_opening_authority()
        records = {}
        status_counts = Counter()
        reason_counts = Counter()
        for observation_id in published.raster_opening_primitive_observation_ids:
            result = authority.prove_existence(
                ObservationSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    observation_id=observation_id,
                )
            )
            status_counts[state(result.status)] += 1
            for reason in result.reason_codes:
                reason_counts[str(reason)] += 1
            if (
                result.status is EvidenceResolutionStatus.CORROBORATED
                and result.proposition == PHYSICAL_OPENING_EXISTS
                and result.existence_record is not None
            ):
                records[result.existence_record.record_id] = result.existence_record
    finally:
        g17._raster_swing_perpendicular_scale_ratio = original_ratio
        g17._raster_door_swing_solutions = original_solutions

    patterns = Counter(record.structural_pattern for record in records.values())
    ratio_status = Counter(
        "unavailable" if row["ratio"] is None else "resolved"
        for row in ratio_calls
    )
    solution_count_distribution = Counter(
        str(row["solution_count"]) for row in solution_calls
    )
    one_solution_rows = [
        row for row in solution_calls if row["solution_count"] == 1
    ]
    multi_solution_rows = [
        row for row in solution_calls if row["solution_count"] > 1
    ]

    payload = {
        "source_sha256": actual,
        "page_id": PAGE_ID,
        "snapshot_id": published.snapshot.snapshot_id,
        "primitive_count": len(published.raster_opening_primitive_observation_ids),
        "physical_opening_count": len(records),
        "pattern_counts": dict(patterns),
        "framed_count": int(patterns.get(RASTER_FRAMED_WALL_BAND_INTERRUPTION, 0)),
        "swing_count": int(patterns.get(RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION, 0)),
        "prove_status_counts": dict(status_counts),
        "prove_reason_counts": dict(reason_counts),
        "swing_registration_call_count": len(ratio_calls),
        "swing_registration_status_counts": dict(ratio_status),
        "swing_solution_call_count": len(solution_calls),
        "swing_solution_count_distribution": dict(solution_count_distribution),
        "one_solution_count": len(one_solution_rows),
        "multi_solution_count": len(multi_solution_rows),
        "one_solution_rows": one_solution_rows,
        "multi_solution_rows": multi_solution_rows,
        "registration_unavailable_rows": [
            row for row in ratio_calls if row["ratio"] is None
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
