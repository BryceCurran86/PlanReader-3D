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
| C06 rooms in wall-ink scope | PARTIAL | synthetic | face authority abstains on every double-line layout; route through the layered ring builder |
| C07 wall identity ambiguity | PARTIAL | report | no verified sheet-7 scale; a band alone would publish non-wall lines (AG holds its scale until C05) |
| C08 room-to-wall identity | PARTIAL | report | 12 walls of two floor rooms linked but ambiguous; none is wall-support ink; refusal correct |
| C09 exterior inside-face trace | NOT STARTED | | |
| C10 garage closure | NOT STARTED | | |
| C11 dual dwellings / party walls | NOT STARTED | | |
| C12 junctions and corners | PARTIAL | synthetic | doors near T/corner/close pairs fine; a straight-through cross junction reads as a door |
| C13 door-gap closures | NOT STARTED | | |
| C14 doors at any angle and scale | PARTIAL | synthetic | found: no opening at non-right angles (precision tolerance 1e-9/1e-6 below float32) |
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

Done 4, partial 9, in progress 1, not started 16. Next in MAX's order: C05 originals measurement, C06 via the ring builder,
then the C14 precision fix (translation/rotation/scale and near-parallel negatives; no original impact claimed yet).
