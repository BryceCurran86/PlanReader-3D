# Architecture: access floors must not invent 600 mm panels, 300 mm FFH, or HEAVY_GRADE

## Observed repository behavior

`AccessFloorZoneSpec` defaults to `HEAVY_GRADE`, `ffh_mm=300.0`, and `panel_size_mm=600.0`. `parse_access_floor_tag` falls back to those figures, including forcing HEAVY when the tag is silent.

## Inference

A typical 600 mm access-floor grid, 300 mm finished-floor height, and heavy-grade rating are not owned evidence. This is the same class as the prior 600 mm hatch fail-closed.

## Proposed change

Omitted grade is `UNKNOWN`. Omitted FFH and panel size stay `0.0`, including parse fallbacks. Evaluate contributes zero panels, pedestals, and plenum volume when panel size is omitted.

## Benchmark observations that must not influence implementation

Expected pedestal counts and project names are not inputs.
