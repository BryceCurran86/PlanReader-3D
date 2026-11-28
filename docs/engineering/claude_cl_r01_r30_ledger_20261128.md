# Claude register CL-R01–R30 (#4764 7235069043, corrected by 7235118617): ledger, 28 Nov 2026

A closure inventory, not a new backlog: earlier work is carried forward and only the remaining delta is pursued.
Categories: **proven** (checked on originals) · **validation** (built; shadow, report, opt-in or synthetic, or partly
checked) · **failed** (candidate failed its checks) · **missing** (no working implementation) · **release** (done, waiting
for merge). "main" = already on main; "#4810" = on Claude's draft only. Nothing new is merged and no new verified
benchmark match is claimed. Earlier detail: `claude_c01_c30_ledger_20261127.md`.

| item | from | category | evidence | remaining delta |
| --- | --- | --- | --- | --- |
| R01 C03 default off | C03 | proven | #4810 `c216571f6`: W2 Lot16/Maryborough and full page byte-identical to main (7235084128) | none unless a relevant change |
| R02 face-aware W2 snap | new | failed | `order-free-snap-1.1.0` (`4fc2d178d`): Lot16 named rooms kept, shuffle invariant; Maryborough sheet 7 gives no rooms | find the first face-ownership gate that fails sheet 7 |
| R03 cold room / false sales cell | new | validation (trace) | self-intersecting ring under the snap; area on a floor-grid cell (7234165306) | fix after R02 |
| R04 finish edges on wall ink | C05/C08 | validation | `pb_finish_face_wall_support_shadow` (#4810) rejects the Office/Food Prep/Sales cells; report-only panel candidate; C05 guard (#4810, off) | cold-room ring runs on outer faces (R07) before any veto; signed rows |
| R05 Office doorway | C08 | validation | `door_jamb_returns` (main, #4763) closes the real Office (92% wall support); union shadow (#4810) keeps WSH/DRY | MAX: is the ring builder the surface source for finish rows |
| R06 Food Prep open plan | C22 | missing (boundary) | the open-plan module only audits; no ring holds the label | threshold and finish-extent evidence from AG (finishes plan) |
| R07 inside-face rings and ids | C06–C08 | validation | ring builder gives Cold Room, Freezer and Office inside-face rings (28 Nov); report-only label-to-ring record `pb_labelled_ring_ownership_shadow` for AG/MAX; ring-wall identity map (#4810); viewport wall links (main #4780, off) | panel walls (MAX); edge-to-wall links without choosing |
| R08 source-lineage identity | new | validation | `pb_wall_lineage_identity_shadow` (#4810); offline: whole chains not enough for hosts; report-only host identity from the pieces at the opening (`c137a06c3`, synthetic) | measure on originals; MAX's decision before any use |
| R09 viewport crossing | C04 | validation | crossing primitives are left out of a viewport scope with a receipt, not clipped (main) | census of wall-like crossings on originals before any clip |
| R10 external footprint first | C09 | validation | footprint-first traces in the live claim, inside-face envelope (main `e1cbd4cb5`, #4549); edge support (main #4650, off) | original proof across plan styles |
| R11 garage closure | C10 | validation | `pb_source_garage_door_footprint_continuity` and envelope (main) | original proof |
| R12 party walls | C11 | validation | dual-dwelling and shared-envelope shadows (main `e18553a1c`) | no dual-dwelling original proven |
| R13 true junctions | C12 | validation | `crossing_wall_negative_shadow` (#4810, off) | originals before/after, signed rows |
| R14 doorway closure | C13 | validation | doorway chords (main #4772/#4773, off), jamb returns (#4763), topology closures (main `5eaffeadb`) | authenticated thresholds on originals |
| R15 angled/mirrored doors | C14 | validation | `angled_opening_precision_shadow` (#4810, off); originals additive only | signed parity; two Maryborough candidates unproven |
| R16 cavity sliders and robes | C15 | validation | cavity slider jamb shadows and internal door census (main `353902bbb`, #4637/#4639), used by the preview and door review; 77 tests pass (28 Nov) | reads explicit internal-wall layer names only; originals without them abstain |
| R17 exterior window hosts | C16 | validation | window footprint continuity and external opening census (main `e0130c180`) | sill/head handoff from AG |
| R18 corner stacker and external doors | C17 | missing (donor) | stacker readiness shadow (main); draft #4751 (MAX branch: 7 production lines re-applying the #4522 corner-frame change) not merged | MAX to say who ports it (host/frame also listed in MAX's lane); an unreviewed corner-terminated host shadow is on `claude/3laurel-slider-host-corner-report-20261109` |
| R19 3Laurel openings | C18 | missing (binding) | door donor A on main (#4639); piece B (in-swing figured width, shadow) recovered into #4810 (28 Nov); piece C's single-host nomination withdrawn (two-wall rule), its read-only receipt gate diagnostics (C') ported (28 Nov); D waits (layer name), E needs promotion review | 18 internal items unbound; open draft #4665 (two-wall door tags and row compiler) merges cleanly into #4810, MAX to say whether to consolidate it |
| R20 opening widths and heights | C19 | validation | figured-label opening quantities (live); schedule binding (#4810 C01) | schedule/elevation reconciliation with AG |
| R21 jamb caps and returns | C20 | validation | `jamb_caps_must_be_wall_ends` and returns (main #4763, off) | originals positives/negatives |
| R22 Lot16 stub candidates | C21 | proven (diagnostic) / validation (retention) | one rule explains 125 → 189; contested candidates now retained for audit (`visible_contested_candidate_groups`, synthetic) | read them on the originals |
| R23 Lot16 raster wall lineage | C26 | validation | paint classifier (#4810); 28 Nov: WC and LINEN walls are raster only, 48–63% picture ink, rest mixed, none vector ink | picture-side lineage is the only lineage; no native path ids to claim |
| R24 holes and exclusions | C23 | validation | `pb_room_face_hole_report_shadow` (#4810) | classify with AG semantics |
| R25 Q5446 finished faces | C24 | validation | finished interior face recovery shadow (main `a05df3bb5`) | BATH/LIVING on the original |
| R26 curved and stepped walls | C25 | validation | skew/curve hardening of footprints (main `74d5db2d9`); report-only paired-arc detector `pb_curved_wall_pair_shadow` (28 Nov, synthetic; three plan sheets: no pairs) | an original with a curved wall; polyline curves; no wall candidacy yet |
| R27 picture/vector corroboration | C26 | failed | picture detection changes identities; Maryborough areas moved (7232754709) | stays off |
| R28 donors and preview wiring | C27/C28 | validation | donor audit; preview chord wiring (main #4772/#4773), piece cache and review recalculation (#4810); 28 Nov branch sweep: door stack is open #4665 | MAX wires the app callback; #4665 decision |
| R29 geometry runtime | C29 | release | speed work on #4810: four originals 2101 → 1624 s, all outputs identical, memory at or below main | merge |
| R30 consolidated #4810 | C30 | release (pending) | #4810 draft | combined release with MAX |
