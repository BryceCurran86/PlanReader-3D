# GPT3 — Canonical workspace destination identity before JobHub package seal

**2026-10-28 AEST; source-neutral production consumer repair.**

## Observed repository behaviour

1. `pb_jobhub_publishing_pipeline.build_publishing_package_from_workspace` reads `workspaces.jobhub_job_id` from SQLite, then applies `int(ws_row["jobhub_job_id"])` before building `ProjectIdentityPayload`.
2. SQLite's `INTEGER` column affinity does not prevent `REAL`, `TEXT`, or `BLOB` values. An actual SQLite `UPDATE workspaces SET jobhub_job_id=501.9` stores `typeof(jobhub_job_id)='real'`.
3. `int(501.9)` returns 501. The builder computes a fresh `PublishingPackagePayload.compute_payload_hash()` **after** the coercion, so the hash seals an invented destination ID rather than detecting the altered source.
4. `validate_publishing_gate` validates the package; `execute_jobhub_publishing` (merged #4067) correctly requires `type(target_job_id) is int and target_job_id > 0`, then checks `jobs.id` and `job_no` within the write transaction. The upstream `int(...)` conversion defeats this final type check.
5. Job numbers may legitimately repeat between distinct JobHub IDs. The identity match is not a repair for an earlier truncated numeric selector.

## Inference and proposed correction

A workspace value that is not an **already exact positive Python integer** must never mint JobHub destination authority. Check the raw SQLite value before constructing a package or computing its payload fingerprint. Preserve `NULL` as a missing link (the final writer already refuses it). Reject REAL (including 501.9), TEXT, BLOB, zero, and negative IDs. Do not change the actual locked destination lookup, the valid positive integer write path, or any measurement issuer.

SQLite affinity can normalize a numeric string or integral float **at insertion time** into an integer. This change cannot retrospectively recover that original input type. The proven fix is for values still stored as non-integer or nonpositive, particularly fractional REAL values previously truncated by the builder.

## Source-neutral downstream evidence

Use the real PlanReader SQLite workspace fixture and real JobHub SQLite consumer. Insert a positive approved test row solely as a test fixture, set the workspace ID to REAL 501.9, and verify package construction fails before any seal/write; repeat across draft/commercial modes and other malformed stored types. Preserve genuine positive integer 501 through builder, fingerprint, gate, and actual JobHub header/line receipt; use a second JobHub job with the same human-facing job number to prove exact ID selection. Verify `NULL` stays missing and cannot publish.

These synthetic fixtures **do not** authenticate any original drawing, confer FIRM/customer authority, or change the frozen Full Plan V2 120-item score. Existing eight signed/customer quantities, original PDF SHA/page/viewport/snapshot/decision scope, benchmark truth, 20,000 primitive cap and 2.5 pt snap are untouched. GPT1, GPT2, GPT MAX, Claude, AntiGravity, and concurrent GPT3 branches are outside this change.
