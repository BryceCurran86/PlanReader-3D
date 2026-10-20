# Architecture: bored piles must not assume CAST_IN_PLACE when type is omitted

## Observed repository behavior

`BoredPileSpec.pile_type` and `parse_callout` default to `BORED_CAST_IN_PLACE`. Invalid caller type strings are coerced to the same value.

## Inference

A typical bored cast-in-place pile is not owned evidence.

## Proposed change

Omitted type is `UNKNOWN`. `BORED` / `CAST IN PLACE` in the callout still resolve to `BORED_CAST_IN_PLACE`.

## Benchmark observations that must not influence implementation

Expected pile counts and project names are not inputs.
