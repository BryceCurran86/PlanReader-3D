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

All shadow / review-only. No FIRM, no gold inputs, no JobHub activation.

## Still blocked for Cursor alone

Door-height convention (12), STACKER host proof (5), GPT2 room producers (19
implementation), GPT3 seal + frozen V2 eval (25, 29–30).
