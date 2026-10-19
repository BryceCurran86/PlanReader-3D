# Lot16 unhosted G17→W4 end-reach original-source receipt (2026-10-20)

Source SHA `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`, page 3.
Tool: `tools/diag_cursor_lot16_unhosted_end_reach_shadow.py`.

| Field | Value |
|---|---|
| unhosted_opening_count | 6 |
| ancestry_rows_with_end_reach | 6 |
| flank_disposition_counts | left_source_primitive_unmapped ×6, right_source_primitive_unmapped ×6 |
| signed_eight_retained | true |
| host_granted | false |
| benchmark_score_granted | false |

Interpretation: every unhosted Lot16 opening fails at **both** flanks with
`raster_source_band_{side}_source_primitive_unmapped` — W4 candidates do not
own authenticated derivation-parent primitives that meet the sealed FACE/END
band. This is the typed host first gate for GPT MAX; Cursor retains candidates
and does not nearest-elect.
