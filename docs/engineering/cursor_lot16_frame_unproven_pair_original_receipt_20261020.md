# Lot16 frame unproven-pair original-source receipt (2026-10-20)

Source SHA `10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`, page 3.
Tool: `tools/diag_cursor_lot16_frame_unproven_pair_shadow.py`.

## Baseline (fragment roles off)

| Field | Value |
|---|---|
| first_gate_counts | host 6, frame 6, kind 3, figured pair 1, axes 5 |
| frame_blocked_openings_with_ledger | 3 |
| relation_counts | {} (no `unproven_wall_pair` reasons without fragment roles) |
| signed_eight_quantity_ids_retained | true |
| frame_granted | false |

## Opt-in `--source-fragment-roles`

| Field | Value |
|---|---|
| first_gate_counts | host 3, frame 10, kind 3, figured pair 1, axes 5 |
| frame_blocked_openings_with_ledger | 7 |
| relation_counts | UNRECORDED: 318 |
| signed_eight_quantity_ids_retained | true |
| frame_granted | false |
| benchmark_score_granted | false |

Interpretation: fragment-role capture surfaces more hosted openings that still
fail closed on whole-wall frame because competitor pairs are UNRECORDED — never
treated as DISTINCT. No quantity or score claim.
