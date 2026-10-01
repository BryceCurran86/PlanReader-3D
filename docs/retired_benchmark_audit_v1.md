# Retired Benchmark Repository Audit v1

## Directive

The legacy percentage/public-tender/golden-plan benchmark systems are retired. Full Plan V2 independently source-closed truth is the only active PlanReader validation framework.

Active chain:

`SOURCE DOCUMENT → SOURCE EVIDENCE → PHYSICAL OBJECT → CANONICAL OBJECT → VERIFIED GEOMETRY → VERIFIED QUANTITY → CUSTOMER OUTPUT`

Primary milestone: `V2_CANONICAL_BUILDING_CORE`.

## Classification

### 1. HISTORICAL

Historical legacy benchmark data, percentage reports, old holdout records and detailed score ledgers are removed from the active tree where they had no runtime dependency. Git history remains the archive. Review patch archives are historical evidence and are not execution inputs.

### 2. ACTIVE CODE

Retired executable scoring surfaces are disabled:

- `pb_benchmark_accuracy_engine.py` — fail-fast retirement tombstone only.
- `pb_public_tender_benchmark.py` — fail-fast retirement tombstone only.
- `pb_benchmark_runner.py` — fail-fast retirement tombstone only.
- `pb_benchmark_schema.py` — compatibility shim exposing only production-neutral project identity contracts.
- `pb_holdout_suite_registry.py` — fail-fast retirement tombstone only.
- `scripts/run_planreader_benchmarks.py` — retired CLI guard only.

Legacy report-set and shadow gold-evaluator modules are removed from the active tree.

### 3. CI

Legacy benchmark-gold separation and frozen-holdout lock execution are removed from CI.

Active CI uses:

- `scripts/check_v2_truth_separation.py`
- `scripts/check_full_plan_v2_integrity.py`
- production-provider isolation from retired benchmark truth

V2 JSON is normalized to LF so reference-takeoff byte pins are cross-platform stable.

### 4. DOCUMENTATION

Active engineering and benchmark docs are rewritten around Full Plan V2. Old public-tender instructions and the old accuracy-gap ledger are retained only as short retirement notices pointing to V2. Historical percentage claims are removed from active architecture, topology, scale-authority and shadow-provider guidance.

### 5. DASHBOARD / UI

Generated legacy percentage dashboards and per-project percentage reports are removed from `benchmark_results/`.

The production `Accuracy Lab` feature is preserved as a local source-verification/correction-learning capability and rebranded `Verification Lab`. It explicitly does not represent the Full Plan V2 product scoreboard.

### 6. AUTONOMOUS TASKS

No tracked repository file with an autonomous-task filename was found during this audit. The retired benchmark is removed from the active roadmap documentation and must not be reintroduced into autonomous queues.

### 7. TEST HELPERS

Legacy scoring/report/holdout tests are removed. Test fixtures that deliberately import retired module names are retained only as negative isolation probes: they prove production providers cannot transitively reach retired benchmark truth.

Synthetic geometry/authority fixtures that test production behavior independently of retired expected values are preserved.

### 8. PRODUCTION DEPENDENCY

Reusable production capabilities are preserved rather than deleted:

- project identity extraction/mismatch protection now imports `pb_project_identity_models.py`, independent of benchmark scoring;
- workspace correction/error learning remains active but is not a product benchmark;
- customer/publication parity diagnostics remain available and should be interpreted as V2/runtime diagnostics, not legacy score authority;
- provider static/runtime isolation keeps retired module/path tokens as deny-list sentinels to prevent reintroduction of old expected values into production.

## Active V2 scoreboard

The authoritative metric list lives in `benchmarks/frozen_holdout/full_plan_v2/manifest.json` and includes source-closed truth coverage, object detection/canonicalization coverage, geometry and quantity correctness, strict exactness where appropriate, correct abstention, provenance completeness, customer-runtime publication coverage, hallucinations, gross mismatches and duplicate/double-counting errors.

No single retired percentage is an active PlanReader headline.

## Guardrail

Do not restore the retired benchmark systems into CI, product reporting, production truth, autonomous tasks or architecture decisions unless Bryce explicitly reverses the retirement directive.
