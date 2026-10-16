"""Prove closure candidate ids move only through ``snapshot_id`` between two source runs.

Physical-opening candidate ids are ``stable_contract_id(kind, payload)`` over a payload
that contains the source-visibility ``snapshot_id`` plus source-owned fields (page,
pattern, sorted ``source_observation_ids``, ``gap_box_pt``, lineage roots, ...).  When a
genuine source observation is added the snapshot changes and every id is re-hashed, so
equal counts and equal observation unions alone do not show that each re-hashed id still
names the same candidate.

For every unresolved closure candidate id of the baseline report this tool takes the
*recorded* hashed payload (``tools/record_candidate_id_inputs.py``), swaps only
``snapshot_id`` for the candidate snapshot, re-hashes, and requires that:

* the baseline id is first reproduced from its own recorded payload (the recording is
  faithful);
* the re-hashed id is a member of the candidate closure's unresolved ids;
* the map is injective and onto the candidate closure set;
* the candidate run's own recorded payload for that id equals the baseline payload
  modulo ``snapshot_id``;
* closure status, reason codes, raw / resolved counts and the unresolved observation
  inventory are equal.

Optionally (``--baseline-observations`` / ``--candidate-observations``) every
observation / lineage id referenced by those payloads must have a recorded
``source_observation`` identity payload (no snapshot inside) that is identical in both
runs.  ``--controls`` perturbs every hashed key of every payload and requires zero hits.

What this proves: the *hashed identity fields* are equal.  It does not prove anything
about non-hashed record attributes, about other documents or pages, about viewport
promotion (``viewport_id`` is attached after the id is computed), or about why a gap
stayed unresolved.  It is evidence, not measurement authority, and approves no quantity.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pb_migration_contracts import stable_contract_id

CLOSURE_KEYS = ("raster_candidate_closures", "native_candidate_closures")
SNAPSHOT_TOKEN = re.compile(r"source_snapshot_[0-9a-f]{8,}")
CLOSURE_SUMMARY_FIELDS = (
    "page_id", "status", "reason_codes", "raw_candidate_count",
    "resolved_candidate_count", "candidate_universe_complete",
)


def report_snapshot(report: Mapping[str, Any]) -> str:
    """The single snapshot id a stage report was built against (refuses 0 or >1)."""
    tokens = sorted(set(SNAPSHOT_TOKEN.findall(json.dumps(report, sort_keys=True))))
    if len(tokens) != 1:
        raise ValueError(f"expected exactly one source snapshot in the report, found {tokens}")
    return tokens[0]


def _rehash(record: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    return stable_contract_id(record["kind"], payload, *record["args"], **record["kw"])


def _single_record(recording: Mapping[str, Sequence[Mapping[str, Any]]], contract_id: str):
    records = recording.get(contract_id)
    if not records:
        return None, "no recorded hash input"
    if len({json.dumps(r, sort_keys=True) for r in records}) != 1:
        return None, "id derived from more than one distinct input"
    return records[0], None


def _modulo_snapshot(payload: Mapping[str, Any], snapshot: str) -> dict[str, Any]:
    out = dict(payload)
    out["snapshot_id"] = snapshot
    return out


def _closure_pairs(base_report, cand_report):
    pairs = []
    for key in CLOSURE_KEYS:
        base_rows, cand_rows = base_report.get(key) or [], cand_report.get(key) or []
        if len(base_rows) != len(cand_rows):
            raise ValueError(f"{key}: baseline has {len(base_rows)} closures, candidate {len(cand_rows)}")
        order = lambda rows: sorted(rows, key=lambda r: str(r.get("page_id")))
        for b, c in zip(order(base_rows), order(cand_rows)):
            pairs.append((key, b, c))
    return pairs


def prove_snapshot_remap(
    baseline_report: Mapping[str, Any],
    candidate_report: Mapping[str, Any],
    baseline_recording: Mapping[str, Sequence[Mapping[str, Any]]],
    candidate_recording: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    baseline_observations: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    candidate_observations: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> dict[str, Any]:
    base_snap_short, cand_snap_short = report_snapshot(baseline_report), report_snapshot(candidate_report)
    snapshots_b = {r["payload"].get("snapshot_id") for recs in baseline_recording.values() for r in recs}
    snapshots_c = {r["payload"].get("snapshot_id") for recs in candidate_recording.values() for r in recs}
    base_snap = [s for s in snapshots_b if s and s.startswith(base_snap_short)]
    cand_snap = [s for s in snapshots_c if s and s.startswith(cand_snap_short)]
    if len(base_snap) != 1 or len(cand_snap) != 1:
        raise ValueError(f"cannot resolve full snapshot ids: {base_snap}, {cand_snap}")
    base_snap, cand_snap = base_snap[0], cand_snap[0]

    failures: list[dict[str, str]] = []
    closures: list[dict[str, Any]] = []
    referenced_observations: set[str] = set()
    for key, base_row, cand_row in _closure_pairs(baseline_report, candidate_report):
        ids_b = list(base_row.get("unresolved_candidate_ids") or [])
        ids_c = list(cand_row.get("unresolved_candidate_ids") or [])
        label = f"{key}[page {base_row.get('page_id')}]"
        if len(set(ids_b)) != len(ids_b) or len(set(ids_c)) != len(ids_c):
            failures.append({"closure": label, "id": "", "reason": "duplicate ids in closure"})
        mapping: dict[str, str] = {}
        payload_equal = 0
        for cid in ids_b:
            record, problem = _single_record(baseline_recording, cid)
            if problem:
                failures.append({"closure": label, "id": cid, "reason": f"baseline: {problem}"})
                continue
            payload = record["payload"]
            if payload.get("snapshot_id") != base_snap:
                failures.append({"closure": label, "id": cid, "reason": "payload snapshot is not the baseline snapshot"})
                continue
            if _rehash(record, payload) != cid:
                failures.append({"closure": label, "id": cid, "reason": "recording does not reproduce the baseline id"})
                continue
            referenced_observations.update(payload.get("source_observation_ids") or ())
            referenced_observations.update(payload.get("source_lineage_root_ids") or ())
            new_id = _rehash(record, _modulo_snapshot(payload, cand_snap))
            mapping[cid] = new_id
            cand_record, cand_problem = _single_record(candidate_recording, new_id)
            if cand_problem:
                failures.append({"closure": label, "id": cid, "reason": f"candidate: {cand_problem}"})
            elif (cand_record["kind"] != record["kind"]
                  or _modulo_snapshot(cand_record["payload"], base_snap) != payload):
                failures.append({"closure": label, "id": cid, "reason": "candidate payload differs beyond snapshot_id"})
            else:
                payload_equal += 1
        targets = list(mapping.values())
        injective = len(set(targets)) == len(targets)
        onto = set(targets) == set(ids_c)
        if not onto:
            for missing in sorted(set(ids_c) - set(targets)):
                failures.append({"closure": label, "id": missing, "reason": "candidate closure id has no baseline preimage"})
            for stray in sorted(set(targets) - set(ids_c)):
                failures.append({"closure": label, "id": stray, "reason": "re-hashed id is not in the candidate closure"})
        summary_equal = all(base_row.get(f) == cand_row.get(f) for f in CLOSURE_SUMMARY_FIELDS)
        obs_equal = (sorted(base_row.get("unresolved_observation_ids") or [])
                     == sorted(cand_row.get("unresolved_observation_ids") or []))
        if not summary_equal:
            failures.append({"closure": label, "id": "", "reason": "closure status / reason codes / counts differ"})
        if not obs_equal:
            failures.append({"closure": label, "id": "", "reason": "unresolved observation inventory differs"})
        if not injective:
            failures.append({"closure": label, "id": "", "reason": "map is not injective"})
        closures.append({
            "closure": label, "baseline_ids": len(ids_b), "candidate_ids": len(ids_c),
            "mapped": len(mapping), "injective": injective, "onto_candidate_set": onto,
            "payload_equal_modulo_snapshot": payload_equal,
            "closure_summary_equal": summary_equal, "unresolved_observation_ids_equal": obs_equal,
            "pairs": sorted([a, b] for a, b in mapping.items()),
        })

    observation_check = None
    if baseline_observations is not None and candidate_observations is not None:
        observation_check = _observation_identity_check(
            referenced_observations, baseline_observations, candidate_observations)
        failures.extend({"closure": "observations", "id": i, "reason": r}
                        for i, r in observation_check.pop("failures"))

    return {
        "baseline_snapshot": base_snap, "candidate_snapshot": cand_snap,
        "total_mapped": sum(c["mapped"] for c in closures),
        "closures": closures, "observation_identity": observation_check,
        "failures": failures, "PROVEN": not failures and bool(closures),
    }


def _observation_identity_check(ids: Iterable[str], base, cand) -> dict[str, Any]:
    failures: list[tuple[str, str]] = []
    checked = 0
    for obs_id in sorted(ids):
        records_b, records_c = base.get(obs_id), cand.get(obs_id)
        if not records_b or not records_c:
            failures.append((obs_id, "no recorded observation identity in one of the runs"))
            continue
        ident_b = {json.dumps(r["payload"], sort_keys=True) for r in records_b}
        ident_c = {json.dumps(r["payload"], sort_keys=True) for r in records_c}
        if ident_b != ident_c:
            failures.append((obs_id, "observation identity differs between runs"))
        elif any("snapshot" in text for text in ident_b):
            failures.append((obs_id, "observation identity embeds a snapshot"))
        else:
            checked += 1
    return {"referenced": len(set(ids)), "identical": checked, "failures": failures}


def _perturb(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return "perturbed" if value is None else (not value)
    if isinstance(value, (int, float)):
        return value + 0.001
    if isinstance(value, str):
        return value + "x"
    if isinstance(value, list):
        return value[1:] if len(value) > 1 else value + ["perturbed"]
    return "perturbed"


def run_controls(
    baseline_report: Mapping[str, Any],
    candidate_report: Mapping[str, Any],
    baseline_recording: Mapping[str, Sequence[Mapping[str, Any]]],
    candidate_recording: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Count how many closure ids still hit after each single perturbation.

    A discriminating proof gives zero for every control.  ``baseline_snapshot_kept``
    additionally shows that no id survives unchanged.
    """
    cand_snap_short = report_snapshot(candidate_report)
    cand_snap = next(r["payload"]["snapshot_id"] for recs in candidate_recording.values() for r in recs
                     if str(r["payload"].get("snapshot_id", "")).startswith(cand_snap_short))
    ids_b = [i for _, b, _ in _closure_pairs(baseline_report, candidate_report) for i in b["unresolved_candidate_ids"]]
    ids_c = {i for _, _, c in _closure_pairs(baseline_report, candidate_report) for i in c["unresolved_candidate_ids"]}
    controls: dict[str, int] = {}
    keys = sorted({k for i in ids_b for k in baseline_recording[i][0]["payload"] if k != "snapshot_id"})

    def hits(mutate) -> int:
        count = 0
        for cid in ids_b:
            record = baseline_recording[cid][0]
            payload = _modulo_snapshot(copy.deepcopy(record["payload"]), cand_snap)
            if not mutate(payload):
                continue
            count += _rehash(record, payload) in ids_c
        return count

    controls["faithful_remap"] = hits(lambda p: True)
    controls["baseline_snapshot_kept"] = sum(
        _rehash(baseline_recording[i][0], baseline_recording[i][0]["payload"]) in ids_c for i in ids_b)
    for key in keys:
        def mutate(payload, key=key):
            if key not in payload:
                return False
            payload[key] = _perturb(payload[key])
            return True
        controls[f"perturb:{key}"] = hits(mutate)
    carrying = {k: sum(k in baseline_recording[i][0]["payload"] for i in ids_b) for k in keys}
    return {"hits_out_of": len(ids_b), "controls": controls, "payloads_carrying_key": carrying,
            "discriminating": all(v == 0 for k, v in controls.items() if k != "faithful_remap")
                              and controls["faithful_remap"] == len(ids_b)}


def _load(path: str | None):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--baseline-stage", required=True)
    parser.add_argument("--candidate-stage", required=True)
    parser.add_argument("--baseline-recording", required=True)
    parser.add_argument("--candidate-recording", required=True)
    parser.add_argument("--baseline-observations")
    parser.add_argument("--candidate-observations")
    parser.add_argument("--controls", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    if bool(args.baseline_observations) != bool(args.candidate_observations):
        parser.error("--baseline-observations and --candidate-observations go together")
    base_report, cand_report = _load(args.baseline_stage), _load(args.candidate_stage)
    base_rec, cand_rec = _load(args.baseline_recording), _load(args.candidate_recording)
    result = prove_snapshot_remap(
        base_report, cand_report, base_rec, cand_rec,
        baseline_observations=_load(args.baseline_observations),
        candidate_observations=_load(args.candidate_observations))
    if args.controls:
        result["controls"] = run_controls(base_report, cand_report, base_rec, cand_rec)
        result["PROVEN"] = result["PROVEN"] and result["controls"]["discriminating"]
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=1, sort_keys=True), encoding="utf-8")
    printable = {k: v for k, v in result.items() if k != "closures"}
    printable["closures"] = [{k: v for k, v in c.items() if k != "pairs"} for c in result["closures"]]
    print(json.dumps(printable, indent=1, sort_keys=True))
    return 0 if result["PROVEN"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
