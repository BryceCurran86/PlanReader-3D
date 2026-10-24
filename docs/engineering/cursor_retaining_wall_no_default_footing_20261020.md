# Architecture: retaining walls must not invent 1200 x 300 mm footings

## Observed repository behavior

`RetainingWallSpec` defaults `footing_width_mm=1200` and `footing_depth_mm=300`. The parser falls back to the same sizes when the annotation has no footing figures.

## Inference

A typical spread footing is not owned evidence.

## Proposed change

Omitted footing width and depth are `0.0` on both the spec and the parser fallback.

## Benchmark observations that must not influence implementation

Expected excavation volumes and project names are not inputs.
