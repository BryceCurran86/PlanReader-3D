# GPT1 — exact source measurement at the floor-finish seal (2026-10-30)

## Observed current-main behavior

Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, W-topology/spec, retired benchmark firewall, CI and accuracy-lever index. Current base main: `65dc4684fbcf1ce36c704457d896fc7c12a651de`.

Real chain: `pb_cross_view_floor_finish_authority.CrossViewFloorFinishProducer.publish` binds original source-defined floor finish to an already metric, physical canonical floor and emits `QuantityEvidence(family="floor_finish_area")`, with original `figured_dimension_ids`. `pb_live_physical_net_wall_integration._collect_live_physical_net_wall_claim` retains that original evidence. `pb_live_floor_finish_area_source_closed_export.build_live_floor_finish_area_source_traces` checks the canonical floor and source material/room receipts, then `seal_live_floor_finish_area_run` directly seals it via `seal_source_closed_run`. Separately, `pb_live_floor_finish_customer_projection.project_live_floor_finish_customer_rows` calls the source trace builder, then `_measurement_authority` validates the original dimension pair or physical scale and `verify_sealed_customer_output` checks the customer result. GPT3's unchanged frozen V2 evaluator is downstream of the actual production replay, not an input to this change.

The **first failing real gate** is the direct source trace/seal boundary: it normalizes both `quantity.authority` and `floor.metric_area_authority` before comparison and does not check the two original figured witnesses or resolved physical scale. Thus the direct seal can accept a forged or incomplete measurement token even though the later customer projector refuses it. This is a source-seal integrity issue, not a new quantity.

## Inference and proposed narrow repair

At the direct source-seal boundary, reject any authority other than an **exact** existing `MeasurementAuthorityType.DOCUMENTED_DIMENSION.value` or `MeasurementAuthorityType.PDF_SCALED.value`, and require the canonical floor's authority to be the same exact token. For documented area, require an original typed pair of two distinct, nonblank, unpadded figured-axis IDs. For scaled area, require exact nonblank `resolved_scale_id`, literal `resolved`/`verified` status, and an empty typed list/tuple of conflicts. No new axis inference, room matching, scale authority, finish definition, measurement value, source ID or scorer logic.

The pre-existing customer-only malformed-axis test now fails earlier at the source-seal boundary, so its expected exception is updated to the stronger source-conflict error. Tests include a valid direct seal/customer/verified row, forged original axes, invalid authority tokens on either/both sides, invalid original physical scale, deterministic replay, and no mutation. A synthetic pass is **not** original-source authority.

## Non-authority and preservation

No changes to GPT2 physical FT2/FT3/RCP/doorway correspondence, GPT MAX/Claude host/glazing, GPT3 signed/frozen scoring, other GPT1 PRs #3758/#4127/#4129/#4130, original PDF bytes or tokens, historical signed fixtures, 20,000 primitive cap or 2.5pt snap. Expected benchmark quantities, tolerances and scores are not used. Unknown, conflicting, or missing original measurement receipts remain ABSTAIN/nonpublishable. Exact-head Python 3.13/3.14 CI and technical diff review are required, followed by trusted SHA-verified original producer→issuer→sealed/customer preservation replay and unchanged frozen evaluator before any merge or FIRM/accuracy claim.
