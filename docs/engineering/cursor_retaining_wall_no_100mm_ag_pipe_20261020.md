# Architecture: retaining walls must not invent a 100 mm ag pipe

## Observed repository behavior

`RetainingWallSpec.ag_pipe_diameter_mm` defaults to `100.0`. `evaluate_retaining_walls` then counts pipe length whenever diameter is greater than zero.

## Inference

A typical agricultural drain size is not owned evidence.

## Proposed change

Omitted ag-pipe diameter is `0.0`, so omitted walls contribute zero pipe length.

## Benchmark observations that must not influence implementation

Expected drain lengths and project names are not inputs.
