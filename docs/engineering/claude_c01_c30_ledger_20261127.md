# Claude geometry tasks C01-C30 (#4764 7211359981): ledger, 27 Nov 2026

Tiers: **live** (changes default behaviour) · **opt-in** (default off) · **report** (changes nothing) · **synthetic** (made-up
drawings only). Nothing here is merged; MAX owns merge, pins and official scoring. No new verified benchmark match is claimed.

| task | status | tier | evidence / first gate |
| --- | --- | --- | --- |
| C01 plan-view ownership report | DONE | report | originals: every floor-plan host owned; only the 6 non-plan (and 2 roof-plan) hosts unowned |
| C02 withhold non-plan hosts | DONE | opt-in | before/after changes only Maryborough's 6; frames and wall scopes identical |
| C03 page-set dependence | DONE | **live** (own revertible commit) | order-independent candidacy; combined AG `6bebb3f8d` + Claude check passed: 65/65 customer rows identical, only unresolved-wall counts differ |
| C04 viewport crossing primitives | NOT STARTED | | |
| C05 non-wall ink never a wall | PARTIAL | opt-in | guard built (two modes); originals: walls withheld, 0 host/frame changes; signed-row check pending before any default |
| C06 rooms in wall-ink scope | PARTIAL | report | existing ring builder gives inside-face rings on the three topology sheets (171 / 18 / 54 candidates); the two floor-finish rooms have no ring (both open into one interior part); not wired |
| C07 wall identity ambiguity | PARTIAL | report | no verified sheet-7 scale; a band alone would publish non-wall lines (AG holds its scale until C05) |
| C08 room-to-wall identity | PARTIAL | report | floor-finish outlines of Food Prep and Office are non-wall linework; shadow `face_wall_support` (28 Nov) rejects both on every edge; real Office ring (builder option `door_jamb_returns`) supported except a 2.2 pt step; that option is not a safe global switch (loses the WSH/DRY room); thick (about 8.6 pt) panel walls fail the 8 pt pair limit (MAX decisions) |
| C09 exterior inside-face trace | NOT STARTED | | |
| C10 garage closure | NOT STARTED | | |
| C11 dual dwellings / party walls | NOT STARTED | | |
| C12 junctions and corners | PARTIAL | opt-in | wall crossing drawn through no longer read as a door under `crossing_wall_negative_shadow` (removal only; needs a full wall thickness of continuation, so lining ticks keep the door); originals before/after pending |
| C13 door-gap closures | NOT STARTED | | |
| C14 doors at any angle and scale | PARTIAL | opt-in | `angled_opening_precision_shadow`: angled openings found and hosted (synthetic); originals purely additive (2 abstained openings); signed-row check pending |
| C15 cavity sliders | NOT STARTED | | |
| C16 external window hosts | NOT STARTED | | |
| C17 door/stacker corners | NOT STARTED | | donor #4751 identified |
| C18 3Laurel missed openings | NOT STARTED | | donor door stack pieces B-E identified |
| C19 opening widths | NOT STARTED | | |
| C20 jamb caps and stroke returns | NOT STARTED | | |
| C21 Lot16 125 -> 189 | DONE | report | one rule explains it; the 74 additions were hidden by ambiguity; no pin changed |
| C22 open-plan continuity | NOT STARTED | | donor #4767 identified |
| C23 holes, shafts, exclusions | PARTIAL | report | lists enclosed loops and net area; does not classify them |
| C24 inside-face room polygons | NOT STARTED | | |
| C25 curved/angled/stepped walls | PARTIAL | synthetic | curved walls are never candidates (only straight segments are extracted) |
| C26 vector/raster corroboration | NOT STARTED | | |
| C27 donor recovery | PARTIAL | report | `claude_donor_audit_c27_20261127.md`; nothing ported |
| C28 preview/review app routes | NOT STARTED | | |
| C29 performance | NOT STARTED | | |
| C30 consolidated PR | IN PROGRESS | | #4810 |

Done 4, partial 9, in progress 1, not started 16. Next: Office doorway closure; Food Prep open-plan ownership (C22);
C12 originals before/after; C14 and C05 signed-row checks.
