# Architecture: bored piles must not assume WEATHERED_ROCK when stratum is omitted

## Observed repository behavior

`BoredPileSpec.stratum` and `parse_callout` default to `WEATHERED_ROCK`. Invalid caller stratum strings are coerced to the same value.

## Inference

A typical founding stratum is not owned evidence.

## Proposed change

Omitted stratum is `UNKNOWN`. Explicit BEDROCK / WEATHERED / CLAY / SAND words still resolve.

## Benchmark observations that must not influence implementation

Expected socket lengths and project names are not inputs.
