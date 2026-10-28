# GPT3 — Named estimator approval at the final JobHub gate (2026-10-29)

## Observed repository behavior

Read current `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, current #3462 claims, the real publishing contract and pipeline, and the existing SQLite end-to-end publishing fixture. Starting main: `f64d1617cad9ff45de4a39b9c386aa4513e361d2`.

Real call path: `build_publishing_package_from_workspace` loads `takeoff_rows.commercial_authority_reviewed_by` unchanged from SQLite into `QuantityLineItemPayload.approved_by`, computes `PublishingPackagePayload.compute_payload_hash`, and `validate_publishing_gate` checks commercial row authority. `execute_jobhub_publishing` rechecks the sealed hash and gate, then inserts a commercial package and lines into JobHub.

First failing authority boundary: the gate previously used `if not q.approved_by` for USER_APPROVED status and AI_DETECTED / MODEL_DERIVED / PDF_SCALED approval. Python treats whitespace-only strings and non-string truthy values as approvals. A SQLite `TEXT` approver containing spaces is a truthy, fully sealed source-neutral package: the hash and JobHub write guards cannot distinguish the missing human approval. This is a commercial approval identity defect, not a geometric measurement or source authentication result.

## Inference and production correction

Estimator approval must identify a real nonblank string actor. Require `type(approved_by) is str and bool(approved_by.strip())` at the final commercial gate for rows whose authority status or source type requires estimator approval. Do not strip or mutate the sealed field (doing so would invalidate its original evidence/hash); reject invalid attribution instead. Preserve existing named approvals, ordinary documented FIRM rows not requiring a separate approval, provisional drafts, all pricing and source SHA checks, duplicate transaction, TOCTOU seal, and approved delegation.

## Tests and actual consumer

New real SQLite PlanReader → sealed package → commercial gate → JobHub tests cover all five approval-required status/source combinations; empty, whitespace, tab/newline and NULL approvers; truthy non-string spoofing with a freshly recomputed SHA; positive named approvals; unchanged documented FIRM; provisional draft; duplicate rejection and zero destination writes on failure. These are synthetic source-neutral gate tests only: they cannot authenticate an original PDF or grant FIRM, customer release or frozen V2 score authority.

## Ownership and protected boundaries

Exclusive hub claim #3462/6475229064. Only `pb_jobhub_publishing_contract.py`, the new publishing regression test and this report are changed. Another GPT3 worker owns #4080 and `pb_jobhub_publishing_pipeline.py`; do not edit or overwrite it. GPT1/2/MAX/Claude/AntiGravity source and geometry, original private PDFs, historical eight signed/customer rows, immutable frozen120 evaluator and denominators, 20,000 raster primitive cap and 2.5pt snap are untouched. The owner-only original-eight/default and original-nine/explicit positive replay for #3796 remains independently blocked.

## Release verification

Review exact three-file patch and record technical review. Require exact new-head full Python 3.13/3.14 CI and applicable source-neutral signed/customer/raster/performance checks, reconcile current main and exclusive claims, then merge only if gates pass. No score improvement is claimed.
