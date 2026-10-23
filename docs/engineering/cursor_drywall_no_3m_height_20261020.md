# Architecture: drywall partitions must not invent 3.0 m height

## Observed repository behavior

`DrywallPartitionSpec` and `parse_callout` default `wall_height_m` to 3.0 when no height is owned.

## Inference

A typical storey height is not owned evidence.

## Proposed change

Omitted wall height stays 0.

## Benchmark observations that must not influence implementation

Expected wall areas and project names are not inputs.
