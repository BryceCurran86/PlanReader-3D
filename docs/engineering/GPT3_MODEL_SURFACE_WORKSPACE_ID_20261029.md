# GPT3 model-surface commercial workspace identity integrity — 2026-10-29

## Observed
In pb_takeoff_authority_v164.approve_model_surface_row and model_surface_authority, int(workspace_id) > 0 accepts forged positive aliases (float 7.9, float 7.0, strings "7" and "07"). The approval issuer then writes approved workspace_id = int(workspace_id) and generates a freshly matching SHA-256 authority fingerprint. The verifier itself accepts alias identities, so even rehashed untrusted model-surface input can reach pricing and is_jobhub_eligible_row.

## Inference / production change
Approval is scoped to a physical source SQLite workspace primary key, which must be an actual native positive integer, not an integer-like representation. Validate exact native type and positivity in both producer and receiving verifier, eliminate int() rewriting of source authority, and retain the existing full model field fingerprint, source evidence and reviewer timestamp checks.

## Verification and limits
Adversarial source-neutral approval issuer tests and self-rehashed receiver attack tests cover both legacy pricing and JobHub eligibility gates, valid native workspace 7, and canonical workspace mutation without reseal. Three file change only, no source PDFs, original issuer seal, archived signed/customer fixtures, frozen four-project evaluator/denominators, 20,000 primitive cap or 2.5 pt snap modifications. Source-neutral negative-only safety does not grant FIRM, signed9 or official benchmark score. Merge requires exact head Python3.13/3.14 plus relevant companions green.
