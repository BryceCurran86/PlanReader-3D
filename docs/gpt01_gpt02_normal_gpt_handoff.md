# Production accuracy handoff: GPT-01 / GPT-02

The user authorized completing validation and merging in this session. GPT-01
PR #1195 passed required CI and merged into main as
`a8b1459ebf1a9510559126ff8c9c49b0b5234a42`. GPT-02 is based on that merged
main. Its final required checks and merge identity are recorded in PR #1196;
do not infer a successful merge from focused tests alone.

## Validation resumed after user authorization

GPT-01 correction commit `bc54b025d27c34b3c3e20bee99e0c4a11269d83c`
preserves the existing `firm` structural quantity status, captures the original
typed quantity through the shadow collector instead of calling its builder from
the live extractor, and retains a proven opening viewport id. The shadow-only
import boundary and all abstention guards remain enforced.

The correction passed 131 focused coverage/structural/opening tests, followed by
10 additional status/sink/page-scope regressions. GitHub CI on Python 3.13 and
3.14 each passed 7,267 tests, with 55 skipped and 13 xfailed. Integrity, provider
isolation, compilation, Ruff, JavaScript, smoke, Docker, performance and wall
equivalence shadow checks all passed for that head.

The GPT-02 tree on merged main passed 184 focused customer, quantity, publication,
registry and lifecycle tests. Its local full run was interrupted by a blocked
external telemetry request; this is not a completed regression result. Required
GitHub CI must pass for its final published head before merging.

One local opening schedule test fails on untouched main as well:
`tests/benchmarks/test_mutation_generic_opening_binding_wiring.py::test_removing_explicit_identity_removes_firm_opening`.
The standalone baseline reproduces the same unresolved instance/type identity;
do not change source authority or weaken the test merely to erase that result.
Two other local subprocess failures came from missing cv2; the fourth came from
missing historical refs in the shallow checkout. After restoring the local
dependency path and fetching those refs, all three rechecks passed. The opening
schedule test still abstained. No test expectations or production authority were
weakened to hide the local result. Required CI uses Python 3.13/3.14; the local
limitation remains separate from PR regression results.

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
| TESTS | 131 focused passes plus 10 added status/sink/page-scope cases. Required GitHub CI: 7,267 passed / 55 skipped / 13 xfailed on each of Python 3.13 and 3.14; all supporting gates passed. Local baseline limitation described above. | 184 focused passes on merged main. Multi-PDF, duplicate source, unselected/invalid pages, collisions, conflicts, malformed quantities, missing sources, stale attachments, typed parity, actual SQLite/rerun/rollback verified. Final full CI evidence is recorded in PR #1196. |
| COMMIT | Tested head `bc54b025d27c34b3c3e20bee99e0c4a11269d83c`; merge `a8b1459ebf1a9510559126ff8c9c49b0b5234a42`. | Original implementation `35bb51e17aa173a29d9715f38a0e1667f64ac95d`, updated with the tested GPT-01 correction and merged main. Validate the latest PR head; its final commit and merge SHA are recorded in PR metadata. |
| PR | [#1195](https://github.com/BryceCurran86/PlanReader-3D/pull/1195), merged into main. | [#1196](https://github.com/BryceCurran86/PlanReader-3D/pull/1196), `accuracy/gpt02-wall-customer-dropouts`, updated onto merged main. |
| UNRESOLVED | Filling identity; unproven physical floor identity; missing complete ceiling/roof/slab lineage; absent live finish-surface producer; downstream family quantity/publication gaps. No claim that all nine are connected. | Separate registered-wall authority policy is retained and explicitly lacks a live canonical registry. Cross-file equivalence beyond identical source replay is unresolved. Real source fixtures with missing height still abstain. Zero-quantity fallback policy is unchanged. No complete source-set accuracy claim. |
| NEXT TASK | Complete GPT-02 validation; preserve null/unavailable and explicit identity requirements. | GPT-03 explicit cross-sheet identity, followed by source-backed metric closure. Do not join instances by shared type marks. |

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

The merge sequence is #1195 before #1196. GPT-01 has completed that sequence;
GPT-02 must target current main and pass checks on its resulting commit before
merging. If conflicts expose competing producer snapshots, retain the
conflict for review; never discard the second path merely to make coverage look
connected. Record final tested heads, outcomes and merge SHAs in the next handoff.
