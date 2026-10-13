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
   "baseline_snapshot_id": "...", "candidate_snapshot_id": "...",
   "expected_new_host_ids": ["physical_opening_existence_..."],
   "expected_new_frame_host_ids": [],
   "expected_unhosted_reason_changes": [
     {"opening_identity_id": "...", "before": ["..."], "after": ["..."]}],
   "tracking_issue": 2608}]}
```

The snapshot ids are printed by `python -m tools.declared_additive_source_retention
--baseline before.json --candidate after.json` when no declaration matches.

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
* source SHA, page scope and the 20,000 primitive cap are unchanged.

A declared event that violates any of this raises. It is never silently
downgraded to the undeclared (strict) path.

## What it does not do

It grants no host, frame, count, quantity or score
(`official_host_receipt_identity_acceptance`, `host_publication_allowed`,
`opening_count_or_metric_publication_allowed` are always `False`,
`benchmark_accuracy` is `None`). It does not judge wall topology changes on
unhosted walls beyond the retained-host and unrelated-opening checks above, and
it does not replace the quantity / sealing / frozen-reconciliation gates.

## Wiring

`compare_source_face_reports` and `compare_opposed_source_reports` load the
committed declarations by default (empty = strict, identical behaviour to
before). Inline workflow assertions use
`assert <strict equality> or declared_event_approved(old, new)`.
