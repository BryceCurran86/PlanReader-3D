# Architecture: overflow scuppers must not invent 300 x 100 mm with 50 mm freeboard

## Observed repository behavior

`OverflowScupperSpec` defaults `width_mm=300`, `height_mm=100`, and `freeboard_mm=50`.

## Inference

Typical overflow-scupper sizes are not owned evidence.

## Proposed change

Omitted scupper sizes are `0.0`. Callers that pass explicit sizes stay unchanged.

## Benchmark observations that must not influence implementation

Expected overflow counts and project names are not inputs.
