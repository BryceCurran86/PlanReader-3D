# Normal GPT: validate and merge GPT-01 / GPT-02

Implementation is published in two **draft** PRs. Run the tests, inspect CI,
resolve failures without weakening authority/abstention, then merge **#1195
before #1196**. The user explicitly assigned test execution and merging to
normal GPT. Neither final implementation head has a completed regression run.

Repository: `BryceCurran86/PlanReader-3D`.
Main fetched independently for both tasks: `e95ef8489f3a0b7c024fb99dc5e48fed887ee40b`.

## Required task handoff

| Field | GPT-01 | GPT-02 |
| --- | --- | --- |
| TASK | Nine-family live registry census and truthful lifecycle dependencies. | Close confirmed selected-PDF wall customer publication dropouts. |
| OBJECT FAMILY | Wall, Opening, Door/Window, Room, Floor/Slab, Ceiling, Roof, Finish Surface, Structural Member. | Wall; opening/room/floor producer objects retain their original coverage independently. |
| PHYSICAL IDENTITY | Only typed producer-owned, physically resolved identities with document/revision/hash/snapshot lineage are admitted. No filling identity is fabricated from an opening. | Original wall identity is preserved. Byte-identical source uploads replay their selected page union once. Same filenames, marks or quantities never merge different sources. |
| CANONICAL IDENTITY | Exact producer canonical ids survive as geometry links. Incomplete floor identity and unsupported lineage remain explicit gaps. | The original QuantityEvidence inputs must agree with the claim/publication's wall ids; matching canonical walls must retain source hash/revision. |
| GEOMETRY | Producer geometry-completeness flags are recorded; canonical presence does not establish complete metric geometry. | No geometry is calculated or filled. Selected pages are explicit; no unselected document falls through to `pages=None`. |
| QUANTITY | Original QuantityEvidence only, joined by input entity ids. Abstention/conflicts block QUANTIFIED. Aggregate totals are not allocated to individual objects. Live publication checks original value/unit. | Original verified net m² quantity reaches the 21-field contract without two-decimal rounding. Conflicting quantity ids between sources and mismatched typed publication/identity/selection require review. |
| CUSTOMER CONSUMER | Live extractor attachments and customer wall producer -> typed registry -> same-transaction takeoff query -> `coverage_lifecycle` report/settings. | `analyse_workspace` -> `_build_facade_rows` -> `_auto_publication` -> SQLite `takeoff_rows` -> existing customer takeoff consumers and AG-09 transaction report. |
| AG-09 STAGE | AUTHENTICATED -> CANONICALIZED -> QUANTIFIED -> PUBLISHED traced independently; missing customer rows remain visible. All nine families classify CONNECTED / PARTIAL / UNAVAILABLE / WRONG / DUPLICATE PATH. Unavailable counts are null. | Repairs QUANTIFIED -> PUBLISHED bridge: accumulate all selected independent claims, source-scoped facade replacement/material labels, continue past failed siblings, preserve original quantity precision and reset/scope registry attachments per workspace/run. |
| TESTS | Earlier draft: 38 focused passes before final guards; **not current-head validation**. Current syntax/diff checks passed; final new dependency/abstention/value/unit tests await execution. | Syntax, Ruff F821/F823 on changed Python, and diff checks passed. Multi-PDF, duplicate source, unselected/invalid pages, collisions, conflicts, malformed quantities, missing sources, stale attachments, typed parity, actual SQLite/rerun/rollback cases added; execution pending. |
| COMMIT | Published implementation `a5b529fbbb321ad5dcc237493177b3820ba5a9df`. | Published implementation `35bb51e17aa173a29d9715f38a0e1667f64ac95d`. This handoff is a later documentation-only commit; validate the latest PR head. |
| PR | [#1195](https://github.com/BryceCurran86/PlanReader-3D/pull/1195), `accuracy/gpt01-ag09-family-coverage`, base main. | [#1196](https://github.com/BryceCurran86/PlanReader-3D/pull/1196), `accuracy/gpt02-wall-customer-dropouts`, stacked base GPT-01 branch. |
| UNRESOLVED | Filling identity; unproven physical floor identity; missing complete ceiling/roof/slab lineage; absent live finish-surface producer; downstream family quantity/publication gaps. No claim that all nine are connected. | Separate registered-wall authority policy is retained and explicitly lacks a live canonical registry. Cross-file equivalence beyond identical source replay is unresolved. Real source fixtures with missing height still abstain. Zero-quantity fallback policy is unchanged. No complete source-set accuracy claim. |
| NEXT TASK | Validate this PR first; preserve null/unavailable and explicit identity requirements. | Validate/merge after GPT-01; then GPT-03 explicit cross-sheet identity, followed by source-backed metric closure. Do not join instances by shared type marks. |

## Validation and merge sequence

Fetch current main and both current PR heads. Use clean isolated worktrees. The
published tree for each implementation was checked against the local committed
tree; GitHub's commit identity differs from the equivalent scratch commit.

For #1195 run its focused coverage tests and related family producer regressions.
For #1196 run the complete focused command below against its latest head:

```bash
PYTHONPATH=. python -m pytest -q \
  tests/test_customer_wall_source_scope.py \
  tests/test_live_canonical_family_coverage.py \
  tests/test_takeoff_coverage_registry.py \
  tests/test_takeoff_coverage_audit_adapter.py \
  tests/test_ag09_customer_coverage_runtime.py \
  tests/test_customer_runtime_net_wall_and_opening_parity.py \
  tests/test_auto_geometry_takeoff_row_contract.py \
  tests/test_live_physical_net_wall_integration.py \
  tests/test_live_external_physical_net_wall_publication.py
```

The multi-source tests mock the authority response to test customer routing;
they do not prove PDF extraction completeness. The typed SQLite test uses the
existing synthetic gross/role authority fixture with the exact same uploaded
PDF bytes on both fixture routes. The unmocked missing-height PDF test must
continue to abstain. Never turn that fixture into a positive claim by adding a
default height.

Run the repository's wider test/CI gates from `.github/workflows/ci.yml`, including
V2 production/truth separation, provider isolation, V2 integrity, compileall,
Ruff, JavaScript syntax, full unit suite and `tests/ci_smoke.py`. **Do not run,
restore or use the retired canonical-five/legacy percentage benchmark.** No
accuracy percentage has been calculated for this work.

Review the original authority trace in
`docs/gpt01_ag09_family_coverage_architecture.md` and
`docs/gpt02_wall_customer_bridge_architecture.md`. Check row precision, original
physical/quantity ids, units, selected-source lineage and review/abstention using
the actual final head. Run `git diff --check` after any fixes. Do not modify
scoring, source truth, expected values, production authority flags, VR UI or
costing to make tests pass.

Merge #1195 only after its required checks and review pass. Retarget #1196 to
main, rebase onto current main after #1195, and validate the resulting commit
before merging. If conflicts expose competing producer snapshots, retain the
conflict for review; never discard the second path merely to make coverage look
connected. Record final tested heads, outcomes and merge SHAs in the next handoff.
