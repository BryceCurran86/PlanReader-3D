# Opening host bindings on sheets without a floor plan (architecture note, 2026-11-27)

Asked for by GPT MAX (#4764 comment 7210278029). **No code is changed by this note. Stop for review.**

## Observed behaviour (main `4cbf46356`, private original read locally, counts only)

- Path: `compose_live_wall_opening_authority` -> `OpeningHostBindingAuthority` -> `_resolve_host_bands`, then, when that finds
  no band for a raster pattern, `_resolve_raster_whole_wall_host` -> `_resolve_raster_split_centerline_host` ->
  `_resolve_raster_source_primitive_host` -> `_resolve_raster_source_band_host` -> supplemental walls.
- The host wall universe is an authenticated viewport scope only when the selector names one; otherwise it is the whole page
  (`OpeningHostWallUniverseAuthority._resolve_physical_wall_scope`). None of the steps asks what kind of view the page holds.
- Maryborough sheets 30 (transmittal) and 31 (schedule) have no authenticated floor-plan viewport, yet each has 3
  corroborated bindings, all `raster_whole_wall_host_resolved`. Sheet 31's page wall scope is reported complete.
- Sheet 7 has 71 corroborated bindings. Every one of their openings **and every member wall** lies inside the sheet's one
  authenticated floor-plan viewport (checked report-only on `main`; the 6 bindings on sheets 30/31 have no plan view at all).
- No sheet has a source-owned *proven* physical plan view, so requiring one today would withhold all 77.
- Location inside a plan view does not show that a host is a physical wall (a grid, fixture or dimension line inside the plan
  would pass). That half of the proof is unmeasured.

## Where the counts came from

| main commit | host bindings (7/30/31) |
| --- | --- |
| before #4167 (`0cc74650d`) | 3 / 0 / 0 |
| #4167 (`4377b8b08`) | 81 / 3 / 3 |
| #4226 (`3c4079068`, guard restore) | 71 / 3 / 3 |
| `main` `4cbf46356` | 71 / 3 / 3 |

The pinned value (3) should stay until the bindings below have an owner proof.

## Inference

On a register or schedule sheet, ruled table lines can look like a raster wall band, and the whole-wall step accepts a single
centred wall candidate that spans the aperture. Nothing separates drawing views from sheet furniture, so plan-view ownership is
the missing check, not a tolerance.

## Proposed change (shadow first, only after review)

1. A report-only predicate: a binding has a plan-view owner when the opening **and every member wall** lie inside the same
   authenticated floor-plan viewport (or a proven physical plan view). Measure it on every development drawing, including the
   ones whose plans have no frame, before anything gates on it.
2. Only then, as a separate authority-promotion review: keep the candidates, but publish `abstained` with a reason such as
   `opening_host_plan_view_ownership_unproven` when no plan view owns the binding. Reuse `EvidenceResolutionStatus` and the
   existing viewport builder; no new vocabulary, no new scale or view resolver.

Main risk: a real floor plan whose viewport is not authenticated would lose its bindings. Step 1 measures that.

## Must not influence implementation

The counts above (3, 71, 77, 87), the sheet numbers, and any expected quantity. No drawing-specific names or thresholds.

## Untouched

Benchmark-defining files, the pinned workflow values, W10 flags, commercial output.
