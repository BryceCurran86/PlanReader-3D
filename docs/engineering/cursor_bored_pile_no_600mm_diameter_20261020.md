# Architecture: bored piles must not invent a 600 mm diameter

## Observed repository behavior

`BoredPileSpec.diameter_mm` defaults to `600.0`. `parse_callout` initializes diameter to `600.0` before any figure is read.

## Inference

A typical bored-pier diameter is not owned evidence. This is the same class as the prior 600 mm hatch / access-floor fail-closed.

## Proposed change

Omitted diameter stays `0.0` on both the spec and the parser initialization. Concrete volume is 0 when diameter is omitted.

## Benchmark observations that must not influence implementation

Expected pile volumes and project names are not inputs.
