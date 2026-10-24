"""Mission 28 — ingest Lot16 original handoff gates into four-project report.

Project keys are report labels only (never prediction inputs). Other three
frozen projects stay listed as missing until their lanes supply rows.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_four_project_first_gate_report_shadow import build_four_project_first_gate_report
from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import (
    original_host_frame_dimension_report,
)

LOT16_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
_REQUIRED = (
    "au_qld_lot16_power",
    "au_qld_maryborough_service_station",
    "au_qld_3laurel",
    "au_qld_q5446",
)
_LOT16_KEY = "au_qld_lot16_power"


def lot16_four_project_first_gate_shadow_report(
    pdf: bytes, *, expected_sha256: str = LOT16_SHA, page_id: str = "3",
) -> dict:
    if type(pdf) is not bytes or not pdf:
        raise TypeError("original PDF bytes required")
    digest = sha256(pdf).hexdigest()
    if digest != expected_sha256:
        raise ValueError("original Lot16 source SHA mismatch")

    queue = original_host_frame_dimension_report(pdf, page_id=page_id)
    if queue["source_sha256"] != digest:
        raise RuntimeError("handoff lost source identity")
    rows = []
    for decision in queue["opening_decisions"]:
        rows.append({
            "project_key": _LOT16_KEY,
            "physical_object_id": decision["physical_opening_id"],
            "first_remaining_gate": decision["first_remaining_gate"],
            "source_sha256": decision["source_sha256"],
            "snapshot_id": decision["snapshot_id"],
            "decision_scope_id": decision.get("source_decision_scope_id"),
            "prior_signed_quantity_id": decision.get("prior_signed_quantity_id"),
        })
    report = build_four_project_first_gate_report(
        rows, required_project_keys=_REQUIRED,
    )
    signed = sum(1 for r in rows if r.get("prior_signed_quantity_id"))
    return {
        "status": "UNPUBLISHED_LOT16_FOUR_PROJECT_FIRST_GATE_SHADOW",
        "source_sha256": digest,
        "page_id": page_id,
        "lot16_opening_count": len(rows),
        "lot16_signed_quantity_id_count": signed,
        "lot16_first_gate_counts": dict(queue.get("first_gate_counts") or {}),
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
        "benchmark_matched": None,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--sha256", default=LOT16_SHA)
    p.add_argument("--page-id", default="3")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    raw = args.pdf.read_bytes()
    if sha256(raw).hexdigest() != args.sha256:
        raise SystemExit("source SHA mismatch")
    report = lot16_four_project_first_gate_shadow_report(
        raw, expected_sha256=args.sha256, page_id=args.page_id,
    )
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "lot16_opening_count": report["lot16_opening_count"],
        "lot16_signed_quantity_id_count": report["lot16_signed_quantity_id_count"],
        "lot16_first_gate_counts": report["lot16_first_gate_counts"],
        "missing_project_keys": report["four_project_report"]["missing_project_keys"],
        "first_gate_counts_by_project": report["four_project_report"][
            "first_gate_counts_by_project"],
        "benchmark_score_granted": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
