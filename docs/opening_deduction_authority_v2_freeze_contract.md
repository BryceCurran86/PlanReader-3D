# Item 13 — Opening Deduction Authority V2 freeze contract

**TEST ONLY / EXPECTED-RED / DRAFT / NEVER MERGE**

Exact baseline: merged main `212f5b0ff9d9e585c4b9db861cf42729166f70f5` (Item 11 Physical Opening Void V2 merged; Item 12 frozen replay complete).

## Proposition

A proved physical opening void is **not** deduction permission.

A positive Opening Deduction record may exist only when all of these independent propositions are producer-owned and exact-scope consistent:

1. the exact physical opening / void is resolved;
2. the exact host binding is resolved;
3. the exact opening decision scope is complete;
4. a separate sealed target-applicability authority proves that this exact opening/void applies to this exact deduction target under an authenticated measurement/applicability rule.

`target_scope_id` is an address only. It cannot self-certify trade, finish, assembly, wall-face, or commercial applicability.

## Required production boundary

`OpeningDeductionProducer.from_authorities(...)` must consume producer-owned authorities for:

- physical opening void;
- host binding;
- opening-universe completeness;
- target applicability.

A positive `OpeningDeductionRecord` must retain, at minimum:

- exact document/revision/source SHA/snapshot/page/decision-scope lineage;
- exact physical opening identity;
- exact host-binding record identity;
- exact physical-void record identity;
- exact opening-universe record identity;
- exact `target_scope_id`;
- immutable target-applicability record identity (`applicability_record_id` or an equivalently explicit provenance field).

The record does not carry raw width/height/area, caller deduction flags, net-wall area, FIRM publication, or JobHub authority.

## Target-applicability prerequisite

The prerequisite is tracked separately in issue #446. The expected production module name for this freeze contract is `pb_opening_deduction_applicability_authority`; an equivalently strict reviewed successor may replace it only by versioning this validator rather than weakening the frozen blob.

The applicability proposition must be producer-owned. It must not be inferred from:

- physical void existence;
- `target_scope_id` existence;
- caller `deductible`, `finish_applicable`, `trade_applicable`, `assembly_applicable`, or similar flags;
- legacy caller-created `commercial_applicability` metadata;
- nearest/first/default target selection;
- type marks, dimensions, or area unless a separately authenticated governing rule explicitly requires them.

## Fail-closed attacks

Before Item 13 may be called frozen, the executable validator must lock at least:

- selector-only deduction lookup/publication;
- raw area and width×height cannot mint deduction;
- caller host IDs cannot mint deduction;
- caller applicability booleans cannot mint deduction;
- exact physical void with no applicability authority cannot authorize deduction;
- exact physical void with unresolved applicability stays unknown / `record=None`, never zero;
- target-scope address without producer-owned target/rule proof cannot authorize deduction;
- wrong wall/trade/finish/assembly applicability fails closed;
- stale document/revision/source/snapshot/page fails closed;
- incomplete opening universe blocks;
- unresolved relevant void blocks;
- duplicate observations of one authenticated opening cannot create duplicate deduction records;
- same-size distinct physical openings remain distinct;
- overlapping distinct openings remain distinct at this layer (Boolean union is later);
- positive records retain applicability provenance;
- deduction authority does not publish net-wall, FIRM/commercial, or JobHub authority.

## Real-source gate

The validator baseline must first prove that the merged real-source chain can produce an authenticated Physical Opening Void from native PDF bytes. Only then may the expected-red deduction/applicability tests run. This prevents a stale upstream fixture from being mistaken for a genuine deduction RED.

## Freeze and replay rule

This branch remains test-only and never merges. Freeze requires:

1. exact-head CI + Fastpath green in ordinary expected-red mode;
2. `--runxfail` (or equivalent focused replay) reaches a genuine missing deduction/applicability proposition after the real physical-void baseline succeeds;
3. no benchmark/gold/scorer/tolerance/denominator/holdout changes;
4. exact validator blob is replayed unchanged over Item 14 production;
5. independent review accepts the exact head/blob.

Production must change to satisfy this contract. Do not weaken the validator to fit #442's current permanent-abstention implementation.