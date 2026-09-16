# Opening Host Binding Authority V3 — Authenticated-Prerequisite Architecture

Status: TEST-ONLY CONTRACT / SELF-AUTHORED / INDEPENDENT REVIEW REQUIRED

Base: `76c7882b1c4b28764d1e6a6f467d72bb276c2e01`

## Purpose

V3 proves exactly one downstream proposition: one already-authenticated physical
opening instance is bound to exactly one eligible authenticated physical wall in
the complete exact source scope.

It does not prove opening dimensions, physical void, wall deduction, wall role,
wall height, wall thickness, net wall area, FIRM/commercial publication or
JobHub data.

## Required chain

real PDF bytes
→ `SourceVisibilityProducer`
→ reviewed `PhysicalOpeningAuthority` existence + exact local identity
→ merged `PhysicalWallCandidateProducer.from_source_visibility_producer(...)`
→ sealed complete `PhysicalWallCandidateAuthority`
→ sealed complete host-wall-universe authority
→ unique-host resolution
→ sealed selector-only host-binding authority.

No caller-authored wall list, candidate id list, local subset, count,
completeness boolean, radius, confidence, nearest/first choice or raw geometry
may establish any stage of that chain.

## Host-wall universe boundary

The host-wall universe must be derived from the merged complete
`PhysicalWallCandidateAuthority`. Its public selector contains only:

- `document_id`
- `revision_id`
- `source_sha256`
- `snapshot_id`
- `page_id`
- `decision_scope_id`

The universe producer is sealed and is created from the real physical-wall
candidate authority. Ordinary callers cannot provide `candidate_wall_ids`,
`walls`, `segments`, `edges_by_id`, `wall_count`, `candidate_count`,
`claimed_complete`, `source_complete`, `host_universe_complete`, radius or
confidence.

## Binding boundary

The binding producer receives producer-owned authorities, not evidence bodies.
Publication must independently re-prove the opening from two source selectors,
confirm exact physical-opening identity, resolve the complete host universe, and
then compute host eligibility/uniqueness.

The public read selector contains lineage/scope plus the already-published exact
`opening_identity_id`. Possessing or guessing such an id is not sufficient to
mint a binding; the binding must already exist in producer-owned state.

## Omitted competitor vs genuine multi-host

These are different attacks.

### Attack 06 — omitted competitor

The real authenticated source contains wall records A+B. The complete merged
wall authority exposes A+B. A downstream caller attempts to construct an A-only
host scope. V3 must make this impossible through public APIs (or otherwise fail
closed); caller omission cannot shrink producer truth or result in
`scope_complete=True` for A-only.

### Attack 07 — genuine multi-host

The complete authenticated universe itself contains multiple physically valid
host candidates. Nothing is omitted. Because uniqueness is not proven, host
binding must ABSTAIN/CONFLICT.

The two attacks must never share the same explanation: Attack 06 is a
completeness/subset attack; Attack 07 is a uniqueness attack on a complete
universe.

## Fail-closed firewalls

Wrong revision/SHA/snapshot/page/scope, foreign primitives, caller-equivalence
claims, reversed/split representation flags, truncation/completeness claims,
tag/schedule/OCR/CV labels, raw opening spans, host ids and nearest/first/radius
inputs cannot produce authority.

Successful host binding must not alter `PhysicalOpeningAuthority.capabilities()`
for physical void or net wall area. Those remain separate future gates.

## Freeze rule

Freeze only when:

1. current GREEN prerequisite tests pass on exact current main;
2. ordinary pytest yields only GREEN + strict expected-XFAIL;
3. `pytest --runxfail --maxfail=1` reaches a genuine missing host-V3 production
   behavior, not an import error, stale 4A API, fixture defect or unsupported
   primitive-count assumption;
4. exact base/head/blob SHAs are recorded;
5. CI/Fastpath/static/integrity gates are green;
6. independent review is requested.

After freeze, production must change to satisfy the validator. The frozen
validator must not be weakened to fit production.
