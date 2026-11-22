# Maryborough door chain run: first failing gate per door (22 Nov 2026)

Branch `claude/interior-door-two-wall-tags-20261121`. Original: Maryborough architectural set, SHA prefix `b1be5353` (31 pages, 29 of them rotated 90 degrees and the last two upright, no layer names). Counts only; no coordinates or drawing content. Shadow only: nothing here is wired, issued, sealed or scored. The owner asked (22 Nov, "Yes, run it") to run the door chain on Maryborough with heads from the A600 door schedule.

## 1. What the drawings say about identity and size

- **One tag per door on the plan.** Each of the 28 door codes (D01 to D28) appears exactly once on the floor plan A110 (page 7) and once as a schedule row on A600 (page 28). The enlarged amenity insets A500 to A503 (pages 24 to 27) repeat some of them (D03 to D10 on A500, D10 on A501, D13 on A502, D11 and D12 on A503) next to elevations. So the door code is the identity witness of a physical door, and the schedule is keyed by it.
- **The A600 schedule gives door-specific width and height for 17 of 28 doors** (read locally by column; the schedule columns run along the rotated page's y axis): 900x2050 (D02), 920x2040 (D03, D07 to D10, D13 to D15, D28), 600 wide partition doors (D04 to D06), 820x2040 (D11, D12), 800x2000 (D16, D17). D01 (automated double sliding door) and D18 to D27 (cool-room and freezer doors, "as per manufacturer") carry no size.
- **The repository's universal schedule reader cannot read this schedule.** `pb_opening_schedule_v171.parse_schedule_page` returns 9 entries on A600, with widths from heuristics (two wrong), no heights, and none at all with the two-level header option. A schedule whose WIDTH and HEIGHT sit under a DOOR LEAF super-header on a rotated sheet needs a column-aware reader; the only reader that handles this set is the job-specific one (`pb_gpt2_maryborough_door_schedule_source`, five doors).

## 2. Where each check stands

| Check | Result |
|---|---|
| Wall connections (two sections) on the insets | A501 to A503: 5 swing doorways found by the layered ring, 4 tagged `STRAIGHT_GAP` by the wall-end core from exact-contact receipts; the fifth has a wall end on one side only. A500 (page 24) is above the 20,000-primitive cap and needs a bounded viewport (not run) |
| Wall connections on the parent plan A110 | Not obtained. The whole-page ring abstains above the same cap (`unlabelled_dark_wall_page_exceeds_20000_primitive_cap_needs_bounded_viewport`); the canonical preview path, which tiles the page, returns 5 rings and 2 stroke closures and **no door closure**. The dark-painted wall path that finds the swing symbols exists only without a viewport option, and the viewport path exists only without the dark-painted option |
| Identity: door code to door symbol | **First failing gate for all 28 doors.** On A502 and A503 the code word sits 4 to 7 points outside the swing symbol's footprint (the tag is placed beside the door, not inside it); on A501 neither swing symbol has a code word near it (its only code word lies far from both, away from the plan inset). No existing evidence associates a tag with its symbol without a proximity tolerance, and a nearest rule is not allowed |
| Width and head level | Door-specific values exist in the schedule for 17 doors (a schedule row's height ranks above any note); text corroboration on these pages was not run (the opt-in glyph-ledger trust is slow on 2384x1684 pages) |
| Base level | **Not provable under the current rule on any door.** No text block on any of the 31 pages pairs a step-like word with a finished-floor datum word (0 statement blocks). Level changes are expressed as slab set-downs relative to the structural slab level ("SLAB TO BE SET DOWN 50mm TO ALLOW FOR TOPPING SLAB & FALLS TO WASTES", a 150mm set-down for the cool-room floors, a threshold ramp and a "RAMP UP 1:8") and a general note that "all slab set downs refer to slab setout plans"; there are level-change marks on A001 (23), A110 (5), A130 (7) and 7 other pages. A set-down under a topping slab reads as leaving the FINISHED floor level unchanged (an inference from the wording, to be confirmed), so the statement rule of the 3Laurel proof is the wrong convention here and the owner has to say what Maryborough's base proof is |

Result: **0 of 28 doors compile to a ready row.** Nothing contradicts a door; the evidence for identity, the schedule reader and the base convention is missing or not owned by this lane.

## 3. What would unblock it (not done here)

1. A universal, column-aware door-schedule reader for rotated sheets (shadow), so width and height of any schedule become door-specific witnesses without a job-specific reader. The measured layout is in section 1.
2. A source-owned door-tag association (tag to symbol) that does not rely on nearest: for example a tag-to-symbol rule with a stated, scale-relative tolerance and retained ambiguity, registered across A110, the insets and the schedule (GPT2's schedule and plan identity item).
3. A bounded-viewport path for the dark-painted wall and swing detection, so A110 and A500 give door closures without exceeding the 20,000-primitive cap (wall and ring topology lane).
4. The owner's base-level convention for slab set-down documents (finished floor unchanged under a topping, ramps and steps as the only finished-level changes), so the level proof can use the structural slab datum and set-down vocabulary instead of an FFL statement.

## 4. Update (same day): pages 23 and 24

- **A500 (page 24) runs once it is bounded to the amenity plan.** With a viewport over the plan inset (11,015 of 20,334 rows, under the cap) the dark-painted ring gives 3 rings and 12 closures (8 stroke closures, 4 swing doorways). The wall-end core tags 1 of the 4 (`STRAIGHT_GAP`); the other 3 stop at `wall_ends_not_collinear_across_the_gap` (2) and `opening_edge_does_not_meet_wall_end` (1). The tiled canonical preview path finds no door closure on this page (3 rings, 5 stroke closures). Door code by containment: 0.
- **Totals for the amenity insets A500 to A503: 9 swing doorways found, 5 tagged.**
- **A300 (page 23, wall sections)** is three 1:20 sections of the exterior walls. It names one door, D01 (the automatic sliding door at the sales shopfront), and carries figured levels (ground 15.50, top of glazing and building ceiling 18.50, top of parapet 19.99). The existing elevation witness finds no self-calibrating datum view on it (0 views), as on A500 to A503. No interior door, nothing to tag; it is a possible vertical source for D01 only.

