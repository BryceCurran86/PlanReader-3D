# Architecture: balustrades must not invent a 300 mm handrail extension

## Observed repository behavior

`BalustradeRunSpec.handrail_extension_m` defaults to `0.30`. Stair and ramp evaluation adds two of those extensions even when none is owned.

## Inference

A typical 300 mm stair-handrail extension is not owned evidence.

## Proposed change

Omitted handrail extension stays `0.0`.

## Benchmark observations that must not influence implementation

Expected handrail lengths and project names are not inputs.
