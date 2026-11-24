# Why wall rings do not close in the canonical bounded preview: a ring-leak census (MAX item 3 follow-on, P4) - architecture note

Date: 2026-11-25 (Brisbane). Status: PROPOSAL, then BUILT as P4a (section 8). Sections 0-7 are the proposal as reviewed; section 8 says what was built. Local branch `claude/ring-leak-census-note-20261125`, cut from main `373ab1d21`. Orders: the owner's question "so what's blocking our room boundaries" and "Yes, start it" (the census proposed in the answer to it); MAX's #4135 comment 7140464704 ("Claude owns wall, room-ring and installed-opening geometry"). It follows the P2c note, which found that the canonical preview calls a fork of the ring builder. Shadow only. No repository code was changed for this note: every measurement ran as a monkeypatch in a scratch process on the owner-local originals and prints counts and lengths only.

## 0. Compliance (AGENTS.md "Before proposing or changing code")

- **Read:** `AGENTS.md`; `docs/AI_ENGINEERING_PLAYBOOK.md` (section 7 duplicate paths, 8 abstention points, 9 required tests, 11 safe homes, 13 priority 6 "stage-wise accuracy and abstention metrics"); the P2c and P3a notes; #4683, #4686, #4694; MAX's #4135 comments 7116011360, 7135679588 and 7140464704.
- **Functions traced** (`pb_next_wall_ring_preview.py`, main `373ab1d21`): `build_layered_wall_doorway_room_rings` (strip assembly `:2335-2368`, domain `:2372-2374`, `_gaps` `:1288`, swing arcs and placement `:2430-2470`, `_place_swings` `:1407`, closure owners `:2501-2625`, free space and rings `:2626-2714`), `_stroke_closed` `:1440`, `_jamb_cap_closed` `:1480`, `_polygon_parts` `:2109`, and the open-gap veto it imports from the layered module (`_unresolved_collinear_gap_breaches_outer_ring`, `pb_layered_wall_doorway_room_ring_shadow.py:2102`); the canonical call in `pb_new_source_trace_preview.py:297-323`; the layered builder's own result for the reference counts.
- **Authority boundaries crossed:** none raised. Rings stay candidate topology (no room, area, opening, host or quantity authority). The playbook's single-room-graph rule (section 7: W5 is the room-face source) is untouched: the census reads the existing ring result and adds no graph, resolver or vocabulary.
- **Expected abstentions, stated from the code before the batches ran:** a region with no wall evidence yields no ring and no reason; an unresolved collinear gap marks a ring ABSTAINED only when both its ends meet that ring's outer boundary; every other unresolved gap is invisible in the ring list.
- **Files that stay untouched:** both ring builders, the preview, all closure gates, the segmented-swing producers and the proposer, W2-W10, `benchmarks/frozen_holdout/full_plan_v2/**`, `documents/sources/*.pdf`, the door stack (#4638, #4649, #4654, #4655, #4665) and the open chord PRs (#4683, #4686, #4694).

## 1. Observed repository behaviour (main `373ab1d21`; originals read in place; counts only)

**1.1 How the preview's builder turns wall evidence into rings, and where it loses them.**

- The wall strips and the non-strip wall fills are united; `domain = union.envelope.buffer(1.0)` (`:2372-2374`). "Outside" is therefore whatever free space reaches the envelope of the wall evidence; it is a function of the strips, not of the page or the viewport.
- `_gaps` (`:1288`) returns the maximal bounded interruptions of every wall band: from a wall run's free end, the free part of the band that is bounded by wall ink at the other end. A gap is `collinear` only when a same-band run ends at both ends (a wall cut in two); any other gap is an open end that meets a perpendicular wall or cap.
- The closure loop (`:2501-2625`) evaluates every raw gap, collinear or not, and closes one only with exactly one owner: a placed native arc swing, one unfilled stroke parallel to the gap and spanning it end to end (`_stroke_closed`: face identity 0.35 pt on 10-140 pt gaps, 0.05 pt otherwise), unique perpendicular jamb caps at both ends (`_jamb_cap_closed`), a sliding leaf, cavity-slider words or panel-lift words (the canonical call enables the sliding-leaf and panel-lift owners and disables the CS-jamb and internal-swing ones). No owner, or two, leaves the gap unresolved. A closure is the whole gap rectangle.
- Free space is `domain - (strips + fills + closure rectangles)` (`:2626-2627`). A part becomes a ring unless it is noise, a sliver (narrower than the page's median strip thickness) or touches the domain boundary, which is dropped without a record (`:2632-2643`). A ring is ABSTAINED only for `open_wall_gap_unresolved` (an unresolved collinear gap with both ends on its outer boundary) or an unowned edge; a page without a candidate ring abstains `open_to_exterior` (`:2709`).
- Consequence: **a room whose perimeter leaks leaves no trace** (no ring, no reason code, no gap list). The result reports `unresolved_gap_count` (collinear gaps only, whether or not any ring touches them) and ABSTAINED rings, which are spaces merged by an unresolved doorway. The census measures the part the result does not report.

**1.2 Method (scratch spies on the real canonical run; no repository code).** Spies on `_collect_strips`, `_gaps`, `_swing_arcs` and `_place_swings`, and a wrapper on the preview's builder call, captured the page rows, strips, fills, domain, raw gaps, swing placement and the result. For every gap the result left unclosed the census records, from ink geometry only (never position, page or sheet name): its length bucket (under 10 pt, 10-140 pt, over 140 pt, the builder's own face-identity bands); the owners the builder's own evidence functions find (more than one = `competing_owners`); a segmented source swing receipt with its first failing P3a gate; a native arc swing that `_place_swings` did not place; and otherwise what ink lies in the gap rectangle (inflated by one wall thickness across, shrunk 0.5 pt at the ends, bounding strips excluded): two or more parallel strokes each spanning at least 60 percent of the gap, exactly one, perpendicular strokes (no such parallel stroke; other ink may also be present), other ink only (arcs, fills, oblique lines), or empty. The 60 percent cut and the 0.12 pt axis tolerance are descriptive census cuts: moving them moves a gap between classes and changes no ring or closure. Two checks guard the replication: the unresolved collinear count equals `result.unresolved_gap_count`, and the ring count recomputed from the captured barrier equals the result's ring count, on every page below. "Unblocking power" is the ring count recomputed after closing a chosen set of gaps with their whole rectangles; a set is a measurement, not a rule.

**Table 1. The preview's builder as-is** (page index in brackets; counts only; classes: perp = perpendicular strokes and no spanning parallel stroke (other ink may be present), partial = one partial spanning stroke, par2+ = two or more parallel strokes, other = other ink only, empty, compete = competing owners, arc-unplaced = native arc swing not placed).

| Page (index) | Strips | Raw gaps | Collinear | Closed | Unresolved | Rings cand / abst | Unresolved by class |
|---|---|---|---|---|---|---|---|
| A110 (6) | 119 | 154 | 6 | 3 | 5 | 6 / 0 | perp 3, other 2 |
| A500 (23) | 98 | 110 | 8 | 9 | 3 | 3 / 0 | perp 3 |
| A501 (24) | 72 | 69 | 10 | 5 | 7 | 2 / 0 | other 4, partial 2, perp 1 |
| A502 (25) | 55 | 55 | 4 | 1 | 4 | 2 / 0 | perp 4 |
| A503 (26) | 87 | 93 | 9 | 1 | 9 | 0 / 0 | perp 5, partial 2, par2+ 2 |
| 3Laurel p3 (2) | 604 | 351 | 124 | 72 | 70 | 16 / 2 | empty 24, partial 22, perp 14, par2+ 7, compete 2, arc-unplaced 1 |
| 3Laurel p2 (1) | 123 | 80 | 38 | 16 | 22 | 1 / 1 | empty 9, partial 4, other 3, par2+ 3, perp 3 |
| Q5446 (6) | 49 | 43 | 8 | 1 | 7 | 1 / 0 | perp 6, empty 1 |

**Table 1b. Unresolved collinear gaps by length bucket, and what they touch** (touch = the ring-veto rule: both ends on the ring's outer boundary).

| Page | lt10 | 10-140 | gt140 | touch no ring | touch an abstained ring | rings held open by a gap |
|---|---|---|---|---|---|---|
| A110 (6) | 1 | 3 | 1 | 5 | 0 | 0 |
| A500 (23) | 1 | 1 | 1 | 3 | 0 | 0 |
| A501 (24) | 0 | 6 | 1 | 7 | 0 | 0 |
| A502 (25) | 0 | 2 | 2 | 4 | 0 | 0 |
| A503 (26) | 0 | 7 | 2 | 9 | 0 | 0 |
| 3Laurel p3 (2) | 37 | 28 | 5 | 68 | 2 | 2 |
| 3Laurel p2 (1) | 9 | 12 | 1 | 21 | 1 | 1 |
| Q5446 (6) | 0 | 4 | 3 | 7 | 0 | 0 |

**1.3 Reading Tables 1 and 1b.** On the five Maryborough pages the preview's builder holds 55-119 strips and closes 1-9 gaps; 3-9 collinear gaps stay unresolved per page (28 in all) and **none of them touches a ring**: no ring on those pages is ABSTAINED, every ring is CANDIDATE, and A503, with no ring, abstains `open_to_exterior`. On 3Laurel p3 (604 strips) 70 of 124 collinear gaps are unresolved; 2 of its 18 rings are ABSTAINED, each held open by exactly one gap (one with two competing owners, one holding a native arc swing that `_place_swings` did not place), and 68 gaps touch no ring. 37 of those 70 are under the builder's own 10 pt opening floor (23 empty, 14 with one partial stroke).

**Table 2. Unblocking power, as-is** (rings recomputed from the same barrier; the "every raw gap" column is an upper bound, not a rule).

| Page | Rings now | Rings if all unresolved collinear gaps closed | Rings if EVERY raw gap closed (upper bound) | Unresolved collinear gaps whose single closure adds a ring | Raw gaps non-collinear |
|---|---|---|---|---|---|
| A110 (6) | 6 (recomputed 6) | 6 | 295 | 0 | 148 of 154 |
| A500 (23) | 3 (recomputed 3) | 3 | 93 | 0 | 102 of 110 |
| A501 (24) | 2 (recomputed 2) | 2 | 34 | 0 | 59 of 69 |
| A502 (25) | 2 (recomputed 2) | 2 | 35 | 0 | 51 of 55 |
| A503 (26) | 0 (recomputed 0) | 0 | 72 | 0 | 84 of 93 |
| 3Laurel p3 (2) | 18 (recomputed 18) | 28 | 148 | 9 | 227 of 351 |
| 3Laurel p2 (1) | 2 (recomputed 2) | 1 | 9 | 1 | 42 of 80 |
| Q5446 (6) | 1 (recomputed 1) | 1 | 30 | 0 | 35 of 43 |

**1.4 Reading Table 2.** The recomputed ring count equals the builder's on all eight pages. Closing every unresolved collinear gap adds no ring on six pages, 10 on 3Laurel p3 (18 to 28; 9 gaps each add one on their own: perpendicular-strokes-only 5, four of them over 140 pt; one partial stroke 2; competing owners 1; two parallel strokes 1; none of the 24 empty or 14 sub-10 pt partial seams adds any), and removes one on 3Laurel p2 (a closing rectangle can also cover a small ring: there two sub-10 pt gaps each remove one and one adds one). Closing **every** raw gap, which is an upper bound and not a rule (it also bridges free-standing partition ends, fixture voids and seams), gives 295, 93, 34, 35 and 72 rings on A110, A500-A503 against 6, 3, 2, 2 and 0 now: the free space behind the strips is mostly enclosed once openings are bridged, and 86-96 percent of the raw gaps on those pages are non-collinear.

**Table 5. Single-gap closure over every unclosed raw gap** (collinear and non-collinear; the preview's builder as-is; "adds a ring" = closing that one gap alone creates a ring; "encloses new space" = the enclosed area grows, so the space was open to the exterior; "splits" = the enclosed area does not grow, so an enclosed ring was divided).

| Page | Unclosed raw gaps (collinear / non-collinear) | Single closure adds a ring: collinear / non-collinear | Encloses new space: collinear / non-collinear | Splits an enclosed ring: collinear / non-collinear | Of the ring-adding: over 140 pt / under 10 pt | With a door witness or native arc | Non-collinear ring-adding, by class | Collinear ring-adding, by class | Closing one removes a ring |
|---|---|---|---|---|---|---|---|---|---|
| A110 (6) | 151 (5 / 146) | 0 (0 / 0) | 0 / 0 | 0 / 0 | 0 / 0 | 0 | - | - | 0 |
| A500 (23) | 101 (3 / 98) | 9 (0 / 9) | 0 / 7 | 0 / 2 | 3 / 3 | 0 | empty 3, partial 3, perp 2, par2+ 1 | - | 0 |
| A501 (24) | 64 (7 / 57) | 3 (0 / 3) | 0 / 3 | 0 / 0 | 1 / 2 | 0 | other 2, perp 1 | - | 0 |
| A502 (25) | 54 (4 / 50) | 5 (0 / 5) | 0 / 1 | 0 / 4 | 0 / 1 | 0 | par2+ 2, perp 2, other 1 | - | 0 |
| A503 (26) | 92 (9 / 83) | 8 (0 / 8) | 0 / 8 | 0 / 0 | 5 / 2 | 0 | partial 3, perp 3, empty 1, other 1 | - | 0 |
| 3Laurel p3 (2) | 279 (70 / 209) | 73 (9 / 64) | 5 / 42 | 4 / 22 | 20 / 2 | 4 | perp 26, partial 18, par2+ 16, arc-unplaced 4 | perp 5, partial 2, compete 1, par2+ 1 | 0 |
| 3Laurel p2 (1) | 64 (22 / 42) | 1 (1 / 0) | 1 / 0 | 0 / 0 | 0 / 1 | 0 | - | empty 1 | 2 |
| Q5446 (6) | 42 (7 / 35) | 0 (0 / 0) | 0 / 0 | 0 / 0 | 0 / 0 | 0 | - | - | 0 |

**1.5 Reading Table 5 (the part the result does not report).** The result never mentions a non-collinear gap: `unresolved_gap_count` counts collinear gaps only and the open-gap veto ignores the rest. Closing one such gap alone adds a ring for 9 gaps on A500, 3 on A501, 5 on A502 and 8 on A503 (25 in all) and for none on A110 or Q5446 (on those pages a new ring needs two or more closures). **19 of the 25 enclose new space** (A500 7, A501 3, A502 1, A503 8): closing the gap turns space that was open to the exterior into a ring. The other 6 (A500 2, A502 4) only split a ring that already existed, so they are partition ends, not leaks. **None of the 25 holds a door witness or a native arc swing.** They are seams under 10 pt (8), long intervals over busy ink (9, over 140 pt; 8 of them with dozens to over a thousand drawing paths inside) and 10-140 pt intervals with strokes (8). On 3Laurel p3, 73 gaps add a ring (9 collinear, 64 non-collinear: perpendicular strokes 26, one partial stroke 18, two parallel strokes 16, a native arc swing not placed 4); 47 of them (5 collinear, 42 non-collinear) enclose new space and 26 split a ring; 20 are over 140 pt and 2 under 10 pt.

**1.6 Native arc swings on 3Laurel p3 (the only page set here with native arcs; none on 3Laurel p2 or Q5446).** The preview's finder returns 10 arcs and rejects 121 curve candidates. `_place_swings` places 2 (both close their gap), finds no candidate gap for 3, and leaves 5 ambiguous: for 4 of them the two candidate gaps overlap in band and interval, i.e. **one aperture exists as two raw gaps** (both non-collinear), and one arc has four candidates (two collinear, two non-collinear) that are different apertures. Placement needs exactly one gap per arc and one arc per gap, so twin gaps leave the door unclosed even though its evidence is present.

**Table 6. Raw gaps against apertures** (raw gaps on one line whose band and interval overlap form one aperture group; descriptive grouping, no closure rule).

| Page | Raw gaps | Aperture groups | Groups with 2+ gaps (gaps in them) | Largest group | Unresolved collinear (sharing a group with a closed gap) | Ring-adding gaps (distinct apertures) | Of which enclose new space (distinct apertures) |
|---|---|---|---|---|---|---|---|
| A110 (6) | 154 | 136 | 14 (32) | 5 | 5 (0) | 0 (0) | 0 (0) |
| A500 (23) | 110 | 102 | 6 (14) | 3 | 3 (0) | 9 (9) | 7 (7) |
| A501 (24) | 69 | 59 | 10 (20) | 2 | 7 (0) | 3 (3) | 3 (3) |
| A502 (25) | 55 | 53 | 1 (3) | 3 | 4 (0) | 5 (5) | 1 (1) |
| A503 (26) | 93 | 88 | 4 (9) | 3 | 9 (0) | 8 (6) | 8 (6) |
| 3Laurel p3 (2) | 351 | 234 | 58 (175) | 8 | 70 (10) | 73 (43) | 47 (26) |
| 3Laurel p2 (1) | 80 | 41 | 18 (57) | 5 | 22 (13) | 1 (1) | 1 (1) |
| Q5446 (6) | 43 | 43 | 0 (0) | 1 | 7 (0) | 0 (0) | 0 (0) |

**1.6b Reading Table 6.** A raw gap is band-specific, so one aperture can appear as several gaps (a wall drawn with face strips and a lining of different bands). 3Laurel p3's 351 raw gaps are 234 apertures (58 groups hold 175 gaps, the largest 8) and p2's 80 are 41 (18 groups hold 57). 10 of p3's 70 and 13 of p2's 22 unresolved collinear gaps share a group with a closed gap, that is, the aperture is already closed through a twin and the "unresolved" gap blocks nothing; p3's 73 ring-adding gaps are 43 apertures and its 47 new-space gaps are 26. On the Maryborough pages 5-29 percent of the raw gaps sit in a multi-gap group (A110 32 of 154, A500 14 of 110, A501 20 of 69, A502 3 of 55, A503 9 of 93), none of their 28 unresolved collinear gaps shares a group with a closed gap, and the ring-adding gaps are almost all distinct apertures (6 of 8 on A503, equal to the gap count elsewhere). The public Q5446 page has none (43 of 43).

**Table 3. What-if: the preview's builder plus the layered merged collinear dark-face strips** (no other change; the preview's closure owners).

| Page | Strips | Collinear gaps = unresolved | Rings cand / abst | Held-open rings | Unresolved by class |
|---|---|---|---|---|---|
| A110 (6) | 470 | 45 = 35 | 170 / 3 | 3 | perp 26, par2+ 6, partial 3 |
| A500 (23) | 344 | 17 = 15 | 148 / 0 | 0 | empty 6, perp 6, partial 2, other 1 |
| A501 (24) | 260 | 20 = 19 | 129 / 0 | 0 | perp 8, partial 5, other 3, empty 2, par2+ 1 |
| A502 (25) | 216 | 11 = 11 | 133 / 1 | 1 | empty 5, other 3, perp 3 |
| A503 (26) | 317 | 19 = 19 | 143 / 0 | 0 | empty 9, perp 5, other 4, partial 1 |

**Table 4. The layered module's builder on the same rows** (run with `dark_painted_wall_source=True` and no other flag, on #4683's head; the module the room-face chain calls, with its own flag set).

| Page | Strips | Raw gaps | Closures | Unresolved collinear | Rings cand / abst | Slivers | Witnesses / chords | Abstain reasons |
|---|---|---|---|---|---|---|---|---|
| A110 (6) | 461 | 413 | 23 | 36 | 171 / 3 | 11 | 12 / 2 | open_wall_gap_unresolved 3 |
| A500 (23) | 331 | 311 | 13 | 15 | 151 / 0 | 17 | 4 / 1 | - |
| A501 (24) | 251 | 210 | 7 | 20 | 126 / 1 | 4 | 2 / 0 | open_wall_gap_unresolved 1 |
| A502 (25) | 210 | 181 | 4 | 11 | 133 / 1 | 9 | 1 / 1 | open_wall_gap_unresolved 1 |
| A503 (26) | 308 | 252 | 5 | 19 | 141 / 1 | 26 | 2 / 1 | open_wall_gap_unresolved 1 |
| 3Laurel p3 (2) | 614 | 354 | 54 | 30 | 60 / 6 | 68 | 0 / 0 | open_wall_gap_unresolved 6 |
| 3Laurel p2 (1) | 124 | 58 | 1 | 2 | 4 / 0 | 7 | 0 / 0 | - |
| Q5446 (6) | 133 | 99 | 2 | 24 | 20 / 0 | 2 | 0 / 0 | - |

**1.7 Reading Tables 3 and 4 (wall evidence supply).** Table 3 changes one thing: the preview's own collectors are given the layered builder's merged collinear dark-face strips (`4285e133a`), with the preview's closure owners unchanged (so no source-swing chords, because the door ink is not hidden as in #4683). Strips go from 55-119 to 216-470, candidate rings from 0-6 to 129-170, collinear unresolved gaps from 3-9 to 11-35, and two pages have rings held open (A110 3, A502 1). Table 4, the layered dark-painted builder on the same rows (with #4683 and its other owners), gives 126-171 candidate rings, 4-23 closures and 11-36 unresolved gaps on the Maryborough pages with 0 or 1 ring abstained (3 on A110). Either way the ring list is 126-173 per page: a ring is any enclosed free region wider than a sliver, and nothing here tells a room from a symbol interior, a hatch cell or a table cell, so **the ring count is not a room count** and no room identity (label, figured box, W5 reconciliation) has been applied.

**1.8 Which builder feeds rooms (traced, not measured).** The room-face scope the downstream chain consumes does not read the preview's fork. `layered_ring_scope_overrides` (`pb_layered_wall_doorway_room_face_scope_shadow.py:1342`) builds rings with the layered module's `build_from_pdf_bytes` (flags `sliding_leaf_frame_closure`, `dark_painted_wall_source`, `wall_end_stroke_closures`), and `layered_ring_room_face_scope` (`:1225`) turns a CANDIDATE ring into a room-face record only when exactly one authenticated figured (horizontal, vertical) pair has the ring's bounding box as its witness box (`figured_box_pair_count`, `:693`, used at `:1297-1303`); every other ring is an abstention. The figured dimensions come from `_trusted_native_dimensions_for_page` and need a source producer, so they were not run here. Two things follow. Tables 1, 2, 3, 5 and 6 describe the canonical preview's builder; the rings the room chain sees are Table 4's (layered builder), whose per-gap classes and unblocking power are not measured here. And the number that decides a room is not the ring count but the count of rings with exactly one figured witness, together with figured pairs that have no ring at all; neither is measured here.

**Table 7. The layered builder's census** (stage 2; the page's raw rows with `dark_painted_wall_source`, what the room-face scope reads; #4683's head tree, the one Table 4 used).

| Page | Strips | Raw gaps (collinear) | Closed | Unclosed collinear, by class | Rings cand / abst | Rings held open by a gap | Single closure adds a ring: collinear / non-collinear | Encloses new space: collinear / non-collinear | Splits an enclosed ring: collinear / non-collinear | Every raw gap closed (upper bound) |
|---|---|---|---|---|---|---|---|---|---|---|
| A110 (6) | 461 | 413 (44) | 23 | perp 24, par2+ 8, partial 2, door-witness 2 | 171 / 3 | 3 | 6 / 98 | 1 / 17 | 5 / 81 | 542 |
| A500 (23) | 331 | 311 (20) | 13 | empty 6, perp 5, partial 2, other 1, door-witness 1 | 151 / 0 | 0 | 1 / 47 | 1 / 16 | 0 / 31 | 342 |
| A501 (24) | 251 | 210 (23) | 7 | perp 8, partial 5, other 3, empty 2, par2+ 1, door-witness 1 | 126 / 1 | 1 | 0 / 32 | 0 / 11 | 0 / 21 | 243 |
| A502 (25) | 210 | 181 (14) | 4 | empty 5, other 3, perp 2, door-witness 1 | 133 / 1 | 1 | 2 / 14 | 0 / 6 | 2 / 8 | 262 |
| A503 (26) | 308 | 252 (23) | 5 | empty 9, other 4, perp 4, par2+ 1, door-witness 1 | 141 / 1 | 1 | 1 / 32 | 0 / 13 | 1 / 19 | 283 |
| 3Laurel p3 (2) | 614 | 354 (48) | 54 | empty 17, partial 7, perp 5, par2+ 1 | 60 / 6 | 6 | 24 / 143 | 8 / 46 | 16 / 97 | 361 |
| 3Laurel p2 (1) | 124 | 58 (2) | 1 | empty 1, perp 1 | 4 / 0 | 0 | 0 / 4 | 0 / 1 | 0 / 3 | 34 |
| Q5446 (6) | no census: the builder abstains (unlabelled_dark_wall_page_exceeds_20000_primitive_cap_needs_bounded_viewport) on the page's raw rows |

**1.9 Reading Table 7 (the builder the room-face chain consumes).** The layered builder leaves 11-36 collinear gaps unresolved on the Maryborough pages (30 on 3Laurel p3) and holds 0-3 rings open (A110 3, A501-A503 1 each, 3Laurel p3 6). Closing one gap alone adds a ring for 16-104 gaps per Maryborough page, but only 6-18 of them enclose new space; the rest (10-86) split a ring that already existed, 1.5 to 5 times as many, so most of the headroom in the ring count there is internal subdivision, not exterior leaks. Collinear gaps hardly matter for new space: 1 on A110, 1 on A500, none on A501-A503 (8 on 3Laurel p3), against 6-17 non-collinear new-space gaps per Maryborough page. Q5446's raw rows exceed the layered builder's structural primitive cap, so the room-face scope's own input abstains there (Table 4 used the preview's scoped rows, which fit).

## 2. Inference

1. **The count the preview's builder reports is the wrong blocker metric.** `unresolved_gap_count` touches no ring on the five Maryborough pages (0 of 28) and closing those gaps adds no ring; on 3Laurel p3, 9 of 70 matter and 37 are sub-10 pt seams that block nothing. A gap-count target ("reduce unresolved gaps") would reward closing seams.
2. **The preview's rings are mostly lost to leaks its result is silent about.** Ring-adding gaps are overwhelmingly non-collinear (25 of 25 on A500-A503; 64 of 73 on 3Laurel p3); 19 of the 25 and 47 of the 73 enclose new space (the rest only split a ring), they carry no door evidence on the Maryborough pages, and they are seams, long intervals over busy ink, or stroke-crossed intervals. By AGENTS.md none of those is a basis for closing: gap width, hatch ticks and furniture are not authority.
3. **For the preview, wall evidence supply is the biggest lever for the ring count, not doorway closure**: the layered merged strips take the same pages from 0-6 to 129-170 candidate rings. That is a topology change in the preview's collectors (P2c note, D1 option 2), not a producer wiring, and it needs a shadow run and its own authority review.
4. **A raw gap is not an aperture.** On 3Laurel, 351 raw gaps are 234 apertures (p3) and 80 are 41 (p2); 10 of 70 and 13 of 22 unresolved collinear gaps share an aperture with a closed gap, so the reported unresolved count includes gaps already covered through a twin. On the Maryborough pages 5-29 percent of the raw gaps sit in a multi-gap group, but no unresolved collinear gap is covered that way. Closure ownership ("exactly one owner") is judged per gap, so an aperture whose stroke evidences one twin and not the others, or whose arc is a candidate for two twins (4 of the 5 ambiguous arcs), is left unresolved or ambiguous, and any gap-count target double-counts apertures. De-duplicating one aperture is a different act from tie-breaking (AGENTS.md forbids nearest, first and smallest); it needs its own hypothesis, tests and review.
5. **Once the walls exist, doorway closure has no evidence to act on.** Unresolved collinear gaps rise from 3-9 to 11-35 per page; their classes (perpendicular strokes only, empty, partial) hold none of the owners the builder accepts. Abstaining stays correct; the census supplies no reason to close any of them.
6. **The Maryborough doors' gate failures and the preview's room-boundary problem are different problems.** The 9 source doors on A500-A503 lie where the preview has no wall strips along their lines (P2c note 1.5), and none of the 25 ring-adding gaps on A500-A503 (19 of them enclose new space) holds a door witness or arc: improving the chord stack cannot by itself make rings appear in the preview.
7. **Which blocker matters depends on the builder.** For the preview: wall evidence supply first (inference 3). For the room-face chain (1.8) the layered builder already has the evidence (126-171 candidate rings per page) and its census is Table 7: 11-36 unresolved collinear gaps per Maryborough page, at most one of them enclosing new space, 6-17 non-collinear gaps that do, and 1.5 to 5 times as many that only split a ring. The deciding gate is the figured witness (1.8): a ring is a room-face record only with exactly one figured pair, so the figured pairs that have no ring are the unmeasured part, and the next census belongs there.

## 3. Proposed change (measurement first; nothing in the preview, the builders or the gates changes)

**P4a: `tools/diag_ring_leak_census.py` plus one small pure module `pb_ring_leak_census.py`, read-only, counts and lengths only.**

- **Pure classifier** `classify_unclosed_gap_ink(rows, gap_record) -> dict` holding the ink classes of 1.2, and `aperture_groups(gaps) -> tuple[...]` (overlap components of raw gaps, order-independent). Both are pure over plain records, so they are testable without a PDF.
- **Stage 1, the preview's builder.** The tool replays `source_native_trace_preview` with throwaway spies (the P3a tool's `capture_proposer_call` pattern; a contract test fails loudly if a spied private function changes its signature) and writes JSON per page: strips, raw gaps (collinear and non-collinear), closures by kind, unclosed gaps by orientation, class and length bucket, rings by status and reason, rings held open with their gap classes, the unblocking-power sets of Tables 2 and 5 (all unresolved, per class, single, every raw gap as an upper bound), aperture groups and the ring-adding gaps per group (with whether each encloses new space or only splits a ring), native arc placement outcomes (no candidate, one, several, with the overlap shape), and the two replication checks, which make the tool exit non-zero if they fail.
- **Stage 2, the layered builder the room-face chain consumes.** The same classifier on the layered builder's gaps, using spies on the layered module's own functions; the first thing the build must prove is that the replication checks hold there (its closure loop also has source-owned chords and segmented-swing placement). Its output is Table 4's columns extended with the classes, ring-adding gaps and apertures. If the replication cannot be made exact the tool says so and reports counts only.
- **Stage 3, figured witness (only if a bare-PDF path exists).** Per ring, `figured_box_pair_count`, and the figured pairs that have no ring; blocked today on `_trusted_native_dimensions_for_page` needing a source producer. Section 6, D5.
- Per `one_partial_spanning_stroke` gap it also reports the signed end misses of the stroke in points (offsets only), without proposing a tolerance. The tool prints no coordinates, only lengths, offsets and counts; the JSON goes outside the repository.
- Not in P4a (each its own claim and review, section 6): any change to a ring, closure, strip collector, gate or the room-face scope; evidence parity in the preview; aperture consolidation; a hatch-poche hypothesis; reporting non-collinear leaks in the ring result; any room identity.

## 4. Tests

Pure classifier, synthetic fixtures built with PyMuPDF like the P3a tests: a wall cut by (a) a door swing arc, (b) one spanning stroke, (c) two parallel strokes, (d) perpendicular ticks only, (e) nothing; look-alike negatives (a dashed non-door polyline, a dimension tick, a hatch lattice, a furniture loop) that must land in the non-door classes; ambiguity (two arcs in one gap, one arc with two candidate gaps, two overlapping gaps that form one aperture group, two disjoint gaps on one line that do not); translation, axis-swap and uniform-scale invariance; row-order and strip-splitting invariance; unrelated-content and viewport-expansion invariance; deterministic replay and a stable receipt id; no mutation of the rows. Tool: the replication checks pass on every fixture; the spies are removed after the run (the preview's functions are the originals again); with the tool off or after it runs, the preview's summary and PNG digests are byte-identical to a clean run; the JSON carries no coordinates (a scan test); a contract test pins the spied functions' signatures. Single-line mutants of the classifier and of the replication checks. Local, counts only: Tables 1 to 6 reproduce exactly on the owner-local originals; the real-source tests skip in public CI.

## 5. Benchmark observations that must not influence the implementation

The page indices, the counts, the Maryborough, 3Laurel and Q5446 page choices and the run times are observations on the owner-local originals, used only to verify. The 10 and 140 pt buckets are the builder's own face-identity bands (`_stroke_closed`), not tuned; the 60 percent span cut and the 0.12 pt axis tolerance in the ink classes and the aperture grouping rule (band and interval both overlap) are descriptive and feed no closure, strip or ring. No threshold, count, page index or sheet name enters production code. The upper bound of Table 2 is a measurement, never a rule or a target.

## 6. Decisions

D1 scope: P4a stages 1 and 2 in one tool (recommended: it is the shadow-run instrument AGENTS.md requires before any lever below, playbook section 13 priority 6, and stage 2 is where the room-face chain lives), or stage 1 only (measured here; the smaller PR but it answers the preview's question, not the room chain's), or go straight to a lever. D2 seam: throwaway spies in a tool, as P3a did (recommended; no production change), or an additive optional diagnostics field on the ring results (a production change to a type five modules import; not recommended). D3 levers after P4a, each its own claim, shadow-first and authority-reviewed: **L1 evidence parity** (default-off opt-in giving the preview the merged collinear dark-face strips; changes its rings when on, so it needs a shadow comparison and MAX's review; Tables 3 and 4 are its evidence; it does not help the room-face chain, which already uses the layered builder); **L2 aperture consolidation** (one aperture, one gap; Table 6 is its evidence, with 3Laurel p3 the strongest case); **L3 reporting non-collinear leaks** in the ring result (report-only, never a closure); **L4 a hatch-poche hypothesis** for the long collinear gaps with dozens of perpendicular strokes (hatch ticks are non-authority today, so it needs look-alike negatives first). D4 the output: counts and lengths only, JSON outside the repository (recommended for a public repository). D5 stage 3 (figured witness per ring and figured pairs without a ring): needs a bare-PDF route to the authenticated native dimensions or a decision to run it inside the source-producer chain; it is the measurement that tells how many printed rooms lack a ring, and it belongs after stages 1 and 2.

## 7. Not claimed or not run

No score, quantity, room count or room area is claimed; rings are candidate topology. Not measured: Lot16 and the 11 other Maryborough sheets, rotated or tile-mode pages, figured pairs or any ring-to-room reconciliation (1.8), partial-stroke end misses (P4a prints them), an idle-machine run time, and a preview with L1 applied. The ring-to-face scope and the figured-dimension chain were read, not run. The owner-local release path and the frozen four-project score were not run. The 60 percent cut, the 0.12 pt tolerance and the aperture grouping rule are descriptive; the closure sets in Tables 2 and 5 are measurements, not rules. Chords from #4683, #4686 and #4694 are not applied to any ring here.

## 8. P4a as built (draft PR; shadow only; nothing in the preview, the builders or the gates changed)

**Files, all new (no existing file is edited):** `pb_ring_leak_census.py` (651 lines: `PlainGap`, `InkIndex`, `classify_unclosed_gap_ink`, `aperture_groups`, `ring_parts` and `count_rings`, `single_closure_effect`, `census_report`, the two ring rules and the capture record), `tools/diag_ring_leak_census.py` (541 lines: the spies and their contract check, the replay of the canonical preview and of the layered builder, the command line), `tests/test_ring_leak_census_v1.py` (118 cases), `tests/test_ring_leak_census_tool_v1.py` (173 cases) and this note.

**Stages.** Stage 1 (the preview's fork, replayed through `source_native_trace_preview`) and stage 2 (the layered builder, on the page's raw `get_drawings()` rows, which is what `build_from_pdf_bytes` and so the room-face scope read; `--layered-rows preview-scoped` feeds it the rows the preview scoped instead) are built. Stage 3 (figured witness per ring) is not (D5).

**Differences from the proposal in sections 3 and 6.**
1. The class `perpendicular_strokes_only` is `perpendicular_strokes`: the rule never required the absence of other ink, and the name now says what it does.
2. A gap that holds a segmented source door swing is `source_door_witness_in_gap` without the P3a gate label (the P3a function is not on main).
3. The "what if these gaps were closed" figures re-run the builder's own union over its own barrier polygons plus the closing rectangles. Re-closing the builder's finished barrier instead is not idempotent at the 0.03 pt closing scale: it gave 149 instead of the 148 of Table 2 for the "every raw gap" bound on 3Laurel p3, and the single union reproduces 148.
4. The layered builder's closing rectangle is padded by its own 1.2 pt (`_STROKE_PAIR_THICK_MIN`), as its `_append_closure` does; a test compares the census's rectangle with the polygon the builder really united.
5. **New: what one closure does.** The proposal called a gap whose single closure adds a ring a "sole leak". A ring count cannot tell a leak from a partition end, so the tool reports every such gap as ring-adding and splits it by whether the enclosed area grows (`encloses_new_space`: the space was open to the exterior) or not (`splits_an_enclosed_ring`). Tables 5-7 use it and it changed the reading: 19 of the 25 ring-adding gaps on A500-A503 enclose new space and 6 only split a ring, and on the layered builder most ring-adding gaps (1.5 to 5 times as many as the new-space ones) are splits.
6. The tool refuses a `--json-out` inside the repository, and a raster-underlay page skips the layered builder when it would read the preview's rows.

**Use.** `python -m tools.diag_ring_leak_census --pdf <original> --page-index 25 --json-out <a path outside the repository>` prints one counts-only line per builder and writes the JSON (add `--per-gap` for one record per unclosed gap, `--builder preview|layered|both`, `--layered-rows preview-scoped`, `--no-unblocking` for a fast run without the ring recomputations). The exit code is 2 when a replication check fails (then the ring figures are withheld), unless `--allow-inexact`.

**Evidence.** 291 synthetic cases; 259 of them fail against a neutral stub with the same names (32 pass vacuously on empty results). Single-line mutants: 297 (191 of the census module, 106 of the tool); every one is killed except four equivalent ones: `ox >= -1e-6` against `ox > -1e-6` in the overlap test (they differ only at an exact 1e-6 boundary), the `if entries:` guard of the ink index (an empty row adds no ink either way), the noise-area guard of `ring_parts` (the sliver test already drops any part that small) and the swapped end points of a door witness (`witness_in_gap` is symmetric in them). On the owner-local originals (counts only, nothing committed) the preview census reproduces the scratch probes behind Tables 1, 2, 5 and 6 field by field on all eight pages (one labelled difference: the P3a gate label on A110's five door-witness gaps), the layered columns reproduce Table 4 exactly on all eight (the preview's scoped rows for 3Laurel and Q5446, the raw rows for the Maryborough pages: identical there), and every replication check is exact on every run (22 census runs; Q5446's layered run on raw rows abstains at the structural cap and has no census). The 31 existing test files that reference a ring builder or the canonical preview give the same 721 passed and 5 skipped on main and on this head, with the new files run first in the same session.

**Not claimed or not run.** Stage 3; the owner-local release path and the frozen four-project score; an idle-machine run time (A502, both builders, took about 50 s on a loaded machine; 3Laurel p3 several minutes); arbitrary-angle rotation (the builders read horizontal and vertical walls; axis swap, translation, uniform scale, row order and strip splitting are tested); any ring-to-room reconciliation. The upper bound of Table 2 and every closing set remain measurements, never rules.
