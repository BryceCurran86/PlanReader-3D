# GPT1 handoff — three Lot16 870 shadow frames

Issue #2396. Continues PR #2813 / #2809. Original Lot16 SHA256
`10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`, page 3,
snapshot `source_snapshot_3fcb6bc5c44b51d930e9600080501d27`.

These are unpublished opt-in `raster_split_frame_shadow` hypotheses.
They are not FIRM quantities, not signed customer rows, and not a GPT1
metric-axis grant. Default production stays 21 openings / 15 hosts / 9
frames / 8 signed opening-area quantities. MAX #2807 still owns ordered
dimension-before-GPT1 work on its own branch.

Reproduce on the actual #2813 head with
`tools/diag_gptmax_source_split_frame_shadow.py`. The artifact field
`gpt1_shadow_frame_source_bundles` is the complete source bundle.

## Shared whole-wall (shadow only)

`opening_host_whole_wall_frame_v1_6e6c93326de616ea9702e0c5932ff5e3`

Members: `wall_037156cd6ac85472c11f`, `wall_2c74d7fb7c6a96671107`,
`wall_2c98be6d134ba709b065`, `wall_e0c3801840a2de6853a6`.

Reproduced on head `13cc46d1`. Default first DISTINCT fail before motif
skip remains `wall_834b98f11c6b792ad73b` / `:713` at (1065.5, 297)–(1070,
297). All three shadow frames name the same five leftover receipts:

- `opening_host_frame_aligned_motif_fragments_skipped`
- `…:wall_834b98f11c6b792ad73b`
- `…:wall_a5598661c0fa52c5b81e`
- `…:wall_c5e00d5a5edcc70f20bf`
- `…:wall_cb4b89ac477d3f26fddf`
- `…:wall_cbd5120133f33920fefa`

Those codes are decision provenance. They do not enter
`opening_host_frame_v2` or `opening_host_whole_wall_frame_v1`. The three
frame ids below match the frames that exist if those leftovers are absent.

## Three additional shadow frames

| Opening | Host binding | Host members | Shadow frame |
|---|---|---|---|
| `physical_opening_existence_4b8c096b603c87f06f2692aa00494ab8` | `opening_host_binding_v3_d359790c77e7632090642d4177cc8c3c` | `wall_2c74d7fb7c6a96671107`, `wall_e0c3801840a2de6853a6` | `opening_host_frame_v2_1119f8f8b79417fbad4259d7f2a1b414` |
| `physical_opening_existence_ab431bf4eca30b24da97e2fe3b0f424b` | `opening_host_binding_v3_70e95586cd2bbf769a790b247047b09c` | `wall_2c98be6d134ba709b065`, `wall_e0c3801840a2de6853a6` | `opening_host_frame_v2_84b7886ae5cfdc50ef777647666f2560` |
| `physical_opening_existence_c3c1e04acd78419e4f707dfcd89c7096` | `opening_host_binding_v3_3d9f107e23c6937695ca30d0b2782f3c` | `wall_037156cd6ac85472c11f`, `wall_2c98be6d134ba709b065` | `opening_host_frame_v2_160b309a576abd9cce008f0dcbc80821` |

Whole-wall origin is (384.0, 298.32), thickness 3.36 pt. Opening intervals
on that axis: `4b8c` u0=242.40–266.16; `ab43` 195.60–219.36; `c3c1`
16.32–40.08. Host bindings remain the two-member sets above; the bundle
`member_wall_ids` field is the shared four-wall whole-wall component.

## Remaining GPT1 blockers (not granted here)

Typed kind on all three is `door` from
`raster_door_swing_wall_band_interruption`
(`opening_kind_structural_door`, `opening_kind_corroborated`). That is
structural pattern only. No schedule instance is bound. Label text is not
a kind source. GPT1 still owns schedule/label corroboration and any
conflict if those sources disagree.

Metric width is `opening_dimension_witness_topology_required` on all three
(and on all 21 page-3 physical openings). `value_mm` is null. Jambs from
G17 support are not enough. `OpeningDimensionAuthority.resolve_width`
still requires one visible dimension line on the two jamb axes, two
distinct witness lines, and trusted text bound to that line. Raster
figured labels that already mint eight signed areas are a different seam
and must not be converted to millimetres here.

`gpt1_metric_axis_handoff_granted` stays false. `firm_quantity_granted`
stays false. `new_customer_quantity_granted` stays false. Shadow frames
are not FIRM quantities.

## Independent of this stack

`2c31` remains ABSTAIN on `:1583`. `2b2a` / `a68d` / `dbce` remain ABSTAIN;
see `docs/engineering/gptmax_2b2a_dbce_frame_abstain_20261016.md`. Sparse
28 pt at pitch 130 remains a typed unsigned motif residual. It does not
grant production DISTINCT.

## Benchmark observations that must not influence implementation

Lot16 Full Plan V2 8/27, expected BOQ, and the 870 labels as prediction
inputs were not used to mint these frames or any millimetre.
