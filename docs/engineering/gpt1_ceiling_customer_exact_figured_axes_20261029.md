# GPT1 — exact original figured axes at ceiling customer projection (2026-10-29)

## Compliance and observed repository behavior

Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`, `.github/workflows/ci.yml`, and the live ceiling production, source-closed and customer modules on main `65dc4684fbcf1ce36c704457d896fc7c12a651de`. Coordinated with the live #3462 and #2017 threads before implementation.

Actual path: `LivePhysicalNetWallClaim.ceiling_lining_quantity_evidence` → `pb_live_ceiling_lining_source_closed_export.build_live_ceiling_lining_source_traces` → `pb_live_ceiling_customer_projection.project_live_ceiling_customer_rows` → `_figured_authority` → `pb_quantity_takeoff_adapter.quantities_to_takeoff_output_rows` → `pb_source_closed_run_export.seal_source_closed_run` → `pb_customer_output_verification.verify_sealed_customer_output`. The source exporter already requires exactly two distinct original figured-dimension strings on a FIRM documented ceiling. The final customer `_figured_authority`, however, currently normalizes arbitrary objects to strings and set-deduplicates before determining whether two axes exist.

## Inference (not original-source evidence)

If a caller changes, bypasses or later refactors the upstream source-trace guard, a forged three-entry pair with a repeated axis, a padded string or a non-native object could be presented as exactly two commercial measuring axes by the final customer authority helper. This is a negative integrity gap, not proof that any original Maryborough or Lot16 area is missing or wrong. Source-positive quantities and the frozen evaluator have not been used to choose this guard.

## Proposed narrow production change

At the final `_figured_authority` gate, require the existing documented-dimension authority and exactly two distinct native `str` IDs, nonempty and unchanged by `strip()`. No set-based repair, lossy conversion, invented dimension, fallback scale or new FIRM quantity. Keep deterministic sorting of a *valid* pair for stable customer receipts. Add adversarial helper and real customer-projection regression tests, plus an unchanged positive and abstained-only result. A malformed original record may fail earlier in `build_live_ceiling_lining_source_traces`; the test must respect that first-failing gate, not bypass it.

## Untouched and release gates

Do not modify GPT2 physical FT2/FT3/RCP source, GPT MAX/Claude openings, GPT3 signing or scoring, other GPT1 source drafts, original PDFs/tokens, source SHA/lineage, archived signed/customer bodies, frozen V2 truth/evaluator, 20,000 raster primitive cap or 2.5 pt snap. This is not a new accuracy match. Exact-head Python 3.13/3.14 tests and applicable companion checks are required; original-source positive replay and byte-exact preservation of nine signed Lot16 customer bodies and verified Maryborough floors remain mandatory before merge. A source-unavailable or skipped CI check does not satisfy them.
