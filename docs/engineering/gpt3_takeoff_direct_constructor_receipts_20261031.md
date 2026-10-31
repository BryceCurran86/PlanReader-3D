# GPT3 — Modern TakeoffOutputRow direct constructor cannot invent source authority

2026-10-31 AEST. Base main: `953d4951f23cf2323721abfc7b0dab076bb58eb8`.

## OBSERVED production call path

`pb_takeoff_output_authority.TakeoffOutputRow(...)` is a directly constructible dataclass. Its default `source_type=documented_dimension` and `authority_status=firm` are taken as source receipts by `pb_planreader_jobhub_publish_contract.run_jobhub_publish_preflight`, via `PlanReaderJobHubQuantityRow.from_takeoff_output_row`. An untrusted typed caller may provide a page, dimension ID, matching revision and `is_publishable=True` without ever asserting actual source/authority fields. The JobHub payload builder repeats this preflight; the typed path has no raw input record on which to check whether the defaults were omitted.

Merged #4107 fixed modern `TakeoffOutputRow.from_dict` missing serialized receipts; existing GPT3 draft #4138 separately owns `PlanReaderJobHubQuantityRow` direct/default and hydration paths. Neither corrects this distinct, modern direct-constructor entry point.

## INFERRED first failing authority boundary

A dataclass fallback is not producer-owned figured-dimension evidence or FIRM status. The final commercial gate must receive the explicit issuer's source/type claims, rather than authority inferred merely because a Python object was constructed. This is a negative-only commercial integrity issue and NOT a newly measured quantity.

## PROPOSED change

Use the existing `TakeoffSourceType.BLOCKED.value` and `AuthorityStatus.BLOCKED.value` as direct `TakeoffOutputRow` constructor defaults. Keep `create_takeoff_output_row`'s explicit calculated authority and `from_dict`'s explicit producer receipts unchanged. Preserve externally supplied, valid typed and serialized source-positive records at the existing commercial preflight. Do not auto-repair a missing receipt to FIRM.

Focused source-neutral regression: missing both/source/authority on direct typed objects; raw and serialized/hydrated paths; actual final commercial preflight and payload builder; genuine explicit positive and factory positive; draft-only negative; deterministic replay and no-mutation.

## BENCHMARK observations excluded from implementation

Frozen Full Plan V2 120-item denominator and prior Lot16/Maryborough signed quantities are evaluation/release facts only. No gold, benchmark identity, expected BOQ, PDF name, source hash, or drawing-specific threshold influences this change. No source-positive original drawing replay or scoring claim is made.

## Explicitly untouched

Original PDFs/credentials, frozen benchmark/evaluator, physical geometry, measurement authority producers, 20,000 primitive cap, 2.5 pt snap, V1 signed/customer archival receipts, GPT3 #3796 release branch, GPT3 #4128 and #4138 claimed paths, and all GPT1/GPT2/MAX/Claude/AntiGravity work. A new signed/customer/source-positive replay is still required before release or merge.
