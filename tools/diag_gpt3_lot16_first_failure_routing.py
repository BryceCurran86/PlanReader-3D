from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT=Path("artifacts/lot16-selected/out")
LEDGER=ROOT/"failure-ledger.json"
OUT=ROOT/"first-failure-routing.json"

OPENING_STAGE="PHYSICAL IDENTITY"
FLOOR_STAGE="MEASUREMENT AUTHORITY"
CEILING_STAGE="CANONICALISATION"

def classify(row: dict) -> dict:
    item_id=str(row["item_id"])
    trade=str(row["trade_category"])

    if item_id.startswith("lot16-floor-"):
        return {
            **row,
            "first_failure_stage":FLOOR_STAGE,
            "generic_root_cause":"canonical floor exists but no authenticated metric/documented floor-area quantity reaches QuantityEvidence",
            "owner":"GPT MAX",
            "next_stage_after_fix":"QUANTITY",
            "evidence_basis":[
                "current surface audit: canonical floors exist",
                "metric_floor_count=0",
                "floor_quantity_count=0",
            ],
        }

    if item_id.startswith("lot16-ceiling-"):
        return {
            **row,
            "first_failure_stage":CEILING_STAGE,
            "generic_root_cause":"no canonical ceiling surface reaches final quantity path; live ceiling lining remains unavailable",
            "owner":"GPT MAX",
            "next_stage_after_fix":"MEASUREMENT AUTHORITY",
            "evidence_basis":[
                "current surface audit: canonical_ceiling_count=0",
                "ceiling_final_quantity_count=0",
                "live_ceiling_lining_unavailable",
            ],
        }

    # Current opening authority matrix proves the generic first blocking cluster
    # before measurement: incomplete physical/opening-host authority. Several
    # individual rows may expose later semantic/measurement gates once this
    # cluster closes, but those are not promoted ahead of the first proven gate.
    next_notes=[]
    if "0870" in item_id or "1200-entry" in item_id:
        next_notes.append(
            "after physical hosting, prove source-owned figured width and authenticated cross-view height; do not infer scale"
        )
    if "2124-corner-stack" in item_id:
        next_notes.append(
            "after physical hosting, resolve unique source-owned corner-stacker label/leader ownership; remain fail-closed if ambiguous"
        )
    if "1215-sgw-obs" in item_id:
        next_notes.append(
            "after host identity, continue semantic/measurement publication for the remaining SGW observation"
        )
    return {
        **row,
        "first_failure_stage":OPENING_STAGE,
        "generic_root_cause":"physical opening / host-topology authority is not source-closed for the remaining opening universe",
        "owner":"GPT MAX",
        "next_stage_after_fix":"SEMANTIC IDENTITY / MEASUREMENT AUTHORITY",
        "evidence_basis":[
            "current opening matrix: many failed openings lack host_wall and host_record",
            "physical_opening_universe_complete=false",
            "opening_universe_completeness_record_unavailable",
            "opening_candidate_viewport_scope_unresolved / snapshot mismatch remains in residual source evidence",
            *next_notes,
        ],
    }

def main():
    ledger=json.loads(LEDGER.read_text(encoding="utf-8"))
    failures=ledger.get("failure_items") or []
    routed=[classify(row) for row in failures]
    stage_counts=Counter(row["first_failure_stage"] for row in routed)
    owner_counts=Counter(row["owner"] for row in routed)
    payload={
        "project_id":"au_qld_lot16_power",
        "schema_version":"gpt3-first-failure-routing-v1",
        "denominator":27,
        "matched_within_tolerance":8,
        "failure_count":len(routed),
        "unsupported_output_count":len(ledger.get("unsupported_outputs") or []),
        "stage_counts":dict(sorted(stage_counts.items())),
        "owner_counts":dict(sorted(owner_counts.items())),
        "routing_rows":routed,
        "reporting_only":True,
        "production_logic_modified":False,
        "benchmark_truth_modified":False,
    }
    if len(routed)!=19:
        raise SystemExit(f"expected 19 failure rows, got {len(routed)}")
    if payload["unsupported_output_count"]!=0:
        raise SystemExit("authoritative Lot16 baseline unexpectedly has unsupported outputs")
    OUT.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(payload,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
