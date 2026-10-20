"""D1 — Lot16 opening first-gate receipt schema refresh (no producer behavior).

Validates the unpublished GPT1 queue shape from
``assess_gpt1_opening_candidates`` after a caller supplies rows. Does not read
PDFs, gold, or expected BOQ values. Publication flags must remain false.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import assess_gpt1_opening_candidates


_REQUIRED_DECISION_FIELDS = (
    "physical_opening_id",
    "source_sha256",
    "snapshot_id",
    "first_remaining_gate",
    "measurement_published",
    "customer_seal_granted",
    "opening_count_granted",
)

_KNOWN_GATES = frozenset({
    "source_owned_floor_plan_unavailable",
    "structural_host_unavailable",
    "whole_wall_frame_unavailable",
    "opening_filling_kind_unproven",
    "source_figured_dimension_pair_unproven",
    "width_height_axis_authority_unproven",
    "original_host_binding_receipt_unbound",
    "original_host_frame_receipt_unbound",
    "independent_gpt1_measurement_validation_required",
})

# Gross source-FIGURED opening area can be reviewed on an authenticated
# structural host without a whole-wall 3D frame. Do not collapse these gates.
_KNOWN_GROSS_AREA_GATES = frozenset({
    "source_owned_floor_plan_unavailable",
    "structural_host_unavailable",
    "opening_filling_kind_unproven",
    "source_figured_dimension_pair_unproven",
    "original_figured_area_receipt_unbound",
    "original_host_binding_receipt_unbound",
    "original_host_frame_receipt_unbound",
    "original_signed_area_already_retained",
    "independent_gpt1_opening_area_measurement_validation_required",
})


def refresh_opening_first_gate_receipt(
    rows: list[dict],
    canonical: list[dict],
    f07: dict,
    *,
    source_root: dict,
) -> dict[str, Any]:
    """Re-emit first-gate receipts and assert fail-closed publication flags."""
    queue = assess_gpt1_opening_candidates(
        rows, canonical, f07, source_root=source_root
    )
    decisions = queue.get("opening_decisions")
    if not isinstance(decisions, list) or not decisions:
        raise ValueError("opening decisions missing from GPT1 queue")

    area_candidates = []
    area_gates = Counter()
    for row in decisions:
        if not isinstance(row, Mapping):
            raise TypeError("opening decision must be a mapping")
        for field in _REQUIRED_DECISION_FIELDS:
            if field not in row:
                raise ValueError(f"missing decision field {field}")
        if row["measurement_published"] is not False:
            raise RuntimeError("receipt refresh attempted measurement publication")
        if row["customer_seal_granted"] is not False:
            raise RuntimeError("receipt refresh attempted customer seal")
        if row["opening_count_granted"] is not False:
            raise RuntimeError("receipt refresh attempted opening count grant")
        gate = str(row["first_remaining_gate"])
        if gate not in _KNOWN_GATES:
            raise ValueError(f"unknown first_remaining_gate {gate}")
        area_gate = row.get("opening_area_first_remaining_gate")
        if area_gate not in _KNOWN_GROSS_AREA_GATES:
            raise ValueError(f"unknown original gross opening area gate {area_gate!r}")
        area_gates[area_gate] += 1
        claimed_area_ready = row.get("new_gpt1_area_candidate_handoff")
        if type(claimed_area_ready) is not bool:
            raise ValueError("typed area review flag required")
        if claimed_area_ready:
            if (
                area_gate != "independent_gpt1_opening_area_measurement_validation_required"
                or row.get("prior_signed_quantity_id")
                or not row.get("authenticated_host_record_id")
                or row.get("figured_pair_area_support") is not True
                or row.get("figured_area_receipt_bound") is not True
                or row.get("original_host_binding_receipt_bound") is not True
                or row.get("filling_kind_source_supported") is not True
                or (row.get("authenticated_frame_record_id") is not None
                    and row.get("original_host_frame_receipt_bound") is not True)
            ):
                raise RuntimeError("unproven gross source-area claim entered GPT1 queue")
            area_candidates.append(row)

    # This queue is an original producer review ledger, not a token granting
    # signed publisher/measurement authority. Its summary is independently
    # recomputed from complete physical decisions.
    if dict(sorted(area_gates.items())) != queue.get("area_first_gate_counts"):
        raise ValueError("gross opening area first-gate census mismatch")
    if area_candidates != queue.get("gpt1_new_area_review_candidates"):
        raise ValueError("gross opening area candidate universe mismatch")
    if queue.get("signed_customer_publisher_activated") is not False:
        raise RuntimeError("receipt refresh activated customer publisher")
    if queue.get("global_opening_count_granted") is not False:
        raise RuntimeError("receipt refresh granted global opening count")

    return {
        "status": "UNPUBLISHED_LOT16_OPENING_RECEIPT_REFRESH_SHADOW",
        "original_physical_opening_count": queue["original_physical_opening_count"],
        "original_authenticated_hosts": queue["original_authenticated_hosts"],
        "original_complete_host_frames": queue["original_complete_host_frames"],
        "original_signed_area_quantities": queue["original_signed_area_quantities"],
        "first_gate_counts": dict(queue["first_gate_counts"]),
        "gross_opening_area_first_gate_counts": dict(sorted(area_gates.items())),
        "gross_opening_area_review_candidates": list(area_candidates),
        "gross_opening_area_host_only_review_count": sum(
            row.get("authenticated_frame_record_id") is None
            for row in area_candidates
        ),
        "opening_decisions": list(decisions),
        "measurement_published": False,
        "customer_seal_granted": False,
        "opening_count_granted": False,
        "benchmark_score_granted": False,
        "pdf_bytes_consumed": False,
        "gold_values_consumed": False,
        "shadow_only": True,
    }
