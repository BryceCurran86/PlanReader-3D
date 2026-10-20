# Architecture: drywall partitions must not invent 25 mm deflection travel

## Observed repository behavior

`DrywallPartitionSpec` and `parse_callout` default `deflection_allowance_mm` to 25.0 when no travel is owned.

## Inference

A typical 25 mm deflection head allowance is not owned evidence.

## Proposed change

Omitted deflection allowance stays 0.

## Benchmark observations that must not influence implementation

Expected head lengths and project names are not inputs.
