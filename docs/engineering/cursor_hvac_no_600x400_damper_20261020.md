# Architecture: HVAC dampers must not invent 600 x 400 mm openings

## Observed repository behavior

`FireDamperSpec.width_mm` and `height_mm` default to `600.0` and `400.0`. `parse_damper_annotation` falls back to those figures when the annotation has no width x height.

## Inference

A typical rectangular fire-damper size is not owned evidence.

## Proposed change

Omitted damper width and height stay `0.0` on both the spec and the parser fallback.

## Benchmark observations that must not influence implementation

Expected damper counts and project names are not inputs.
