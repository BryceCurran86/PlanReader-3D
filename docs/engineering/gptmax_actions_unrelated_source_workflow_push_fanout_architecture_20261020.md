# Actions queue fan-out from unrelated main-push source workflows — architecture-first review (2026-10-20)

**Status:** OBSERVATION / ARCHITECTURE / REVIEW ONLY — NOT A CODE CHANGE. GPT MAX cross-lane CI-capacity support; coordination #3462. No test result, permission to merge, engineering quantity or benchmark improvement is implied.

## Observed live GitHub evidence (exact date and source)

Using GitHub's real Actions REST collection `GET /repos/BryceCurran86/PlanReader-3D/actions/runs?status=queued&per_page=1`, the queue on 2026-10-20 had **1,970 queued runs**, of which **1,516** were `push` and **454** `pull_request`; `in_progress` had **14**, `workflow_dispatch` queued had zero. Queue counts are volatile, not a test or performance metric, but the event distribution matters. The workflow directory `.github/workflows` had **254 workflow YAML files** at the observed main. Several active source/CI PRs, including GPT MAX #3525, were queued with unassigned GitHub-hosted jobs, so their exact-head Python3.13/3.14 correctness was **not verified**. This report cannot determine whether the queue's ultimate constraint is Actions billing/quota, GitHub service availability, rate limit, concurrency or merely fan-out; an admin must confirm.

An actual `push`/main queued-run sample (IDs 39385875717 and 39385873237 through 39385873371, created 07:20:33–34 UTC) contained at least fourteen narrowly themed `TEST/DIAG GPT2` native original-source jobs plus `CI`, all triggered on the same main commit/time. This is distinct from important PR-scoped original-source tests, which may be essential to validate a geometry change.

Root trigger inspection directly from the exact main files:

| Workflow | Actual push trigger | Impact |
|---|---|---|
| `test-gpt2-native-compound-sheet-label.yml` | `push.branches=[main]`, `push.paths=["pb_*.py", "pb_page_title_authority.py", test file, own YAML]` | Any newly added `pb_source_*.py` from an unrelated trade triggers original title test |
| `test-gpt2-original-native-dimension-strokes.yml` | same `pb_*.py` wildcard plus own module/test/workflow | Any unrelated `pb_*.py` change triggers original PWD dimension test |
| `test-gpt2-original-ft2-ft3-source-rows.yml` | same `pb_*.py` wildcard plus its source test/diagnostic/workflow | Unrelated trade change triggers original FT2/FT3 source rows |
| `test-gpt2-rcp-source-viewport-coverage.yml` | same `pb_*.py` wildcard plus its source diagnostic/test/workflow | Unrelated `pb_*.py` triggers original ceiling viewport census |
| `diag-gpt2-original-mixed-amenities-insets.yml` | same `pb_*.py` wildcard plus own tool/test/workflow | Unrelated `pb_*.py` triggers mixed-inset diagnostic |
| `test-gpt2-a600-original-column-header.yml` | `push.branches=[main]`, **no** paths restriction | Every main push schedules a specialised A600 door-column test |
| `ci.yml` | `push.branches=[main]` and `pull_request.branches=[main]`, concurrency cancels superseded PR runs | This is the mandatory source/private-original addition guard and dual-Python full test; **do not disable/filter/reduce it** |

Four of the five path-filtered specialised examples have `if: github.event_name != 'push' || vars.ORIGINAL_SOURCES_REPOSITORY != ''` on the original-source job. On unprovisioned repositories, those jobs may skip, but the **workflow run is still created and queues**; skipped source is NOT an original-PDF pass. Their `pull_request.paths` lists are already narrower. Trigger storms do NOT require 254 workflow YAML files to be active on every push; do not claim that.

## Inference, clearly separate from observation

The wide `pb_*.py` path pattern makes any `pb_` producer change count as relevant to numerous unrelated source-specific GPT2 workflows. Frequent independent agent merges of new source-shadow modules amplify the queued **push** runs and reduce timely exact-head CI availability. This provides a concrete unnecessary fan-out mechanism, not proof that reducing fan-out will by itself fix the unassigned runner capacity, quota, GitHub service delays or backlog already queued.

## Proposed candidate remedy — STOP for cross-lane architecture review BEFORE editing YAML

1. Audit all `.github/workflows/*.yml` source-specific `push` triggers and list the declared source/test/workflow paths AND the directly imported producer modules, before identifying any redundant `pb_*.py` wildcard. Record safe change-path matrices for each affected workflow; do not blindly mass-edit 254 files.
2. For owner-approved original-source workflows whose `pull_request` and `workflow_dispatch` guarantees remain intact, replace unrelated catch-all `pb_*.py` push patterns with **source-relevant explicit module paths** and the workflow/test/diagnostic paths. For the A600 header workflow, consider a scoped `push.paths` based on `pb_source_door_schedule_authority.py`, its own test, its workflow and any source-authority dependencies proved necessary. Preserve `workflow_dispatch` for manual original replay after broad upstream changes.
3. Ensure source-root and shared-code changes with material impact still receive appropriate original-source replay: codify dependency-aware test selection (or an explicit release checklist invoking the relevant manual workflows) rather than shrinking safety scope. Every PR retains mandatory `ci.yml` Python3.13/3.14, private-original file-addition checks, provider-gold isolation, Full Plan V2 integrity, correct SHA source provenance and historical eight-body retention when it touches output geometry.
4. Add source-neutral workflow-trigger **change-path matrix tests**: unrelated `pb_source_unrelated_trade.py` should trigger mandatory `ci.yml` but no original native sheet-title/FT2/A600 diagnostics; direct source module, own test and own workflow file MUST trigger the relevant specialised suite; positive upstream dependency modification still triggers required source tests or has a documented explicit manual dispatch. Prove `pull_request` and `workflow_dispatch` contracts unchanged. No Gold expected quantities in thresholds/selection.
5. Do not cancel other agents' queued current-exact-head required checks; cancel only proven obsolete runs with admin authority after consulting active claims, never a CI SUCCESS/FAILURE for a different code commit. Avoid creating extra TEST-ONLY integration PRs merely to generate more actions while existing jobs have no runner assignment.
6. Have a human repository Actions administrator separately check Actions billing/quota, available runners/concurrency, usage policy and job queue reasons. Current GitHub connector's available GitHub operations have no privileged cancelling or Actions account/billing endpoint; do not invent such access.

## Safety and promotion boundaries

No original drawing, immutable SHA, signed construction quantity, canonical physical identity, customer projection, 20,000 raster primitive cap, 2.5 pt snap, frozen `full_plan_takeoff_reconciliation_v2` truth/evaluator/tolerances or release performance metric is altered. This document does not claim 30 engineering blockers solved, tests passed or PRs merged.

**Review required:** A GitHub Actions maintainer and independent GPT2 source authority reviewer must approve the exact set of workflow trigger changes and demonstrate that source-positive original tests remain invoked when appropriate. Owner approval must follow exact-head CI and independent authority review. Until then, **STOP** at this architecture-first document under `AGENTS.md`.
