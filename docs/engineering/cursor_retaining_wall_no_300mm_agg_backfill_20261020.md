# Architecture: retaining walls must not invent 300 mm aggregate backfill

## Observed repository behavior

`RetainingWallSpec.agg_backfill_width_mm` defaults to `300.0`.

## Inference

A typical drainage-aggregate width is not owned evidence.

## Proposed change

Omitted aggregate backfill width is `0.0`.

## Benchmark observations that must not influence implementation

Expected aggregate volumes and project names are not inputs.
