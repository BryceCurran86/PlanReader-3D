# Architecture: door swing must not assume left-hand inward 90 degrees

## Observed repository behavior

`resolve_swing_door` defaults `is_left_hand=True`, `swings_inward=True`, and `swing_angle_deg=90.0`. The compile-receipt test omits those arguments and therefore authenticates left-hand inward 90-degree swing.

## Inference

Assumed handing and a typical 90-degree swing are not owned evidence.

## Proposed change

`is_left_hand` and `swings_inward` are required. Omitted swing angle defaults to `0.0`.

## Benchmark observations that must not influence implementation

Expected door counts and project names are not inputs.
