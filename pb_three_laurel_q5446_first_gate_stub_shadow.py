"""Mission 28 stubs: 3Laurel / Q5446 remain missing until lane producers exist."""
from __future__ import annotations

from typing import Any

from pb_four_project_first_gate_report_shadow import build_four_project_first_gate_report


_REQUIRED = (
    "au_qld_lot16_power",
    "au_qld_maryborough_service_station",
    "au_qld_3laurel",
    "au_qld_q5446",
)


def build_three_laurel_q5446_missing_stub_report(
    *,
    lot16_and_maryborough_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    report = build_four_project_first_gate_report(
        lot16_and_maryborough_rows,
        required_project_keys=_REQUIRED,
    )
    return {
        "status": "UNPUBLISHED_THREE_LAUREL_Q5446_MISSING_STUB",
        "missing_project_keys": report["missing_project_keys"],
        "first_gate_counts_by_project": report["first_gate_counts_by_project"],
        "stub_reason": {
            "au_qld_3laurel": "no_cursor_owned_original_first_gate_producer",
            "au_qld_q5446": "no_cursor_owned_original_first_gate_producer",
        },
        "evaluator_invoked": False,
        "gold_values_consumed": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
