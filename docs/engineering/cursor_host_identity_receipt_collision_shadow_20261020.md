# Cursor — host identity, receipt refresh, W4 collision shadows (2026-10-20)

Follow-on to the quantity-recovery architecture and the mission brief from the
explore pass (D1 / D3 / D5). Shadow only.

## Observed

- `#3342` stage 1 needs a first-gate receipt refresh without behavior change.
- Multi-host openings must retain candidates; nearest/first is forbidden.
- GPT2 `#3344` Task A: shared `wall_candidate_id` with distinct geometry must
  not silently overwrite.

## Delivered

| Module | Role |
|---|---|
| `pb_lot16_opening_receipt_refresh_shadow` | Schema refresh + publication flag lock |
| `pb_opening_host_identity_shadow` | Retain multi-host candidates; typed abstention |
| `pb_w4_candidate_id_collision_shadow` | Detect shared-ID distinct fingerprints |

## Untouched

Frozen truth, PDFs, commercial publishers, host binding producer defaults,
signed Lot16 eight. Benchmark scores are not inputs.
