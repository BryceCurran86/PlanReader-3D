"""Batch40b deep Lot16 census from handoff/observe/unhosted ancestry (shadow)."""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from pb_opening_kind_axis_original_attach import attach_kind_and_axis_shadows
from pb_unhosted_vs_signed_eight_retention_shadow import (
    prove_unhosted_retention_vs_signed_eight,
)


def _label_values(row: Mapping[str, Any]) -> tuple[float, ...]:
    evidence = (row.get("original_label_dimension_result") or {}).get("evidence") or {}
    values = evidence.get("dimension_values_mm") or ()
    out = []
    for v in values:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return tuple(out)


def census_lot16_batch40b_deep(
    *,
    opening_decisions: Sequence[Mapping[str, Any]],
    canonical_by_id: Mapping[str, Mapping[str, Any]],
    observe_rows_by_id: Mapping[str, Mapping[str, Any]],
    unhosted_ancestry: Sequence[Mapping[str, Any]],
    customer_quantity_ids: Sequence[str],
    parent_kind_counts: Mapping[str, int],
    visible_observation_id_count: int,
    face_end_support_kind_counts: Mapping[str, int],
    flank_disposition_counts: Mapping[str, int],
) -> dict[str, Any]:
    kind_axis = attach_kind_and_axis_shadows(
        opening_decisions=opening_decisions,
        canonical_by_id=canonical_by_id,
        observe_rows_by_id=observe_rows_by_id,
    )
    signed = []
    unsigned = []
    single_figured = []
    figured_pair = []
    kind_supported_ids = []
    kind_unproven_ids = []
    frame_reasons: Counter[str] = Counter()
    label_bound = 0
    for decision in opening_decisions:
        oid = str(decision["physical_opening_id"])
        observed = observe_rows_by_id[oid]
        values = _label_values(observed)
        evidence = (observed.get("original_label_dimension_result") or {}).get("evidence") or {}
        if evidence.get("evidence_id"):
            label_bound += 1
        if decision.get("prior_signed_quantity_id"):
            signed.append(oid)
        else:
            unsigned.append(oid)
        if len(values) == 1:
            single_figured.append({
                "physical_opening_id": oid,
                "single_value_mm": values[0],
                "invented_second_axis": False,
            })
        elif len(values) == 2:
            figured_pair.append(oid)
        for reason in decision.get("frame_reason_codes") or ():
            text = str(reason)
            if text.startswith("opening_host_frame_unproven_wall_pair:"):
                frame_reasons["opening_host_frame_unproven_wall_pair"] += 1
            else:
                frame_reasons[text] += 1

    for row in kind_axis["openings"]:
        gate = row["kind_shadow"]["first_remaining_gate"]
        oid = row["physical_opening_id"]
        if gate == "opening_filling_kind_source_supported":
            kind_supported_ids.append(oid)
        elif "unproven" in gate:
            kind_unproven_ids.append({
                "physical_opening_id": oid,
                "kind_gate": gate,
                "source_kind_evidence_ids": row["kind_shadow"].get(
                    "source_kind_evidence_ids") or [],
            })

    retention = prove_unhosted_retention_vs_signed_eight(
        unhosted_physical_opening_ids=[r["physical_opening_id"] for r in unhosted_ancestry],
        all_physical_opening_ids=[d["physical_opening_id"] for d in opening_decisions],
        required_signed_quantity_ids=customer_quantity_ids,
        observed_signed_quantity_ids=[
            str(d["prior_signed_quantity_id"])
            for d in opening_decisions if d.get("prior_signed_quantity_id")
        ],
    )

    return {
        "status": "UNPUBLISHED_LOT16_BATCH40B_DEEP_CENSUS",
        "opening_count": len(opening_decisions),
        "signed_opening_count": len(signed),
        "unsigned_opening_count": len(unsigned),
        "signed_physical_opening_ids_sample": sorted(signed)[:8],
        "unsigned_physical_opening_ids_sample": sorted(unsigned)[:8],
        "single_figured_opening_count": len(single_figured),
        "single_figured_openings": single_figured,
        "figured_pair_opening_count": len(figured_pair),
        "kind_gate_counts": kind_axis["kind_gate_counts"],
        "axis_gate_counts": kind_axis["axis_gate_counts"],
        "kind_source_supported_ids_sample": sorted(kind_supported_ids)[:14],
        "kind_unproven_openings": kind_unproven_ids,
        "frame_reason_histogram": dict(sorted(frame_reasons.items())),
        "label_witness_bound_count": label_bound,
        "label_witness_bound_rate": (
            label_bound / len(opening_decisions) if opening_decisions else 0.0
        ),
        "parent_kind_counts": dict(sorted(dict(parent_kind_counts).items())),
        "visible_observation_id_count": int(visible_observation_id_count),
        "face_end_support_kind_counts": dict(sorted(dict(face_end_support_kind_counts).items())),
        "flank_disposition_counts": dict(sorted(dict(flank_disposition_counts).items())),
        "unhosted_vs_signed_eight": retention,
        "invented_second_axis": False,
        "host_granted": False,
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
