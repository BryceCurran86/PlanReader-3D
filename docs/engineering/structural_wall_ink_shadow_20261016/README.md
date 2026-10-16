# Structural wall-ink evidence (shadow): what the original plans show and what the pipeline ignores

Status: **shadow-only evidence module and read-only overlay tool.** Nothing here is called by a live path, raises an authority,
filters a candidate, or changes a quantity. Claude integration lane, 2026-10-16. Code: `pb_structural_wall_ink_shadow.py`,
`tools/diag_structural_wall_ink_overlay.py`; tests: `tests/test_structural_wall_ink_shadow.py` (37),
`tests/test_structural_wall_ink_overlay_tool.py` (2).

> **Update 2026-10-17.** The wide-gap rule (§2) now also accepts a partner face whose line is clear over the gap interval and has a face ending on each side of it, so a jamb symbol that
> overhangs one face end no longer hides an opening (the aligned-ends rule is kept; no candidate was dropped on any page). The counts below were measured before that change; after it:
> 3Laurel p3 849 -> 860 candidates and 354 -> 369 gap candidates; Q5446 p1 177 -> 189 and 53 -> 87; Q5446 p2 222 and 46 -> 68; Maryborough p7 320 -> 339 and 180 -> 222; Lot16 p3 unchanged (0).
> `tests/test_structural_wall_ink_shadow.py` now has 45 tests. Attached partition ink, room-region evidence and the room-region overlay are in
> `../structural_room_region_shadow_20261017/README.md`.

## 1. Why (observed repository behaviour)
`docs/engineering/3laurel_p3_wall_universe_architecture_report_v1.md` §9.6 named the first impossible gate for 3Laurel page 3:
**no authority separates structural wall geometry from finish, joinery, fixture and annotation geometry.** Production keeps every drawn
primitive as a wall candidate (1,559 on 3Laurel p3), and `pb_physical_wall_source_metadata_shadow.py` deliberately describes stroke
weight, colour, layer and fill without classifying. Every relaxation behind that gate (boundary completeness, scale, equivalence)
then raises ownership of non-wall candidates, e.g. the gas-cylinder symbols that became a false host.
The owner has confirmed that on 3Laurel and Q5446 the walls are clearly drawn and heavier than everything else. This module turns that
into typed, source-owned, **relational** evidence.

## 2. What the module reports
Per native source primitive id: `WALL_NETWORK_INK_CANDIDATE`, `NOT_WALL_INK` (definite negatives only) or `UNPROVEN` (retained, with a
reason). Rules, all relational on the page's own drawing:
- Eligible ink = the **darkest ink present on the page** (an ordinal rank on that page's own stroke and fill colours; no colour list,
  no weight threshold, no layer name).
- Walls drawn as two faces: a parallel partner a wall thickness apart (search bound 8 pt) overlapping along a run at least 8 thicknesses
  long. Walls drawn as filled strips: the strip's long edges pair the same way. Walls drawn as one heavy line each: the heaviest dark stroke
  class whose own strokes form a building-scale network.
- A connected network of such pairs (stroke contact within half the widths plus 0.6 pt, plus a collinear continuation across an
  opening-sized gap of up to 12 wall thicknesses between facing face ends) is a candidate only if it is of building scale
  (major side at least 15 % and minor side at least 10 % of the sheet's shorter side).
- Definite negatives: a sheet-frame ring or sheet-scale component, a dashed/patterned stroke, and a run of at least three
  glyph-sized paths (at most 2 % of the sheet) on one baseline (outlined lettering and dimension ticks). A glyph-sized run is judged
  only after the networks are known: pieces that touch each other form a cluster, and a cluster that touches a building-scale wall
  network anywhere (door jambs, posts, returns) is kept `UNPROVEN` (`glyph_sized_run_attached_to_wall_network`), never rejected.
  This was found on the original 3Laurel plan: the first version rejected the door-frame pieces of a sliding door.
- Everything else is `UNPROVEN` with its reason (no partner, lighter ink, below the minimum run length, small island, ...). `UNPROVEN` is never dropped.
Determinism and invariances (translation, quarter turn, uniform scale, input order, splitting faces into pieces, unrelated content) are tested; six
single-constant or single-rule mutants of the module are each killed by a test.
Known limits: constants in page points (8 pt face gap, 2 pt minimum run, 0.6 pt contact slack) are only exercised in a scale band; walls drawn
thicker than 8 pt stay `UNPROVEN`; fixtures that touch a wall network are not separated from it; a wall drawn as a raster image has no native ink and stays `UNPROVEN`.

Opening-gap evidence (`StructuralWallInkReport.opening_gaps`): two facing ends of one wall face line, equal thickness, with a gap of up to 12 wall
thicknesses on one face, or up to 80 thicknesses when the partner face of the same wall is interrupted over the same interval (two collinear walls on opposite
sides of a room do not do that). It is evidence of an interruption in the wall body only; the kind, host, frame and size of whatever occupies the gap are not claimed.
Glyph-sized runs (`StructuralWallInkReport.glyph_runs`): every run of at least three glyph-sized paths on one baseline, with its box, baseline, glyph height, path and segment
counts, a `touches_wall_network` flag, and the **sorted source primitive ids of every piece** (ancestry). This is the label ink of Q5446's outlined lettering with its vector
ancestry preserved, not its text: reading it needs a separately approved source-positive reader or a human hint, and a run is not text by itself (dimension ticks and
door-frame pieces are runs too, which is what the flag is for). Counts (runs / touching a wall network): 3Laurel p3 409 / 260; Q5446 p1 956 / 106, p2 742 / 115;
Maryborough p7 515 / 220; Lot16 p3 98 / 0. In the Q5446 p1 overlay the purple boxes sit on the room names (GARAGE, ENTRY, LIVING, GUEST, MEALS, FAMILY, KITCHEN, W.I.P ...).
A pairing bug found by a test on the way: a short face failed to find a much longer partner because candidates were indexed by midpoint; faces are now indexed by every cell they cover (regression test fails on the earlier version).

## 3. What the original plans show (overlays in `overlays/`: red = candidate, blue = paired but unproven, purple = repeated small paths, orange = frame)
| page (original PDF) | native segments | candidates | negatives | unproven | opening-gap candidates | wall representation seen |
|---|---:|---:|---:|---:|---:|---|
| 3Laurel p3 floor plan | 9,977 | 849 | 1,018 | 8,110 | 354 | black filled strips + 0.71 pt outlines |
| Q5446 p1 ground floor plan | 47,184 | 177 | 36,520 | 10,487 | 53 | paired 0.96 pt faces with a 1.92 pt core; lettering is outlined |
| Q5446 p2 first floor plan | 35,997 | 222 | 27,698 | 8,077 | 46 | same |
| Maryborough p7 floor plan (rotated sheet) | 59,874 | 320 | 2,546 | 57,008 | 180 | paired black faces; green hatch and joinery are lighter ink and stay unproven |
| Lot16 p3 floor plan (negative control) | 1,739 | 0 | 609 | 1,130 | 0 | **no native wall ink**: the sheet is 11 tiled raster images with vector text and dimensions over them, so the module abstains |
The same code, with no per-project input, finds the walls on three different drawing conventions and abstains on the fourth.

## 4. Counterfactuals through the unchanged source-authority stage tool (3Laurel p3, original PDF; module attributes swapped in a running process only)
| mode | wall candidates | tainted | scope complete | authenticated hosts | note |
|---|---:|---:|---|---:|---|
| baseline (production) | 1,559 | 114 | no | 1 | |
| `eligible`: every candidate relaxed (earlier report) | 1,559 | 4 | no | **2** | the second host is the gas-cylinder false positive (four primitives on layer `Service_Gas.Bottled`) |
| `negatives_withheld_eligible`: definite negatives withheld, every candidate relaxed | 1,468 | 4 | no | **2** | the false host is still there: its ink is `UNPROVEN`, not a definite negative |
| `structural_boundary`: relax only candidates made wholly of structural ink | 1,559 | 105 | no | 1 | the false host is **not** added |
| `darkest_ink_eligible`: only dark, non-negative ink enters, relaxed | 626 | 1 | no | 0 | |
| `structural_input_eligible`: only structural ink enters, relaxed | 227 | **0** | **yes** | 0 | |
Reading. Only **positive** structural evidence keeps the false host out: none of the gas-cylinder primitives is ever a candidate (they are lighter ink, unpaired or a typed negative),
whereas withholding only the definite negatives leaves it in. Positive-only input completes the wall scope (227 walls, nothing tainted) but then loses the one genuine host,
because that host (a sliding door between the alfresco and the living area) is made of door-frame pieces (all `UNPROVEN`, attached) and slab-edge lines that are not wall ink: its binding becomes
`no_authenticated_host_wall_band`. So a wall-structural universe is necessary to complete the scope and not sufficient to host an opening; the host band needs the opening's own frame and slab evidence,
and physical scale is still unavailable (the sheet's native scale bar is a block-style bar that the scale producer does not recognise). That is the next measured gate; no host, quantity or score is created here.
No quantity, count or score is affected by anything in this folder.

## 5. Q5446: the 20,000-segment cap is a text problem, not a wall problem
Segments per page that would remain if the typed negatives were withheld from wall topology (after the production motif filter; the cap and the live path are untouched):
p1 8,794; p2 6,668; p3 5,023; p4 3,991; p5 4,352; p6 4,276; p7 6,183; p8 6,187; p9 4,376; p10 2,997 (production today: p1 41,932 ... p9 20,129, nine pages over the cap).
Withholding is an authority-promotion decision and needs its own review; this table is the diagnostic only.

## 5b. Room closure: measured, not solved
With the candidate network plus the opening-gap chords, a closed-face check (polygonize and raster free-space) gives, on 3Laurel p3, about 14 enclosed regions
including the two alfresco rooms (face area 10.47 m2 and 13.17 m2 if the printed 1:100 is applied, as an inspection only; the printed legend says 10.50 and 13.60),
a bath and the WIP, but the bedrooms, living areas and the garage merge: the partitions end at joinery drawn in thinner ink (wardrobe fronts), which this
evidence deliberately does not call wall. On Q5446 p1 the interior is connected to the outside even with 30 pt of dilation, because the envelope has open sides (porch, alfresco, garage
door) and window gaps without typed ends. So the first failing stage for room closure is the wall network's ends at openings and joinery, not the lettering and not the
printed names. No room, area or label is claimed.

## 6. Reproduce
`python -m tools.diag_structural_wall_ink_overlay --pdf <original pdf> --page <1-based> --png out.png --json out.json`. The tool reads the PDF and writes only the two output files.
Counterfactuals: swap `pb_physical_wall_candidate_authority._scope_boundary_reason_from_viewports` (and optionally `_filter_repeated_non_physical_drafting_primitives`) in a running process around `tools/diag_gptmax_source_authority_stages.py`, as `docs/engineering/3laurel_p3_wall_authority_gate_trace/counterfactual_stage.py` does.

## 7. Not claimed, and what is next
Not claimed: any wall authority, quantity, room, score, or that attached fixtures are separated. Not changed: the 20,000 cap, scope rules, scale, viewport or host authorities, frozen V2, signed outputs.
Next (shadow, one change each, each needing authority review): block-style scale-bar and dimension-string scale evidence; F.07-eligible viewport containment for the wall boundary rule gated on this evidence; then host-band equivalence.
