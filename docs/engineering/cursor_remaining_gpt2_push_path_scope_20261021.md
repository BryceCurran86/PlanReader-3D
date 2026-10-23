# Architecture: remaining GPT2 specialist main-push paths after #3727

## Observed repository behavior

`#3727` (squash `987d452dc`) removed `pb_*.py` from six specialist GPT2 workflows and left global `ci.yml` unfiltered. After that merge, sixteen other GPT2 specialist workflows still list `push.paths: ["pb_*.py", <owned tool/test/workflow>]`. Their `pull_request.paths` already name only the owned files. `workflow_dispatch` is present on each.

Four GPT3 workflows still contain `pb_*.py`. Two of those (`test-gpt3-maryborough-original-floor-score-input.yml`, `score-gpt3-lot16-1215-opening-local.yml`) comment that every production-chain module must re-run signed-output replay. Those stay untouched.

Traced: GitHub `on.push.paths` in the sixteen GPT2 specialist YAML files listed in `tests/test_cursor_remaining_gpt2_push_path_selection.py`. No producer function is called.

## Inference

Any new `pb_source_*` merge still enqueues those sixteen original-source jobs. That is the same fan-out `#3727` closed for its six files. Per-PR wait is this wildcard, not missing local pytest.

## Proposed change

Delete only the `pb_*.py` push wildcard on those sixteen GPT2 files. Keep each workflow's existing named tool, test, producer, and own YAML paths. Keep `workflow_dispatch`. Do not edit `ci.yml`. Do not edit GPT3 signed-replay path lists. Do not rewrite original-source job bodies.

## Authority boundaries

None. Trigger headers and a static path-selection test only. Shadow producers, W10, commercial rows, and `benchmarks/frozen_holdout/full_plan_v2/**` stay untouched.

## Expected abstentions

Unrelated `pb_source_unrelated_trade_shadow.py` must not match the sixteen `push.paths` lists. Owned tool/test/workflow paths must still match. Required CI remains unfiltered.

## Benchmark observations that must not influence implementation

Queue depth, Lot16/Maryborough scores, and expected BOQ values are not inputs.
