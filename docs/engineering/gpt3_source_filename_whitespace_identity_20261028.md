# GPT3 — Canonical filename identity across original source manifest and JobHub seal

**2026-10-28 AEST — source-neutral production consumer integrity repair.**

## Observed production call path
1. `pb_jobhub_publishing_pipeline.build_publishing_package_from_workspace` loads the SQLite `documents` table. It already strips `file_name` for the SHA-256 source revision manifest, but before this repair the independently sealed `DrawingRevisionPayload.file_names` roster retained leading/trailing whitespace.
2. `pb_jobhub_publishing_contract.PublishingPackagePayload.compute_payload_hash` seals both fields. Thus the same SHA-256 original bytes and the same canonical manifest could yield different full commercial hashes solely because a filename had incidental padding on re-ingestion.
3. `validate_publishing_gate` verifies the commercial source SHA-derived revision and other customer authority requirements. `pb_jobhub_publishing_pipeline.execute_jobhub_publishing` checks the **full** payload hash in the destination JobHub SQLite/PostgreSQL transaction; a padding-induced hash change evades the duplicate lookup even though the source revision has not changed.

## Inference and narrow repair
The SHA-manifest canonical name is the already-adopted source revision identity. Reuse exactly its `str(value or "").strip()` normalization for the filename roster, then sort. Preserve original filename case and all duplicate-name occurrences. Do not invent source identity for empty/whitespace-only names: the existing SHA manifest rejects them and the commercial gate remains blocked. A genuinely different canonical filename or SHA remains a distinct revision.

## End-to-end proof and negative controls
Real SQLite PlanReader workspace and JobHub publisher tests verify: padded and unpadded names yield the same source revision, full payload hash and transactional duplicate rejection; reversed ingestion order and duplicate filenames preserve multiplicity; blank names retain missing source authority and block commercial writing; materially changed canonical names remain distinct. These are **source-neutral synthetic tests**, not original PDF replay.

## Authority and untouched files
No source PDF SHA/page/viewport/snapshot/decision-scope is promoted or rewritten. No FIRM quantity, original eight/nine signed/customer rows, original source files/credentials, frozen V2 120-item evaluator/denominators, GPT1/2/MAX/Claude/AntiGravity claims, other GPT3 #3995/#3996 branches, 20,000 primitive cap or 2.5pt snap changes. No benchmark truth enters production. Historical packages sealed under the old padded roster are **not migrated**. Require exact-head Python3.13/3.14 CI, companion signed/customer/raster/performance checks and recorded final diff review before merge; owner-only original replay still blocks #3796.
