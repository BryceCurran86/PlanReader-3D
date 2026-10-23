# Architecture: operable acoustic walls must not invent 1000 mm panels

## Observed repository behavior

`OperableWallSpec.panel_width_mm` and `parse_callout` default to `1000.0` when no panel width is owned. `evaluate_operable_walls` then divides clear length by that width, so an omitted callout still invents a panel count.

Traced: `OperableWallSpec`, `SourceOperableAcousticWallShadowAuthority.parse_callout`, `SourceOperableAcousticWallShadowAuthority.evaluate_operable_walls`.

## Inference

A typical 1000 mm operable panel is not owned evidence.

## Proposed change

Omitted panel width stays `0`. Panel count is `0` when width is not owned (no divide-by-zero). Explicit `1000mm PANEL` in a callout still parses. Status stays `CANDIDATE`; `takeoff_eligible` stays `False`.

## Authority boundaries

Shadow module only. No live extractor, W10, commercial rows, or `benchmarks/frozen_holdout/full_plan_v2/**`.

## Expected abstentions

Callout `"OPERABLE WALL"` and a bare `OperableWallSpec` keep `panel_width_mm == 0` and `total_panels_count == 0`.

## Benchmark observations that must not influence implementation

Expected panel counts, wall areas, and project names are not inputs.
