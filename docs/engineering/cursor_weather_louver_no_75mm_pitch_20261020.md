# Architecture: weather louvers must not invent a 75 mm blade pitch

## Observed repository behavior

`WeatherLouverSpec.blade_pitch_mm` defaults to `75.0`. `parse_louver_annotation` falls back to `75.0` when the annotation has no pitch figure.

## Inference

A typical louver blade pitch is not owned evidence.

## Proposed change

Omitted blade pitch stays `0.0` on both the spec and the parser fallback. Evaluate already contributes zero blades when pitch is 0.

## Benchmark observations that must not influence implementation

Expected blade counts and project names are not inputs.
