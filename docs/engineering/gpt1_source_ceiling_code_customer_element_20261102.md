# GPT1 — Original RCP finish code in customer ceiling element (2026-11-02)

## OBSERVED
- Real source path: `pb_cross_view_ceiling_quantity_authority.publish_cross_view_ceiling_quantities` → `LivePhysicalNetWallClaim.ceiling_lining_quantity_evidence` → `pb_live_ceiling_lining_source_closed_export.build_live_ceiling_lining_source_traces` → `pb_live_ceiling_customer_projection.project_live_ceiling_customer_rows` → `quantities_to_takeoff_output_rows` and `verify_sealed_customer_output`.
- Source-closed exporter independently validates the signed `ceiling_lining:<ceiling_id>:<finish_code>:<semantic_finish>` identity against source occurrence, definition, physical room, source SHA/revision/page/viewport and figured axes.
- The customer bridge formerly wrote identical generic `element = "Ceiling lining area"` for different authenticated RCP systems, while only retaining semantic family in `finish_system`. Thus distinct original codes such as `GRID` / `IPF1` were not visible as takeoff elements.

## INFERENCE
- A real source-authenticated ceiling quantity can be commercially ambiguous even when signed m², schema and semantic finish are intact. Displaying its existing exact code improves estimator review and keeps source-trace identity visible.
- A different original-page or unowned code must NOT be guessed or repaired from material descriptions or normalized text.

## CHANGE
- Retain the exact source-owned, typed, nonempty, unpadded `metadata["finish_code"]` already independently checked by the source-closed exporter.
- Set customer `element = f"Ceiling lining area ({source_finish_code})"`; preserve `finish_system` semantic, quantity precision, source ref, original seal and customer `To review` state.
- Real producer-shaped positive test asserts `GRID` is in the customer element AND original `9.05352` survives; seven source-code tampering negatives fail sealed/customer projection, with positive reissue proving no mutation. No original documents or benchmark gold in test.

## BENCHMARK FIREWALL AND RELEASE
- This is **commercial output clarity**, NOT a new original A120 ceiling quantity, source-positive OFFICE GRID proof, benchmark match, or FIRM advancement. Synthetic `9.05352` fixture is NOT an original Office ceiling measurement.
- Do not change source geometry, thresholds, 2.5pt snap, 20k cap, existing signed opening and room areas, frozen 4-project/120 evaluator or private source PDFs.
- Keep PR draft pending exact-head Python 3.13/3.14 CI and GPT3's source-original replay, signed/customer retention. The original Maryborough W4→A120 ink/room/ceiling source correspondence remains GPT2-dependent.

## Additional signed/customer authority parity implementation
- **Observed:** `pb_customer_output_verification._verify_row_lineage` already rejects retyped source FT codes/materials, but had no symmetric check for the source-coded ceiling material key. A numerically unchanged verified RCP quantity could therefore acquire an unrelated source-code display caption if the customer metadata and computed fingerprint were modified together.
- **Change:** for original RCP `ceiling_lining:<ceiling-id>:<code>:<material>` (and only that four-part key), require the exact sealed ceiling ID in original source identity refs, exact producer metadata code/material/canonical ID, exact customer `finish_system`, and exact `Ceiling lining area (<code>)` in machine provenance and row. The two-part legacy `ceiling_lining:<id>` quantity remains on its unchanged legacy source path.
- **Negative proof:** changed customer element/material, changed machine RCP identity/definition fields, and self-consistently recomputed provenance/fingerprint including notes-only legacy persistence must still fail against the unchanged sealed source identity. Original valid `GRID` re-verifies without mutation.
- **Real workspace seam:** `pb_auto_geometry_v1219._try_physical_net_wall_rows` consumes the live projector through `_takeoff_row`; combined integration branch #4155 includes the exact source-closed `finish_system` and `INCLUSION` constructor fix and checks an actual in-memory workspace takeoff row retaining `Ceiling lining area (GRID)`, full m² precision and To review status.
- **Safety:** no original RCP measurement is minted and no FT/RCP semantics are inferred. The original Maryborough A120/W4 physical ceiling source remains an independent GPT2 blocker, and trusted-source replay/frozen120 remain required before customer release.
