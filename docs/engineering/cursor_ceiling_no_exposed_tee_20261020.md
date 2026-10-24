# Architecture: suspended ceilings must not assume EXPOSED_TEE when grid type is omitted

## Observed repository behavior

`SuspendedCeilingSpec.grid_type` and `parse_ceiling_annotation` default to `EXPOSED_TEE` when the annotation is silent.

## Inference

A typical exposed-tee grid is not owned evidence.

## Proposed change

Omitted grid type is `UNKNOWN`. Explicit EXPOSED / CONCEALED / FINELINE words still resolve.

## Benchmark observations that must not influence implementation

Expected tile counts and project names are not inputs.
