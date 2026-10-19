# GPT3 — Lot16 original opening-area issuer convergence

**Status: independent diagnostic only. No new source-issued quantity, customer release, opening count or Full Plan V2 score is asserted by this documentation.**

## Source of truth
- Owner original: Lot16 Power REV E, 13-page PDF. SHA-256: `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`. The client PDF is private and not checked into GitHub.
- Immutable original eight Lot16 signed opening-area source-closed run fingerprint: `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`.
- Independent signed/customer originals: `docs/engineering/lot16_original_signed_eight_row_20261015/production/{source_sealed_run.json,verified_customer_rows.json}`.
- Current first review gate: `tools/diag_gptmax_lot16_host_frame_gpt1_handoff.py`; production issuer: `pb_live_opening_area_quantity_publication.publish_live_opening_area_quantities`.
- MAX source area review PR #3377 can offer a host-only figured gross-area candidate; complete whole-wall frames remain separately required for 3D deductions. Original signed 1215 SGW 1.80 m² already exists with host binding but null whole-wall frame.

## Owner-original execution

The owner runner must provision the original PDF only in its authorised environment, never upload PDF bytes or page images to public Actions artifacts.

```bash
python -u tools/diag_gpt3_lot16_max_area_owner_original_replay.py \
  --pdf "documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf" \
  --output artifacts/gpt3-lot16-max-original-area-source-replay.json
```

This runs one original source visibility ingest (page 3), producer-owned physical openings, structural host bindings, frames and canonical opening issuer; reproduces read-only sealed/customer bodies, recomputes MAX first-gate area review and independently reconciles with the true producer issuer. It checks the exact source SHA before ingest, original predecessor fingerprint, all eight unchanged signed/customer bodies, current sealed/customer one-to-one provenance, source snapshot/retention immutability and opening physical identity. Reports a newly source-issued signed quantity **only** if its exact current live producer-issued record exists outside the archived original eight. An unsigned MAX review candidate never enters the new quantity count.

Public CI runs source-neutral synthetics (including an eight-to-nine *synthetic* producer/seal/customer exercise), canonical original eight fixture parity and adversarial failure cases. The original-source job remains **skipped** without `PLANREADER_OWNER_ORIGINAL_SOURCE_READY=true` and a privately provisioned exact PDF; never call that skipped gate positive. Source replay must be rerun on the exact integrated release SHA, not on a different PR head.

## Limits and next release gates

- `source_verified_new_quantity_count=null` without verified predecessor/source retention is **unknown**, not zero.
- The diagnostic separates original-source **figured gross opening area** from complete 3D wall-frame/void deductions and global opening-count completeness; it does not grant other trade families or opening kind from label proximity.
- A new source-verified quantity still needs independent GPT1 authority, customer approval and GPT3 official frozen Full Plan V2 identity/evaluator score under project `au_qld_lot16_power` (27 scored source targets), with the 120-target four-project aggregate reported separately.
- No modifications to frozen truth, evaluator, tolerance, W2 2.5 pt snap, 20,000 wall raster primitive cap or client source inputs are permitted.
- #3373 fixes an unrelated missing axis-pair helper in baseline full CI and requires independent review/owner approval before merge. #3380 remains DRAFT until exact-head integrated CI, owner-original source replay and independent release review.

## Source/producer audit expectations

Expect `original_source_pdf_sha256_verified=true`, `original_source_customer_retention_unchanged=true`, `historical_full_signed_and_customer_bodies_verified=true`, no duplicates, and `source_verified_new_quantity_count` reflecting only actually sealed, customer-verified rows outside original eight. The benchmark score is **never** returned by this tool, and customer release remains false.
