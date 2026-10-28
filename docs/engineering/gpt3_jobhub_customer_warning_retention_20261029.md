# GPT3 — Retain gate warnings in real JobHub customer publishing (2026-10-29)

## First actual failing recipient boundary

Read AGENTS.md, playbook, current hub, original/frozen separation, customer and signed retained tests, and the real SQLite PlanReader→JobHub writer on main `aeeee5d3510f442059d333d42f54b255be8a1ae4`. The `validate_publishing_gate` code explicitly says every source-owned publishing warning must be visible to the JobHub recipient: commercial `Info` and `Warning` may publish and drafts retain critical source/row provisional notices. Nevertheless `execute_jobhub_publishing` discarded `PublishingGateResult.warnings` at the database boundary: `painting_takeoff_packages.notes` kept only mode, preflight fingerprint, payload SHA, publisher and sealed creator, while its return receipt also omitted warnings. Thus original source uncertainty permitted in draft and advisory commercial notices disappeared before the buyer saw the package.

## Production implementation

After validating the exact source hash and before the atomic DB destination lock, retain exactly the gate-visible warning strings in `customer_warnings=sorted(gate_result.warnings)`. Append a deterministic, JSON-escaped ` | Gate warnings: [...] ` suffix to the existing JobHub notes ONLY when nonempty. Return this same list in the successful publish receipt. This preserves multiplicity (never loses duplicate warnings), stable order under canonical source warning reordering from merged #4077, full warning contents including draft unresolved authority, and the earlier established legacy notes prefix. No warning text enters raw prediction, scoring, seal, or commercial risk classification. Commercial Critical/Blocker/Review warnings remain vetoed by the original gate before DB access.

## Real consumer tests

Real SQLite JobHub destination tests: commercial Info survives in notes+return without source package mutation; draft Critical and provisional review notices preserved; clean package notes unchanged and empty warnings returned; unresolved commercial blocker never connects; duplicate/replay still refused; equivalent permutations hash identically, preserve duplicate notice multiplicity, and result in deterministic notes.

## Safety

No original PDF/credential, source/FIRM quantity, customer signed-eight archive, frozen four-project120 benchmark, 20k primitive cap, 2.5pt snap, other agent code or #3796 release flow changed. New test fixtures are synthetic gate-mechanics only; no V2 official score or new source-positive customer release asserted. Exact-head dual Python CI, signed/customer/raster/performance companion checks and full patch review required before merge.
