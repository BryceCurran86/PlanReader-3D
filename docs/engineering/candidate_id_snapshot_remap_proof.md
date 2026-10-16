# Candidate-id snapshot remap proof (tools only)

Evidence tooling; **no production module, report shape, quantity or benchmark file changes**.

## Problem

Physical-opening candidate ids are `stable_contract_id(kind, payload)`, and the payload
contains the source `snapshot_id`. A genuine source addition (for example the Lot16 1215
recovery in #2610) changes the snapshot, so every candidate id is re-hashed. Equal counts
and an equal observation union do not show that each re-hashed id still names the same
candidate. The stage report only carries the ids, not the payloads behind them.

## What the tools do

1. `tools/record_candidate_id_inputs.py` wraps `stable_contract_id` (returns identical ids)
   while the unchanged stage tool runs, and stores `(kind, payload, args, kwargs)` for the
   `physical_opening_raw_candidate` / `physical_opening_candidate` prefixes (and, with
   `--include-observations`, `source_observation`). Run it once from the baseline checkout
   and once from the candidate checkout.
2. `tools/prove_candidate_id_snapshot_remap.py` takes both stage reports plus both
   recordings. For every unresolved closure candidate id of the baseline it:
   - re-hashes the recorded payload as recorded and requires the baseline id back
     (the recording is faithful);
   - swaps only `snapshot_id`, re-hashes, and requires the result to be in the candidate
     closure, with the map injective and onto;
   - requires the candidate run's own recorded payload to equal the baseline payload modulo
     `snapshot_id`;
   - requires closure status, reason codes, raw / resolved counts and the unresolved
     observation inventory to be equal;
   - optionally (`--baseline-observations` / `--candidate-observations`) requires every
     referenced observation / lineage id to have an identical recorded identity payload
     with no snapshot inside;
   - with `--controls`, perturbs every hashed key and requires zero hits.
   Exit code 0 only when everything holds.

```
# in each checkout (baseline, then candidate)
PYTHONPATH=. python -m tools.record_candidate_id_inputs --recording-out rec.json -- \
    --pdf plan.pdf --page-id 3 --source-all-pages --output stage.json
# anywhere
PYTHONPATH=. python -m tools.prove_candidate_id_snapshot_remap \
    --baseline-stage stage_base.json --candidate-stage stage_cand.json \
    --baseline-recording rec_base.json --candidate-recording rec_cand.json --controls
```

## Real result (Lot16 REV E, source SHA `10109b4b...`, page 3)

Baseline main `ae507bfc` (the #2610 merge-base `c1cc7d5a` gives the same ids) versus #2610
head `0d2c0649`: 134/134 closure ids (9 raster raw, 125 native) map one-to-one in both
page-local (`7c0d1996` to `3fcb6bc5`) and `--source-all-pages` (`fc75bec9` to `7ad8bf09`)
mode; 849 referenced observation ids have identical identity payloads; every control gives
0 hits. Evidence comment: #2610 (issuecomment-6139332325).

## Limits (read before relying on it)

- It proves equality of the **hashed identity fields** only. Non-hashed record attributes,
  per-gap rejection reasons and viewport promotion (`viewport_id` is attached after the id
  is computed; Lot16 page 3 has no authenticated viewport) are not covered.
- One document and page, on one OS. Other drawings can differ, for example where the
  supplemental pass adds different segments.
- Payloads containing sets are not reproduced by their JSON recording (`str(set)` is hash-
  seed dependent); the prover refuses such ids instead of trusting them. Real candidate
  payloads hold only dict / str / float / tuple / None.
- It is independent of, and complementary to, the producer-side per-group sidecar in #2626
  and its CI replay #2634: those expose the groups from production code, this recomputes the
  ids from recorded hash inputs with no production change.
- Evidence only. It approves no count, quantity or benchmark claim.
