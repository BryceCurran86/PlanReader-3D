# Architecture: retaining walls must not invent an 1800 mm retained height

## Observed repository behavior

`RetainingWallSpec.retained_height_mm` defaults to `1800.0`. `parse_retaining_wall_annotation` falls back to `1800.0` when the annotation has no height.

## Inference

A typical retaining height is not owned evidence.

## Proposed change

Omitted retained height is `0.0` on both the spec and the parser fallback.

## Benchmark observations that must not influence implementation

Expected concrete volumes and project names are not inputs.
