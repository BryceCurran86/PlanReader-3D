# GPT MAX — aligned-fragment DISTINCT vs original Lot16 dimension ticks

Issue #2396. Continues PR #2809. F07 remains supporting physical-view evidence, not host membership.

## Observed repository behavior

Original Lot16 SHA256 `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`, page 3, snapshot `source_snapshot_3fcb6bc5c44b51d930e9600080501d27`.

`physical_opening_existence_2c31ccb074d8eae86cac281c0fde1176` (2148 PANEL LIFT) already has a source-proven split-centreline host (`wall_7d3dcc7ce4afc5c15704`, `wall_b25b5ffd3a29be53747f`, shared raster primitive `:1585`). The selected connected component contains only those two members. The first aligned W4 fragment that fails DISTINCT is `wall_3c9933f91a1a3079fcf3` / `wall2_72e9c558ade6b4d38426`, primitive `:1583`, centerline (410.04, 596.16)–(408.75, 624.5). Identity candidacy is `pair_excluded_no_longitudinal_overlap`; stored classification is missing; live classification is AMBIGUOUS. Original raster of that interval is the MSB/PCD corner of the same garage wall run, a genuine structural fragment with a 55 pt gap from `:1585`. DISTINCT is unproven. ABSTAIN is required.

`physical_opening_existence_4b8c096b603c87f06f2692aa00494ab8`, `ab431bf4eca30b24da97e2fe3b0f424b`, and `c3c1e04acd78419e4f707dfcd89c7096` already share one connected four-wall component (`wall_037156cd6ac85472c11f`, `wall_2c98be6d134ba709b065`, `wall_e0c3801840a2de6853a6`, `wall_2c74d7fb7c6a96671107`). Their first aligned DISTINCT failure is `wall_834b98f11c6b792ad73b` / primitive `:713`, a 4.5 pt horizontal at (1065.5, 297.0)–(1070.0, 297.0). Original source at that coordinate is a repeated 90/1080 dimension-witness tick family, not a structural wall. Raster-visible segments are injected with `path_index` unset, so the pre-W2 singleton motif filter cannot see them.

A unique aligned unconnected source wall still has no DISTINCT relation. `tests/test_raster_connected_host_frame.py::test_aligned_unproven_fragment_blocks_whole_wall_extent` remains the negative.

## Inference

`:1583` is a continuation or T-junction return of the PANEL LIFT host wall. Connection would require a new snap or T-join. DISTINCT would be an assumption. Keep ABSTAIN.

`:713` and the same-length orthogonal raster family are drafting ticks. Identity already refuses SAME-wall candidacy because they do not overlap the host. The missing pair is not DISTINCT only because non-candidates carry no relation.

## Proposed change

Opt-in `raster_split_frame_shadow` only. After W4 IDs exist, reuse the existing orthogonal drafting-motif repeat count and span fraction on raster-only single-segment W4 records. The fraction is applied to the repeated family's own along-axis occupancy, not a page or viewport bbox. A motif wall with no stored identity relation against a non-motif component member is accepted as DISTINCT for the whole-wall aligned-fragment gate. This is a repeat census, not a dimension-annotation bind. Unique aligned fragments, native remote strokes, SAME/AMBIGUOUS pairs, eight or more genuine wall-length collinear fragments, and default production stay fail-closed. Split IDs are not rekeyed.

## Independent original-source result

Default production is unchanged: 21 physical openings, 15 hosts, 9 complete frames, 8 signed opening-area quantities, snapshot `source_snapshot_3fcb6bc5c44b51d930e9600080501d27`. Opt-in shadow publishes three additional complete frames that share one whole-wall identity:

| Opening | Host binding | Frame record | Whole-wall frame |
|---|---|---|---|
| `physical_opening_existence_4b8c096b603c87f06f2692aa00494ab8` | `opening_host_binding_v3_d359790c77e7632090642d4177cc8c3c` members `wall_2c74d7fb7c6a96671107`, `wall_e0c3801840a2de6853a6` | `opening_host_frame_v2_1119f8f8b79417fbad4259d7f2a1b414` | `opening_host_whole_wall_frame_v1_6e6c93326de616ea9702e0c5932ff5e3` |
| `physical_opening_existence_ab431bf4eca30b24da97e2fe3b0f424b` | `opening_host_binding_v3_70e95586cd2bbf769a790b247047b09c` members `wall_2c98be6d134ba709b065`, `wall_e0c3801840a2de6853a6` | `opening_host_frame_v2_84b7886ae5cfdc50ef777647666f2560` | same |
| `physical_opening_existence_c3c1e04acd78419e4f707dfcd89c7096` | `opening_host_binding_v3_3d9f107e23c6937695ca30d0b2782f3c` members `wall_037156cd6ac85472c11f`, `wall_2c98be6d134ba709b065` | `opening_host_frame_v2_160b309a576abd9cce008f0dcbc80821` | same |

Whole-wall members: `wall_037156cd6ac85472c11f`, `wall_2c74d7fb7c6a96671107`, `wall_2c98be6d134ba709b065`, `wall_e0c3801840a2de6853a6`. No new customer quantity. GPT1 metric-axis handoff is not granted.

`2c31` remains `opening_host_frame_aligned_fragment_distinctness_unproven` on `:1583`. `2b2a91e8` and `dbcec9c3` remain independently ABSTAINED; see `docs/engineering/gptmax_2b2a_dbce_frame_abstain_20261016.md`.

## Benchmark observations that must not influence implementation

Lot16 Full Plan V2 8/27, expected BOQ, project names, and the F07 sheet outline as host proof were not used as prediction inputs. Signed customer receipts stay unverified here and must not change.
