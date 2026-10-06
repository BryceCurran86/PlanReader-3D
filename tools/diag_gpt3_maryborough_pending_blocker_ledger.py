from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

MANIFEST=Path("benchmarks/frozen_holdout/full_plan_v2/projects/au_qld_maryborough_service_station/source_manifest.json")
OUT=Path("artifacts/gpt3-maryborough-pending")
PROJECT="au_qld_maryborough_service_station"

def classify(item: dict) -> dict:
    item_id=str(item["item_id"])
    trade=str(item["trade_category"])
    if trade in {"doors","windows"}:
        return {
            "item_id":item_id,
            "trade_category":trade,
            "unit":item["unit"],
            "expected_object_refs":item.get("expected_object_refs") or [],
            "execution_state":"PENDING_UPSTREAM_PRODUCTION",
            "first_blocking_stage":"PHYSICAL IDENTITY",
            "generic_root_cause":"Maryborough opening/window authority remains physically conflicted or lacks source-closed host-wall topology; no opening_area/opening_count QuantityEvidence reaches sealing.",
            "owner":"GPT 2",
            "next_gate_after_fix":"SEMANTIC IDENTITY / MEASUREMENT AUTHORITY",
            "evidence_basis":[
                "current core handoff: opening_area=0 and opening_count=0",
                "semantic_opening_physical_conflict",
                "semantic_opening_universe_exhaustiveness_unproven",
                "physical_wall_candidate_scope_bounds_unresolved / cropped_at_viewport_boundary",
                "complete_authenticated_host_wall_universe_required",
                "no_authenticated_host_wall_band",
                "host_binding_record_unavailable",
            ],
        }
    if trade in {"tiling","ceilings"}:
        return {
            "item_id":item_id,
            "trade_category":trade,
            "unit":item["unit"],
            "expected_object_refs":item.get("expected_object_refs") or [],
            "execution_state":"PENDING_UPSTREAM_PRODUCTION",
            "first_blocking_stage":"SEMANTIC IDENTITY",
            "generic_root_cause":"Maryborough canonical room population exists but room-label/source-room ownership is not authenticated, so no room area or derived floor/ceiling quantity can progress.",
            "owner":"GPT 1",
            "next_gate_after_fix":"MEASUREMENT AUTHORITY",
            "evidence_basis":[
                "current room-area diagnostic: canonical_room_count=687 and canonical_floor_count=687",
                "eligible_room_count=0",
                "unique_label_count=0",
                "cross_view_room_area_label_unavailable",
                "cross_view_room_area_dimensions_unavailable",
                "floor_quantity_count=0",
            ],
        }
    raise SystemExit(f"unclassified denominator item: {item_id} / {trade}")

def main():
    raw=json.loads(MANIFEST.read_text(encoding="utf-8"))
    items=[
        row for row in raw["verified_takeoff_items"]
        if bool(row.get("denominator_eligible",True))
    ]
    rows=[classify(row) for row in items]
    stages=Counter(row["first_blocking_stage"] for row in rows)
    owners=Counter(row["owner"] for row in rows)
    trades=Counter(row["trade_category"] for row in rows)
    payload={
        "schema_version":"gpt3-maryborough-pending-blocker-ledger-v1",
        "project_id":PROJECT,
        "source_sha256":"b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007",
        "denominator":len(rows),
        "production_execution_present":False,
        "evaluator_state":"MISSING_EXECUTION_NOT_MISSED",
        "stage_counts":dict(sorted(stages.items())),
        "owner_counts":dict(sorted(owners.items())),
        "trade_counts":dict(sorted(trades.items())),
        "pending_rows":rows,
        "reporting_only":True,
        "benchmark_truth_modified":False,
        "production_logic_modified":False,
    }
    assert len(rows)==24
    assert stages["PHYSICAL IDENTITY"]==8
    assert stages["SEMANTIC IDENTITY"]==16
    assert owners["GPT 2"]==8
    assert owners["GPT 1"]==16
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"maryborough-pending-blocker-ledger.json").write_text(
        json.dumps(payload,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print(json.dumps(payload,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
