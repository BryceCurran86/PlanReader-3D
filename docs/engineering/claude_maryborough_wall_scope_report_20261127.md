# Maryborough walls: why 3,909 candidates stay unresolved, and a report-only next step

Date: 2026-11-27. Order: #4764 7208783677 items 3 to 5. AGENTS.md: report first, no code changed. Stop for review.

## Observed

- `pb_live_canonical_wall_composition.compose_live_canonical_walls` reads page decision scopes (`wall-source:page-N`). When a scope is corroborated but incomplete with an evaluated boundary, it takes the boundary-clean-partial path: boundary-tainted candidates are withheld and **every** candidate stays unresolved, including those equivalence resolved.
- Saved scopes from the local replay (sheets 7, 30, 31; `main` and #4810 identical):
  - sheet 7 (floor plan): 3,737 candidates, incomplete (`bounds_unresolved`, `cropped_at_viewport_boundary`), 42 tainted; equivalence would resolve 488 clean representatives.
  - sheet 30: 136 candidates, incomplete (`bounds_unresolved`), 24 tainted.
  - sheet 31: 36 candidates, complete, none resolved by equivalence.
  - Total 3,909 unresolved, 66 withheld.
- Sheet 30 is a drawing transmittal register and sheet 31 a schedule, not floor plans.
- By eye (local crops), none of the 66 tainted candidates looks like a building wall: on sheet 7 they are title block, border and crop marks, tables and note underlines, a north arrow, logo edges and legend or site lines; on sheet 30 all 24 are register table lines.
- Paint, by the repository's own `_source_wall_ink_role`: of 3,909, 1,545 are wall-support; 825 green (owner-excluded), 617 grey, 563 white-fill edges, 139 raster segments, the rest other colours or mixes.
- Sheet 7 equivalence: 129,942 ambiguous pairs, of which 24,000 join two wall-support candidates; only 66 of 1,115 unresolved wall-support candidates are ambiguous solely with non-wall paint.
- A viewport scope producer already exists (`_build_authenticated_viewport_scope_results`); this composition resolved only page scopes.

## Inference

The page-wide scope mixes sheet furniture, and whole non-plan sheets, into the wall universe. Taint from furniture then leaves complete pages unresolved. Restricting walls to an authenticated plan view is the first generic gate; excluding non-wall paint is second, and not sufficient alone.

## Proposed change (report-only; not built)

1. For each page, additionally resolve the existing authenticated plan-view scopes and report: viewport found or "no plan view", boundary status, tainted count, equivalence outcome. Live scopes, equivalence, room binding and sealing are unchanged.
2. In that report-only scope, additionally drop source paths the repository's wall-ink rule excludes (green, grey, white masks) and report the same counts, plus whether candidate rooms keep complete bounding walls.
3. Promotion (replacing the page scope, or abstaining on non-plan sheets) only after review, with protected rows unchanged on all originals.

Files touched when built: a new report-only producer path beside the composition; no change to authority rules. Untouched: equivalence rules, scale, room faces, floor-finish sealer, quantities, benchmark files.

Synthetic tests: a sheet with a title block, a table and a plan view; a non-plan sheet; translation, rotation, input order; no input mutation; live results unchanged.

## Must not influence the implementation

Counts, sheet numbers, names and anything seen in the crops: no coordinates or page numbers in code or tests.

## Questions for review

1. Is the authenticated viewport scope the right seam, or should non-plan sheets be removed where the wall pages are chosen (AG / MAX lane)?
2. Last measured on 2026-10-04, the plan viewport on sheet 7 was itself incomplete because of annotation crossing its frame. Is a report that names the remaining primitives enough for the next step?
