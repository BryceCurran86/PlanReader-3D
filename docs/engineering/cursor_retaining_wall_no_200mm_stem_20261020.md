# Architecture: retaining walls must not invent a 200 mm stem

## Observed repository behavior

`RetainingWallSpec.stem_thickness_mm` defaults to `200.0`. `parse_retaining_wall_annotation` falls back to `200.0` when the annotation has no thickness.

## Inference

A typical cantilever stem is not owned evidence.

## Proposed change

Omitted stem thickness is `0.0` on both the spec and the parser fallback.

## Benchmark observations that must not influence implementation

Expected concrete volumes and project names are not inputs.
