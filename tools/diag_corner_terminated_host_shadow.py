"""Read-only, counts-only diagnostic for the corner-terminated two-face host SHADOW.

Runs the existing live wall/opening composition on ONE original page, then asks
``pb_opening_corner_terminated_host_shadow`` about every non-hosted two-face opening.
Writes short ids, reason codes and counts only. It never writes a host binding,
frame, quantity or customer row and never edits the PDF. The original is read in place.

    python -m tools.diag_corner_terminated_host_shadow --pdf <original.pdf> --page 3 \
        --expected-source-sha256 <hex> --output out.json
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_opening_corner_terminated_host_shadow import assess_corner_terminated_host_shadow
from pb_source_visibility_authority import SourceVisibilityProducer


def run(pdf: Path, page: int, expected_sha: str) -> dict:
    payload = pdf.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    if sha != expected_sha:
        raise SystemExit("original source SHA-256 mismatch")
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
        raster_paired_outer_faces_shadow=True,
    )
    initial = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}", source_bytes=payload,
        source_locator="memory://live-physical-net-wall-source.pdf", page_ids=(page,),
    )
    comp = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=initial.revision.revision_id,
        page_ids=(str(page),), include_unmeasured_ink_closed_flanks_shadow=True,
        source_fragment_roles_shadow=True,
    )
    bindings_before = [(b.opening_identity_id, b.status.value, b.host_wall_id) for b in comp.opening_bindings]
    records = assess_corner_terminated_host_shadow(comp, enabled=True)
    bindings_after = [(b.opening_identity_id, b.status.value, b.host_wall_id) for b in comp.opening_bindings]
    first_gates = Counter(r.first_remaining_gate for r in records)
    return {
        "schema_version": "1.0.0",
        "source_sha256": sha,
        "page": page,
        "shadow_only": True,
        "benchmark_score_granted": False,
        "composition_unchanged": bindings_before == bindings_after,
        "openings_in_composition": len(bindings_before),
        "hosted_in_composition": sum(1 for _, status, _ in bindings_before if status == "corroborated"),
        "assessed_non_hosted_two_face_openings": len(records),
        "candidates": sum(1 for r in records if r.result.is_candidate),
        "first_remaining_gate_counts": dict(sorted(first_gates.items())),
        "candidate_rows": [
            {
                "opening": r.opening_identity_id[-8:],
                "collinear_side": r.result.collinear_side,
                "host_member_count": len(r.result.host_member_ids),
                "terminator_witness_count": len(r.result.terminator_witness_ids),
                "perpendicular_thickness_pt": r.result.perpendicular_thickness_pt,
                "result_id": r.result.result_id,
            }
            for r in records if r.result.is_candidate
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.pdf, args.page, args.expected_source_sha256)
    args.output.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("assessed_non_hosted_two_face_openings", "candidates", "composition_unchanged")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
