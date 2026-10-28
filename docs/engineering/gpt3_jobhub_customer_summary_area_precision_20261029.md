# GPT3 — JobHub customer area-summary precision (2026-10-29)

## Observed repository behavior

Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, the frozen/public benchmark firewall, `.github/workflows/ci.yml`, and current #3462 claims on main `60234ec70a61ca319d29d335f8b0ac0ded2e18d3`.

Actual production path: `pb_jobhub_publishing_pipeline.build_publishing_package_from_workspace` reads SQLite takeoff rows and preserves the source measurement float; `PublishingPackagePayload.compute_payload_hash` seals the complete quantity; `pb_jobhub_publishing_contract.validate_publishing_gate` verifies the seal and commercial price/source authority; `execute_jobhub_publishing` inserts full-precision line quantities after #4074 but still rounds `interior_m2` and `exterior_m2` to 2 decimal places both in `painting_takeoff_packages` and the returned customer summary.

Example, source-neutral: a sealed 0.004 m² internal line priced at $250/m² passes cent-exact commercial validation with $1.00 payable, and its JobHub line retains 0.004 m²; the package header and returned summary instead report 0.00 m². This is a customer summary integrity defect **after** the source and commercial gates, not a missing scale or FIRM proof.

## Inference

A customer package area summary is an aggregate of the accepted, sealed measured lines. Two-decimal rounding is not a measurement authority and may erase small but genuine source areas. The aggregation should use a stable full-precision sum and persist the resulting float without additional rounding; monetary payable totals remain cent-exact and unchanged.

## Proposed change

Within `execute_jobhub_publishing`, gather explicitly classified internal and external m² quantities, compute each using `math.fsum` for order-stable float aggregation, and write/return the unrounded result. Retain the existing ambiguity abstention (conflicting interior/exterior section tokens contribute to neither bucket), unit filtering, project lock, source/hash/TOCTOU checks, duplicate transaction, line values and price rounding. Add source-neutral **real PlanReader SQLite → sealed payload → commercial gate → JobHub SQLite** regression tests for sub-cent area, mixed interior/exterior, ambiguous section, unit exclusion, input-order stability, duplicate rejection and post-seal tampering.

## Authority boundary and expected abstentions

This patch does **not** mint source, FIRM, customer or benchmark authority. Synthetic FIRM rows in tests exercise the gate mechanics only; they do not prove original PDF provenance or frozen V2 accuracy. Original 8-default/9-explicit positive replay and #3796 remain owner-only blocked. Existing eight signed/customer quantities must remain intact. No frozen120 files, original PDFs, source hashes, 20k primitive cap, 2.5pt snap, geometry modules or other agents' branches are changed.

## Benchmark observations (not algorithm inputs)

The 120-object frozen evaluator and historical Lot16 eight signed opening areas are retained, not consulted to choose thresholds or implementation. No score change is claimed.

## Verification required

Inspect complete three-file patch and record actual technical review. Require exact new-head Python 3.13/3.14 CI and applicable signed/customer/raster/performance checks before merge. Any original-positive replay is separate owner evidence and cannot be replaced by source-neutral CI.
