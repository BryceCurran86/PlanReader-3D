"""Run genuine source-owned H/V witness census without changing the live caller.

The only substitution is a temporary Python diagnostic wrapper around the
existing SameViewRoomAreaProducer.publish method. The original method runs
unchanged and its result is returned exactly; no source/write/quantity hook.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_same_view_room_area_authority import SameViewRoomAreaProducer
from tools.diag_gpt1_same_view_witness_census import report_same_view_witness_census

# Source receipt IDs are only a reporting address, never production detectors.
_MARYBOROUGH_FACES = (
    "source_room_face_record_6722d55c0ce8c8a8706cdcc6094860f9",
    "source_room_face_record_a0f786d8997e532c332b1a1c28980d14",
    "source_room_face_record_dde9e143bdd9627f96b7d5aaaea51f7f",
    "source_room_face_record_42bef3e350b3cc042f17107fe610f0d8",
)


@contextmanager
def _observe_same_view_source(*, output: list[dict], source_face_ids: tuple[str, ...]):
    """Only observe the original producer's exact source+rooms scope."""
    original = SameViewRoomAreaProducer.publish

    def observe(producer):
        result = original(producer)
        report = report_same_view_witness_census(
            source=producer._source,
            rooms=producer._rooms,
            target_source_face_ids=source_face_ids,
        )
        output.append(report)
        return result

    with patch.object(SameViewRoomAreaProducer, "publish", observe):
        yield


def run_original_witness_census(
    pdf_path: Path, *, expected_sha: str, source_face_ids: tuple[str, ...],
    topology_page_indices: tuple[int, ...],
    support_page_indices: tuple[int, ...],
) -> dict:
    if type(expected_sha) is not str or len(expected_sha) != 64:
        raise ValueError("full original source SHA-256 required")
    raw = pdf_path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != expected_sha:
        raise ValueError("immutable original source SHA mismatch")
    if not topology_page_indices or not source_face_ids:
        raise ValueError("explicit topology and producer-issued faces required")
    observed: list[dict] = []
    with _observe_same_view_source(output=observed, source_face_ids=source_face_ids):
        claim = collect_live_physical_net_wall_claim(
            pdf_path, pages=topology_page_indices,
            topology_pages=topology_page_indices,
            room_area_support_pages=support_page_indices,
        )
    if len(observed) != 1:
        raise ValueError("one exact same-view source producer audit required")
    rows = observed[0]["rows"]
    if len(rows) != len(source_face_ids):
        raise ValueError("incomplete original source face census")
    # Original geometry and old quantities belong to production, not this
    # read-only diagnostic. Preserve them and expose comparison IDs only.
    firm = tuple(sorted(
        (q.quantity_id, q.value, q.unit)
        for q in claim.room_area_quantity_evidence
        if q.status == "firm" and not q.abstained
    ))
    return {
        "diagnostic_only": True,
        "source_sha256": sha,
        "source_face_ids": sorted(source_face_ids),
        "witness_census": observed[0],
        "unchanged_production_firm_quantities": firm,
        "unchanged_production_quantity_count": len(firm),
        "frozen_benchmark_scored": False,
        "commercial_approval_issued": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--page-index", type=int, action="append", required=True)
    parser.add_argument("--support-page-index", type=int, action="append", default=[])
    parser.add_argument("--source-face-id", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_original_witness_census(
        args.pdf, expected_sha=args.source_sha,
        source_face_ids=tuple(args.source_face_id or _MARYBOROUGH_FACES),
        topology_page_indices=tuple(args.page_index),
        support_page_indices=tuple(args.support_page_index),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print("G1_ORIGINAL_ROOM_HV_WITNESS_DIAGNOSTIC_ONLY",
          json.dumps({
              "original_source_sha256": report["source_sha256"],
              "audited_source_face_count": len(report["witness_census"]["rows"]),
              "unchanged_original_firm_count": report["unchanged_production_quantity_count"],
              "benchmark_scored": False,
          }, sort_keys=True))


if __name__ == "__main__":
    main()
