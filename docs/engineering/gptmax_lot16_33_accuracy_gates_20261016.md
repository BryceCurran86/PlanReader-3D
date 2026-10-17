# GPT MAX — 33 Lot16 accuracy gates (12 frame/host + 21 width)

Issue #2396. Original Lot16 SHA256
`10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`, page 3,
snapshot `source_snapshot_3fcb6bc5c44b51d930e9600080501d27`.

Traced `compose_live_wall_opening_authority` →
`OpeningHostBindingProducer` / `_proven_raster_opening_flank_boxes` →
`OpeningHostFrameProducer._shared_host_frame` →
`OpeningDimensionAuthority.resolve_width`. No measurement seam. `#273`
ranking was not consulted. Default production stays 21 / 15 / 9 / 8.

## 12 frame / host gates

| # | Opening | Outcome | First original-source fail |
|---|---|---|---|
| 1 | `4b8c096b603c87f06f2692aa00494ab8` | Shadow frame `opening_host_frame_v2_1119f8f8b79417fbad4259d7f2a1b414` | `:713` ticks; motif DISTINCT in opt-in shadow only |
| 2 | `ab431bf4eca30b24da97e2fe3b0f424b` | Shadow frame `opening_host_frame_v2_84b7886ae5cfdc50ef777647666f2560` | same whole-wall `…6e6c93326de616ea9702e0c5932ff5e3` |
| 3 | `c3c1e04acd78419e4f707dfcd89c7096` | Shadow frame `opening_host_frame_v2_160b309a576abd9cce008f0dcbc80821` | same |
| 4 | `2c31ccb074d8eae86cac281c0fde1176` | ABSTAIN | `:1583` MSB/PCD corner; `pair_excluded_no_longitudinal_overlap`; DISTINCT unproven |
| 5 | `2b2a91e8afaf8b7e9a3e07605a80a4a9` | ABSTAIN | neighbour `a68d0b7d` has no host; members supplemental-only |
| 6 | `dbcec9c3cfa8e22b332479d09a601985` | ABSTAIN | real 2.4 vs 3.36 thickness step at west kitchen return |
| 7 | `a68d0b7d738b5de9a1588b4e680e1a8f` | ABSTAIN | right pier 716.16–760.32 has no W4; `area_m2` is None; do not transfer 1215 |
| 8 | `33d277d4c6b6ce758b0594f9d47ce4d8` | ABSTAIN | left faces 581.04–584.88 are 3.84 pt, below unchanged 4.0 pt rule; `area_m2` is None |
| 9 | `81a45c3a33c2a4c0bfdf243aa45a780d` | ABSTAIN | right faces 425.28/427.44 y=247.68–252.48 (4.8 pt) unmapped; `area_m2` is None |
| 10 | `b248972669988c108ebc90c6ca3908fd` | ABSTAIN | near faces 5.76 pt unmapped; no solid left W4; `area_m2` is None |
| 11 | `ba7f75a2e5f68bcce87cd00ac1acf90b` | ABSTAIN | near faces 6.48 pt unmapped; `area_m2` is None |
| 12 | `f819752382d44a00d9f28feca4b00787` | ABSTAIN | left 4.8 pt pier is the same interval as 81a45 right; `area_m2` is None |

Gates 7, 9 and 12 share one producer: `_proven_raster_opening_flank_boxes`
skips a closed G17 flank unless a figured label minted `area_m2`. Removing
that gate in default is the #2660 churn path (existing 15 host IDs, including
1215 members `wall_ad5e43e87149682d9900` / `wall_f92ac8eb34b0048e144b`).
Keep the gate. A later opt-in source-perception workstream may nominate
closed flanks without `area_m2` only after snapshot and host-identity
retention are proved.

Gate 8 must not lower `_MIN_LINE_LENGTH_PT = 4.0`. Inclusive painted-cell
support remains diagnostic-only (`shadow_inclusive_source_cells`).

## 21 width gates

`OpeningDimensionAuthority.resolve_width` on every page-3 physical opening
returns `opening_dimension_witness_topology_required` (21/21). Jambs from
G17 support are not enough. The authority requires one visible dimension
line whose endpoints sit on the two jamb axes, plus two distinct witness
lines, plus trusted text bound to that line. Raster figured labels that
already mint eight signed areas are a different seam
(`OpeningLabelDimensionProducer`) and must not be converted to millimetres
here. No gap width, nearest text, or schedule row is authorized.

## Readiness (corrected 2026-10-16)

#2809 remains OPEN on `main` (`61fcb385`). #2813 stays stacked on that
parent until #2809 merges. Do not retarget the child early. The
split-centreline workflow keeps `on.pull_request.branches: [main]`;
`workflow_dispatch` is additive so exact-head original-source can run on
the stacked SHA without changing that trigger. W4 run `38829635307`
job `116745178857` failed installing dependencies before geometry; rerun
that job. Do not change geometry to repair an install failure.

The three 870 frames are unpublished shadow hypotheses, not FIRM
quantities. Default production stays 21 / 15 / 9 / 8. Sparse 28 pt at
pitch 130 stays a typed unsigned motif residual under occupancy; it does
not grant production DISTINCT.

## Proposed change

None in default production. The three 870 shadow frames stay opt-in
`raster_split_frame_shadow=True`. GPT1 still owns typed opening + metric
axes. GPT3 still owns signed customer output. MAX owns overlapping
#2807 dimension-before-GPT1 work; this stack does not edit that branch.

## Benchmark observations that must not influence implementation

Lot16 Full Plan V2 8/27, expected BOQ, opening size labels as prediction
inputs, and room names were not used to choose a host, thickness, or width.
Signed receipts stay unverified here.
