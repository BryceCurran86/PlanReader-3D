# Architecture: level-datum must not invent floor-to-floor height

## Observed repository behavior

`compile_level_stack` uses `floor_to_floor_height_m` default `3.0` for the top level, default finish thickness `0.05`, and default ceiling offset `0.60` when the caller omits those fields.

## Inference

Assumed 3.0 m storey height and assumed slab/ceiling offsets are the same class of default as `2.8 m`. Defaults must not become height authority, even in shadow.

## Proposed change

Missing top-level `floor_to_floor_height_m` becomes `0.0`, not `3.0`. Missing finish thickness and ceiling offset default to `0.0`. Status, sorting, and commercial flags stay unchanged.

## Benchmark observations that must not influence implementation

Expected storey heights and project names are not inputs.
