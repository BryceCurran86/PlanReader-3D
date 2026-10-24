# Architecture: suspended ceilings must not invent a 1200 x 600 mm grid

## Observed repository behavior

`SuspendedCeilingSpec.grid_module` defaults to `GRID_1200X600`. `parse_ceiling_annotation` falls back to the same module. `evaluate_ceilings` treats any other module as 1200 x 600 for cross tees and tiles.

## Inference

A typical exposed-tee module is not owned evidence. This is the same class as the prior 600 mm hatch fail-closed.

## Proposed change

Add `UNKNOWN`. Omitted module is `UNKNOWN`. Parser fallback is `UNKNOWN`. Unknown modules contribute zero main, cross, and tile quantities.

## Benchmark observations that must not influence implementation

Expected tile counts and project names are not inputs.
