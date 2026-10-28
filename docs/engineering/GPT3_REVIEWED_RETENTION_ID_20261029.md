# GPT3 reviewed commercial row primary-key fidelity — 2026-10-29

## Observed call path
pb_takeoff_output_supersedence.select_prior_reviewed_row_ids_to_retain preserves existing estimator-reviewed source-closed takeoff rows during new original-source runs that abstain. The source SHA, family, semantic physical-entity identity and ai_takeoff_authority review gates run first. At the final SQLite physical row identity boundary, int(raw_id) silently truncated 17.9 to 17 and accepted string "017" and float 17.0 as the exact original integer 17.

## Inference / production correction
A previous estimator review must never be retained under a coerced, potentially different source SQLite row ID. Require an exact native positive int, before the caller can retain the database row. Keep source key/source SHA identity semantics, old signed rows and replacement precedence unchanged.

## Test and score firewall
Source-neutral 18-case alias rejection, two independent reviewed physical IDs, source SHA mismatch, legitimate replacement and native integer positive controls. No original PDFs, issuer promotions, frozen 120 benchmark, signed eight/customer nine, 20,000 primitive cap or 2.5 pt snap edits. Negative-only safety cannot be claimed as original FIRM or a benchmark accuracy gain. Full exact-head dual Python CI, source/signed/customer and applicable companion checks required before merge.
