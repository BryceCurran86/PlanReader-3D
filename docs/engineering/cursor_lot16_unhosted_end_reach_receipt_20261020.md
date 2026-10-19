# Lot16 unhosted G17→W4 end-reach original-source receipt (2026-10-20)

Source SHA `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`, page 3.
Tool: `tools/diag_cursor_lot16_unhosted_end_reach_shadow.py`.
Re-verified on main after GPT MAX multi-parent end-reach retention (`1a684d28`).

| Field | Value |
|---|---|
| unhosted_opening_count | 6 |
| ancestry_rows_with_end_reach | 6 |
| flank_disposition_counts | left+right `source_primitive_unmapped` ×6 |
| source_line_gate_counts | `authenticated_raster_parent_lines_empty` ×6 |
| sample census | support 8, derivation parents 8, authenticated lines **0**, usable W4 primitives 2282, intersection 0 |
| signed_eight_retained | true |
| host_granted | false |
| benchmark_score_granted | false |

Interpretation: G17 support and derivation-parent IDs exist, but
`_authenticated_raster_source_lines` returns **no** `visible:` raster segment
lines for those parents. End-reach therefore never sees W4-owned source geometry
in the sealed flank band. GPT MAX next step is parent-observation kind /
`visible:` line authentication — not proximity host election.
