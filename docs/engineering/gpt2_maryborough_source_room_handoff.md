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


## Three original FIRM rooms — publisher handoff (2026-10-12)

The original-SHA-verified Maryborough source run (PDF SHA
`b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`)
retains the following producer-owned receipts. These identifiers are **diagnostic
observations**, not new benchmark truth or constants used in production.

| Original room label | Exact source room-face receipt | Canonical floor | Source room-area QuantityEvidence | Original FIRM m² |
| --- | --- | --- | --- | ---: |
| FOOD PREP | `source_room_face_record_a163b3690c0b2db83f89fcf7465bd831` | `physical_room_floor_surface_10d0d5ddf8103483397512c5a74584f7` | `qty_be2a3b3108220d48f6f5` | 13.270425 |
| OFFICE | `source_room_face_record_735f9b309cca70f513c9fcd9390e3e10` | `physical_room_floor_surface_980b1ad9cbaebb3cc41351623718270e` | `qty_29e71bd466a9e5fa1783` | 9.05352 |
| COLD ROOM | `source_room_face_record_17f0cb15ba5c2f25ff17b12b2ccc5129` | `physical_room_floor_surface_4bca8579c101670bbfa0853cbbfc6f87` | `qty_9795d69439e85c35b01c` | 25.37875 |

The first report (`report_source_room_handoff`) reports
`COMMERCIAL_FLOOR_AREA_AUTHORITY_UNAVAILABLE` because canonical floors
**deliberately** leave `metric_geometry_complete=False` and
`commercial_quantity_authority=False` for documented-only room areas.
**Neither flag should be manually flipped.** A source-FIRM documented area is
not a scaled physical polygon or a certified finish occurrence.

The follow-on `inspect_room_measurement_gates` report runs **real**
`publish_live_floor_area_quantities` and
`publish_live_canonical_room_area_quantities` for the *same live claim* and
reports exact separate `FLOOR_QUANTITY_PUBLICATION`,
`CANONICAL_ROOM_AREA_REISSUE`, `SEALED_CUSTOMER_PROJECTION_UNVERIFIED` or
`CUSTOMER_REVIEW_ROW_VERIFIED_UNSCORED` stages. It also reports any actual
reissued source-owned quantity IDs, plus canonical/source-floor ownership and
individual first-failure receipts. These are the correct actionable GPT1/GPT3
gates. The new SHA-pinned workflow stores both
`original-maryborough-source-room-handoff.json` and
`original-maryborough-floor-publisher-firstgate.json` from **one** original
PDF extraction; it asserts that all three exact source face and canonical
floor IDs agree, that the source FIRM areas are unchanged, and that no
commercial flag, finish, benchmark numerator or evaluator has been altered.

Other observed source-positive rooms: FREEZER is withheld at
`SOURCE_ROOM_PHYSICAL_POLYGON_INCOMPLETE` in the stricter source handoff;
PWD, AIRLOCK, LAUNDRY and SALES are withheld at
`FIRM_AREA_SOURCE_MEASUREMENT_UNAVAILABLE`. Six other requested named rooms
and DRY STORE have no unique authenticated closed face. The separate W4/GRID
original source ledger in issue #2009 explains the source wall and invalid
polygon causes. Nothing in this diagnostic publishes unsupported customer
quantities.
