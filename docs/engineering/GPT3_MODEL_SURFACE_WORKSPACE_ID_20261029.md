# GPT3 model-surface commercial workspace identity integrity — 2026-10-29

## Observed
In pb_takeoff_authority_v164.approve_model_surface_row and model_surface_authority, int(workspace_id) > 0 accepts forged positive aliases (float 7.9, float 7.0, strings "7" and "07"). The approval issuer then writes approved workspace_id = int(workspace_id) and generates a freshly matching SHA-256 authority fingerprint. The verifier itself accepts alias identities, so even rehashed untrusted model-surface input can reach pricing and is_jobhub_eligible_row.

## Inference / production change
Approval is scoped to a physical source SQLite workspace primary key, which must be an actual native positive integer, not an integer-like representation. Validate exact native type and positivity in both producer and receiving verifier, eliminate int() rewriting of source authority, and retain the existing full model field fingerprint, source evidence and reviewer timestamp checks.

## Verification and limits
Adversarial source-neutral approval issuer tests and self-rehashed receiver attack tests cover both legacy pricing and JobHub eligibility gates, valid native workspace 7, and canonical workspace mutation without reseal. Three file change only, no source PDFs, original issuer seal, archived signed/customer fixtures, frozen four-project evaluator/denominators, 20,000 primitive cap or 2.5 pt snap modifications. Source-neutral negative-only safety does not grant FIRM, signed9 or official benchmark score. Merge requires exact head Python3.13/3.14 plus relevant companions green.

## Exact-head full CI regression repair (2026-10-29)

CI 40747185443 Python 3.14 ran 28,338 passing tests but found three legacy failures. In phase6 and P14, mixed pandas fixtures included `workspace_id` for *only* the approved 3D row: pandas converted the native source ID `1` into float `1.0` because all other entries were missing. The tightened authority correctly rejected this alias, leaving fewer eligible rows. Both fixtures now model the actual SQLite workspace ownership by setting the same source-native integer workspace key on **every** row before projection; no alias is authorised by the production verifier. P27 also checked the historical `positive workspace identity` denial text; the verifier retains that phrase and explicitly states that exact positive integer identity is required. Re-run full exact-head dual-Python CI and companion source/customer checks before merging. No FIRM or score impact asserted.
