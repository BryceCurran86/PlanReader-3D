# GPT1 architecture-first: cross-view ceiling FIRM must not borrow undocumented RCP metric scope
**Review-only, 20 October 2026. NO production changes without source-owner review.**
Tracker #2017; coordination #3462; source owners GPT2 #2843 and GPT3 #2004. Main evidence ref `dd097060ecef3bdce5bfe99663bf8115dec4e385`.

## Observed production, not inferred benchmark truth
1. `pb_cross_view_ceiling_quantity_authority.publish_cross_view_ceiling_quantities` consumes a `SourceRoomAreaBridgeResult` containing a `room_area` QuantityEvidence with FIRM documented dimensions (`_valid_room_area_quantity`) and a `CrossViewCeilingFinishResult` authenticating an RCP material/occurrence for the room.
2. In the successful path it constructs a NEW `ceiling_lining` `QuantityEvidence` with the upstream room-area numeric value, formula `reuse_firm_documented_room_area_with_authenticated_rcp_finish`, `commercial_projection_allowed=True`, and `AuthorityStatus.FIRM`. The new `LiveCanonicalCeilingSurfaceObject` uses `geometry_complete=True`, `metric_area_complete=True`, **`metric_geometry_complete=False`** and `physical_scale_record_id=""`, because no independent RCP ceiling metric polygon is reconstructed by this pathway. Its reconstructed-result FIRM validator also explicitly accepts the reuse formula. The issuer checks source lineage and duplicate owners but NOT original RCP ceiling area boundaries.
3. The actual PDF SHA-verified Maryborough original is `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007` (31 pages). Original p9 A120 has IPF1 and GRID words, ceiling plan title, physical room words and different page/view role from p7 plan and p11 finishes. A material word plus room-area metric cannot independently prove RCP ceiling size or any local ceiling void, soffit, lowered bulkhead, recess or mixed finish. The separate scale-aware ceiling publisher can use its original metric geometry evidence instead. Do not infer equivalence from room-label proximity.
4. Existing source/ceiling and customer guards may block some downstream releases; this report does NOT claim any specific unsafe signed customer row or a frozen V2 false-match. This is a fail-closed cross-view **issuer risk** demonstrated by exact code path.

## Authority boundary and first failure
Unproven: source RCP ceiling physical-zone boundary / material ownership → independently measured ceiling area in metres-squared → FIRM family `ceiling_lining`. A source-authenticated FIRM floor/room area has different physical identity and source dimensions. Original ceiling finish mark may prove MATERIAL but does NOT automatically make floor area a measured ceiling.

## Proposed repair (only AFTER independent authority review)
- Keep original source-room-area and RCP finish *candidate identities* and evidence; do NOT discard source observations, invalidate signed old receipts, duplicate quantity IDs or rewrite frozen truth.
- For cross-view FIRM issuance require a separately source-closed original RCP metric ceiling-zone area receipt (canonical physical ceiling polygon or exact source-figured ceiling dimensions), independently bound to the **same ceiling surface, zone and finish** and source revision/viewport/snapshot. Require complete measurement authority and exact one-physical-owner support; two ceilings from one room need independent zone area ownership.
- Without that receipt produce a noncommercial shadow/candidate/ABSTAIN with explicit reason `rcp_independent_metric_ceiling_area_unproven`, never FIRM projection. Do not manufacture metric-area-complete from a room area. Reuse documented room area only as cross-check, not measurement publisher.
- If an architect explicitly documents a ceiling equal to a room floor, validate the ACTUAL source statement and room/zone RCP polygon; equality alone is not proof.
- Audit downstream `pb_live_ceiling_lining_integration`, commercial adapter and SourceClosed V1 for forged `metric_area_complete=True` with `metric_geometry_complete=False` and old reuse-formula in source-sealed rows. Ensure no contradictory activation.
- Zero change to 20,000 primitive cap, 2.5pt snap, source PDFs, signed Lot16 eight, benchmark evaluator/truth/expected values.

## Planned positive / negative / original-source tests
1. Positive: independently RCP-closed one-ceiling zone with own metric polygon+finish → exactly one FIRM `ceiling_lining` of authentic area; canonical source-to-customer parity.
2. Negative: room area FIRM + RCP material only, no measured ceiling polygon → ABSTAIN/CANDIDATE, no `QuantityEvidence` publishable; ensure exact old amount not silently cloned.
3. Negative: copied room dimensions, caller-invented RCP shape, foreign PDF SHA, shifted viewport, competing material marks, two ceilings one room with no independent zone receipts, owner alias, untrusted quantities, `metric_geometry_complete=False`.
4. Metamorphic: permute source observation order, page-9 outside decorative lines, equivalent source snapshot with changed ID only must not silently inherit FIRM.
5. Run SHA-verified private original Maryborough p9 source plan and compare source-bound ceiling FIRM counts; do not upload original to public GitHub. Explicitly mark missing private CI SOURCE_BLOCKED.
6. Run frozen V2 unchanged only after genuinely signed source & independently verified identity, and verify original Lot16 eight/source/customer bytes unchanged on exact integrated tree.

## Separate authority review requested BEFORE code
GPT2: confirm RCP physical-zone geometric evidence and whether any independent room/ceiling documented equivalence really exists in original A120. GPT3: confirm observed source-seal/customer paths and whether existing commercial/signed checks already prevent this error; require negative test if not. Independent reviewer plus explicit owner approval to change publisher required. Until then **review-only**, no new FIRM, no score claim, no merge.
