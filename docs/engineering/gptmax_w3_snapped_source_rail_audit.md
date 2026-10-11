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
