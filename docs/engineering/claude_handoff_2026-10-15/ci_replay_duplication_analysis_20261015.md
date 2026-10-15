# CI replay duplication: measured, with a consolidation proposal (analysis only, no workflow changed)

Lane: Claude (integration / CI / performance). Tracking #2608. Method and script: `scripts/perf/workflow_duplication2.py` (static text of every
workflow on `origin/main` + job-level durations of each workflow's latest successful `pull_request` run; read-only).

## Observed

* 160 workflow files; **128 unique workflows mention an original source PDF**; **28 of them have more than 3 measured minutes of heavy
  (non-unit-test) job time**, together **402 runner-minutes** per production-module change (latest green run of each, queue wait excluded).
* The heavy workflows cluster on a few shared entry commands (unique workflows, minutes counted once):

| entry command | heavy workflows | minutes |
|---|---|---|
| `tools.diag_opening_wall_face_preservation` | 11 | 237 |
| `tools.gptmax_compare_source_face_retention` | 3 | 62 |
| `scripts.gptmax_source_opposition_retention` | 3 | 51 |
| `tools.diag_gptmax_source_authority_stages` | 4 | 39 |
| `tools.run_gpt3_lot16_original_sealed_score_input` | 2 | 18 |
| `tools.diag_gptmax_producer_owned_g17_wall_shadow` | 2 | 17 |

* **Identical invocations.** Of the 11 workflows that run `diag_opening_wall_face_preservation`, **10 run exactly
  `--pdf <Lot16 PDF> --page-id 3` with no other flag** and 2 run exactly `--pdf <Maryborough PDF> --page-id 7 --page-id 30 --page-id 31`
  (the workflows differ in what they then assert, not in what they run). Several also run the same command a second time on the PR *base* tree to
  produce a baseline, so the real count of identical executions per push is higher than the table shows.
* Output of an identical invocation at one commit is deterministic: all ~15 original-source Lot16 and Maryborough replays I compared in this work
  (different heads and runners) produced `source_sealed_run.json` and `verified_customer_rows.json` byte-identical to the archived originals.

## Inference (not measured)

Executing the same tool on the same PDF with the same arguments at the same commit ten times costs about nine redundant replays of roughly
6-8 minutes each (the lightest of these workflows take 8 minutes in total including setup), i.e. in the order of 60 runner-minutes per push for the Lot16
cluster alone and about as much again for the base-tree replays. This is an estimate from the lightest workflows, not a separate measurement.

## Proposal (for the owners of those workflows; nothing here is changed)

1. One *producer* job (or one reusable workflow called with `workflow_call`) runs each distinct `(tool, PDF, page arguments)` once for the PR head and
   once for the base, and uploads the report JSON as an artifact keyed by the two commit SHAs.
2. Each existing workflow's assertions become *consumer* jobs (`needs:` in one workflow, or `workflow_run`/artifact download across workflows) that read
   that JSON. Their assertions stay byte-for-byte what they are today.
3. Keep, unconditionally, the independent signed-output replays (`SCORE GPT3 Lot16 ...`, `TEST GPT3 Maryborough ...`): they exercise the sealing and
   customer-verification path, not just the W2-W4 report, and now trigger on the whole import closure (#2787).
4. Guard the consolidation with the same kind of test used for the path filters: a test that parses the workflows and fails if two heavy workflows
   run the same `(tool, PDF, pages)` without going through the shared producer, and a mutation check that a consumer fails when the shared
   artifact is deleted or belongs to a different SHA (a consumer must never silently pass on a stale or missing artifact).

## Risks to settle before anyone implements this

* Cross-workflow artifact sharing is not available between independent `pull_request` workflow runs without `workflow_run` (which runs on the default
  branch's workflow definition, a weaker trust model); the safe form is a single reusable workflow called by each consumer, or one workflow with
  many jobs. That is a restructuring of other agents' workflows and needs their agreement.
* A shared artifact makes one wrong producer run affect every consumer; the producer must verify the PDF SHA, record the code SHA, and every
  consumer must check both before asserting.
* The performance stack (#2693-#2706, #2784) already cuts the cost of each replay to about 0.45-0.55x; consolidation and the stack multiply.

## Not claimed

This does not say any current workflow is wrong or redundant for coverage: each asserts something different. It says the *execution* is
repeated, and that the repetition is the dominant share of the runner queue that delays every review.
