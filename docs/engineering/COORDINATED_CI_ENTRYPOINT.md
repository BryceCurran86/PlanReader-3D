# One coordinated CI entry point — keep public, preserve checks

The ordinary PlanReader `.github/workflows/ci.yml` is the **single canonical
entry point for required source-neutral/full code verification**. It also
supports three manually dispatched modes, in **one workflow**, through
GitHub → Actions → **CI** → Run workflow:

| Manual suite | What it does | What it does NOT claim |
| --- | --- | --- |
| `focused` | One Linux/Python 3.13 runner executes frozen truth + provider isolation, syntax, linter and a curated cross-agent synthetic test set | Not the entire 3.13/3.14 CI suite; cannot authorise FIRM source quantities |
| `full` | The existing **unchanged** required `CI / test` jobs (Python 3.13 **and** 3.14), all tests, smoke, frozen and source-safety gates | Cannot supply removed original PDFs or invent a score |
| `readiness` | Frozen **120-target** source-neutral report in `GITHUB_STEP_SUMMARY`, 4 projects/27+63+24+6, `UNPUBLISHED` with null scores | Not real four-source producer execution; not a benchmark score |

The automatic `push(main)` and `pull_request(main)` triggers and required
`CI / test` status/context retain their original semantics and Python matrix.
No new automatic workflow is created, so no extra public runner is consumed
unless a user explicitly selects a manual mode. Same-PR CI already uses
`concurrency.cancel-in-progress: true` (old heads cancel, independent PRs do
not cancel one another). Do not switch off all other workflow triggers as a
mass edit: the repository has over 200 independently named specialist
workflows, including original-source and sealed-customer tests; disabling
them before matching ALL security/source checks would silently reduce
coverage. Migrate subsets only with demonstrated parity and independent
review (existing concurrency PR #2995 covers part of the GPT3 subset).

## Private source/real four-job benchmark

**Never upload client PDFs into this PUBLIC code repository.** Real original
sources stay in the owner's private machine or the private source companion
repository described in
`docs/engineering/ORIGINAL_SOURCE_PROVISIONING.md`.
The existing `Provision original sources (smoke test)` workflow must succeed
in its separate *trusted-main* pathway before owner-controlled original
producer execution or publisher scoring. No secrets are exposed to the
manual `focused` or `readiness` paths, nor to unreviewed PR code. After
a **real** all-four full-source production, the GPT3 lane must present
original SHA, complete original source snapshots, all per-project seals,
canonical identity maps, verified customer bijections and the unchanged
Full Plan V2 evaluator outputs. Only then publish `coverage_accuracy` and
`precision_adjusted_accuracy`. A partial Lot16 8/27 archival report cannot
be represented as a 120-item current production score.

## Existing queued runs and costs

Changing this file does NOT merge or cancel existing queued historical
workflow runs; those may be cancelled individually from the GitHub Actions
UI. Changing an old queued result or force-merging untested code cannot
establish a passing `CI / test`. Both automatic and manual jobs use normal
`ubuntu-latest` runners, never a paid large runner or self-hosted process.

Do not directly enable a private-source download in a PR test job. Protect
the source token by approved main-only workflow execution and avoid
uploading workspace directories as artifacts.
