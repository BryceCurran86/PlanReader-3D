# Architecture: acoustic walls must not invent a 3.0 m storey height

## Observed repository behavior

`AcousticWallSpec.wall_height_m` defaults to `3.0`. Omitted heights therefore invent elevation area and sealant length.

## Inference

A typical storey height is not owned evidence.

## Proposed change

Omitted `wall_height_m` is `0.0`. Callers that pass an explicit height stay unchanged.

## Benchmark observations that must not influence implementation

Expected wall areas and project names are not inputs.
