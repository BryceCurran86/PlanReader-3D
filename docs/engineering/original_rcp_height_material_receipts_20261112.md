# Original PlanReader: source-trusted RCP height/material word receipts (GPT MAX, 12 Nov 2026)

## Purpose and source of the idea

This is a bounded port of the useful **same-native-text-block, adjacent-line RCP height/material detector** from the isolated draft Next engine (#4284, reviewed head `1b7e2c593f130ac0c29a97089ede4ed3cd76d921`) to **original PlanReader's** PDF text-integrity and cross-view ceiling-finish pipeline.

The new `pb_source_rcp_height_material_evidence.py` uses **only** a current `SourceVisibilityProducer` snapshot. The producer owns original PDF source bytes, SHA, clipping and overprint/glyph decisions, native block/line/word ordinals and observation IDs. The consumer re-resolves each word through existing `_trusted_words_by_page` and discards all words whose native integrity result was not CORROBORATED.

The opt-in method `CrossViewCeilingFinishProducer.source_rcp_height_material_evidence(revision_id=..., page_id=...)` is now an accessible seam in original PlanReader. The existing `publish()` and the original room/floor/ceiling/lining issuer, sealing and customer adapters are **unchanged**.

## What is authenticated, and what is not

A candidate requires:
- One original trusted numeric 1500..6000 mm word and one trusted RCP material code (GRID, IPF, FPB, etc.).
- The **same document revision, source partition, native page and text block**, adjacent source line ordinals, and the correct 90-degree rotated or unrotated callout geometry.
- Unique one-to-one material/height pairing. Competing nearby labels or heights cannot take ownership of a repeated word.
- Exact source observation IDs, source SHA, revision, snapshot, original block/line ordinals and word boxes. Noncanonical source/view selectors abstain or fail closed.

The records are explicitly `SOURCE_TEXT_CANDIDATE_ZONE_UNRESOLVED` and carry `commercial_projection_allowed=false`, `benchmark_credit=false`. They **do not** prove an actual ceiling exists, its geometry, a finished wall's height, which room owns an RCP callout, any ceiling area or any customer takeoff row.

A supported production follow-on must cross-bind a candidate to a source-authenticated physical ceiling zone, room identity, finish definition/occurrence, and specific surface in **existing** `pb_cross_view_ceiling_finish_authority.py` and `pb_cross_view_ceiling_quantity_authority.py`. That must independently prove geometry and area. A linked wall lining additionally needs a finished-face length and physical opening deductions. No Next raw `NativeWord` or PDF text can bypass the original producer.

## Original-source results

On the owner PC, the private Maryborough original SHA-256 `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`, original p9/index8 RCP, gave **18** source-trusted material/height candidate pairs. Independent Next code also detected 18 same-bubble pairs at the exact reviewed PR head. A missing or corrupted original must never be labelled as a pass. Existing original Office GRID / Food Prep FPB customer ceiling areas remain exactly sealed as before; the 18 pairs add zero current customer m².

For 3Laurel, the Next engine reads Section A-A's 2700 mm FFL-to-FCL nominal height, and the owner explicitly approved this project's standard height unless overridden. The **original glyph-integrity pipeline p7 currently distrusts the exact 2,700/FFL/FCL words** (`text_glyph_mapping_unverified`), so this patch deliberately does not issue new source-FIRM 3Laurel wall/ceiling height from it.

## Acceptance and safety

Tests use negative same-block, wrong-line, wrong-partition, ambiguous double material/height, wrong-viewport and untrusted-word conditions, plus the actual private Maryborough original. Run existing cross-view/ceiling tests to ensure unchanged production behavior. The new method is **opt-in only**; no default customer flow changes, no benchmark denominator or truth changes, no original PDF in public Git, no signed Lot16 eight opening or Maryborough three floor records modified.

The most recent separately verified development 4-project original-app scoring packet is **33/120 (27.5%)**, but official publication is still withheld because source inventories are incomplete. This patch claims no new accuracy improvement until physical ceiling-zone/room authority is explicitly resolved and a new source-owned customer/score packet independently passes.


## Original issued ceiling region / height cross-check (follow-on)

The same draft now offers `bind_original_rcp_height_to_issued_ceiling(source=..., correspondence=...)`, exposed through `CrossViewCeilingFinishProducer.source_rcp_height_for_issued_ceiling(...)`. It **refuses** caller-made or altered ceiling correspondences: the exact `SourceCrossViewCeilingCorrespondenceRecord` instance must be retrievable from original `get_authenticated_ceiling_correspondence`, with CORROBORATED status, existing takeoff eligibility, correct revision/snapshot/source SHA, and no authority blockers. It then re-runs the current trusted original RCP text receipt collection. Exactly one pair must lie **entirely within** the already registered ceiling support region and match its finish code and printed height; all conflicting/unowned/ambiguous candidates abstain.

A positive is `AUTHENTICATED_EXISTING_CEILING_RCP_HEIGHT_SOURCE`, with explicit `physical_zone_area_reissued=false`, `wall_finish_height_authenticated=false`, `commercial_projection_allowed=false`, and `benchmark_credit=false`. This supplements the existing verified customer ceiling, never publishes a second area or blanket wall height. The region correspondence and area come from the original producer; the RCP height comes from text-integrity receipts.

A SHA-verified private Maryborough replay produced exact registered original ceiling correspondences for **Office GRID (2400 mm, existing 9.05352 m²)** and **Food Prep FPB (3000 mm, existing 13.270425 m²)**. Each matched precisely one distinct trusted RCP native block and a candidate inside its existing source region. Replaying the link returned the identical source ID. Forged `dataclasses.replace(...)` copies of the correspondence, mismatched source snapshots, nonissued objects and altered region/height/material/face claims all abstain.

**Full targeted exact-head regression: 71 passed** (real PDF source included), comprising new trusted source and registered-ceiling tests plus existing ceiling/cross-view tests. No existing quantity, signed customer receipt, material definition, RCP zone metric, frozen benchmark input or application default was modified. The next project-level improvement still requires newly authenticated **additional physical ceiling regions**, not repeated height receipts for already issued Office/Food Prep.


## Owner correction: A120-first physical ceiling-zone authority

Bryce confirmed on 12 November that the Maryborough A120 reflected ceiling plan **itself** draws ceiling material/height and zone boundaries. **A p7 closed floor-plan room ring is not a mandatory prerequisite** to authenticate an independently enclosed A120 ceiling zone. Labels within one connected, unpartitioned ceiling finish field (for example Food Service/POS or Dry Store/Wash Up/Food Prep) are sections, not automatically distinct rooms or ceilings. Source-drawn wall, ceiling finish transition, bulkhead and opening strokes own the boundary. The existing registered Office/Food Prep correspondence is one legitimate route for already issued ceilings, not the only permissible future route. A future RCP-first source geometry issuer must fail closed when a segment, inner-finished face, transition or scale/dimensions are absent.

Additional read-only original p9 Cold Room probe: the native **COLD/ROOM** label (block 59) and nearby **IP 2400** text pair (block 40) each passed the original glyph/visibility authority; another IP/2400 pair also exists elsewhere (block 39). Their vicinity contains a 15496-path RCP drawing universe including text-bubble/annotation strokes, large white-filled source rectangle paths, and actual separate line segments. An enclosing white fill or an annotation bubble cannot itself be promoted into a finished ceiling boundary. The Cold Room source mark is **not** a new physical ceiling zone or m² takeoff yet. The next step is to source-close the particular true A120 ceiling boundary and its printed dimensions, without inventing a rectangle or using the frozen gold area as geometry.


## Frozen Maryborough WC/shower source joins (GPT MAX, 12 November, original app)

A **scored** next case is the three independent `WC & SHOWER` floor and ceiling benchmark identities. The previous Cold Room text was not one of the frozen 24 Maryborough truth items; do not divert frozen-score work to Cold Room.

New opt-in original-app evidence modules:
- `pb_maryborough_wc_ceiling_source_witness.py`: three distinct D07/D08/D09 room witnesses across original A120/p9 and A500/p24. The original text-integrity producer authenticates a shared figured **2935 mm** source dimension, three separate **1620 mm** source dimension words, three individual `FT2` floor finish words, three `WC & SHOWER` room-label pairs, and three separate source `WFPB / 2400` RCP callouts. All references are source-owned observation IDs, from exactly the private original SHA and revision. **Each is a source candidate only**; the physical ceiling zone and customer quantities remain unauthenticated.
- `pb_maryborough_wc_door_ceiling_gap.py`: reuses these three original source witnesses, authenticates separate A600/p28 door-schedule rows for D07, D08, D09. In three distinct native source schedule blocks (131, 132, 133) each door is labelled `WC & SHOWER`, `SINGLE SWING`, **920 mm width** and **2040 mm leaf height**. The RCP ceiling height is 2400 mm; the source-supported arithmetic difference is **360 mm**, which makes a header possible, NOT independently proven to exist. This is a possible source-owned way to reconcile door gaps on an upper wall, not permission to draw a missing wall through an opening.
- The original three WFPB ceiling dimensions imply 2.935 × 1.620 = **4.7547 m² each** as source-schedule arithmetic. This equals existing benchmark expectation but **was not copied from benchmark truth** and is **not** yet a signed customer quantity. Any future measured area must be independently linked to physical inside faces and ceiling material zone without double counting.

**Important native paint/visibility first gate:** On original A120/p9 the three WC white-fill layout masks `d137`, `d138`, `d139` have dark source-paint candidates around all four edges. Actual dark native rectangle paths `d38`, `d109`, `d106` have original producer-authenticated source-visible edge observations. However, `d23` (south), `d100` (north) and `d112` (east) are NOT all registered as visible 4-edge source receipts, despite raw PDF dark-fill path entries. A strict create-only original wall-ring issuer therefore ABSTAINED (`original_maryborough_wc_source_visible_wall_edges_incomplete`), and its experimental code was quarantined in private diagnostics rather than added to the production PR.

A source render **must use the p9 PDF's native page rotation=90** before evaluating the painted pixels. After this correction, dark vertical dividers and south strip were raster-visible; the nominal north `d100` strip contains three repeated **white gaps** (for example original PDF unrotated x320–355, x420–450, x525–545 at y1778) corresponding to the three door/opening positions. It would be WRONG to use that dark PDF fill path's full raw bbox as a continuously painted wall. The renderer's non-visible outcome is meaningful, not a test infrastructure fault. Preserve these doorway gaps; look at genuine door-header elevations/source wall above the door before closing the ceiling-level boundary. The schedule provides source-owned 2040 mm leaf height below 2400 mm ceiling but does not alone authenticate the overhead wall/header.

Private SHA-verified three-project-page original receipt tests (p9, p24, p28): **5 passed** for three distinct rooms and three schedule rows, including invalid revision/missing source fail-closed tests. All new records explicitly `customer_quantity_allowed=false` and `benchmark_credit=false`. Unchanged original 4-project DEVELOPMENT score **33/120**, official UNPUBLISHED; any +3 ceiling or +3 floor future score needs sealed customer quantities, unique benchmark identities and a rerun, not source observations alone.

**Next original-app blocker:** source-authenticate the real upper-wall/door-header portion for D07–D09 (A500 elevations/A600 schedule) and resolve the actual p9 ceiling-level physical 4-sided zone, including finished wall face vs white mask. Once complete, issue original source `QuantityEvidence`, sealed customer rows and original evaluator identities for the three ceiling cases, while retaining the existing signed three floor areas, Office/Food Prep outputs and Lot16 eight opening areas unchanged.


## Independently authenticated D09 actual wall above the doorway (same source)

The printed **300 mm** dimension on A600/p28 D07,D08,D09 DOOR ELEVATION is **the kickplate height** at the base of the door, NOT a wall-header dimension. The actual image of that door-only elevation was inspected; never convert this annotation into a phantom 300 mm overhead partition.

Separately, **A500/p24 WC & SHOWER ELEVATION** genuinely draws a **black solid wall above the D09 door to the 2400 mm ceiling level**. Its original native PDF painted-path index **17143**, 4 source-visible rect-edge observations, is corroborated by the original `SourceVisibilityAuthority.authenticated_visible_observations` and `SourceVisibilityProducer.native_paint_facts` as fully opaque black filled real drawn geometry (unrotated PDF bbox x667.68–706.56, y1356.80–1367.36). The original D09 tag is a separately **trusted** native p24 text receipt at x821.08,y1354.27 and `2400` printed elevation height at x798.41,y1397.77. A600 door schedule independently says D09 leaf=2040 mm and single swing, with 2400 RCP ceiling.

The new original-app opt-in `pb_maryborough_wc_d09_header_source.py` source-attests **only D09** by the exact source revision/SHA/snapshot; four source-visible actual path observations, own original paint, D09 elevation label, 2400 word, corresponding independently source-owned RCP and A600 schedule receipt. Both original private-source and missing-source adversarial tests pass. The record explicitly says `other_wc_headers_authenticated=false`, `complete_physical_ceiling_zone_authenticated=false`, `customer_quantity_allowed=false` and `benchmark_credit=false` until the complete actual RCP physical 4-sided zone and figured internal wall faces are linked to original `QuantityEvidence` and a sealed customer row.

This illustrates why source paint role and *visual* confirmation are both required: A120 raw dark-fill path `d100` appears continuous in native geometry, yet the rendered physical drawing visibly has **three white doorway openings**. Conversely A500 has genuine visible black wall above D09. Neither the white mask nor the A600 kickplate can be silently used as a fabricated wall. Complete only the D09 ceiling first; expand to D07/D08 only with their own authenticated real upper-wall evidence or a documented source-owned typical-equivalence binding.
