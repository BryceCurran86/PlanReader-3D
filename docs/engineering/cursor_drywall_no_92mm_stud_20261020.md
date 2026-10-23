# Architecture: drywall partitions must not invent 92 mm studs

## Observed repository behavior

`DrywallPartitionSpec` and `parse_callout` default `stud_width_mm` to 92.0 when no stud width is owned.

## Inference

A typical 92 mm steel stud is not owned evidence.

## Proposed change

Omitted stud width stays 0.

## Benchmark observations that must not influence implementation

Expected drywall quantities and project names are not inputs.
