# GPT MAX — Real source W3 snapped-pair provenance versus physical identity

## Source observation

The original Lot16 Rev E PDF (SHA
`10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`)
contains source-authenticated raster-opening `33d277d4...` with an unmapped
left wall flank. Independent source-owned positive-pixel observations
`source_observation_25f534ef92bfe35696461e862f9ba2c9`
and `source_observation_88079f10454dbc093cd9c8de4e05a2d9`
form separately painted page-space lines `[581,363]–[585,363]` and
`[581,363.5]–[585.5,363.5]` respectively. Experimental W2 edges
`split_6131` and `split_21591` retain their original source parents but
are marked `w3_removed=True` and have no W4 owner.

The current W3 `deduplicate_coincident_edges` implementation treats equal
*snapped node-pair IDs* as physical line redundancy. That equivalence does
not necessarily hold when two truly different original source lines fall
within the 2.5 PDF-point topology snap range. This is an **observed source
loss**, not yet proof that both input rails are independent physical walls.

## Read-only engineering seam

Without modifying the live `deduplicate_coincident_edges` implementation,
the original-positive-pixel source diagnostic now reports every actual W3
snapped-pair edge loss as a dual-source receipt:
- removed and retained W2 original edge IDs
- their separate parent `SourceObservation` IDs
- original W2 geometry before node collapse, snapped node IDs and endpoint
  displacement (both edge directions checked)
- explicit parent-set overlap and nonpublishing flags.

Input graph, actual deduplicated W3 graph, W4 candidate assembly and old
physical opening/host/frame extraction are unchanged. Common snapped node
addresses, distinct source parents or any measured displacement alone
cannot publish physical SAME/DISTINCT, a wall, host, count, quantity or
benchmark gain.

Positive real-source tests require the entire source PDF SHA, rendered pixel
source authentication, complete 1,952 original positive-run record inventory,
both original Python runtimes, and source primitive cap 20,000; they inspect
the known originally removed source rail *only as a fixture-specific control*.
No project-specific pixels or expected benchmark quantities enter algorithms.

## Retained-side integrity review on current main

**Observed:** `_trace_sources` builds original W2 records and passes the actual
output of `deduplicate_coincident_edges` to
`_nonpublishing_w3_snap_pair_source_losses`. The diagnostic validates original
edge geometry and discarded addresses, but accepts a retained record without
checking its original W2 address, geometry or ancestry. Its length check also
does not independently prove that retained and removed addresses partition the
original inventory. Removed identifiers are converted to strings, and output
order follows the caller's removal order.

**Inference:** a copied or corrupted diagnostic graph could describe invented
retained geometry or parents as original source evidence. This does not affect
the production deduplicator but invalidates a downstream source-loss audit.

**Proposed:** require each retained record to match its original W2 record
exactly; validate node addresses against the original node census; require a
disjoint, complete retained/removed partition using actual nonblank string
addresses; sort audit rows deterministically; reject nonfinite displacement;
and explicitly distinguish an unavailable parent inventory from positively
proven disjoint source parents. Empty parent inventories stay retained as
negative evidence. No topology, physical sameness, host or quantity promotion.

**Expected abstentions:** altered retained records, foreign/duplicate node or
edge addresses, omitted/overlapping census members and arithmetic overflow
must fail the audit. Missing source parents cannot prove disjointness.

**Benchmark observations:** the known source rail IDs, 14 hosts, nine frames,
1,952 pixel observations and the original PDF digest are validation controls
only. They do not enter the generic audit predicates. Production `pb_*.py`,
commercial output, source PDFs, W2/W3/W4 behavior, frozen V2 and the 20,000 input
primitive cap remain untouched.

### Current-main local verification

On unchanged source-production base `94f12a30d801201345c1c4bc3516454c3d39823c`,
the strengthened audit passes 153 focused source, loss, retained-record,
comparison and opening-face tests (Python 3.12). Ten adversarial cases failed
before the diagnostic repair. Original PDF and 144-DPI render hashes match;
the pixel audit retains 1,952 observations, 6,035 inputs and 5,034 W3 loss
records. No source-parent inventory is missing in that real audit. Independent
production replay preserves every opening binding and frame trace exactly:
23 claims, 14 hosts, nine frames, zero lost or changed proofs. Provider
isolation, frozen V2 integrity, compilation and Ruff F821/F823 pass.

The full local suite is still running and the W21 schedule identity test was
independently reproduced as failing on unchanged `6b7908c` main. This is not a
full-suite pass or an accuracy result. The workflow now explicitly runs the
original PR-base production extraction and requires strict host/frame receipt
retention. Exact final-head Python 3.13/3.14 CI and source gates remain required
before merge.

## Next implementation authority

A separate experimental source-wall structural classifier must authenticate
**whether each retained/lost pair is the same painted physical member or
two distinct solid-wall faces** under exact original source, physical G17
sealed face/end contact, W2 endpoint locality and independent W4 equivalence.
Only then can one consider preserving an additional source rail in W3 without
rekeying the 14 authenticated Lot16 hosts and nine original frames. Prior
global compact-raster experiments #2032/#2161 failed this exact source
retention and must not be replayed wholesale.

Frozen V2 manifests, object universe, denominators, expected quantities,
evaluator and tolerances untouched. No 20,000 primitive bound relaxation.
