# GPT2 → GPT1/GPT3 exact source-room metric handoff (read-only)

Task tracker: [#2009](https://github.com/BryceCurran86/PlanReader-3D/issues/2009).
Original SHA-pinned Maryborough source: `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`, 31 pages. Real handoff invocation selects topology page 7 (zero-index 6) and *separately source-decodes* support page 11 (zero-index 10). Never turn a support-page label or finish code into a physical wall.

This new **read-only** tool inspects production `LivePhysicalNetWallClaim`; it neither creates missing rooms, geometry, scale, finishes or output quantities nor accesses frozen evaluator truth. It reports the **first missing source authority** for 15 specifically requested labels; those names are **targets for reporting only**. They cannot mint `canonical_rooms`.

## Eight independent ownership gates

1. **Unique original physical source room identity**: exact room face receipt/physical identity/document/revision/snapshot, source SHA, authenticated view and distinct physical face (no nearest-label matches).
2. **Original trusted text receipt**: one original room label binding and unique unshared native source text observation IDs.
3. **Positive original closed room polygon**: finite PDF source vertices, source-complete polygon and positive *page-point²* area, not a metric conversion.
4. **Unique canonical floor owner**: one floor owned by the exact canonical source room, no last-write-winning duplicate canonical floor identity.
5. **Immutable source face-to-floor lineage**: same original face, document, page, viewport, snapshot and source polygon.
6. **Source-owned firm figured/scale metric evidence**: one uniquely identifiable numeric, finite, independently supported `QuantityEvidence` owned by the **original source face** via its exact record receipt, area producer `room_area:<source_face_id>` semantic key, and unchanged SHA/revision/viewport context. Missing evidence is **UNAVAILABLE**, never 0 m².
7. **Exact commercial floor permission**: floor quantity ID equals the independently measured quantity, matching finite metric area and producer-authenticated surface/metric/commercial authority. A valid *room area* does not bypass this.
8. **Separate actual finish/ceiling occurrence authority**: no finish or ceiling lining is published just because a floor, grid title, code or material definition exists; both require separately authenticated placement, view and exact room ownership. This report always leaves such output `False`.

Tests exercise each missing and conflicting stage, original SHA mismatch, malformed and duplicated label evidence, nonfinite polygon/area, duplicate quantities and floor IDs, and missing targets. A required SHA-verified original source run will report first failing stages for Food Prep, Cold Room, Office, Freezer, PWD, Airlock, Laundry, Sales, POS Counter, Food Service, Wash Up, Truck Driver Lounge, M-AMB, F-AMB and Dry Store.

## Verified historical controls versus current integration

Historical original-source runs already produced Food Prep **13.270425 m²**, Office **9.05352 m²**, Cold Room **25.37875 m²** through documented-area evidence. Those control values are historical evidence, **not constructor defaults or acceptance bypasses**. A new source run must establish its own exact area QuantityEvidence and customer-ready floor status. [#2451](https://github.com/BryceCurran86/PlanReader-3D/pull/2451) merged original positive text-to-face ownership for these three rooms plus five others; the page-7 authenticated floor viewport still has a PARTIAL face universe (687 positive source face receipts and 511 withheld). [#2453](https://github.com/BryceCurran86/PlanReader-3D/pull/2453) found six withheld unresolved boundaries, only one sharing source W4 candidate IDs with directly labelled **Freezer** and **Sales**. A source-ID intersection does not prove face adjacency or metric area.

**GPT1 handoff:** every reported target carries only a source-proven physical room ID, exact source face receipt, canonical floor ID and source quantity ID if and only if the matching gates pass. Do not infer area from PDF points² or a printed finish code; do not treat missing evidence as zero. **GPT3 handoff:** seal no commercial floor/finish/ceiling row without producer-owned quantified floor authority, unique lineage and all independently required view/material occurrence gates. No customer row, final V2 scorer or benchmark numerator is produced here.

DRY STORE **ABSTAIN**. M-AMB/F-AMB and POS/FOOD SERVICE/WASH UP/TRUCK DRIVER LOUNGE **ABSTAIN** on missing unique genuine physical room closure until original-source evidence proves otherwise. The frozen 24 Maryborough +27 Lot16 object universes, evaluator, reference values, tolerances and 20,000 input primitive safety limit are unchanged.

### Producer-key distinction established on current code

`pb_ceiling_lining_scope_binder.build_owned_source_room_face_index` derives the documented-area RoomCandidate `room_ref` from the **source face ID**; `pb_room_area_quantity.build_room_area_quantities` therefore issues source room-area `QuantityEvidence.input_entity_ids=(room.room_ref,)`, not a canonical floor ID. The quantity's independently authenticated `evidence_ids` include the producer-owned source-room-face **record** ID, and its `metadata` includes original source SHA/revision/viewport. The auditor now matches that exact source receipt/context first, then asks whether the resulting quantity ID and value were actually projected into the *same* canonical floor and whether the floor grants commercial publication. This makes failures at source room measurement separate from failures at the canonical floor bridge. A bare matching room label, value, page-points area or matching floor ID is insufficient.

### Auditable GPT1/GPT3 handoff receipts

Positive reports include `original_source_face_receipt_id` and **only after a source-authenticated distinct original word owner** also `original_label_binding_record_id` and the exact `original_label_evidence_ids`. The first admissible independently producer-owned documented/physically-scaled room area adds `documented_area_quantity_id`, `documented_area_source_evidence_ids`, `documented_area_original_authority` and `source_proven_area_m2`. Those fields remain **null/empty** when their producer stage is unavailable or conflicted, even if the room name appears on the PDF or a historical control happens to have that number. They never imply `commercial_quantity_authority`, which requires a separate unique canonical floor with the exact quantity ID/value and explicit producer permission. No raw text names or fields are acceptable source geometry substitutes.

### Independent floor-area reissue versus customer sealing (original source, 2026-10-12)

The current canonical floor object may deliberately retain `commercial_quantity_authority=False` despite having source-FIRM documented room area. **Do not override that flag.** The independent production `publish_live_floor_area_quantities` checks all original source-room-area receipts, complete canonical floor ownership, source SHA, physical floor identity, duplicate source claims and exact measured values, and can reissue a separate `floor_area` QuantityEvidence. That reissue is *neither* a source finish occurrence *nor* a confirmed sealed customer row.

The read-only GPT2 handoff therefore reports `producer_floor_area_reissue_quantity_id_observed_only` separately from `first_unproved_authority`, and always publishes `customer_floor_area_seal_verified_by_this_report=False`. It calls the actual publisher only for an exact production `LivePhysicalNetWallClaim`, never a synthetic or name-matched claim, and accepts a reissue only with a unique exact upstream quantity ID, canonical floor ID, original physical room-face receipt, source SHA, FIRM `floor_area` status, exact amount, and producer `row_role` and `commercial_projection_allowed` metadata. Duplicates or contradictory ownership remain unavailable.

The SHA-pinned original 31-page Maryborough source run independently witnessed existing floor-area reissues for **FOOD PREP 13.270425 m², COLD ROOM 25.37875 m² and OFFICE 9.05352 m²**. Its new regression requires exactly those three originals and does not alter 24-object frozen benchmark truth, the downstream customer sealing gate or the independent RCP/floor material occurrence contracts. FREEZER, PWD, AIRLOCK, LAUNDRY, SALES and the remaining unclosed physical rooms still lack admissible metric evidence; DRY STORE remains ABSTAIN. GPT1/GPT3 should validate sealed customer output separately from this diagnostic before claiming any benchmark improvement.

### Original-source customer row verification, separate from official V2 (2026-10-12)

An independently run SHA-pinned production source handoff in [original
artifact 11750297601](https://github.com/BryceCurran86/PlanReader-3D/actions/runs/38253592536/artifacts/11750297601)
called the actual GPT1 floor-area and canonical-room reissuers and the
separate GPT3 source-closed customer gate against the *same original
Maryborough claim*. Its precise evidence counts are **3 FIRM floor-area
reissues, 3 canonical-room-area reissues, 3 source-closed floor seals and
3 customer rows verified**, without modifying production commercial flags.

| Room | Original source area quantity | FIRM floor-area reissue | Canonical-room area reissue | FIRM area m² |
| --- | --- | --- | --- | ---: |
| FOOD PREP | `qty_be2a3b3108220d48f6f5` | `floor_area_quantity_d62c2f382a0c773ec36f` | `canonical_room_area_quantity_a691af59bcb8a78c474d` | 13.270425 |
| OFFICE | `qty_29e71bd466a9e5fa1783` | `floor_area_quantity_8bcdc01455538a6a105a` | `canonical_room_area_quantity_3b2be6bc2f91a42ee569` | 9.05352 |
| COLD ROOM | `qty_9795d69439e85c35b01c` | `floor_area_quantity_6b28b3abaedf519631ed` | `canonical_room_area_quantity_409cc3811baafced5beb` | 25.37875 |

The three records each report
`CUSTOMER_REVIEW_ROW_VERIFIED_UNSCORED`. Their original physical-room face,
literal source label, independent documented-dimension evidence and exact
canonical floor have been cross-checked. Their canonical floors correctly
retain `metric_geometry_complete=False` and
`commercial_quantity_authority=False`: a documented FIRM area is not a
metrically scaled polygon or source-authenticated floor finish. The source
proof validates *floor area only*. No actual floor-finish, ceiling-lining or
additional named room has been authenticated.

The new workflow checks all these producer and customer stages in one
original source extraction and stores
`original-maryborough-floor-publisher-firstgate.json` beside the existing
room/face handoff. The **frozen 24-object Maryborough V2 evaluator has not
run** on that artifact, and `benchmark_accuracy=null` remains required.
A customer-row verification is not permission to count that row as matched
within the benchmark tolerance until GPT3 reconciles it.
