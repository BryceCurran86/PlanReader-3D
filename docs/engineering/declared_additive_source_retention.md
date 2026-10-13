# Declared additive-source retention

Why this exists: host and frame receipts (`opening_host_binding_v3`,
`opening_host_binding_group`) hash the SourceVisibility `snapshot_id`. Any
change that legitimately adds source observations to a page rekeys every
previously authenticated receipt, even when the physical proposition behind it
is untouched. The strict retention gates reject that, on purpose
(`tools/gptmax_source_host_rekey_parity_ledger.py` calls it an *unapproved*
rekey). A change that intends to add a host therefore cannot pass them.

This is the separate, explicit approval step. It does not publish anything.

## What a declaration binds

One event, exactly: `source_sha256` + `baseline_snapshot_id` +
`candidate_snapshot_id`, in `tools/declared_additive_source_retention.json`.
Once the candidate becomes the next baseline the declaration no longer matches,
so it is single-use and every later rekey needs a new, reviewed declaration.

```json
{"schema": "declared_additive_source_retention.v1",
 "declarations": [{
   "source_sha256": "<64 hex>",
   "report_shape": "stage_report | face_report",
   "baseline_snapshot_id": "...", "candidate_snapshot_id": "...",
   "expected_new_host_ids": ["physical_opening_existence_..."],
   "expected_new_frame_host_ids": [],
   "expected_unhosted_reason_changes": [
     {"opening_identity_id": "...", "before": ["..."], "after": ["..."]}],
   "expected_changed_report_keys": ["snapshot_id", "opening_bindings", "..."],
   "expected_id_churn_report_keys": ["native_candidate_closures", "..."],
   "allow_snapshot_receipt_rekey": false,
   "tracking_issue": 2608}]}
```

The snapshot ids are printed by `python -m tools.declared_additive_source_retention
--baseline before.json --candidate after.json` when no declaration matches.

## Receipt rekey is a separate decision

`allow_snapshot_receipt_rekey: false` (the stance to start from) means every
previously authenticated host and frame receipt must be retained **exactly**; the
declaration then only admits the declared new host(s), reason transitions and
changed report keys, i.e. it turns a full-report parity gate into "unchanged
except exactly this". Set `true` only when the production change adds source
observations to the page snapshot, which rekeys every snapshot-hashed receipt
(`host_wall_id`, `opening_host_binding_v3`, `opening_host_frame_v2`); the
approval then additionally proves the physical proposition behind each rekeyed
receipt is unchanged. Reviewers should treat `true` as the decision to accept a
re-signed seal for prior quantities (their evidence ids and fingerprints change
by exactly one host-binding and one frame receipt per row, which
`sealed_quantities_changed_only_by_snapshot_receipts` can prove). The better
long-term fix is a design where additive source does not change the primary
snapshot (see #2297); this flag exists so that decision is explicit, not hidden.

## What an approval proves

On top of `compare_source_host_rekeys` (W4 member identity, candidate identity,
source primitive ancestry, source-edge geometry, centerline, frame geometry;
generated `split_N` ordinals and snapshot-scoped receipt ids are ignored):

* the physical opening identity universe is identical;
* every previously hosted opening is still hosted, and its binding and frame
  rows differ **only** in `host_wall_id` / `record_id`;
* newly hosted openings are exactly the declared ones, each an existing physical
  opening (same page and representative source observation) with a corroborated
  host receipt; a newly resolved frame must be declared too
  (`expected_new_frame_host_ids`), a previously hosted opening can never gain one;
* every other unhosted opening keeps status, page, representative observation,
  members, receipts and frame reasons; its host reason codes change only through
  an exact declared `before -> after` transition that actually occurs;
* source SHA, page scope and the 20,000 primitive cap are unchanged;
* **all original source geometry is conserved** (W4): a wall id present in both
  keeps its candidate identity, source primitive ancestry and physical path, and
  its source fragments cover exactly the same physical line (it may only gain an
  interior split node); every wall id that disappears has exactly one successor
  on the same source primitives whose source fragments **cover every original
  fragment, terminal endpoints included** (tolerance 1e-3 pt); every other new
  wall contains a source primitive no baseline wall used. A successor that
  merely shares primitive ids but lost a terminal tail (snap-collapsed at a new
  crossing), a shifted endpoint or diagonal, a hole, several candidate
  successors, or a new wall made only of old source is refused -- never elected;
* the W4 **scope-level claims** (status, completeness, equivalence groups,
  boundary evaluation, source metadata table, ...) are equal modulo snapshot ids,
  with `*observation_ids` lists allowed to grow; any change to what the scope
  claims is refused (after the record-level check above names the wall). This
  means an event that adds or re-addresses W4 walls cannot be approved by this
  contract as it stands -- the aggregate lists derived from the wall set change --
  and needs a reviewed derivation rule first;
* **every top-level report key not listed in `expected_changed_report_keys` is
  equal** (after the gate's own order-insensitive normalizer, if it has one), and
  every key that *is* listed is either verified or reported:
  * `canonical_openings`: per opening, only the host receipts, `snapshot_id` and
    receipt evidence ids may move (one binding + one frame per prior row, one new
    binding for a declared new host); figured areas, geometry and every other
    field stay equal, and the record must agree with the verified host/frame rows;
  * `summary`: host / frame counts move only by the declared new hosts / frames;
  * `semantic_inventory`: equal modulo snapshot-scoped ids, `*_observation_ids`
    may only gain members;
  * `expected_id_churn_report_keys`: equal modulo the code-derived set of
    snapshot-scoped id prefixes (`tools/source_report_scoped_equality.py`; each
    prefix hashes `snapshot_id`) and list order -- physical ids, source
    observation ids, values and counts are still compared exactly;
  * any other declared key is listed in `unverified_changed_report_keys` of the
    approval: nothing verified it, and reviewers should read that list.
A declared event that violates any of this raises. It is never silently
downgraded to the undeclared (strict) path.

## Report shapes

`stage_report` is `tools/diag_gptmax_source_authority_stages.py` (carries
`resolved_host_frame_evidence`; every retained frame is geometry-verified).
`face_report` is `tools/diag_opening_wall_face_preservation.py`, which never
carries frame geometry: membership, receipts and reasons are verified but frame
**geometry is not** (`frame_geometry_verified: False`). The declared shape must
match the reports (an evidence array that appears or vanishes is refused), so a
tool change cannot silently downgrade a `stage_report` verification. The two
shapes have different snapshot ids (the stage tool ingests every page), so an
event needs one declaration per shape that its gates use.

## Real Lot16 evidence (page 3, original SHA `10109b4b…65844`)

* #2606 (global additive source): **refused** -- seven unhosted W4 walls lose an
  original terminal (raster tails `[x, 427.8 .. 429.5]` at x=597.75 / 669 / 682.25
  and three native diagonals shifted 0.12-0.13 pt), first reported at
  `wall_280f16c8… -> wall_c902ecb0…`.
* #2609 (W2 terminal-tail retention, head `d8f01bb2`): record-level conservation
  holds (2092 retained exactly, 2 re-addressed ids with covering successors) but
  the scope-level aggregates (`evaluated_wall_candidate_ids`, equivalence
  ambiguous/abstained lists, blocking reasons of the 4 changed walls, one
  representative id, `source_segment_count`) change with the wall set, so it is
  **refused** until a derivation rule for them is reviewed.
* #2610 (isolated opening-local supplemental W4): approved with canonical W4
  2094 retained / 0 lost / 0 gained and an unchanged scope; `composition_reason_codes` is now verified against the already-proven changed opening binding/frame rows, so the reviewed #2610 event has no intentionally blind changed report key. Any unrelated aggregate reason addition/removal is refused.

Nothing in this PR enables either: the committed declaration list is empty and
adding a real declaration needs the owners' sign-off.

## What it does not do

It grants no host, frame, count, quantity or score
(`official_host_receipt_identity_acceptance`, `host_publication_allowed`,
`opening_count_or_metric_publication_allowed` are always `False`,
`benchmark_accuracy` is `None`). It does not replace the quantity / sealing /
frozen-reconciliation gates, and it proves nothing about *why* the added source
is physically right (that needs the producer's own proof and a visual check).

## Wiring

`compare_source_face_reports` and `compare_opposed_source_reports` load the
committed declarations by default (empty = strict, identical behaviour to
before). Inline workflow assertions use
`assert_unchanged_or_declared(old, new, normalize=...)`: strict equality, or one
declared and proven event, or an `AssertionError` (a declared-but-violated event
raises `ValueError`, it is never mistaken for the undeclared case). The failing
undeclared case prints the exact event key a declaration would have to bind.
