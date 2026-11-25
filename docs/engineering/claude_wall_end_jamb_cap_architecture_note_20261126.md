# Wall-end jamb caps in the dark-painted layered ring (26 November 2026)

Default off (`jamb_caps_must_be_wall_ends`). Ships in the paired door successor on current main with `door_jamb_returns`
(see that note, section 9). Claim: #4135 comment 7169924177. The owner approved building, then merging.

## 1. Observed

- The jamb-cap closure (`_jamb_cap_closed`, dark-painted path only) shuts a 10 to 140 pt wall interruption when strokes at both
  ends cover the wall. Since `3ce1d9b18` it takes any visible stroke colour, strokes up to 80 pt long, anywhere within one wall
  thickness of each end.
- Survey of 17 pages from 10 drawing sets on main (counts only; originals read in place): it closed 93 interruptions on 9 pages.
  Judged by eye on local crops: 40 a real opening or wall line, **51 no wall there**, 2 inside wall material.
- The false ones' cap strokes are mostly dimension and extension lines, edges of fixtures and joinery, floor finish lines and long
  wall faces; in 49 of the 51 at least one end is capped only by strokes running well past the wall. A few are grey or pink
  hairline ticks. The three reported walls (#4135 comment 7156845089) are among them: one hangs from an open door leaf.
- Real openings mostly have short jamb strokes that stop at the wall faces. For several of them this closure is the only one.

## 2. Inference

A real jamb end is a short wall-ink stroke that stops at the wall faces. Length alone is the main fault; colour catches the ticks.

## 3. The rule (only with the switch on)

| | A stroke caps an interruption only when | Reused limit |
|---|---|---|
| C1 | its row is wall support ink | the module's `_source_wall_ink_role` |
| C2 | it ends within the wall band (the 80 pt allowance is not used) | face cluster 0.8 pt |
| C3 | the band may reach a far face line: a parallel interruption lying inside this one that already holds a door swing, the two lines together no deeper than a third of this interruption's width; every such line counts, else the band alone | 0.35 pt; `_JAMB_THICK_WALL_DOOR_RATIO` |

Unchanged: station window, notch merging, at most two paths per end, tie abstention, sibling-face consumption. No new constant.
Switch off: identical.

**As built:** `_wall_end_depth`, a `wall_depth` argument on `_jamb_cap_closed`, and the default-False explicit-bool keyword
`jamb_caps_must_be_wall_ends` (requires `dark_painted_wall_source`) on `build_layered_wall_doorway_room_rings` and
`build_from_pdf_bytes`.

## 4. Expected abstentions

A cap stroke that runs past the wall (dimension line, fixture edge, return face, finish line, leaf) or is not wall ink (grey, pink,
blue; dark grey outside a named wall layer). A far face line without a swing, with a swing reaching past this interruption, or
deeper than a third. An opening with no jamb stroke where only a continuing wall face ends it.

## 5. Proof

RESULTS-PENDING

## 6. Not covered

The app preview (`pb_next_wall_ring_preview`) has its own copy of the rule and is not changed; run as the app does on the nine
survey pages with cap closures it also draws some false walls, of another kind (wall ends facing each other across open space,
links between appliance outlines). The other closure kinds were not surveyed. A drawing whose walls are dark grey on unnamed
layers would lose these closures under the switch. The by-eye judgements are one reviewer's.

## 7. Observations that must not influence implementation

Drawing, room and door names, positions, page numbers, the 40/51 judgement and any quantity. Two choices were informed by
development cases, stated so they can be challenged: 0.8 over 0.35 pt (a jamb frame 0.72 pt past its faces) and C3 (keeping the
page index 26 D11 closure the integrator asked to preserve).

**Authority.** Topology only. Ring records stay candidate or abstained; no quantity, authority or score. Nothing in product code
turns the dark-painted path or this switch on.
