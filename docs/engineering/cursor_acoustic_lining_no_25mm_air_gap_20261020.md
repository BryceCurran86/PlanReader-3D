# Architecture: acoustic walls must not invent a 25 mm air gap

## Observed repository behavior

`AcousticWallSpec.air_gap_mm` defaults to `25.0`.

## Inference

A typical acoustic air gap is not owned evidence.

## Proposed change

Omitted `air_gap_mm` is `0.0`. Callers that pass an explicit gap stay unchanged.

## Benchmark observations that must not influence implementation

Expected acoustic ratings and project names are not inputs.
