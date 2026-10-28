# GPT3 — Canonical original source manifest and unknown issue (2026-10-28)

## Observed production path
- `pb_jobhub_publishing_pipeline.build_publishing_package_from_workspace` reads SQLite `documents` in insertion-ID order, derives `revision_documents` from exact (filename, original SHA-256) pairs and sorts those pairs before hashing. The same builder previously emitted `drawing_revision.file_names` in insertion order and substituted literal `BA` for absent `workspaces.drawing_issue`.
- `pb_jobhub_publishing_contract.PublishingPackagePayload.compute_payload_hash` seals both the sorted SHA-derived source revision and the separately insertion-ordered filename list, plus the issue label, into one full-evidence SHA-256. Thus re-ingesting the same original files in a different order can change the commercial payload seal despite unchanged source bytes, quantities, pricing, approvals and project identity.
- `pb_jobhub_publishing_pipeline.execute_jobhub_publishing` checks existing JobHub packages by exact sealed hash inside an SQLite/PostgreSQL transaction. A changed hash can evade that duplicate check. The literal default `BA` also falsely asserts a drawing issue that was not supplied by the workspace.

## Inference and proposed change
Document insertion ID is a storage event, not original drawing revision authority. Preserve the complete filename multiset, including duplicate names, but canonicalize its order before constructing `DrawingRevisionPayload`. Keep SHA-256 source manifest derivation unchanged. Missing/blank issue becomes explicit unknown `""`, not invented `BA`. A nonblank workspace issue is preserved after trimming incidental whitespace; this does **not** authenticate the issue against the original PDF.

## Production-positive and negative expectations
- The same two SHA-identified source documents ingested in either order produce identical source revision, filename roster and full sealed payload; the real JobHub SQLite publisher rejects the second unchanged package.
- Duplicate filename entries are preserved, not collapsed; changing one SHA changes revision identity and full seal.
- Missing, empty and whitespace-only workspace issue stays unknown, never fabricated. No original drawing date is inferred.
- Missing original source SHA continues to block commercial publication; draft/valid commercial paths and destination transactional safeguards remain unchanged.

## Limits and non-authority
No original PDF, source-page viewport, snapshot, decision-scope, source issuer, FIRM measurement, customer promotion, signed archive or frozen V2 score is changed or authenticated here. This fixes new package construction only; historical packages with old order-dependent hashes are not migrated or reidentified. No changes to frozen 120 evaluator/denominators, 20,000 primitive cap or 2.5pt snap. Production code never consults benchmark truth. Same-agent technical review is allowed but must record actual diff and exact-head Python3.13/3.14 plus signed/customer/raster/performance checks before merge.
