# Architecture: bored piles must not invent an 8.0 m design depth

## Observed repository behavior

`BoredPileSpec.design_depth_m` defaults to `8.0`. `parse_callout` initializes design depth to `8.0` before any figure is read, so omitted callouts still publish 8 m of drilled length.

## Inference

A typical bored-pier storey/founding depth is not owned evidence.

## Proposed change

Omitted design depth stays `0.0` on both the spec and the parser initialization. Drilled length and concrete volume are 0 when depth is omitted.

## Benchmark observations that must not influence implementation

Expected pile lengths and project names are not inputs.
