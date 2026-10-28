# GPT3 — Sealed source creator and JobHub publishing actor retention (2026-10-29)

## Observed repository path

Studied current `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, source/frozen-V2 firewall, CI, the published JobHub contract, the real `test_dbs` SQLite fixture, and the shared agent coordination hub. On main `f64d1617cad9ff45de4a39b9c386aa4513e361d2`, `build_publishing_package_from_workspace(acting_user)` stores the source estimator/package creator in `PublishingPackagePayload.created_by`; `compute_payload_hash` seals it. `validate_publishing_gate` validates the original evidence. The real `execute_jobhub_publishing(package, bridge, user_name)` separately receives the delivery actor at write time and stores only that name in JobHub `created_by` and `notes`.

## Inference and first failure

`created_by` on the SHA-sealed PlanReader package and `user_name` at JobHub delivery represent potentially *different legitimate people*. A delegated release must not be blocked by an incorrect forced equality. Yet the source-sealed creator is absent from the destination audit trail and an empty/whitespace/non-string delivery actor can still produce a recipient package. This loses distinct provenance and admits unattributed customer delivery.

## Implemented change

At the final writer, reject a missing/non-string/blank publishing actor **before any JobHub connection**. Strip incidental outer whitespace from the independent publishing actor. Keep the JobHub `created_by` field as the delivery actor, and append separately signed `Package creator:` provenance to recipient notes only when source `package.created_by` exists. Preserve the original `Published by`, exact SHA-256 payload hash, source creator's immutable signed value, approval/status checks, TOCTOU, transactional identity/duplicate checks, real quantity/rate/area precision, price, and customer line contents. Drafts without a sealed creator continue to abstain from inventing one.

## Synthetic proof and safety scope

New real PlanReader/JobHub SQLite writer tests: two different legitimate creator/publisher actors, full hash retention and duplicate veto across publishers, blank/non-string rejection without a database connection, whitespace normalization, missing creator in draft without invented provenance, post-seal source creator mutation blocked, no source package mutation. No frozen benchmark truth is used as algorithm input. Excluded from change: all private original PDFs/tokens, frozen 120 denominator, signed customer archives, `#3796` original-eight/nine trusted release, GPT1/GPT2/MAX/AntiGravity/Claude modules, 20,000 primitive cap, 2.5pt snap. No new source, FIRM, original-positive replay, customer release certification or V2 score is claimed.

## Release gate

Inspect the three intended paths, exact-head full Python 3.13 and 3.14 CI and signed/customer/raster/performance companion checks. No merge before actual passing results. Original-backed activation stays separately blocked on the owner/main-only signed eight/default plus nine/explicit replay.
