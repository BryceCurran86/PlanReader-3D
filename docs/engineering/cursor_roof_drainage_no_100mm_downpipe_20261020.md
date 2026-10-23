# Architecture: downpipes must not invent a 100 mm diameter

## Observed repository behavior

`DownpipeSpec.diameter_mm` defaults to `100.0`.

## Inference

A typical PVC downpipe size is not owned evidence.

## Proposed change

Omitted diameter is `0.0`. Callers that pass an explicit diameter stay unchanged.

## Benchmark observations that must not influence implementation

Expected downpipe sizes and project names are not inputs.
