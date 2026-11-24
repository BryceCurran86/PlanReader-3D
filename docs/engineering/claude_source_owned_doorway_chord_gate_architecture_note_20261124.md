# Source-owned doorway chords: why A110 lost them, why A500-A503 never had them (MAX item 3, chord work, P3a) - architecture note

Date: 2026-11-24 (Brisbane). Status: PROPOSAL. Nothing here is merged, pushed, posted or wired. Local branch `claude/chord-gate-measurement-20261124`, cut from main `dd356cd93`. Orders: MAX's integration note #4135 comment 7116011360 ("The candidate still has zero source-owned doorway chords. Claude's canonical-preview and chord work remains the next geometry task") and the P2 note (section 3, P3a: measure the first failing gate per door, find the `4285e133a` change); the owner said "Start P3a". Shadow only; no authority, quantity or score is touched. No repository code was changed for this note: every experiment below ran as a monkeypatch in a scratch process.

## 0. Compliance (AGENTS.md "Before proposing or changing code")

- **Read:** `AGENTS.md`; the P2 note (PR #4675, section 3 and 8); MAX's comments 7111308442 and 7116011360; the modules below.
- **Functions traced:** `pb_source_segmented_door_swing_shadow.collect_source_black_segmented_door_swings` and `propose_source_owned_doorway_chords`; in `pb_layered_wall_doorway_room_ring_shadow.py`: `build_layered_wall_doorway_room_rings` (dark-painted strip assembly and the chord call at `:2231-2310`), `_gaps`, `_gaps_containing_swing`, `_place_swings`, `_collect_merged_collinear_dark_face_strips`, `_collect_stroke_pair_strips`, `_collect_dark_painted_source_wall_strips`; the diff of `4285e133a`.
- **Authority boundaries crossed:** none raised. Chords stay topology only (`candidate_topology_doorway_closure`, `source_physical_door_host_authenticated=False`, `metric_area_issued=False`, `commercial_publishable=False`); nothing here can become a wall, opening, quantity or score.
- **Expected abstentions, predicted before any measurement:** a door with no raw wall gap on its wall line, or two competing parent gaps, still yields no chord (AGENTS.md: retain all candidates, never resolve a tie by nearest, first or smallest); a page without a segmented swing witness is byte-identical under any change proposed here.
- **Files that stay untouched by the proposal's first PR:** the proposer's 0.18 pt tolerances and gate order, `_gaps`, the merged-face collector's own rules, `pb_next_wall_ring_preview.py` (P2c), the door stack (#4638, #4649, #4654, #4655, #4665), W10, `benchmarks/frozen_holdout/full_plan_v2/**`, the 20,000 constant.

## 1. Observed repository behaviour (main dd356cd93; real originals read in place; counts only)

**1.1 The proposer's gates.** For each segmented swing witness (a quarter-turn chain of black single-line strokes with exactly one separate radial leaf line from the hinge to a chain end) `propose_source_owned_doorway_chords` applies, in order: **G0** the hinge-to-closed-tip axis is horizontal or vertical; **G1** four supports exist among the other black single-line strokes (a wall-end stroke ending at each end of the swing interval and a perpendicular jamb stroke at each end); **G2** a raw wall gap of the same orientation whose band holds the swing, that contains the interval within 0.18 pt and has at least one end within 0.18 pt of it; **G3** exactly one such parent (and the interval is not a duplicate). It never closes the raw gap itself, only the bounded chord.

**1.2 Where all 21 witnesses on the five Maryborough pages stop** (A110 12, A500 4, A501 2, A502 1, A503 2). G0 and G1 pass for 21 of 21 in every configuration; the first failing gate is always G2 or G3.

| Configuration | chords | no parent gap (G2) | two competing parents (G3) |
|---|---|---|---|
| known-good `e93dbfe2e` | 2 (A110) | 19 (10 on A110; 9 on A500-A503, none of which has any same-axis raw gap on the door's wall line) | 0 |
| current main | 0 | 21 | 0 |
| door-owned strokes hidden from the strip collectors (scratch, 1.5 below) | 5 (A110 2, A500 1, A502 1, A503 1) | 12 | 4 |

**1.3 What `4285e133a` changed, and only that.** On A110 the first bad commit raises the strip count from 118 to 559 and loses both chords (bisect, same producer and page, cap bypassed in the old trees). On current main, with ONLY `_collect_merged_collinear_dark_face_strips` (the collector that commit added) switched off, A110 returns to exactly 118 strips, 10 rings, 14 closures, 153 raw gaps and 2 chords (current: 475 strips, 175 rings, 28 closures, 428 raw gaps, 0 chords), and A500, A501, A502 and A503 return to the known-good strip counts (92, 66, 51, 79). The raw gaps at the proposal grow from 153 to 428 (A110), 105 to 322 (A500), 60 to 213, 51 to 182 and 81 to 251.

**1.4 The mechanism: door symbol ink becomes wall ink.** The two A110 doors that had chords now have a raw gap that STILL starts exactly at the door's near end (0.00 pt) but ends 2.40 and 0.60 pt SHORT of the far end; before, those gaps ran 1,286 and 1,200 pt beyond the far end. The proposer needs the interval inside the gap within 0.18 pt, so G2 fails. For each strip the layered ring builds, the strips that contain a witness's OWN native paths (its radial leaf and the collinear jamb support stroke it touches) are: on A110, one 1.2 pt strip from the merged-face collector in 12 of 12 witnesses (2 to 3 paths, longer than 40 pt, centred on the stroke, so it reaches 0.6 pt into the interval from the hinge end), plus a 2.16 to 2.64 pt stroke-pair strip in 3 of 12; on A500, a 1.2 pt merged-face strip and a 4.56 pt stroke-pair strip in 4 of 4 (on A500 the 4.56 pt shortfall disappears when those strokes are hidden, 1.5 below). The leaf is collinear with the hinge-side jamb line, so the "collinear dash" merge (gap up to 4 pt, span at least 40 pt) reads door ink as a wall face. Nothing about the 0.18 pt tolerance is wrong.

**1.5 Counterfactual (scratch only).** With the native paths owned by a witness hidden from the merged-face and stroke-pair collectors (everything else unchanged, the merged-face collector still on): chords A110 0 to 2, A500 0 to 1, A501 0, A502 0 to 1, A503 0 to 1; strips 475 to 461, 339 to 331, 254 to 251, 212 to 210, 309 to 308; closures 28 to 23, 13 to 13, 6 to 7, 4 to 4, 6 to 5. A500, A502 and A503 had NO chord at the known-good commit either, so these are new real chords. 4 doors then show two competing parents (retained as ambiguity, not resolved) and 12 still have no parent gap (for example a door whose wall line has no raw gap at all, or an A501 pair strip of non-witness strokes that still cuts the gap end by 4.56 pt: a second layer this does not touch).

**1.6 Blast radius.** Over 61 PDFs and 861 local pages only 6 pages carry any segmented witness (Maryborough 5, one public sample page with 7). The public page is unchanged by the counterfactual (384 strips, 109 rings, 0 chords, 14 closures before and after). Every other page has no witness, so a change keyed on witness-owned paths cannot touch it.

## 2. Inference

1. The chord loss on A110 is a role error, not a tolerance error: a source-bound door swing (chain plus unique leaf) owns its strokes, and the dark-painted collectors let those strokes mint thin wall strips that bite into the very gap the chord needs. Two counterfactuals agree (collector off restores the known-good shape; door-owned strokes hidden restores the chords).
2. Loosening G2 to 5 pt would "fix" these pages and would be tuned to them; it would also accept coincidences. The 0.18 pt rule stays.
3. The measurement is already decisive for the mechanism, so the small, principled fix (door-owned strokes do not mint wall strips) is worth proposing now; the per-door gate receipts remain valuable as the regression and review tool.
4. Even with the fix 16 of 21 witnesses have no chord: no raw gap on the wall line (the dominant class), two competing parents, or a non-witness strip at the door end. Those are separate questions and stay abstentions.
5. Real chords in the layered builder do not appear in the canonical preview until P2c wires the producers into `pb_next_wall_ring_preview`; the fix is therefore the first of two steps toward MAX's "real doorway chords in the bounded preview".

## 3. Proposed change (shadow, no new authority)

**P3b, the fix (small PR, `pb_layered_wall_doorway_room_ring_shadow.py` only).** In the dark-painted path, compute the segmented swing witnesses once, before the strip collectors, and give every line-based strip collector of the strip assembly (merged-face, stroke-pair, and the opt-in wall-end closure and heavy-stroke collectors) a view of the rows in which the witness-owned native paths are inert (same indices, same length, no renumbering); the door detection and the chord proposer keep reading the full rows. Witness-free pages get the same list contents, so their results are byte-identical. No tolerance, no new vocabulary, no change to `_gaps`.

**P3a, measurement receipts (separate PR, measurement-only).** `diagnose_source_owned_doorway_chord_gates(drawings, witnesses, gaps)` in `pb_source_segmented_door_swing_shadow.py` returns one receipt per witness: axis result, the four support counts and path ids, the same-axis gap candidates on the wall line with signed end misses and containment, the parent count and whether two parents are one geometry or competing, the first failing gate, and `chord_proposed` (flags false, `measurement_only`). It does not change the proposer. A read-only tool (`tools/diag_source_door_chord_gates.py`, counts and offsets only) spies on the proposal call and adds the strip attribution used above (which collector's strips own a witness's paths and how far they reach into the interval).

**P2c (after P3b).** Default-off producers and a chord-carrying merge in the viewport-aware preview builder, as in the P2 note.

## 4. Tests

**P3b (synthetic, no private data):** a door whose jamb and radial leaf are collinear: old code leaves the raw gap 0.6 pt short and proposes no chord, new code proposes it; the witness-owned rows are inert in the collectors' view but the proposer still reads them; look-alike negatives (a wall stroke with the same geometry but a different native path index is NOT excluded; a swing without a unique leaf is not a witness and excludes nothing; green ink and original indices untouched); witness-free inputs give identical strips and results (differential against a verbatim copy of the old assembly on seeded fuzz); translation, 90 degree rotation, unrelated-content and input-order invariance; no mutation of the rows; deterministic replay; the P1 structural count unchanged; single-line mutants (the exclusion, the index set, each collector call site, the inert-row shape).

**P3a (synthetic):** one scene per gate (axis ambiguous; each support missing; no same-axis gap; gap shorter or longer than the interval; end miss at 0.18 and 0.19 pt; two competing parents; duplicate interval); the receipts' `chord_proposed` set equals the proposer's output on seeded fuzz; translation and 90 degree rotation invariance; no mutation; mutants.

## 5. Benchmark observations that must not influence the implementation

The page numbers, the strip, gap and chord counts, the 0.60, 2.40 and 4.56 pt offsets and the thicknesses 1.2 and 4.56 are observations on the Maryborough original, used only to verify. No threshold, count, page index or sheet name enters code; ownership is by native path index from a source-bound witness.

## 6. Decisions

D1 order and split: P3b first as its own small PR, then P3a, then P2c (recommended), or P3a first as asked. D2 scope of the exclusion: every line-based strip collector of the dark-painted block (recommended), or only the two the counterfactual used. D3 native-curve doors (`_swing_arcs` records a `leaf` index) get the same ownership rule later, not in P3b. D4 competing parents stay abstentions (AGENTS.md ties rule) and are exported typed by P3a. D5 `_lining_face_wall_strips(all_ink=True)` also sees door strokes: measure before changing. D6 the five open door-stack PRs edit the same module in other hunks: run `git merge-tree` against their heads before building.

## 7. Not claimed or not run

The owner-local release path (signed Lot16 and Maryborough retention) and the frozen four-project score were not run, and nothing here is a score. The experiments are monkeypatches in scratch processes; no repository file changed. The counterfactual covers 6 pages with witnesses; no page without a witness was run (unchanged by construction). Rings and closure counts are not an accuracy score and no ground truth is used.
