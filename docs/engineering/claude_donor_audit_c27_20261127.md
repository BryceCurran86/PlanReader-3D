# Unmerged geometry donors (task C27, 2026-11-27, first pass)

Compared with `main` `6340ebd322`. "On main" means the module exists there; none of the donor changes below is on `main`
unless stated. No donor was merged or deleted by this pass.

| donor (draft PR, head) | production files | state | note |
| --- | --- | --- | --- |
| #4710 `cd0433b45` (Claude) | ring builder | not on main | default-off aperture-complete closures |
| #4723 `ab895f367` | ring builder | not on main | follows #4710: same-aperture wall-host ownership |
| #4754 `ee48c7070` | ring builder | not on main | rebases #4723 onto newer main: the successor of the #4710 chain; recover only this head |
| #4751 `4d6a87e46` | opening area publication, host frame | not on main | Lot16 corner-frame transplant (relevant to C17) |
| #4767 `3c3f7f036` | 2 new modules + tiled room-face authority | not on main | coincident fixture boundary and multi-wall open room faces (relevant to C22) |
| #4802 `2c2b090ab` | 8 modules + new `pb_surface_substrates` (3 app importers on its branch) | not on main | missed app work (substrates, native page frame, wall/opening performance); touches two authority files #4810 also changes, so port, do not merge |
| #4727 `0cee21f15` | none differ from main | superseded | code already on `main`; only its tests are new |
| #4689 `400f077f2` | cross-view floor finish authority | not on main | measured room outline for same-sheet floor finishes (source lane, AG) |

Earlier inventories still apply: `claude_cursor_lane_donor_inventory_20261123.md` and
`claude_3laurel_door_donor_port_plan_20261121.md` (door stack pieces B to E).

Duplicate-engine check: the ring chain is one engine (the layered builder); no donor adds a second wall, opening or room
engine to a live route. Recovery order when ported: #4754 (rings), #4767 (open room faces, C22), #4751 (corner frames, C17),
then the app-only parts of #4802.
