# GPT3 — Preserve sealed quantity and unit-rate precision at JobHub write

Date: 2026-10-29 AEST. Exclusive GPT3 claim: coordination PR #3462, comment #6471656631.

## Files and actual call path

Read current `main` `04f3d8467eda07b35fbcb2f0e40bb3f1439500be`:
`AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`,
`docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`,
`docs/planreader_jobhub_publishing_pipeline.md`, the full
`pb_jobhub_publishing_contract.py`, `pb_jobhub_publishing_pipeline.py`,
`tests/publishing/test_publishing_pipeline_e2e.py`, and #3462 claims.

**Observed:** `build_publishing_package_from_workspace` reads source takeoff
`quantity`, client `rate`, and explicit `total_price` from SQLite.
`PublishingPackagePayload.compute_payload_hash` seals their full float
representations, not four/two decimal rounded values.
`validate_publishing_gate` permits a sub-cent client rate provided the
`quantity * rate` payable amount is cent-exact after half-up quantization.
The actual `execute_jobhub_publishing` transaction then wrote
`round(q.quantity, 4)` and `round(q.rate, 2)` into
`painting_takeoff_package_lines`, silently changing the values AFTER
the SHA-256 contract and commercial gate. Example source-neutral values:
100 m² × $0.015 = $1.50, but prior SQLite row persisted a $0.01 rate,
making the stored row's recomputed cost $1.00, not $1.50.

**Inference:** Four-decimal source quantity truncation and two-decimal
unit-rate truncation are not authenticated measurement or client-price
adjustments. The writer must not alter the source/customer values it
just validated and sealed. The existing cent-exact payable total and
explicit commercial authority requirements are separate invariants.

**Proposed/implemented:** Only the JobHub INSERT arguments for
`quantity` and `rate` change to the original gate-validated floats.
Keep `total_price` cent rounding and all source, mode, authority,
destination, transaction, duplicate and SHA guards intact. No new
evidence vocabulary, source promotion, score path or schema is created.

**End-to-end proof:** Dedicated actual PlanReader SQLite → builder →
full commercial gate → JobHub SQLite transactional insert → persisted
line checks for sub-cent unit rates, >4dp measured quantities, ordinary
cent-rate controls, duplicate rejection and post-seal tamper rejection.
The test fixtures are synthetic and cannot certify any original PDF,
signed quantity, FIRM source, customer release or frozen V2 score.

**Boundary:** SQLite REAL stores the validated Python floats without
the writer's extra rounding. A separately configured PostgreSQL column
with narrower numeric scale may still round on the server; this patch
does not claim schema-level precision validation for external JobHub
deployments. Existing historical packages are not rewritten.

**Protected:** GPT1/GPT2/MAX/Claude/AntiGravity and other GPT3 claimed
branches, original PDFs/credentials, signed eight/customer receipts,
frozen 120 evaluator/denominators, 20,000 raster cap and 2.5pt snap.
No FIRM, customer or frozen score authority is conferred.
