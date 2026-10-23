# Architecture: gutters must not invent 300 x 150 mm sections

## Observed repository behavior

`GutterSpec` defaults `width_mm=300` and `depth_mm=150`. `parse_gutter_annotation` falls back to the same sizes when the annotation has no dimensions.

## Inference

A typical eaves-gutter section is not owned evidence.

## Proposed change

Omitted width and depth are `0.0` on both the spec and the parser fallback.

## Benchmark observations that must not influence implementation

Expected gutter lengths and project names are not inputs.
