"""Merge Lot16 + Maryborough + 3Laurel/Q5446 stubs into one first-gate report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pb_three_laurel_q5446_first_gate_stub_shadow import (
    build_three_laurel_q5446_missing_stub_report,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lot16-multi-gate", type=Path, required=True)
    p.add_argument("--maryborough-finish", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)

    lot16 = json.loads(args.lot16_multi_gate.read_text(encoding="utf-8"))
    mary = json.loads(args.maryborough_finish.read_text(encoding="utf-8"))

    rows: list[dict] = []
    idx = 0
    for gate, count in (lot16.get("handoff_first_gate_counts") or {}).items():
        for _ in range(int(count)):
            idx += 1
            rows.append({
                "project_key": "au_qld_lot16_power",
                "physical_object_id": f"lot16-gate-sample:{idx}",
                "first_remaining_gate": gate,
                "source_sha256": lot16["source_sha256"],
                "snapshot_id": "lot16-multi-gate-receipt",
            })
    finish = mary.get("finish_pitch_attach") or {}
    for gate in finish.get("finish_gate_sample") or ():
        idx += 1
        rows.append({
            "project_key": "au_qld_maryborough_service_station",
            "physical_object_id": f"mary-finish:{idx}",
            "first_remaining_gate": gate,
            "source_sha256": mary["source_sha256"],
            "snapshot_id": "maryborough-finish-pitch-receipt",
        })
    for gate in finish.get("pitched_ceiling_gate_sample") or ():
        idx += 1
        rows.append({
            "project_key": "au_qld_maryborough_service_station",
            "physical_object_id": f"mary-pitch:{idx}",
            "first_remaining_gate": gate,
            "source_sha256": mary["source_sha256"],
            "snapshot_id": "maryborough-finish-pitch-receipt",
        })

    stub = build_three_laurel_q5446_missing_stub_report(
        lot16_and_maryborough_rows=rows,
    )
    report = {
        "status": "UNPUBLISHED_FOUR_PROJECT_BATCH40_MERGE",
        "lot16_source_sha256": lot16.get("source_sha256"),
        "maryborough_source_sha256": mary.get("source_sha256"),
        "lot16_signed_eight_retained": lot16.get("signed_eight_retained"),
        "stub_report": stub,
        "maryborough_finish_pitch": finish,
        "evaluator_invoked": False,
        "gold_values_consumed": False,
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "missing_project_keys": stub["missing_project_keys"],
        "first_gate_counts_by_project": stub["first_gate_counts_by_project"],
        "benchmark_score_granted": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
