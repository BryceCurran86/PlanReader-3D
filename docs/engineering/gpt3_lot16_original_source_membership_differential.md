# Lot16 source membership differential — original artifact, unpublished

This is a **source-diagnostic ledger**, not source authentication for a new
opening, a commercial quantity, or a benchmark match.

## Immutable provenance and comparison

- Original architectural PDF SHA-256: `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`.
- Preserved GitHub Actions pair: workflow run
  [38203747665](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38203747665),
  artifact ID `11727074490`, ZIP members
  `snap-source-baseline.json` and `snap-source-current.json`.
- The comparison is historical PR #2511 base `46be9c4995fc2e9590a70e04205914b72222fe2a`
  against head `af58690c6b664a329ef24452414ded2240a616e8`.
  **It is not a fresh current-main differential.**
- Both source reports preserve the original SHA, source revision/snapshot,
  classified page and 20,000 source-primitive cap.

## Exact source-observation membership (zero-based PDF page 3)

| Collection | Before | After | Added IDs | Removed IDs |
| --- | ---: | ---: | ---: | ---: |
| Unresolved native physical opening candidates | 125 | 189 | 74 | 10 |
| Unresolved native source observations | 434 | 648 | 260 | 46 |
| Semantic conflict observations | 591 | 385 | 0 | 206 |
| Residual visible observations | 480 | 694 | 260 | 46 |
| Conflict / residual **overlap** | 212 | 274 | — | — |

Important exact-set findings:

1. The **260 newly residual observations are exactly the 260 newly
   unresolved native observations**.
2. All 260 newly residual observations were present in the **old**
   semantic conflict set. However **147 of those 260 are STILL in the new
   semantic conflict set**. Only 113 of those moved out of the new conflict set.
   Therefore `newly residual` is **not proof of resolution**.
3. The old conflict set loses 206 total IDs; these removals must not be
   converted into authoritative physical host or opening claims without
   corroborating original wall-stub evidence.
4. The top-level 21 canonical opening records, 21 opening bindings and
   host-frame traces, nine resolved source frames, and eight area-record
   summary are retained. The full structural evidence changes nonetheless.

Representative newly unresolved native candidate:
`physical_opening_candidate_036daef54a69c217d95b5aa54f08a18a`.

Representative removed unresolved native candidate:
`physical_opening_candidate_0642f50e4b1edd105bb816f13f5bcd27`.

Representative newly unresolved source observation:
`source_observation_00ab7937e88412757c15b1d38274a646`.

## Next source-authority gate

Use the read-only `tools/diag_gpt3_original_source_membership.py`
comparison against the exact SHA-verified workflow reports to enumerate
missing/added ID sets. Resolve the candidate-specific original source line
continuation and competing wall-face evidence before altering #2511's strict
original-source parity assertion. Repeat the differential on **fresh main**,
because the archived base predates subsequent source-producer merges.

Never weaken the native/source candidate-universe completeness gate; do not
promote an unresolved source candidate, hallucinate a wall host, or publish an
opening count because summary totals happen to match. Keep the Full Plan V2
120-object score **UNPUBLISHED** until genuine sealed source and frozen
reconciliation artifacts are available.
