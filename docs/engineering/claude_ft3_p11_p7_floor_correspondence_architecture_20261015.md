# FT3 page-11 -> page-7 floor correspondence: architecture report (shadow, no authority)

**Read-only. Nothing is published: no material occurrence, floor finish, quantity, scale, customer row or benchmark identity.**
**Authority level: CANDIDATE relationship evidence. Unique authenticated wall/face equivalence is NOT established (see section 1 and 3.4).**
Evidence tool: `tools/diag_ft3_p11_p7_floor_correspondence.py` (25 synthetic tests, exact-head CI replay with Tesseract).
Stop for review per AGENTS.md; no production file is changed in this PR.

## 0. Compliance block

- **Read:** `AGENTS.md`; `docs/AI_ENGINEERING_PLAYBOOK.md` (§5-7, §11-13); engineering reports
  `gpt1_maryborough_ft3_page11_source_scope_firstfailure`, `gpt2_maryborough_source_room_handoff`,
  `gptmax_source_owned_physical_plan_view`, `gptmax_source_plan_material_occurrences` (main `e1ca1c23`).
- **Traced:** `collect_live_physical_net_wall_claim` -> `CrossViewRoomAreaProducer.publish` (metadata
  `source_dimension_box_pdf_pts`, `pb_cross_view_room_area_authority.py:1906`) -> `CrossViewFloorFinishProducer.publish`
  (`_dimension_box` :176, occurrence-fully-in-box :915, `len(candidates) > 1` = conflict :943, label fallback :957);
  `PhysicalWallCandidateProducer.from_authenticated_viewports` / `resolve_scope`; `build_source_room_face_authority`;
  `_fully_grid_opposed_wall_evidence`; `pb_cross_sheet_registration_authority` (callout-based plan/elevation links, **not**
  geometric); `pb_source_grid_registration_shadow` (#2708, construction-grid census).
- **Authority boundaries crossed:** none raised. W4 candidate geometry and the already-FIRM room-area evidence are consumed
  read-only. The new object is *relationship evidence*, shadow only.
- **Untouched:** every production module, W10 flags, scale resolvers, the quantity schema, and all benchmark/frozen files
  (not opened; their FT3 expectations did not influence any step).

## 1. Result

**OFFICE is the only measured floor whose page-11 FT3 mark is geometrically owned, uniquely, at CANDIDATE tier.** The page-11 FT3 plan mark at
(327.8, 1437.5) lies 54.8 pt inside the page-11 dimension box that measures the OFFICE floor; under the wall-derived registration
T = (-78.0, 0.0) that box is a wall-bounded rectangle on **both** sheets (identical wall evidence, one registered door opening) and holds
no other finish code. The diagnostic never reports `corroborated`: the wall evidence is W4 *candidate* geometry (p7 viewport scope
`scope_complete=False`, box-side primitives shared by several candidates or owned by none), page 11 has no source-owned room-face or label
authority (it is not a topology page; #2726 is open) and no physical-wall-equivalence authority resolves the box sides. A grid or wall-derived
translation is a candidate; it does not by itself prove the same physical room. The geometric ownership record, ready for the authenticated
gates to consume, is (identifiers from the exact-head CI replay, which has Tesseract; a machine without it derives different quantity ids):

| field | value |
|---|---|
| canonical floor / physical surface | `physical_room_floor_surface_980b1ad9cbaebb3cc41351623718270e` |
| physical room / source face record | `live_physical_room_9eea8a328d9da55c19258c05c282c88c` / `source_room_face_record_735f9b309cca70f513c9fcd9390e3e10` |
| measured area (existing FIRM evidence) | 9.05352 m2: room-area `qty_29e71bd466a9e5fa1783`, floor-area reissue `floor_area_quantity_8bcdc01455538a6a105a`, area evidence `cross_view_room_area_4cf27c55d27af1646c2d78f76ee66fa5` |
| FT3 occurrence (candidate, not authenticated) | p11 native word `(112,0,0)`, bbox `[321.157, 1429.586, 334.402, 1445.359]` |
| registration | identity, scale 1, T = (-78.0, 0.0); 22,338 pt support, 3.66x over the best competitor, 131x over null; independent grid shadow agrees |

**Cannot be bound (and why), per mark:** see section 3.4. FOOD PREP's box holds one FT3 mark but is an open-plan measurement rectangle
(two sides lie on grid/dimension lines); COLD ROOM is wall-bounded but its mark is EPX; the FT3 marks at DRY STORE, WASH UP and FOOD SERVICE lie
outside every measured box. **Quantity production is still blocked upstream and is not attempted:** the FT3 definition authenticates 21/24 words
and mark occurrences are withheld (#2719, #2724/#2728 glyph analysis); this report closes only the geometric floor-identity candidate.

## 2. Observed repository behavior

1. `CrossViewRoomAreaProducer` already gives each measured floor a **dimension box on the support page** (page 11):
   the two figured-dimension systems' extents, e.g. OFFICE `[251.04, 1382.72, 394.80, 1585.04]` (2536 x 3570 mm = 9.05352 m2).
   Its identity to the page-7 room rests on the *label* (same trusted label line inside/next to the dimension pair).
2. The live page-7 floor object is only the label's tile-grid **cell** (`metric_geometry_complete=False`; OFFICE: 33.9 x 33.9 pt),
   not the room. 683 live floors, one FIRM measured locally (three in CI: FOOD PREP, OFFICE, COLD ROOM).
3. `CrossViewFloorFinishProducer` (dimension-box mode) binds a material occurrence that lies fully inside that box. Two occurrences
   in one box are a conflict even when they carry the same code; nothing checks that the box is a physical room.
4. Upstream gates are still closed on main: FT3 definition authenticates 21/24 words (#2719 report); the plan view
   `floor_finish_plan` `(251.52, 471.20, 1195.44, 1946.48)` exists in shadow (#2716); mark occurrences are withheld until the definition closes.
5. GPT1's grid shadow (#2708) independently reports a native vector construction-grid translation of `(78.0, 0.0)`.

## 3. Evidence (original source SHA `b1be5353...e007`, pages 7 and 11)

### 3.1 Registration (page 11 -> page 7), from wall geometry only

Evidence per page = source primitives of the production W4 wall candidates minus candidates whose every edge carries the producer's
own typed `KIND_GRID` opposition (p7 viewport scope: 195 of 3,467 excluded; p11 page scope: 110 of 1,412). Score = two-axis minimum of
split-invariant collinear interval overlap (coordinate tolerance 0.06 pt), every D4 orientation and scales 0.5-2 retained.

| hypothesis (p11 -> p7) | min-axis support | note |
|---|---|---|
| **identity, scale 1, T = (-78.0, 0.0)** | **22,338 pt** | winner; 18 % of p11 non-grid wall line-work |
| identity, next distinct translation (-43.92, 0.0) | 6,096 pt (3.66x lower) | one tile-pitch alias |
| mirror_x / mirror_y / rot180 | 4,774 / 4,331 / 4,101 pt | |
| rot90 / rot270 / transposes | <= 2,582 pt | |
| non-unit scales 0.5 / 0.75 / 1.25 / 2.0 | <= 1,909 pt | |
| sheet-frame alignment (0, 0) | 201 pt | |
| random translations (300, seeded) | max 171 pt | winner is 131x the null maximum |

Independent cross-check: #2708's native vector construction-grid candidate is `(78.0, 0.0)`. Local windows (R = 260 pt) around each of the five
plan marks all choose the same translation (support 783 pt at the weakest, a periodic-dominated window, to 4,720 pt); the schedule/legend
FT3 cell has no support at it (156 pt; best local translation unrelated) and the plan marks lie inside #2716's authenticated plan view while
that cell does not.

### 3.2 Marks (original native words, block/line/word addresses from `TEXTFLAGS_WORDS`)

Five plan FT3 marks `(112,0,0) (112,1,0) (112,2,0) (113,0,0) (114,0,0)` at p11 centres (327.8, 1437.5), (324.4, 1022.3), (316.3, 622.9),
(586.7, 642.8), (737.0, 508.0); the sixth, `(262,0,0)` at (1383.4, 2205.6), is the schedule cell and is unregistered. Page 7 carries no FT text.

### 3.3 Measured floors (existing FIRM documented-dimension areas; boxes are the room-area evidence's `source_dimension_box_pdf_pts`)

| floor (box on p11, native pt) | side wall evidence p11 / p7 (face coverage) | wall-bounded both sheets | finish marks in box | outcome |
|---|---|---|---|---|
| OFFICE `[251.04, 1382.72, 394.80, 1585.04]` | x0 1.00/1.00, x1 .995/1.00, y1 .997/1.00, y0 .578/.578 (door, IoU 1.0) | yes, identical | FT3 x1 (margin 54.8) | **candidate owner** |
| FOOD PREP `[483.12, 578.48, 678.48, 811.04]` | x0 .98/.98 and y1 .98/.98 are walls; y0 1.00/1.00 but no second face; x1 0.00/0.71 | **no** | FT3 x1 (64.4) | ABSTAINED: open plan |
| COLD ROOM `[442.32, 811.04, 666.24, 1175.12]` | four wall sides; x1 .90/1.00 (differs between sheets) | yes, not identical | EPX x1 (93.4) | ABSTAINED: other finish code |

All three rows are from the exact-head CI replay of head `22d408dd` (Tesseract present; run 38629073071, artifact `claude-ft3-p11-p7-floor-correspondence`).
The boxes are the room-area evidence's own `source_dimension_box_pdf_pts`; they equal the native dimension endpoints of the same figured dimensions
(2536 x 3570, 4025 x 3297 and 6425 x 3950 mm are exactly the documented areas).

OFFICE in detail (`canonical_floor_id physical_room_floor_surface_980b1ad9cbaebb3cc41351623718270e`, room-area quantity
`qty_29e71bd466a9e5fa1783`, floor-area reissue `floor_area_quantity_8bcdc01455538a6a105a`, area evidence
`cross_view_room_area_4cf27c55d27af1646c2d78f76ee66fa5`, face record `source_room_face_record_735f9b30...`): box
`[251.04, 1382.72, 394.80, 1585.04]` on p11 maps to `[173.04, 1382.72, 316.80, 1585.04]` on p7. Each side is a wall face on **both** sheets
(coverage 99.5-100 %, a parallel second face 4.3-6.5 pt away) except one side with a door opening covered 57.8 % on **both** sheets
with identical intervals (IoU 1.0). Inside the box: one room label, one finish mark (FT3, margin 54.8 pt), no other finish code;
placing the same box at the frame-aligned or alias translation fails the wall test on two sides.

The original OFFICE two-sheet overlay is retained privately with the owner-supplied plan; source-native dimension and geometry evidence remains described in this report.

### 3.4 Why each FT3 mark cannot yet be bound (all alternatives retained)

| mark (p11 centre) | inside a measured box | p11 face holding it -> p7 faces at T (IoU) | first blocker |
|---|---|---|---|
| (327.8, 1437.5) | OFFICE | tile cell 1,161 pt2 -> p7 cell .993 (one other overlap .004) | candidate only (below); the measured floor object is the *neighbouring label cell*, so no face-level join exists: only the dimension box relates mark and floor |
| (324.4, 1022.3) | none | cell -> cell .993 | outside every measured box (DRY STORE has no source ring) |
| (316.3, 622.9) | none | no exact p7 face (best .79, three other overlaps) | outside every measured box; WASH UP ink has opposing grid sources (GPT2 P3) |
| (586.7, 642.8) | FOOD PREP | cell -> cell .992 | box not wall-bounded (open plan); the WASH UP and FOOD SERVICE marks sit in the same open region |
| (737.0, 508.0) | none | cell vs a 70,255 pt2 p7 face (.016) | outside every measured box; the p7 face is a large unclosed region |
| (1383.4, 2205.6) schedule cell | n/a | no face | unregistered region |

Face-level equivalence is not identity evidence here: 475 of 992 published p11 faces have a p7 face at IoU >= 0.98 under T, and they are tile-grid
cells (periodic; a one-pitch alias is equally "exact"). The wall-derived registration is a candidate, and OFFICE's box is a *consistent* candidate, not an
authenticated equivalence, because:

- **W4 ownership behind the OFFICE box sides is not unique.** p7 viewport scope (`scope_complete=False`): x0 has 3 primitives (1 unowned, 1 claimed by
  several candidates, 8 distinct candidates), x1 3 primitives owned by one candidate, y0 5 primitives (3 unowned), y1 4 (2 unowned, 1 shared). p11 page scope
  (complete): x0 and y1 each have a primitive claimed by two candidates, y0 has one unowned primitive. No claimant is grid-opposed.
- Page 11 is not a topology page: no source-owned room face, label or W4 wall authority is published for it (GPT2 #2726 is the open seam).
- No physical-wall-equivalence authority resolves these W4 candidates (the live claim itself reports `ambiguous_physical_wall_equivalence_for_host`).
- FT3 definition (21/24 words) and mark occurrences are not authenticated.

Caveat: the p7 W4 viewport scope is `scope_complete=False` (cropped at the viewport boundary, ambiguous primitive ownership). Its candidates are used
only for geometric coincidence, never for completeness.


### 3.5 Independent cross-checks received (GPT2 #2731 / #2743, original-source shadow census, 2026-10-14)

Reported by GPT2 from artifact 11930473701 of its original-source run (not reproduced by me; the arithmetic below is):

- Page 11 has one authentic F07 `FLOOR_FINISH_PLAN` viewport, 890 W4 candidates and a read-only shadow census of 1,238 planar face candidates
  (1,235 with unique W4 edge owners), but production `SourceRoomFace` publishes **zero** closed physical faces
  (`source_room_face_boundary_unresolved`). Raw shadow faces are not construction rooms.
- The largest uniquely edge-owned raw face is 20,058.76 PDF pt2. The OFFICE dimension box `[251.04, 1382.72, 394.80, 1585.04]` encloses
  143.76 x 202.32 = **29,085.52 pt2** (recomputed), so **no single raw tile-grid face can be the OFFICE floor**. A composite of several cells is
  not ruled out, but it needs true physical separators, a complete native room ring and a uniquely owned label / finish mark, none of which
  exists on page 11 today.
- The OFFICE box west edge x = 251.04 lies 0.48 pt outside the authenticated F07 viewport left edge x = 251.52. The viewport extent is
  source-certified and is **not** adjusted here: this report neither enlarges the viewport nor uses viewport bounds as evidence, and the
  box is used only as the extent of the figured-dimension systems (section 3.3). Whether the 0.48 pt is a source-frame crop is a question for the
  viewport owner, not something this diagnostic may settle.

**What this report does and does not claim (restated at GPT2's request):** it claims a geometric, wall-derived, CANDIDATE-tier correspondence
for OFFICE only. It does **not** claim a source-sealed unique OFFICE FT3 floor identity, any FT3 quantity, physical-wall equivalence
authority or a measured finish area; the diagnostic never emits `corroborated` and reports
`authenticated_physical_wall_face_equivalence: False` with the authority blockers listed in 3.4.

## 4. Inference

- A bare affine transfer (rejected by GPT1 and by the floor-finish authority) is not what is proved: the transform is *derived* from
  wall evidence, and the correspondence claim is made per measured box on **both** sheets (wall faces + second face behind them,
  identical covered intervals including the registered door opening).
- The dimension box is the measured floor. Its wall-boundedness decides whether "box area == tiled floor area" is physically meaningful.
  An open-plan box (two sides on grid/dimension lines) is a measurement rectangle, not a floor.
- Label text, tile-grid cells and union-find over grid adjacency are **not** usable for this: grid adjacency over-merges rooms
  (the OFFICE "component" spans the sheet), and tile-grid support is periodic (alias translations keep 49 % of the best score before
  typed grid evidence is excluded, 27 % after).

## 5. Proposed change (shadow first; not implemented here)

New sibling of `pb_source_grid_registration_shadow` / `pb_source_figured_plan_plane_shadow`:
`pb_source_cross_view_floor_correspondence_shadow.py`, consuming producer-owned objects only (`SourceVisibilityProducer`, W4 scopes with
typed evidence, `CrossViewRoomAreaResult`, `LiveCanonicalFloorSurfaceComposition`); returns frozen records with `stable_contract_id`,
`EvidenceResolutionStatus`, reason codes, every retained hypothesis, `commercial_projection_allowed=False`, `takeoff_eligible=False`.
Gates: (G1) exact lineage both pages; (G2) one rigid registration, margin and null separation, local consistency at each mark;
(G3) box wall-bounded on both sheets with identical wall evidence; (G4) exactly one finish code in the box and every mark inside a registered
region and inside the authenticated plan view; (G5) no overlapping measured box. Consumption by `CrossViewFloorFinishProducer`
(as a veto on dimension-box binding) is a **separate authority-promotion review**; this change alters no commercial output.

## 6. Competing interpretations (all retained, typed)

| # | interpretation | evidence against / for | disposition |
|---|---|---|---|
| C1 | registration = sheet-frame alignment (0, 0) | support 201 pt (111x lower); box test fails on two sides | rejected, retained |
| C2 | registration = tile-pitch alias (-43.92, 0) / (-78, 136.08) | 6,096 / 2,587 pt; box test fails | rejected, retained |
| C3 | mirror, rotation, transpose, non-unit scale | <= 4,774 pt | rejected, retained |
| C4 | the OFFICE mark belongs to the neighbouring room | mark is 54.8 pt inside the wall-bounded OFFICE box | rejected |
| C5 | FT3 marks at DRY STORE / WASH UP / FOOD SERVICE belong to measured floors | none lies in a measured box | unowned (no measured floor): abstain |
| C6 | FOOD PREP owns its FT3 mark and area | box not wall-bounded; WASH UP and FOOD SERVICE marks sit in the same open region | abstain |
| C7 | COLD ROOM owns FT3 | box holds EPX only | not FT3 |
| C8 | existing dimension-box binding (no registration) | would also bind FOOD PREP (one FT3 in its box): two FT3 floors | geometry supports one |
| C9 | label equality (OFFICE) as identity | agrees, but is not an input | corroboration only |
| C10 | FT1 mark at p11 (935.5, 1081.1) | not in a registered region | no registration-based ownership |

## 7. Required tests (before the shadow module; the diagnostic already carries the pure-geometry subset)

Synthetic positives; look-alike negatives (periodic grid, open-plan box, wrong registration); ambiguity/conflict (repeated rooms,
competing codes, overlapping boxes); translation/rotation/scale metamorphic; input-order and segment-splitting invariance;
unrelated-content and viewport-expansion invariance; deterministic replay and stable IDs; no-mutation; proof that live predictions and
commercial quantities are unchanged with the shadow present. 25 tests of these exist for the diagnostic's geometry; stable-ID and
live-unchanged proofs belong to the module PR.

## 8. Benchmark observations that must not influence implementation

The frozen reference contains FT3 floor-finish objects; this work never opened them. Areas quoted above are production-measured
documented-dimension values, not expectations, and select nothing. `--finish-codes` is a reporting filter in the diagnostic; the
module must take codes from authenticated schedule definitions.

## 9. Decisions requested at review

1. Approve the shadow module name/location and gates G1-G5; the numeric parameters in the diagnostic (side coverage 0.95/0.50, wall band 3-15 pt,
   3x registration margin, 20x null margin, 5 pt mark margin) are diagnostic values and need independent derivation before they become gates.
2. Confirm that the cross-view dimension box is the floor extent for this proof (the live floor object is a tile-grid cell), rather than requiring
   completed W5 faces (union-find over grid adjacency over-merges and is rejected).
3. Decide the rule for several same-code occurrences in one box (today: conflict) once the correspondence exists.
4. Require two-source agreement of the registration (wall-derived here, grid shadow #2708) in the module.
5. The veto on `CrossViewFloorFinishProducer` dimension-box binding is a separate authority-promotion review; it would change FOOD PREP
   from bindable to abstained, and no commercial output changes before that review.
6. Upstream gates (FT3 definition 21/24 words; occurrence scope) stay with their owners; ownership here is ready for them.
