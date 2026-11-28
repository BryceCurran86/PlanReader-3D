# Floor-grid cell veto: default-off experiment (MAX 29 Nov 00:09)

## Observed
On one original plan sheet the centreline route publishes many rooms that are floor-tile cells
(`claude_floor_grid_negative_note_20261128.md`).

## Proposed (this change, default off)
`collect_live_physical_net_wall_claim(..., floor_grid_cell_veto_shadow=True)` withholds canonical rooms whose outline is
at least 90% on lattice lines alone (`pb_floor_grid_cell_veto_shadow`), after room composition. Dark ink drawn on the
same stretch never counts, so walls over grid lines keep their rooms; partly tiled cells (at most 75% in a synthetic
edge cell) are kept. Withheld rooms are listed with their share and lattice ids in
`surface_pipeline_diagnostics["floor_grid_cell_veto"]` (present only when on). Walls, openings and every other room are
unchanged; floors, ceilings and quantities follow from the kept rooms. Off (the default) changes nothing.

## Synthetic proof
Interior tile cells withheld; edge cells, a narrow space between dark walls, a whole room and other pages kept; no grid
or nothing to withhold returns the same composition; all withheld abstains; the live claim on a two-room tiled plan keeps
50 rooms off and 32 on with identical wall and opening ids; a non-boolean option is refused.

## Original before/after (28–29 Nov, `823a4ef90`, three plan sheets)
Withheld: Maryborough 241 of 683, 3Laurel 81 of 292, Lot16 0. Kept rooms, walls and openings identical; firm
values unchanged. A "SALES" and a "WC" label sat on single tile cells and are withheld with them.
Gap found and fixed afterwards: the area bridge built entries for every face of a scope, so a withheld cell could
still carry one; withheld faces now go to the bridge's `withheld_room_refs` (synthetic test; the originals were run
before this fix, their firm values did not depend on any withheld face).
