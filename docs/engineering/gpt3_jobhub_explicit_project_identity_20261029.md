# GPT3 — Explicit project identity at the V1 JobHub customer gate (2026-10-29)

## Observed production boundary

Read current main `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, hub #3462 and current claims; traced `pb_planreader_jobhub_publish_contract.run_jobhub_publish_preflight` → `build_jobhub_payload` → `PlanReaderJobHubPayload.is_commercial_ready` and existing publishing tests. Base main `f64d1617cad9ff45de4a39b9c386aa4513e361d2`.

The V1 preflight accepted any `project_identity` with a nonempty `project_id` unless `identity_confirmed is False`. Missing confirmation, `None`, numeric 0/1 and strings like `"true"` all bypassed the negative branch. An otherwise publishable source-neutral FIRM row could then be placed into `build_jobhub_payload` and stamped `is_commercial_ready=True` without an explicit project/source match. The string project ID is not evidence of source ownership.

## Inference and repair

Commercial project identity must be affirmatively established: require `identity_confirmed is True`, rejecting missing, ambiguous or non-boolean truthy values. Preserve the existing explicit `False` mismatch veto and its detailed reason. Drafts with unknown identity may remain drafts only with an explicit visible unconfirmed-identity warning, never `is_commercial_ready`. A known mismatch remains blocked even for draft preflight. Do not rewrite or infer project identity from filename, title, benchmark, or expected quantities.

## Actual downstream consumer tests

New source-neutral tests call `run_jobhub_publish_preflight` and the real `build_jobhub_payload` consumer with a typed documented FIRM row. Cover missing confirmation, eight ambiguous/non-boolean values, explicit mismatched source, exact `True` positive, provisional draft warning, and known-mismatch draft block. Assert that unverified commercial inputs cannot produce a customer-ready payload and that approved source-neutral rows retain their physical quantity ID and sealed fingerprint. These synthetic rows exercise policy only, not real original-PDF authority or customer approval.

## Ownership, authority and release

Exclusive coordination claim #3462/6475286905. Only `pb_planreader_jobhub_publish_contract.py`, new `tests/publishing/test_gpt3_jobhub_explicit_project_identity.py`, and this report change. Disjoint from GPT3 #4081 contract and other GPT3 #4080 pipeline, GPT1/GPT2/MAX/Claude/AntiGravity source/geometry, historical eight signed/customer rows, original private PDFs, frozen V2 120 evaluator/denominators, 20,000 raster primitive cap and 2.5pt snap.

Exact-head Python 3.13/3.14 CI, signed/customer/raster/performance companion checks, full patch technical review and main overlap verification are required before merge. No original-positive replay, new FIRM/customer authority or frozen V2 score change is claimed. Owner-only #3796 original-eight/default and original-nine/explicit trusted replay remains blocked.
