# Lot16 unhosted parent-line kind census (2026-10-20)

Source SHA `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`, page 3.
Tool: `tools/diag_cursor_lot16_unhosted_parent_line_kind_census.py`.

| Field | Value |
|---|---|
| unhosted_opening_count | 6 |
| parent_observation_kind_counts | `raster_opening_primitive_segment`: **48** |
| line_auth_outcome_counts | `parent_kind_not_raster_pdf_visible_segment`: **48** |
| signed_eight_retained | true |
| host_granted | false |

Interpretation: every G17 derivation parent for the six unhosted openings is a
`raster_opening_primitive_segment`, while
`_authenticated_raster_source_lines` only accepts `RASTER_PDF_VISIBLE_SEGMENT`
with a `visible:` primitive ref. That is why end-reach sees empty authenticated
lines and reports `source_primitive_unmapped`. GPT MAX next step is parent→visible
line authentication (or an owned alternate geometry path) — not proximity hosting.
