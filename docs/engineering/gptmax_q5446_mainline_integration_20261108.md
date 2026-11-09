# Mainline integration of archived canonical-customer and Q5446 source-role dispatch

**8 Nov 2026 — GPT MAX — isolated integration branch only; not release approval.**

## Observed in current repository and protected runs

- Current main source head: `22ebd4e3c97f8efff807e9b9d84ea78837424647`. Archived #4238 exact head: `d20699f17c1a194f97c10d06b57c665dba53cc9b`; archived stacked #4240 exact head: `a5cf40623a99431d0c891600e154b76dd62abe23`. Neither archived PR was merged. GitHub commit comparison shows no changed-file overlap between the intervening main changes and the nine #4240 stack paths listed in the #4135 claim (comment 6717572899).
- The existing source-owned primary-role adapter calls the ALFRESCO quantity/customer producer. In protected original source runs, one Q5446 role produced an authenticated canonical customer row. The canonical whole-project customer repair was separately source-verified for Maryborough and 3Laurel. These are proofs of different exact heads, not yet a proof of this combined head.
- Source-role runner path: `produce_all_source_roles` -> authenticated `original_roster` -> one role-specific `q5446_source_role_customer_runtime` or generic `run_source_closed_project_handoff` -> `production_summary.json` -> `load_verified_sealed_run` -> strict customer-verification/combination. Complete roles are required for source-universe publication.
- Separate protected original secondary-role diagnostic returned source-status `no_sealable_quantities`, physical wall identity unresolved and integration unavailable. A source input receipt is NOT a quantity or commercial-authority receipt.

## Inference / authority boundary

The current-main compiler and the archived stack do not modify the same files, permitting mechanical reapplication without a semantic merge conflict. It does NOT follow that source role 2–6 should be sealable: no source-authoritative quantities were observed for them. There must be no fake empty signed run, injected supporting document digest, inferred geometry or bypass of the unchanged frozen 120-item scorer.

## Proposed and implemented scope

Reapply the exact nine source/customer/role files from archived #4240 onto a new isolated branch based on current main, preserving #4238 changes already contained in the child. The only deliberate modification is to the CI workflow push branch selector so *this new immutable branch* receives its own exact-head Python 3.13 and 3.14 tests. Keep the old branch and closed PRs untouched. Do not touch original PDFs, Claude/AntiGravity branches, benchmark truth/identity maps/evaluator, scale, wall or opening authorities, or source-observation modules.

## Expected outcomes and required acceptance

- Exact archived source-neutral tests should still pass, but rebase proof requires testing on this **new** head, with final-head full public dual-Python CI and static/frozen/provider checks.
- An actual protected original run must independently authenticate all relevant source documents and validate signed/customer byte-retention for Lot16 eight and Maryborough three. The new head has no inherited release approval.
- Where Q5446 support roles are only candidates, preserve `SOURCE_ROLES_INCOMPLETE`, no whole-project customer bijection and no official accuracy value. Only publish an official four-project score after all four original projects, every required source role, identity maps, and customer verification independently pass.

## Benchmark observations isolated from code changes

Historical 9/120 provisional and user-reported higher development counts have no power to set code, thresholds or truth; all 120 frozen targets and tolerances are unchanged. This branch makes no score claim.
