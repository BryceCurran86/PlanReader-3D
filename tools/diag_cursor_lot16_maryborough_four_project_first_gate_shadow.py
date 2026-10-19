"""Mission 28 — Lot16 + Maryborough original first-gates into four-project report.

Does not invoke the frozen evaluator or read gold quantities.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_four_project_first_gate_report_shadow import build_four_project_first_gate_report
from pb_four_project_lane_row_adapters import (
    lot16_handoff_to_four_project_rows,
    maryborough_room_scopes_to_four_project_rows,
)
from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import (
    original_host_frame_dimension_report,
)
from tools.diag_gptmax_maryborough_room_first_owner_gate import (
    replay_original_maryborough_room_gate,
)

LOT16_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
MARY_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
_REQUIRED = (
    "au_qld_lot16_power",
    "au_qld_maryborough_service_station",
    "au_qld_3laurel",
    "au_qld_q5446",
)


def lot16_maryborough_four_project_first_gate_shadow_report(
    *,
    lot16_pdf: bytes,
    maryborough_pdf: bytes,
    lot16_sha: str = LOT16_SHA,
    maryborough_sha: str = MARY_SHA,
) -> dict:
    if type(lot16_pdf) is not bytes or not lot16_pdf:
        raise TypeError("Lot16 PDF bytes required")
    if type(maryborough_pdf) is not bytes or not maryborough_pdf:
        raise TypeError("Maryborough PDF bytes required")
    if sha256(lot16_pdf).hexdigest() != lot16_sha:
        raise ValueError("Lot16 source SHA mismatch")
    if sha256(maryborough_pdf).hexdigest() != maryborough_sha:
        raise ValueError("Maryborough source SHA mismatch")

    lot16_queue = original_host_frame_dimension_report(lot16_pdf, page_id="3")
    mary = replay_original_maryborough_room_gate(
        maryborough_pdf, expected_source_sha=maryborough_sha,
    )
    rows = []
    rows.extend(lot16_handoff_to_four_project_rows(lot16_queue["opening_decisions"]))
    rows.extend(maryborough_room_scopes_to_four_project_rows(
        mary["source_scope_first_failures"],
        source_sha256=maryborough_sha,
    ))
    report = build_four_project_first_gate_report(
        rows, required_project_keys=_REQUIRED,
    )
    return {
        "status": "UNPUBLISHED_LOT16_MARYBOROUGH_FOUR_PROJECT_FIRST_GATE_SHADOW",
        "lot16_source_sha256": lot16_sha,
        "maryborough_source_sha256": maryborough_sha,
        "lot16_opening_count": lot16_queue.get("original_physical_opening_count"),
        "lot16_signed_quantity_id_count": lot16_queue.get(
            "original_signed_area_quantities"),
        "lot16_first_gate_counts": dict(lot16_queue.get("first_gate_counts") or {}),
        "maryborough_scope_count": len(mary.get("source_scope_first_failures") or ()),
        "maryborough_authenticated_floor_plan_viewport_count": mary.get(
            "authenticated_floor_plan_viewport_count"),
        "four_project_report": {
            "status": report["status"],
            "required_project_keys": report["required_project_keys"],
            "missing_project_keys": report["missing_project_keys"],
            "first_gate_counts_by_project": report["first_gate_counts_by_project"],
            "total_object_rows": report["total_object_rows"],
            "evaluator_invoked": False,
            "gold_values_consumed": False,
        },
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lot16-pdf", type=Path, required=True)
    p.add_argument("--maryborough-pdf", type=Path, required=True)
    p.add_argument("--lot16-sha", default=LOT16_SHA)
    p.add_argument("--maryborough-sha", default=MARY_SHA)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    report = lot16_maryborough_four_project_first_gate_shadow_report(
        lot16_pdf=args.lot16_pdf.read_bytes(),
        maryborough_pdf=args.maryborough_pdf.read_bytes(),
        lot16_sha=args.lot16_sha,
        maryborough_sha=args.maryborough_sha,
    )
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "lot16_first_gate_counts": report["lot16_first_gate_counts"],
        "maryborough_scope_count": report["maryborough_scope_count"],
        "first_gate_counts_by_project": report["four_project_report"][
            "first_gate_counts_by_project"],
        "missing_project_keys": report["four_project_report"]["missing_project_keys"],
        "benchmark_score_granted": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
