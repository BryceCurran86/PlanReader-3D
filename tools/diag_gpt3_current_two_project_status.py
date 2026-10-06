from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from benchmarks.frozen_holdout.full_plan_v2.development_scoreboard import (
    build_development_failure_ledger_v2,
    evaluate_development_suite_v2,
)
from benchmarks.frozen_holdout.full_plan_v2.manifest_io import load_project_manifest
from benchmarks.frozen_holdout.full_plan_v2.sealed_reconciliation import (
    identity_map_from_dict,
    reconcile_sealed_run_v2,
)

ROOT=Path("benchmarks/frozen_holdout/full_plan_v2")
ART=Path("artifacts/gpt3-current-two-project")
LOT16="au_qld_lot16_power"
MARY="au_qld_maryborough_service_station"

def load_json(path: Path) -> dict:
    obj=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj,dict):
        raise TypeError(path)
    return obj

def main():
    manifests=(
        load_project_manifest(ROOT/"projects"/MARY/"source_manifest.json"),
        load_project_manifest(ROOT/"projects"/LOT16/"source_manifest.json"),
    )

    sealed=sealed_source_closed_run_from_dict(
        load_json(ART/"lot16"/f"{LOT16}.json")
    )
    identity=identity_map_from_dict(
        load_json(ART/"lot16"/"lot16.identity-map.json")
    )
    lot16_manifest=next(m for m in manifests if m.project_id==LOT16)
    produced_lot16=reconcile_sealed_run_v2(
        lot16_manifest,
        sealed.to_dict(),
        identity,
    )

    produced={LOT16:produced_lot16}
    score=evaluate_development_suite_v2(manifests,produced)
    ledger=build_development_failure_ledger_v2(manifests,produced)

    payload={
        "main_sha":"baa839c07032983615e1ab0463db52fbfe5642c8",
        "selected_projects":[MARY,LOT16],
        "combined_denominator":51,
        "score":asdict(score),
        "failure_ledger":asdict(ledger),
        "interpretation":{
            "authoritative_combined_accuracy_available":score.development_accuracy is not None,
            "lot16_exact_accuracy":8/27,
            "maryborough_execution_present":False,
            "reason":"Maryborough has no current sealable production run, so the 51-object headline must remain blocked rather than treating its 24 objects as MISSED.",
        },
    }
    ART.mkdir(parents=True,exist_ok=True)
    (ART/"current-two-project-status.json").write_text(
        json.dumps(payload,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print(json.dumps(payload,indent=2,sort_keys=True))

    assert score.configured_projects==2
    assert score.executed_projects==1
    assert score.source_closed_truth_items==51
    assert score.executed_denominator==27
    assert score.matched_within_tolerance==8
    assert score.missed==19
    assert score.hallucinations==0
    assert score.lineage_conflicts==0
    assert score.development_accuracy is None
    assert score.precision_adjusted_accuracy is None
    assert MARY in ledger.missing_execution_project_ids
    assert LOT16 not in ledger.missing_execution_project_ids
    assert len(ledger.failure_items)==19

if __name__=="__main__":
    main()
