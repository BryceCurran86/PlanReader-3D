# Structural room regions, attached partitions, a symbol-tolerant opening-gap rule and a ruled-ring negative (shadow evidence, 2026-10-17)

Status: **shadow-only modules and a read-only overlay tool.** Nothing here is called by a live path, raises an authority, filters a
candidate, changes a threshold or the 20,000-segment cap, touches a benchmark file or a signed output, or publishes a quantity.
`room_authority_granted`, `scale_authority_granted` and `wall_authority_granted` are `False` and `live_effect` is `False` in every
report. Tracker: #2608 (coordination), GPT1 #2017, GPT2 #2843, GPT3 #2004. Author: Claude integration lane (one shared login: this is
independent measurement, not a formal independent approval).

Code: `pb_structural_partition_ink_shadow.py`, `pb_structural_room_region_shadow.py`, `tools/diag_structural_room_region_overlay.py`,
`tools/diag_region_translation_vote.py`, and two small changes to `pb_structural_wall_ink_shadow.py` (merged in #2848): the wide-gap rule and a
ruled-ring typed negative.
Tests: `tests/test_structural_partition_ink_shadow.py` (22), `tests/test_structural_room_region_shadow.py` (32),
`tests/test_structural_room_region_overlay_tool.py` (10), `tests/test_region_translation_vote.py` (10), `tests/test_structural_wall_ink_shadow.py` (37 -> 61).

## 1. Observed repository behaviour (before this change)
- `pb_source_room_face_authority` derives room faces only from authenticated physical-wall scopes (`SourceRoomFaceAuthority`). It has no notion
  of a doorway: a room whose door is a gap in its wall is not a bounded face. On the owner's 3Laurel p3 handoff the chain ends with 0
  canonical walls, 139 physical-opening existence claims, `no_authenticated_host_wall_band`, and `room_area_support_pages: []`
  (`docs/engineering/four_job_runs/20261016_47c8031a/au_qld_3laurel/outputs/production_summary.json`); Q5446 stops earlier, at
  `physical_wall_candidate_scope_complexity_exceeded` on 9 of 10 pages.
- `pb_structural_wall_ink_shadow` (#2848) proves only the darkest ink present on a page and types the interruptions of paired wall faces as
  opening-gap candidates. A gap wider than 12 wall thicknesses was accepted only when the *partner face's* gap ends lined up with
  this face's to 1 pt.
- Native text is untrusted outside Lot16 (#2849: 0 of 1,215 words on 3Laurel p3, 0 of 1,545 on Maryborough p7), so every printed room name
  below is source-native text whose integrity is **not** established; Q5446's lettering is vector outlines with no native text at all.

## 2. Observed on the original drawings (what the pipeline ignores)
- 3Laurel p3 draws external walls in black (0.71 pt outlines, black filled strips) and **internal partitions in a lighter grey class**
  (0.37 pt, grey 0.42, white-filled strips). "Darkest present ink" therefore leaves every internal partition `UNPROVEN`
  (`lighter_than_darkest_present_ink`), and the rooms merge.
- Pairing every lighter class is not safe: the floor-finish plank pattern is also made of parallel lines inside wall thickness of each other
  (grey 0.75, 0.43 pt: 380 segments on 3Laurel p3) and touches every wall. Measured during development, a pairing-only attachment (no ladder rejection)
  attached 629 strokes, 305 of them plank lines, and cut the living, dining, bedrooms and master suite into small cells: only the garage and two alfresco
  areas survived as rooms. The ladder tests keep that look-alike.
- Q5446 draws every wall as two 0.96 pt faces around a 1.92 pt core, and its openings carry symbols (a sewer-stack box, a hatched
  cased-opening strip, a dashed head line) that overhang one face end by up to about 4 pt, so the opening's two faces do not line up to a point.

## 3. What this change adds (all additive, shadow)
1. **Symbol-tolerant wide-gap rule** (`pb_structural_wall_ink_shadow.py`, `_partner_line_interrupted`). A gap wider than 12 thicknesses is now also
   accepted when the partner face's line (one thickness to either side) carries **no solid wall run over the gap interval** (the interval is
   shortened by one face-gap bound, 8 pt, at each end) **and has a face ending on each side of it** within that bound. The previous aligned-ends rule is
   kept (union), so nothing previously accepted is lost (verified on all five pages: 0 candidates dropped). A face that continues through the
   opening, a partner ending further than the bound, or a partner running far into the opening are refused (tests).
2. **Attached partition ink** (`classify_attached_partition_ink`). From the solid strokes that are neither structural candidates nor typed negatives:
   (a) *ladder rejection*: a stroke with a parallel **same-class** partner within wall-thickness on both sides, or whose only partners are such
   strokes (the outer line of the field), is a hatch/plank/tile ladder and is typed `NOT_PARTITION_INK`; (b) *attachment*: the rest are re-read, as
   one ink with the structural candidates, by the **unchanged** structural classifier; a stroke is a `PARTITION_INK_CANDIDATE` only when it is a paired-face
   member of a network that also contains structural candidates. It also returns the joint reading's opening gaps, so an internal doorway between attached faces is typed like an
   external one. No numeric stroke weight, colour list, layer name, project name or page number is used.
3. **Room-region evidence** (`derive_structural_room_regions`). Every structural/partition primitive and every typed gap chord is a barrier of
   half-width 4 pt (half of the structural pairing bound, so every wall that rule can pair is one barrier); the free space around the
   building is cut into enclosed regions, each grown back to the faces. Per region: polygon (native frame), net/gross area (pt²), inscribed radius, the
   primitive ids that run along its boundary with their tier, the **typed chords that close it** (nothing is closed without one), the printed-name
   candidates and the outlined-lettering runs whose centre stands in it (`multi_label` when two or more: an open or merged area, never split), and the
   primitives adjacent to the page exterior / to enclosed regions only / to neither.
4. **Ruled-ring typed negative** (`pb_structural_wall_ink_shadow.py`, `table_grid_runs`). Reported by the owner on the first A140 overlay: the WALL TYPE SCHEDULE table appeared as a blue region
   inside a box, because its frame is drawn in the heaviest ink class and is of building scale. A component is now a `NOT_WALL_INK` **ruled ring** (reason `ruled_ring_table_or_grille`, retained with every rule line) when it is a
   pure ring (at least 90 % of its length along its own box sides, within one face-gap bound) around at least four parallel full-span rule lines, closer-than-1-pt double rules counted once, with column rules joining when rows hold. A pair
   of full-span lines a wall thickness apart (1 - 8 pt) inside the ring is a partition, never a rule: such a ring is a building. On the seven original pages it drops exactly six candidates (the schedule frame on A140) and types the title-block
   ring on 3Laurel p3 and a few grille symbols; no building candidate changes. Residual risk, stated: a pure ring of one ink class around four or more *single* thin full-span lines at 8 pt pitch or more (a terrace drawn as a single-line ring with single-line
   party walls) would be typed a ruled ring; the primitives are retained with the reason, not dropped.
5. **Translation vote** (`tools/diag_region_translation_vote.py`). Which translation takes the regions of one sheet onto the regions of another, by exact corner coincidences (0.05 pt) of the region polygons: every candidate with its own count,
   whole regions identical by shape after the shift, `selected_by_this_tool: null` always, and `unambiguous` only as a 3x ratio statement. Translation only; no label text, no scale, no plausibility.
6. **Overlay tool** (`tools/diag_structural_room_region_overlay.py`). Draws all of the above (rotated sheets handled) and writes JSON. **Share-safe by default**: the repository is public and the
   originals are private customer drawings, so the drawing is made on a white sheet (no render of the page: no title block, client name, address or note text), only room names the existing vocabulary accepts are kept, and
   `--ocr-candidates` readings (RapidOCR, `candidate_only`) are reduced to the vocabulary match, its confidence and position. `--private-detail` adds the faded page render and every OCR line for local review only.

## 4. Evidence from the original PDFs (private kit; `main` `ef6ca359` + this branch)
Share-safe overlays (geometry on a white sheet) and per-region JSON: `overlays/`; the private-detail versions with the faded original were written outside the repository. Legend: red = structural wall ink (heavy red = looks onto the page exterior), blue = attached partition ink, cyan = typed
opening-gap chord, orange = ladder negative, purple = outlined-lettering negative, green boxes = native room-name lines, grey boxes = glyph runs,
filled polygons = regions (`#k`).

| page | segments | structural candidates | gap candidates (tier 0 -> with partitions) | partition candidates / ladder negatives | regions listed (+ discarded fragments) | regions closed with a typed chord | native room-name lines on page / standing in a region / regions with a name / multi-label regions |
|---|---:|---:|---:|---:|---:|---:|---|
| 3Laurel p3 floor plan | 9,977 | 860 | 369 -> 463 | 338 / 334 | 38 (+7) | 18 | 41 / 22 / 16 / 4 |
| Q5446 p1 ground floor | 47,184 | 189 | 87 -> 90 | 7 / 27 | 7 (+0) | 7 | outlined: 0 native; OCR candidates below |
| Q5446 p2 first floor | 35,997 | 222 | 68 -> 68 | 2 / 12 | 10 (+1) | 8 | outlined: 0 native; OCR candidates below |
| Maryborough p7 A110 floor plan | 59,874 | 339 | 222 -> 219 | 256 / 287 | 26 (+4) | 17 | 18 / 18 / 9 / 3 |
| Maryborough p11 A140 finishes and partitions | 27,160 | 244 | 75 -> 123 | 121 / 36 | 29 (+1) | 16 | 30 / 18 / 14 / 3 |
| Lot16 p3 (negative control: eleven raster tiles) | 1,739 | 0 | 0 | none | 0 (`no_structural_wall_ink`) | - | 17 / 0 / 0 / 0 |

**Ablation** (regions listed, regions that carry a native room-name line; same code, three configurations; columns (a) and (b) still count the schedule table on A140 as a region):

| page | (a) `main` #2848 ink and gaps | (b) + symbol-tolerant gap rule | (c) + attached partitions (this change) |
|---|---|---|---|
| 3Laurel p3 | 17 regions, 9 named | 18, 10 | **38, 16** |
| Q5446 p1 | 1 region | 6 | **7** |
| Q5446 p2 | 3 regions | 10 | **10** |
| Maryborough p7 | 6 regions, 1 named | 8, 3 | **26, 9** |
| Maryborough p11 | 7 regions, 2 named | 9, 4 | **29, 14** |

What the overlays show, honestly:
- **3Laurel p3.** Sixteen regions carry a native room-name line: LIVING and DINING (one open-plan region, `multi_label`, with the kitchen in it), GARAGE, MEDIA, BED 4, BED 5,
  ENTRY, three WIR, BATH, LAUNDRY, ENS, WC, and two multi-name regions (PANTRY + LIVING; BED 2 + BED 3 with their ROBEs). BED 2 and BED 3, and PANTRY and LIVING,
  are reported as merged because the wall between them is not in the evidence; they are **not** split by an invented wall. 22 of the 41 name-like lines stand in a region; the rest
  are dimension-string captions outside the plan.
- **Q5446 p1 / p2.** Walls, openings and 7 / 10 enclosed regions are traced without a single native word. The garage, the entry and the stair void stay open to the page
  exterior (a 4.8 m garage opening and an open porch are real; no chord is invented). GUEST, W.I.R and ENS are one region on p1 because the interior doorways between them were not typed.
  Candidate OCR (RapidOCR, `candidate_only`, confidence kept) read a printed name inside **every** p1 region and in 9 of 10 p2 regions in the private-detail run (for example KITCHEN, SERVERY, MEALS and FAMILY together in the open-plan region; GUEST, W.I.R
  and ENS together; LIVING; ALFRESCO; L'DRY and W.I.P; PDR'; POR' on p1; BED 2, BED 3, BED 4, MASTER, BATH, WC, ENS' on p2). The committed share-safe JSON keeps only the readings the existing room-name vocabulary accepts (p1: the open-plan region with
  KITCHEN, SERVERY, MEALS, FAMILY; GUEST and ENS; LIVING; p2: MASTER, BED, LINEN, BED 3, BATH, WC, ENS'), because the vocabulary has no ALFRESCO, PORCH, W.I.P, L'DRY or PDR' (§5).
- **Maryborough p7 (A110) / p11 (A140).** 26 / 29 regions on the rotated sheet. FREEZER and COLD ROOM come out as their own enclosures (FREEZER's actual enclosure, not a box around its label);
  OFFICE, LAUNDRY, PWD and WC & SHOWER are separate regions; M-AMB, F-AMB and PWD (p7) and WC & SHOWER and AIRLOCK (both sheets) share regions where an interior doorway was not typed. On A110 the shop floor,
  back of house and lounge are **one** region with seven names: no closed partition between them is in A110's structural or partition ink (A140, the partitions plan, separates them), and nothing is drawn around a label. On A140:
  DRY STORE, WASH UP and FOOD PREP, which carry the same floor-finish mark (FT3), stand in **one** enclosed region; OFFICE (FT3) is its own enclosed region; FOOD SERVICE (FT3) stands in the open region that also carries SALES (FT1).
  So an FT3 area for FOOD SERVICE cannot come from a room enclosure, while the other FT3 marks can be compared with enclosed-region areas (geometry evidence only: whether the finish is uniform over a region is a finishes-plan fact that is not read here).
- **A look-alike this evidence does not separate (Maryborough A140).** POS COUNTER stands in a region of its own, bounded by the outer wall and by the 150 mm *step-down* outline, which is drawn as single heavy lines.
  The owner states that FOOD SERVICE and POS COUNTER are zones of one space, so this is a **false split**: a floor-level or zone outline drawn in wall-weight ink looks like a wall to a geometry-only rule.
  `boundary_evidence_kinds` reports it (4 paired-face, 2 single heavy stroke and 1 attached-partition primitive on that region's boundary), so a consumer can treat single-stroke sides as weaker than paired faces; no rule here removes it.
  The WALL TYPE SCHEDULE table, which the first A140 overlay drew as a blue region inside a box (the owner spotted it), is now a typed ruled ring and is no region: no region lies inside its box on the final overlay.
  Removing it also moved A110's LAUNDRY left edge onto A140's (x0 = 173.5 pt on both after the -78 pt shift; six table-like primitives that had been partition candidates are now typed negatives).
- **Lot16 p3** is eleven raster tiles with no native linework: the modules return `no_structural_wall_ink` and zero regions, as they must.

## 5. Limits and open findings
- A merged region is a **finding**, not a defect hidden: where an internal doorway was not typed, or a partition is absent from the evidence, two rooms share a region and say so.
- Region areas are in square points of the sheet. There is no scale in any of these modules and no scale is taken from the title block. (Observation, not an input: with the sheet's printed 1:100 a
  3Laurel region 29,210 pt² reads as about 36.4 m², and the plan's own area legend prints a garage of 36.40 m²; nothing in the code reads a legend or any expected quantity.)
- Printed names are native text whose integrity is not established (#2849); OCR names are candidates. `RegionLabelCandidate.trust` is whatever the caller passes, default `not_supplied`.
- The existing room-name vocabulary (`pb_room_face_takeoff.ROOM_LABEL_EXACT`, 75 names) has no ALFRESCO, PORCH, BALCONY, VERANDAH, W.I.P, LDY or PDR. ALFRESCO and PORCH are printed on
  both 3Laurel and Q5446 and stand in their own regions, so they are not room-name candidates for `SourceRoomLabelAuthority`. That is an authority-owner decision (generic residential names, no benchmark-aware vocabulary), not changed here.
- Fixtures and joinery that stand on a wall and are drawn as a double line are not separated from partitions (the same open gate as the structural report).
- **Floor-plan sheets only.** On Maryborough's reflected ceiling plan (A120, page 9, private-detail run) the perimeter and the amenity rooms come out as regions, but the ceiling grid and troffer lines attach as partition ink and cut the sales floor into bands.
  Ceiling zones are not wall-bounded; do not read regions from a ceiling sheet as rooms. (Observation for GPT2's ceiling lane: each enclosed amenity room on A120 carries one ceiling-type mark and height as native text.)
- The 20,000-segment cap, the motif filter and `PhysicalWallCandidateAuthority` are untouched; these modules are not consumed by them.

## 6. Verification
- 137 shadow tests pass locally (structural 61, partition 22, regions 32, room-region overlay tool 10, structural overlay tool 2, translation vote 10). Each module has synthetic positives,
  look-alike negatives (plank ladder, detached grey building, paper-coloured / zero-width / too-short strokes, stub too short for its distance, parallel line beside the partner
  face, solid ink through the partner line, partner ending beyond the bound), ambiguity (two labels in one region, label in a wall body, label straddling a wall, hairline break), translation, quarter-turn,
  uniform-scale and segment-splitting invariance, input-order and unrelated-content / larger-sheet invariance, deterministic replay with stable region ids, no mutation of inputs, bounded work with an explicit reason
  (no silent cap), and shadow-flag checks. The OCR path is tested with an injected mock backend, including a rotated sheet.
- Mutation checks: 45 mutants were run against the first set of rules and behaviours (the gap rule's blocked / overhang / shrink / support / side / tolerance conditions, the ladder's two-sided / edge / class / offset /
  overlap / aspect conditions, anchoring, re-inking, the paper / short / zero-width filters, the region barrier width, caps, growth back to the faces, adjacency by shared boundary length, label centre containment,
  the multi-label threshold, fragment discard, ordering, partition tier, partition gaps, chord use, hole identity, area, the boundary-evidence kinds, the rotated-sheet OCR mapping, and the share-safe page render / OCR text / flag):
  43 are killed by a test, one is equivalent (a parallelism guard that the endpoint-offset test already subsumes), and one exposed a redundant check (dashed strokes are already typed negatives of the structural report), which was removed instead of tested.
  Later, 18 mutants of the ruled-ring rule (row count, span, double-rule separation, pure-ring fraction and band, rows inside the ring, column rules, both branches, marking of the rule lines, the wall-pair disqualifier) and 10 of the translation vote
  (coincidence tolerance, merge, ranking by exact coincidence rather than votes, shape identity, translation, no selection, ratio) were run: every one is killed.
- No production module imports any file added or changed here (`grep` over `*.py` outside `tests/`, `tools/diag_structural*`, `docs/`: only the shadow modules themselves), so no signed Lot16 / Maryborough output, customer row or commercial quantity can change.
  Exact-head replays of the two signed-output workflows on this PR's head `ce05a0b4` (before the ruled-ring and vote commits, which touch no production module): Lot16 `ef58f8ae...` and Maryborough `9f3ab9ac...`, `source_sealed_run.json` and `verified_customer_rows.json` byte-identical (`cmp`) to the archives.
- Nothing in `benchmarks/frozen_holdout/full_plan_v2/` or `documents/sources/` is touched (truth separation).

## 7. Counterfactual (not a repository change): what the 20,000-segment cap hides on Q5446
`counterfactual/run_cap_counterfactual.py` wraps, in a child process only, the live authority's own motif filter so that the primitives the structural ink types `NOT_WALL_INK`
(outlined lettering, dimension ticks, dashes) are not passed to the wall topology, then runs the unchanged source-stage tool and keeps counts. The cap and every authority are untouched.

| Q5446 standard plans | live chain at the cap (baseline) | wall-topology input with typed negatives withheld | wall-candidate scope | wall candidate records | physical-opening existence claims | authenticated hosts | room-face scope |
|---|---|---:|---|---:|---:|---:|---|
| p1 | `physical_wall_candidate_scope_complexity_exceeded` | 8674 of 47193 | corroborated | 1768 | 82 | 1 | 43 faces (scope_resolved, universe_partial) |
| p2 | `physical_wall_candidate_scope_complexity_exceeded` | 6570 of 36009 | corroborated | 1405 | 70 | 0 | 0 faces (boundary_unresolved) |
| p3 | `physical_wall_candidate_scope_complexity_exceeded` | 5013 of 28114 | corroborated | 1379 | 22 | 0 | 0 faces (tiny_or_degenerate) |
| p4 | `physical_wall_candidate_scope_complexity_exceeded` | 3905 of 39077 | corroborated | 946 | 24 | 0 | 0 faces (tiny_or_degenerate) |
| p5 | `physical_wall_candidate_scope_complexity_exceeded` | 4345 of 26192 | corroborated | 1072 | 41 | 0 | 56 faces (scope_resolved, duplicate_edge_ownership, universe_partial) |
| p6 | `physical_wall_candidate_scope_complexity_exceeded` | 4158 of 24867 | corroborated | 1014 | 41 | 0 | 0 faces (tiny_or_degenerate) |
| p7 | `physical_wall_candidate_scope_complexity_exceeded` | 6054 of 30067 | corroborated | 1364 | 24 | 0 | 0 faces (duplicate_edge_ownership) |
| p8 | `physical_wall_candidate_scope_complexity_exceeded` | 6133 of 29301 | corroborated | 1438 | 30 | 0 | 0 faces (duplicate_edge_ownership) |
| p9 | `physical_wall_candidate_scope_complexity_exceeded` | 4344 of 22621 | corroborated | 832 | 22 | 0 | 0 faces (duplicate_edge_ownership) |
| p10 | scope corroborated, 1074 candidates | 2804 of 10130 | corroborated | 455 | 10 | 1 | 0 faces (scope_unavailable) |

Reading it: the 20,000-segment cap is the first failing stage on nine of ten Q5446 pages, and it is hit by outlined lettering, not by walls. With the typed negatives withheld the input falls to 3,905 - 8,674 segments per page,
the wall-candidate scope resolves, and the unchanged chain reports 22 - 82 physical-opening existence claims per page, authenticated hosts on p1 and p10 only (one each), and room faces on p1 (43) and p5 (56) only: every other page
abstains at `tiny_or_degenerate` or `duplicate_edge_ownership` room faces, i.e. the interior doorways are open, which is exactly what §4 closes with typed chords and the room-face authority cannot. Counts only; no quantity; nothing here changes the cap,
the motif filter or any authority. (`counterfactual/q5446_cap_counterfactual_summary.json` has the rows; page 10 does not hit the cap at baseline.)

## 8. Benchmark observations that did not influence the implementation
The four original projects are also the benchmark projects. The constants here are the structural module's own (8 pt face-gap bound; closure half-width = half of it; 0.5 / 8 overlap rules; 12x / 80x gap factors) and
were fixed by drawing failure modes (a symbol overhanging a face end; a plank ladder), each with a synthetic look-alike test, never by a quantity, a legend value, a benchmark id, a file name or a score. The sheets' printed area
legends are visible on the plans and were used only as a plausibility glance at the regions' sizes (§5); no constant, rule or test was chosen or changed to match a printed value. The closure half-width follows from the pairing bound
(both faces of any wall the pairing rule can pair must be one barrier); an earlier trial with a thickness estimate showed wall-body slits between the faces, which is why it was replaced.

## 9. Decisions this needs (none taken here)
1. **Room faces at typed openings.** `SourceRoomFaceAuthority` can only close a face along an authenticated wall. Whether it may close at a typed opening void (a threshold chord whose two jamb ends are authenticated wall faces) is an authority-promotion
   review for the room-face / physical-opening owners (GPT MAX, GPT1, GPT2); until then the regions here are evidence for that review. The chords and their primitive ancestry are in the JSON.
2. **Withholding typed negatives before the cap** (Q5446, §7) is the same kind of decision (AGENTS.md: typed negatives are evidence against promotion, not deletion before W2).
3. **Text trust** (#2849): 3Laurel and Maryborough names are untrusted native text; Q5446 names need a separately approved source-positive reader. The OCR candidates here are only a visual aid for that review.
4. **Room-name vocabulary** (§5): generic residential names missing from `ROOM_LABEL_EXACT`.
5. **Maryborough FT3** (GPT2 #2843): p11 regions show an enclosed room and a finish zone are different objects; the FT3 area for FOOD SERVICE cannot come from a room enclosure.

## 10. Reproduce
```
python -m tools.diag_structural_room_region_overlay --pdf <original pdf> --page 3 --png out.png --json out.json [--dpi 110] [--ocr-candidates] [--private-detail]
python -m pytest tests/test_structural_wall_ink_shadow.py tests/test_structural_partition_ink_shadow.py tests/test_structural_room_region_shadow.py tests/test_structural_room_region_overlay_tool.py tests/test_structural_wall_ink_overlay_tool.py -q
python docs/engineering/structural_room_region_shadow_20261017/counterfactual/run_cap_counterfactual.py <repo> <Q5446 standard plans pdf> <outdir> 1,2,3,4,5,6,7,8,9,10
```
The overlay tool opens the PDF read-only, writes only the PNG/JSON you name, and publishes nothing. Never commit or post `--private-detail` output: it can show a title block, names and notes.
