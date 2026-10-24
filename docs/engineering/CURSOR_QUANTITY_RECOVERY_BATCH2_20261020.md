# Cursor quantity recovery — batch 2 (2026-10-20)

Continues the autonomous mission after #3348 / #3350 / #3351 / #3354.

## Developments in this PR

| Mission | Module |
|---|---|
| 4 | `pb_opening_fragment_identity_shadow` |
| 6 | `pb_signed_opening_dedupe_shadow` |
| 10 | `pb_opening_label_leader_witness_shadow` |
| 13 | `pb_glazed_opening_frame_area_readiness_shadow` |
| 19 | `pb_room_finish_quantity_readiness_shadow` |
| 20 | `pb_pitched_ceiling_readiness_shadow` |
| 21 | `pb_canonical_quantity_attach_shadow` |
| 22 | `pb_source_lineage_required_fields_shadow` |
| 3 | `pb_whole_wall_frame_readiness_shadow` |
| 25/27 | `pb_source_closed_seal_readiness_shadow`, `pb_trade_quantity_evidence_readiness_shadow` |
| 29–30 | `pb_frozen_v2_eval_readiness_shadow` (refuse-closed; no score claim) |
| 5-shadow | `pb_stacker_host_frame_readiness_shadow` (image frame ≠ host) |
| 7-shadow | `pb_bifold_filling_kind_shadow` |
| 12-shadow | `pb_door_height_owner_gate_shadow` (never invents 2100) |
| compose | `tools/diag_cursor_quantity_recovery_compose_shadow.py` |
| ledger | `tools/diag_cursor_quantity_recovery_mission_ledger.py` |

All shadow / review-only. No FIRM, no gold inputs, no JobHub activation.

## Still blocked for Cursor alone (FIRM / eval)

STACKER host FIRM (5), BIFOLD kind FIRM (7), door-height FIRM without owner
atom (12), GPT2 room producers (19), GPT3 seal + frozen V2 eval (25, 29–30).
