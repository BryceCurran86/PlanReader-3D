# Architecture: rainwater heads must not invent 400 x 250 x 300 mm

## Observed repository behavior

`RainwaterHeadSpec` defaults `width_mm=400`, `depth_mm=250`, and `height_mm=300`.

## Inference

Typical rainhead sizes are not owned evidence.

## Proposed change

Omitted rainhead sizes are `0.0`. Callers that pass explicit sizes stay unchanged.

## Benchmark observations that must not influence implementation

Expected rainhead counts and project names are not inputs.
